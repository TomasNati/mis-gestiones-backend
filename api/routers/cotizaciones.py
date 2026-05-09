from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
import httpx
import httpx
from uvicorn import logging

import models
from services.cafci import download_cafci_to_memory, get_cafci_data_list, normalize_string
from services.crypto_service import get_crypto_service
from services.exchange_service import get_exchange_service
from services.fci_service import get_fci_service
from services.instrumento_service import get_instrumento_service
from services.yahoo_service import get_current_price_value

router = APIRouter(prefix="/api/cotizaciones", tags=["Cotizaciones"])

_COT2_CACHE = None
_COT2_LIST_CACHE_DURATION = timedelta(hours=24)

_FONDOS_CACHE = {
    "data": [],
    "last_updated": None
}

def load_data_into_cache():
    """Helper to encapsulate the download and storage logic"""
    print("🚀 Fetching/Refreshing CAFCI data...")
    download = download_cafci_to_memory()
    
    if download["success"]:
        global _FONDOS_CACHE
        _FONDOS_CACHE["data"] = get_cafci_data_list(download["file"])
        _FONDOS_CACHE["last_updated"] = date.today()
        print(f"✅ Loaded {len(_FONDOS_CACHE['data'])} funds into memory.")
    else:
        print(f"❌ Failed to load CAFCI data: {download['message']}")

def get_fondos():
    """Access point for the data that checks for expiration"""
    today = date.today()
    
    # If cache is empty OR the date is from a previous day, refresh it
    if not _FONDOS_CACHE["last_updated"] or _FONDOS_CACHE["last_updated"] < today:
        load_data_into_cache()
        
    return _FONDOS_CACHE["data"]


