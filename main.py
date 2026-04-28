from typing import Optional, Union
from uuid import UUID
from fastapi import FastAPI, HTTPException, Query, status, Header, Depends, File, UploadFile, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from db import (
    obtener_categoria_por_id,
    obtener_categorias,
    obtener_subcategorias,
)
from structure import CategoriaDeletionError, SubcategoriaDeletionError
import db
from models import CategoriaOut, CategoriasCrear, SubcategoriaOut, CategoriaBasicOut
import models
import os
import hmac
import io
import mimetypes
from urllib.parse import quote
from fastapi.responses import StreamingResponse
import drive
from services import get_exchange_service, get_crypto_service, get_instrumento_service


app = FastAPI(
    title="Vercel + FastAPI",
    description="Vercel + FastAPI",
    version="1.0.0",
)

origins = [
    "http://localhost:5173", # Default Vite dev server port
    "http://localhost:9999", # Custom port for testing
    "https://mis-gestiones-admin.vercel.app",
    "https://mis-gestiones-opal-kappa.vercel.app"
]

app.add_middleware( CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.post("/api/movimientos-gasto",  response_model=models.MovimientoGastoSearchResults, tags=["Movimiento Gasto"])
def buscar_movimientos_gasto(params: models.MovimientoGastoQueryParams):
    movimientos = db.obtener_movimientos_gasto(
        id=params.id,
        categoriaIds=params.categoriaIds,
        subcategoriaIds=params.subcategoriaIds,
        detalleSubcategoriaIds=params.detalleSubcategoriaIds,
        tiposDePago=params.tiposDePago,
        active=params.active,
        monto_min=params.monto_min,
        monto_max=params.monto_max,
        comentarios=params.comentarios,
        desde_fecha=params.desde_fecha,
        hasta_fecha=params.hasta_fecha,
        page_size=params.page_size,
        page_number=params.page_number,
        sort_by=params.sort_by,
        sort_direction=params.sort_direction,
    )
    return movimientos

@app.post("/api/vencimientos", response_model=models.VencimientoSearchResults, tags=["Vencimientos"])
def buscar_vencimientos(params: models.VencimientoQueryParams):
    if not params.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one query parameter must be provided"
        )
    vencimientos = db.obtener_vencimientos(
        id=params.id,
        categoriaIds=params.categoriaIds,
        subcategoriaIds=params.subcategoriaIds,
        esAnual=params.esAnual,
        fechaConfirmada=params.fechaConfirmada,
        pagado=params.pagado,
        active=params.active,
        monto_min=params.monto_min,
        monto_max=params.monto_max,
        comentarios=params.comentarios,
        desde_fecha=params.desde_fecha,
        hasta_fecha=params.hasta_fecha,
        page_size=params.page_size,
        page_number=params.page_number,
        sort_by=params.sort_by,
        sort_direction=params.sort_direction,
    )
    return vencimientos

@app.get("/api/categorias", response_model=list[CategoriaOut], tags=["Categoría"])
def get_categorias(
    id: Optional[UUID] = Query(None), 
    nombre: Optional[str] = Query(None),
    active: Optional[bool] = Query(None)
):
    categorias = obtener_categorias(id=id, nombre=nombre, active=active)
    return categorias

@app.get("/api/categoria/{id}", response_model=Union[CategoriaOut, CategoriaBasicOut], tags=["Categoría"])
def get_categoria(id: UUID, con_hijos: Optional[bool] = Query(None)):
    categoria = obtener_categoria_por_id(id, con_hijos)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    if con_hijos:
        return CategoriaOut.model_validate(categoria)
    else:
        return CategoriaBasicOut.model_validate(categoria)


@app.put("/api/categoria/{id}", response_model=CategoriaBasicOut, tags=["Categoría"])
def actualizar_categoria(id: str, categoria: CategoriaBasicOut):
    if str(categoria.id).lower() != id.lower():
        raise HTTPException(
            status_code=400,
            detail=f"ID mismatch: path ID is {id}, but body ID is {categoria.id}"
        )
    
    categoria = db.actualizar_categoria(id, categoria_update=categoria)
    
    return CategoriaBasicOut.model_validate(categoria)

