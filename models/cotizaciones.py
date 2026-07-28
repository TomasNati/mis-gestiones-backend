from typing import Optional

from pydantic import BaseModel


class DolarOut(BaseModel):
    """USD/ARS exchange rate response"""
    tipo: str
    moneda: str
    casa: str
    nombre: str
    compra: Optional[float] = None
    venta: Optional[float] = None
    fecha_actualizacion: Optional[str] = None

    class Config:
        from_attributes = True


class CryptoOut(BaseModel):
    """Cryptocurrency price response"""
    id: str
    nombre: str
    precio_usd: Optional[float] = None
    precio_ars: Optional[float] = None
    cambio_24h_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None
    fecha_actualizacion: Optional[str] = None

    class Config:
        from_attributes = True


class CryptoTopOut(BaseModel):
    """Top cryptocurrency response"""
    id: str
    simbolo: str
    nombre: str
    precio_actual: Optional[float] = None
    market_cap: Optional[float] = None
    volumen_24h: Optional[float] = None
    cambio_24h: Optional[float] = None
    imagen: Optional[str] = None
    moneda: str

    class Config:
        from_attributes = True


class InstrumentoPriceOut(BaseModel):
    """Instrument latest price response (scraped from IOL public quote page)"""
    ticker: str
    precio: float
    precio_raw: str
    simbolo_moneda: str
    moneda: str
    fuente: str
    url: str
    fecha_consulta: str

    class Config:
        from_attributes = True


class ClaseFondoOut(BaseModel):
    """A single share class entry from a fondo's `clase_fondos`."""
    id: str
    nombre: Optional[str] = None
    monedaId: Optional[str] = None
    fondoId: Optional[str] = None

    class Config:
        from_attributes = True


class ClaseFondoSearchOut(BaseModel):
    """Wrapper for a list of clase_fondo matches."""
    clase_fondos: list[ClaseFondoOut]

    class Config:
        from_attributes = True


class FCIInfoOut(BaseModel):
    """FCI catalog entry response."""
    codigoCNV: str
    nombre: Optional[str] = None
    clase_fondos: list[ClaseFondoOut] = []

    class Config:
        from_attributes = True


class FCISearchOut(BaseModel):
    """Wrapper for a list of FCI catalog matches."""
    fcis: list[FCIInfoOut]

    class Config:
        from_attributes = True


class FCINameEntryOut(BaseModel):
    """Single entry returned by the Cotizaciones2 FCI name list (one per clase)."""
    fondo_id: str
    codigo_cnv: Optional[str] = None
    fondo_nombre: Optional[str] = None
    fondo_moneda: Optional[str] = None
    clase_id: str
    clase_nombre: Optional[str] = None

    class Config:
        from_attributes = True


class FCINamesOut(BaseModel):
    """Wrapper for a list of FCI name entries returned by Cotizaciones2."""
    fcis: list[FCINameEntryOut]

    class Config:
        from_attributes = True


class FCIQuoteOut(BaseModel):
    """FCI (mutual fund) quote response (fetched from CAFCI public ficha)"""
    fondo_id: str
    clase_id: str
    nombre: Optional[str] = None
    moneda: str
    fecha: Optional[str] = None
    vcp_unitario: float
    fuente: str
    url: str
    fecha_consulta: str

    class Config:
        from_attributes = True