@router.get("/instrumento/{ticker}", response_model=models.InstrumentoPriceOut)
async def get_instrumento_price(ticker: str):
    """
    Get the latest price + currency of a financial instrument by scraping the
    public IOL quote page.

    The endpoint loads `https://iol.invertironline.com/titulo/cotizacion/BCBA/{ticker}`
    and extracts both the currency symbol (sibling `<span>$</span>` or
    `<span>US$</span>`) and the latest price (`<span data-field="UltimoPrecio">`)
    from inside the `<span id="IdTitulo">` container.
    """
    try:
        instrumento_service = get_instrumento_service()
        return await instrumento_service.get_price(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching instrument price: {str(e)}")


@router.get("/fci/clase-fondos", response_model=models.ClaseFondoSearchOut)
async def search_clase_fondos(
    id: Optional[str] = Query(None, description="Optional exact clase_fondo id."),
    nombre: Optional[str] = Query(None, description="Optional comma-separated keywords. Each must appear in the clase_fondo's `nombre` (case-insensitive)."),
    fondoId: Optional[str] = Query(None, description="Optional parent fondo id (matches `clase_fondo.fondoId`)."),
    clear_cache: bool = Query(False, description="If true, refresh the CAFCI catalog cache (24h) and this search's result cache before searching."),
    log: bool = Query(False, description="If true, log internal HTTP calls and inputs/outputs."),
):
    """
    Search clase_fondos across the CAFCI catalog by `id`, `nombre`, and/or `fondoId`.

    At least one of `id`, `nombre`, or `fondoId` must be provided.

    The CAFCI catalog (>1000 entities) is cached for 24 hours; pass
    `clear_cache=true` to force a refresh.

    Returns a list of clase_fondos with `id`, `nombre`, `monedaId`, `fondoId`.
    """
    from services.fci_service import InvalidFilterError
    try:
        fci_service = get_fci_service()
        results = await fci_service.search_clase_fondos(
            id=id, nombre=nombre, fondo_id=fondoId, clear_cache=clear_cache, log=log
        )
        return {"clase_fondos": results}
    except InvalidFilterError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching clase_fondos: {str(e)}")


@router.get("/fci/search", response_model=models.FCISearchOut)
async def search_fcis(
    codigo_cnv: Optional[str] = Query(None, description="Optional exact CNV code."),
    nombre: Optional[str] = Query(None, description="Optional comma-separated keywords. Each must appear in the fund's `nombre` (case-insensitive)."),
    clear_cache: bool = Query(False, description="If true, refresh the CAFCI catalog cache (24h) and this search's result cache before searching."),
    log: bool = Query(False, description="If true, log internal HTTP calls and inputs/outputs."),
):
    """
    Search the CAFCI catalog by `codigoCNV` and/or `nombre`.

    At least one of `codigo_cnv` or `nombre` must be provided.

    The CAFCI catalog (>1000 entities) is cached for 24 hours; pass
    `clear_cache=true` to force a refresh.

    Returns a list of matching funds, each with the fund's full JSON
    serialized as a string.
    """
    from services.fci_service import InvalidFilterError
    try:
        fci_service = get_fci_service()
        results = await fci_service.search(
            codigo_cnv=codigo_cnv, nombre=nombre, clear_cache=clear_cache, log=log
        )
        return {"fcis": results}
    except InvalidFilterError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching FCI info: {str(e)}")


@router.get("/fci/{fondo_id}/{clase_id}", response_model=models.FCIQuoteOut)
async def get_fci_quote(fondo_id: str, clase_id: str, log: bool = Query(False, description="If true, log internal HTTP calls and inputs/outputs.")):
    """
    Get the latest quote for a mutual fund (FCI) from CAFCI.

    `fondo_id` and `clase_id` are the numeric ids that appear in the CAFCI
    URL `.../fondo/<fondo_id>/clase/<clase_id>/ficha` — i.e. the parent fondo
    id and the share class (clase_fondo) id (e.g. `fondo_id=739`,
    `clase_id=1611` → "Allaria Dólar Latam - Clase A").

    Returns the latest `vcpUnitario` (price), date, fund name and currency
    (`ARS` for `monedaId=1`, `USD` for `monedaId=2`).
    """
    try:
        fci_service = get_fci_service()
        return await fci_service.get_quote(fondo_id, clase_id, log=log)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching FCI quote: {str(e)}")


@router.get("2/fci/search", response_model=models.FCINamesOut, tags=["Cotizaciones2"])
async def cotizaciones2_search_fcis(
    codigo_cnv: Optional[str] = Query(None, description="Optional exact CNV code."),
    nombre: Optional[str] = Query(None, description="Optional comma-separated keywords. Each must appear in the fondo's or clase's `nombre` (case-insensitive)."),
    clear_cache: bool = Query(False, description="If true, refresh the 24h cached estadisticas JSON."),
    log: bool = Query(False, description="If true, log HTTP call info and counts."),
):
    """
    Search and return FCI names+classes using the CAFCI estadisticas JSON.

    Requires at least one of codigo_cnv or nombre (same validation as existing search).
    """
    if not codigo_cnv and not nombre:
        raise HTTPException(status_code=400, detail="at least one of codigo_cnv or nombre must be provided")

    try:
        # try to use cached fondos list
        global _COT2_CACHE
        fondos = None
        if not clear_cache and _COT2_CACHE is not None:
            ts, cached_fondos = _COT2_CACHE
            if datetime.now() - ts < _COT2_LIST_CACHE_DURATION:
                fondos = cached_fondos
                if log:
                    logging.getLogger(__name__).info(f"Cotizaciones2 cache hit -> {len(fondos)} fondos")

        if fondos is None:
            url = "https://estadisticas.cafci.org.ar/consulta-de-fondos.json"
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)
                if log:
                    logging.getLogger(__name__).info(f"GET {url} -> status={resp.status_code}, bytes={len(resp.content) if resp.content is not None else 0}")
            if resp.status_code >= 400:
                raise HTTPException(status_code=503, detail=f"Error fetching CAFCI estadisticas: status {resp.status_code}")

            resp_json = resp.json()
            data = resp_json.get("Response", {}).get("json", resp_json)
            fondos = data.get("fondos", []) or []
            _COT2_CACHE = (datetime.now(), fondos)

        results = []
        keywords = [kw.strip().lower() for kw in (nombre or "").split(",") if kw.strip()]

        for fondo in fondos:
            fondo_id = fondo.get("id")
            codigo = fondo.get("codigo_cnv") or fondo.get("codigoCNV") or fondo.get("codigoCnv")
            fondo_nombre = (fondo.get("nombre") or "")
            moneda_obj = fondo.get("moneda")
            if isinstance(moneda_obj, dict):
                moneda = moneda_obj.get("nombre") or str(moneda_obj.get("id", ""))
            elif moneda_obj is None:
                moneda = None
            else:
                moneda = str(moneda_obj)
            clases = fondo.get("clases") or []

            # If codigo_cnv provided and doesn't match, skip entire fondo
            if codigo_cnv and (codigo is None or str(codigo).strip() != codigo_cnv.strip()):
                continue

            for clase in clases:
                clase_id = clase.get("id")
                clase_nombre = (clase.get("nombre") or "")

                # keyword matching: match if ALL keywords appear in fondo.nombre OR in clase.nombre
                if keywords:
                    match_fondo = fondo_nombre and all(k in fondo_nombre.lower() for k in keywords)
                    match_clase = clase_nombre and all(k in clase_nombre.lower() for k in keywords)
                    if not (match_fondo or match_clase):
                        continue

                results.append({
                    "fondo_id": str(fondo_id) if fondo_id is not None else "",
                    "codigo_cnv": codigo,
                    "fondo_nombre": fondo.get("nombre"),
                    "fondo_moneda": moneda,
                    "clase_id": str(clase_id) if clase_id is not None else "",
                    "clase_nombre": clase.get("nombre"),
                })

        if log:
            logging.getLogger(__name__).info(f"Cotizaciones2 returned {len(results)} entries")

        return {"fcis": results}
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Error fetching CAFCI estadisticas: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing FCI estadisticas: {str(e)}")