@app.post("/api/categoria", response_model=CategoriaBasicOut, tags=["Categoría"])
def crear_categoria(categoria: CategoriasCrear):
    categoria = db.crear_categoria(nombre=categoria.nombre)
    return CategoriaBasicOut.model_validate(categoria)

@app.delete("/api/categoria/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Categoría"])
def eliminar_categoria(id: UUID, eliminar_subcategorias: Optional[bool] = Query(None)):
    try:
        db.eliminar_categoria(id, eliminar_subcategorias=eliminar_subcategorias)
    except CategoriaDeletionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/api/subcategoria", response_model=models.SubcategoriaBasicOut, tags=["Subcategoría"])
def crear_subcategoria(subcategoria: models.SubcategoriaCrear):
    subcategoria = db.crear_subcategoria(subcategoria=subcategoria)
    return models.SubcategoriaBasicOut.model_validate(subcategoria)

@app.put("/api/subcategoria", response_model=models.SubcategoriaBasicOut, tags=["Subcategoría"])
def actualizar_subcategoria(subcategoria: models.SubcategoriaBasicOut):
    subcategoria = db.actualizar_subcategoria(subcategoria=subcategoria)
    return models.SubcategoriaBasicOut.model_validate(subcategoria)

@app.get("/api/subcategoria/{id}", response_model=models.SubcategoriaOut, tags=["Subcategoría"])
def get_subcategoria(id: UUID):
    subcategoria = db.obtener_subcategoria_por_id(id)
    if not subcategoria:
        raise HTTPException(status_code=404, detail="Subcategoria no encontrada")

    return models.SubcategoriaOut.model_validate(subcategoria)

@app.get("/api/subcategorias", response_model=list[SubcategoriaOut], tags=["Subcategoría"])
def get_subcategorias(
    id: Optional[UUID] = Query(None), 
    nombre: Optional[str] = Query(None),
    active: Optional[bool] = Query(None)
):
    subcategorias = obtener_subcategorias(id=id, nombre=nombre, active=active)
    return subcategorias

@app.delete("/api/subcategoria/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Subcategoría"])
def eliminar_subcategoria(id: UUID):
    try:
        db.eliminar_subcategoria(id)
    except SubcategoriaDeletionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# Drive endpoints

def require_api_key(x_api_key: str = Header(...)) -> None:
    secret = os.getenv("BACKEND_SHARED_SECRET")
    if not secret or not hmac.compare_digest(x_api_key, secret):
        raise HTTPException(status_code=401, detail={"error": "Unauthorized", "message": "invalid or missing X-API-Key"})


@app.get("/api/drive/files", response_model=models.DriveFileListOut, tags=["Drive"], dependencies=[Depends(require_api_key)])
async def list_drive_files(q: Optional[str] = Query(None)):
    files = drive.list_files(q)
    return {"files": [models.DriveFileOut.model_validate(f) for f in files]}


@app.get("/api/drive/files/{file_id}/download", tags=["Drive"])
def download_drive_file(file_id: str, x_api_key: str = Header(...)):
    # validate API key
    require_api_key(x_api_key)
    metadata = drive.get_file_in_folder(file_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail={"error": "Not Found", "message": "file is not in the allowed folder"})
    if drive.is_google_native(metadata.get("mimeType", "")):
        raise HTTPException(status_code=415, detail={"error": "Unsupported Media Type", "message": "google-native file types cannot be downloaded directly"})
    filename = metadata.get("name", "file")
    headers = {"Content-Disposition": f'attachment; filename="{quote(filename)}"'}
    return StreamingResponse(drive.download_stream(file_id), media_type=metadata.get("mimeType", "application/octet-stream"), headers=headers)


