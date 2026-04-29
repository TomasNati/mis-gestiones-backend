import datetime
from pydantic import BaseModel
from typing import Optional, Sequence
import uuid

class MovimientoGastoQueryParams(BaseModel):
    id: Optional[uuid.UUID] = None
    categoriaIds: Optional[Sequence[uuid.UUID]] = None
    subcategoriaIds: Optional[Sequence[uuid.UUID]] = None
    detalleSubcategoriaIds: Optional[Sequence[uuid.UUID]] = None
    tiposDePago: Optional[Sequence[str]] = None
    monto_min: Optional[float] = None
    monto_max: Optional[float] = None
    comentarios: Optional[str] = None
    desde_fecha: Optional[str] = None
    hasta_fecha: Optional[str] = None
    active: Optional[bool] = True
    page_size: Optional[int] = 50
    page_number: Optional[int] = 1
    sort_by: Optional[str] = "fecha"
    sort_direction: Optional[str] = "desc"

    class Config:
        from_attributes = True

class CategoriasCrear(BaseModel):
    nombre: str
    comentarios: Optional[str] = None

class CategoriaBasicOut(CategoriasCrear):
    id: uuid.UUID
    active: bool

    class Config:
        from_attributes = True

class CategoriaOut(CategoriaBasicOut):
    subcategorias: list['SubcategoriaBasicOut']

    class Config:
        from_attributes = True

class SubcategoriaCrear(CategoriasCrear):
    categoriaId: uuid.UUID

class SubcategoriaBasicOut(SubcategoriaCrear):
    id: uuid.UUID
    active: bool

    class Config:
        from_attributes = True

class SubcategoriaOut(SubcategoriaBasicOut):
    categoria: CategoriaBasicOut

    class Config:
        from_attributes = True

class DetalleSubcategoriaBasicOut(BaseModel):
    id: uuid.UUID
    nombre: str
    subcategoriaId: uuid.UUID
    comentarios: Optional[str] = None
    active: bool

    class Config:
        from_attributes = True

class MovimientoGastoBasicOut(BaseModel):
    id: uuid.UUID
    subcategoriaId: uuid.UUID
    detalleSubcategoriaId: Optional[uuid.UUID] = None
    tipoDePago: str
    monto: float
    comentarios: Optional[str] = None
    fecha: Optional[datetime.datetime] = None
    active: bool

    class Config:
        from_attributes = True

class MovimientoGastoOut(BaseModel):
    id: uuid.UUID
    subcategoria: SubcategoriaOut
    detalleSubcategoria: Optional[DetalleSubcategoriaBasicOut] = None
    tipoDePago: str
    monto: float
    comentarios: Optional[str] = None
    fecha: Optional[datetime.datetime] = None
    active: bool

    class Config:
        from_attributes = True

class MovimientoGastoSearchResults(BaseModel):
    total: int
    page_number: int
    page_size: int
    movimientos: list[MovimientoGastoOut]

    class Config:
      from_attributes = True

class VencimientoQueryParams(BaseModel):
    id: Optional[uuid.UUID] = None
    categoriaIds: Optional[Sequence[uuid.UUID]] = None
    subcategoriaIds: Optional[Sequence[uuid.UUID]] = None
    esAnual: Optional[bool] = None
    fechaConfirmada: Optional[bool] = None
    pagado: Optional[bool] = None
    monto_min: Optional[float] = None
    monto_max: Optional[float] = None
    comentarios: Optional[str] = None
    desde_fecha: Optional[datetime.datetime] = None
    hasta_fecha: Optional[datetime.datetime] = None
    active: Optional[bool] = True
    page_size: Optional[int] = 50
    page_number: Optional[int] = 1
    sort_by: Optional[str] = "fecha"
    sort_direction: Optional[str] = "asc"

    class Config:
        from_attributes = True

class VencimientoOut(BaseModel):
    id: uuid.UUID
    subcategoria: SubcategoriaOut
    fecha: datetime.datetime
    monto: float
    esAnual: bool
    comentarios: Optional[str] = None
    active: bool
    fechaConfirmada: Optional[bool] = None
    pagoId: Optional[uuid.UUID] = None
    pago: Optional[MovimientoGastoBasicOut] = None

    class Config:
        from_attributes = True

class VencimientoSearchResults(BaseModel):
    total: int
    page_number: int
    page_size: int
    vencimientos: list[VencimientoOut]

    class Config:
        from_attributes = True


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