@router.get("/cotizaciones/us/{symbol}")
async def yahoo_price(symbol: str):
    """
    Endpoint to fetch the current price of a stock or ETF using yfinance.
    """
    price = get_current_price_value(symbol)
    
    if price is None:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found or no data available.")
    
    return {
        "symbol": symbol.upper(),
        "price": price
    }

@router.get("/dolar", response_model=list[models.DolarOut])
async def get_all_dolar_rates():
    """Get all USD/ARS exchange rates from DolarAPI"""
    try:
        exchange_service = get_exchange_service()
        data = await exchange_service.get_all_dolares()
        
        # Normalize to match our model
        results = []
        for item in data:
            results.append({
                "tipo": item.get("casa", ""),
                "moneda": item.get("moneda", "USD"),
                "casa": item.get("casa", ""),
                "nombre": item.get("nombre", ""),
                "compra": item.get("compra"),
                "venta": item.get("venta"),
                "fecha_actualizacion": item.get("fechaActualizacion")
            })
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching exchange rates: {str(e)}")


@router.get("/dolar/{tipo}", response_model=models.DolarOut)
async def get_dolar_especifico(tipo: str):
    """
    Get specific USD/ARS exchange rate from DolarAPI
    
    Available types: oficial, blue, bolsa (MEP), contadoconliqui (CCL), mayorista, cripto, tarjeta
    """
    try:
        exchange_service = get_exchange_service()
        data = await exchange_service.get_dolar_especifico(tipo)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching {tipo} rate: {str(e)}")


@router.get("/crypto/{crypto_id}", response_model=models.CryptoOut)
async def get_crypto_price(crypto_id: str):
    """
    Get cryptocurrency price in USD and ARS from CoinGecko
    
    Common IDs: bitcoin, ethereum, cardano, dogecoin, litecoin, ripple, etc.
    """
    try:
        crypto_service = get_crypto_service()
        data = await crypto_service.get_crypto(crypto_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching crypto price: {str(e)}")


@router.get("/crypto/top/{limit}", response_model=list[models.CryptoTopOut])
async def get_top_cryptos(
    limit: int = 10,
    vs_currency: str = Query("usd", description="Currency: usd, ars, eur, etc.")
):
    """Get top cryptocurrencies by market cap from CoinGecko"""
    try:
        crypto_service = get_crypto_service()
        data = await crypto_service.get_top_cryptos(vs_currency=vs_currency, limit=limit)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching top cryptos: {str(e)}")

@router.get("/fondos")
async def search_fondos(
    names: Optional[str] = Query(None, description="Comma-separated keywords"),
    codigo_cnv: Optional[int] = None,
    codigo_cafci: Optional[int] = None
):
    results = get_fondos()

    if names:
        keywords = [normalize_string(k.strip()) for k in names.split(",") if k.strip()]
        results = [
            f for f in results 
            if all(kw in normalize_string(f["nombre"]) for kw in keywords)
        ]

    if codigo_cnv is not None:
        results = [f for f in results if f["codigo_cnv"] == codigo_cnv]

    if codigo_cafci is not None:
        results = [f for f in results if f["codigo_cafci"] == codigo_cafci]

    return results

