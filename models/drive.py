import datetime
from pydantic import BaseModel
from typing import Optional, Sequence
import uuid


class DriveFileOut(BaseModel):
    id: str
    name: str
    mimeType: str
    size: Optional[int] = None
    modifiedTime: datetime.datetime

    class Config:
        from_attributes = True


class DriveFileListOut(BaseModel):
    files: list[DriveFileOut]

    class Config:
        from_attributes = True


class DriveUploadOut(BaseModel):
    file: DriveFileOut
    created: bool

    class Config:
        from_attributes = True


# ============================================================================
# COTIZACIONES / MARKET QUOTES MODELS
# ============================================================================

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


class ClaseFondoSearchOut(BaseModel):
    """Wrapper for a list of clase_fondo matches."""
    clase_fondos: list[ClaseFondoOut]

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


# ============================================================================
# INVERSIONES MODELS
# ============================================================================

from enums import InstrumentoTipo, ClaseRenta, Moneda


class InstrumentoCrear(BaseModel):
    nombre: str
    codigo: Optional[str] = None
    tipo: InstrumentoTipo
    clase_renta: ClaseRenta
    moneda: Moneda

    class Config:
        from_attributes = True


class InstrumentoOut(InstrumentoCrear):
    id: uuid.UUID
    active: bool
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None
    precios: list['PrecioSimple'] = []

    class Config:
        from_attributes = True


class PrecioCrear(BaseModel):
    monto: float
    fecha: datetime.datetime
    instrumento_id: uuid.UUID

    class Config:
        from_attributes = True


class PrecioOut(BaseModel):
    id: uuid.UUID
    active: bool
    monto: float
    fecha: datetime.datetime
    instrumentoId: uuid.UUID
    created_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class PrecioSimple(BaseModel):
    id: uuid.UUID
    fecha: datetime.datetime
    monto: float

    class Config:
        from_attributes = True


class InstrumentoSimple(BaseModel):
    id: uuid.UUID
    nombre: str
    codigo: Optional[str] = None
    tipo: str
    clase_renta: str
    moneda: str

    class Config:
        from_attributes = True


class InversionCrear(BaseModel):
    cantidad: float
    instrumento_id: uuid.UUID
    broker: Optional[str] = None
    fecha: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class InversionOut(BaseModel):
    id: uuid.UUID
    active: bool
    cantidad: float
    instrumento: InstrumentoSimple
    broker: Optional[str] = None
    fecha: Optional[datetime.datetime] = None
    created_at: Optional[datetime.datetime] = None

    class Config:
        from_attributes = True


class InstrumentosSearchOut(BaseModel):
    """Wrapper for list of instrumentos with their latest prices"""
    instrumentos: list[InstrumentoOut]

    class Config:
        from_attributes = True