@app.post("/api/drive/files", response_model=models.DriveUploadOut, tags=["Drive"])
async def upload_drive_file(request: Request, file: UploadFile = File(...), overwrite: bool = Query(False), x_api_key: str = Header(...)):
    require_api_key(x_api_key)
    max_bytes = drive.MAX_UPLOAD_BYTES
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > max_bytes:
                raise HTTPException(status_code=413, detail={"error": "Payload Too Large", "message": f"upload exceeds {max_bytes} bytes"})
        except ValueError:
            pass
    buf = io.BytesIO()
    total = 0
    chunk_size = 262144
    while True:
        chunk = file.file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=413, detail={"error": "Payload Too Large", "message": f"upload exceeds {max_bytes} bytes"})
        buf.write(chunk)
    buf.seek(0)
    mime = file.content_type
    if not mime or mime == "application/octet-stream":
        mime = mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
    matches = drive.find_by_name(file.filename)
    if len(matches) == 0:
        created = drive.create_file(file.filename, mime, buf)
        return {"file": models.DriveFileOut.model_validate(created), "created": True}
    elif len(matches) == 1:
        if overwrite:
            updated = drive.update_file_content(matches[0]["id"], mime, buf)
            return {"file": models.DriveFileOut.model_validate(updated), "created": False}
        else:
            raise HTTPException(status_code=409, detail={"error": "Conflict", "message": f"a file named '{file.filename}' already exists; pass overwrite=true to replace it"})
    else:
        raise HTTPException(status_code=409, detail={"error": "Conflict", "message": f"multiple files named '{file.filename}' exist in the folder; resolve manually before uploading"})


# ============================================================================
# COTIZACIONES / MARKET QUOTES ENDPOINTS
# ============================================================================

@app.get("/api/cotizaciones/instrumento/{ticker}", response_model=models.InstrumentoPriceOut, tags=["Cotizaciones"])
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


@app.get("/api/cotizaciones/dolar", response_model=list[models.DolarOut], tags=["Cotizaciones"])
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


@app.get("/api/cotizaciones/dolar/{tipo}", response_model=models.DolarOut, tags=["Cotizaciones"])
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


@app.get("/api/cotizaciones/crypto/{crypto_id}", response_model=models.CryptoOut, tags=["Cotizaciones"])
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


@app.get("/api/cotizaciones/crypto/top/{limit}", response_model=list[models.CryptoTopOut], tags=["Cotizaciones"])
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


@app.get("/", response_class=HTMLResponse)
def read_root():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Vercel + FastAPI</title>
        <link rel="icon" type="image/x-icon" href="/favicon.ico">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
                background-color: #000000;
                color: #ffffff;
                line-height: 1.6;
                min-height: 100vh;
                display: flex;
                flex-direction: column;
            }

            header {
                border-bottom: 1px solid #333333;
                padding: 0;
            }

            nav {
                max-width: 1200px;
                margin: 0 auto;
                display: flex;
                align-items: center;
                padding: 1rem 2rem;
                gap: 2rem;
            }

            .logo {
                font-size: 1.25rem;
                font-weight: 600;
                color: #ffffff;
                text-decoration: none;
            }

            .nav-links {
                display: flex;
                gap: 1.5rem;
                margin-left: auto;
            }

            .nav-links a {
                text-decoration: none;
                color: #888888;
                padding: 0.5rem 1rem;
                border-radius: 6px;
                transition: all 0.2s ease;
                font-size: 0.875rem;
                font-weight: 500;
            }

            .nav-links a:hover {
                color: #ffffff;
                background-color: #111111;
            }

            main {
                flex: 1;
                max-width: 1200px;
                margin: 0 auto;
                padding: 4rem 2rem;
                display: flex;
                flex-direction: column;
                align-items: center;
                text-align: center;
            }

            .hero {
                margin-bottom: 3rem;
            }

            .hero-code {
                margin-top: 2rem;
                width: 100%;
                max-width: 900px;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            }

            .hero-code pre {
                background-color: #0a0a0a;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 1.5rem;
                text-align: left;
                grid-column: 1 / -1;
            }

            h1 {
                font-size: 3rem;
                font-weight: 700;
                margin-bottom: 1rem;
                background: linear-gradient(to right, #ffffff, #888888);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }

            .subtitle {
                font-size: 1.25rem;
                color: #888888;
                margin-bottom: 2rem;
                max-width: 600px;
            }

            .cards {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 1.5rem;
                width: 100%;
                max-width: 900px;
            }

            .card {
                background-color: #111111;
                border: 1px solid #333333;
                border-radius: 8px;
                padding: 1.5rem;
                transition: all 0.2s ease;
                text-align: left;
            }

            .card:hover {
                border-color: #555555;
                transform: translateY(-2px);
            }

            .card h3 {
                font-size: 1.125rem;
                font-weight: 600;
                margin-bottom: 0.5rem;
                color: #ffffff;
            }

            .card p {
                color: #888888;
                font-size: 0.875rem;
                margin-bottom: 1rem;
            }

            .card a {
                display: inline-flex;
                align-items: center;
                color: #ffffff;
                text-decoration: none;
                font-size: 0.875rem;
                font-weight: 500;
                padding: 0.5rem 1rem;
                background-color: #222222;
                border-radius: 6px;
                border: 1px solid #333333;
                transition: all 0.2s ease;
            }

            .card a:hover {
                background-color: #333333;
                border-color: #555555;
            }

            .status-badge {
                display: inline-flex;
                align-items: center;
                gap: 0.5rem;
                background-color: #0070f3;
                color: #ffffff;
                padding: 0.25rem 0.75rem;
                border-radius: 20px;
                font-size: 0.75rem;
                font-weight: 500;
                margin-bottom: 2rem;
            }

            .status-dot {
                width: 6px;
                height: 6px;
                background-color: #00ff88;
                border-radius: 50%;
            }

            pre {
                background-color: #0a0a0a;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 1rem;
                overflow-x: auto;
                margin: 0;
            }

            code {
                font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
                font-size: 0.85rem;
                line-height: 1.5;
                color: #ffffff;
            }

            /* Syntax highlighting */
            .keyword {
                color: #ff79c6;
            }

            .string {
                color: #f1fa8c;
            }

            .function {
                color: #50fa7b;
            }

            .class {
                color: #8be9fd;
            }

            .module {
                color: #8be9fd;
            }

            .variable {
                color: #f8f8f2;
            }

            .decorator {
                color: #ffb86c;
            }

            @media (max-width: 768px) {
                nav {
                    padding: 1rem;
                    flex-direction: column;
                    gap: 1rem;
                }

                .nav-links {
                    margin-left: 0;
                }

                main {
                    padding: 2rem 1rem;
                }

                h1 {
                    font-size: 2rem;
                }

                .hero-code {
                    grid-template-columns: 1fr;
                }

                .cards {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <header>
            <nav>
                <a href="/" class="logo">Vercel + FastAPI</a>
                <div class="nav-links">
                    <a href="/docs">API Docs</a>
                    <a href="/api/data">API</a>
                </div>
            </nav>
        </header>
        <main>
            <div class="hero">
                <h1>Vercel + FastAPI</h1>
                <div class="hero-code">
                    <pre><code><span class="keyword">from</span> <span class="module">fastapi</span> <span class="keyword">import</span> <span class="class">FastAPI</span>

<span class="variable">app</span> = <span class="class">FastAPI</span>()

<span class="decorator">@app.get</span>(<span class="string">"/"</span>)
<span class="keyword">def</span> <span class="function">read_root</span>():
    <span class="keyword">return</span> {<span class="string">"Python"</span>: <span class="string">"on Vercel"</span>}</code></pre>
                </div>
            </div>

            <div class="cards">
                <div class="card">
                    <h3>Interactive API Docs</h3>
                    <p>Explore this API's endpoints with the interactive Swagger UI. Test requests and view response schemas in real-time.</p>
                    <a href="/docs">Open Swagger UI →</a>
                </div>

                <div class="card">
                    <h3>Sample Data</h3>
                    <p>Access sample JSON data through our REST API. Perfect for testing and development purposes.</p>
                    <a href="/api/data">Get Data →</a>
                </div>

            </div>
        </main>
    </body>
    </html>
    """
