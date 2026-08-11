from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

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
    id: UUID
    active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InstrumentoConPreciosOut(InstrumentoOut):
    """InstrumentoOut plus its prices — used by read endpoints that load them."""
    precios: list['PrecioSimple'] = []

    class Config:
        from_attributes = True


class PrecioCrear(BaseModel):
    monto: float
    fecha: datetime
    instrumento_id: UUID

    class Config:
        from_attributes = True


class PrecioOut(BaseModel):
    id: UUID
    active: bool
    monto: float
    fecha: datetime
    instrumentoId: UUID
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PrecioSimple(BaseModel):
    id: UUID
    fecha: datetime
    monto: float

    class Config:
        from_attributes = True


class InstrumentoSimple(BaseModel):
    id: UUID
    nombre: str
    codigo: Optional[str] = None
    tipo: str
    clase_renta: str
    moneda: str

    class Config:
        from_attributes = True


class InversionCrear(BaseModel):
    cantidad: float
    instrumento_id: UUID
    broker: Optional[str] = None
    fecha: Optional[datetime] = None

    class Config:
        from_attributes = True


class InversionOut(BaseModel):
    id: UUID
    active: bool
    cantidad: float
    instrumento: InstrumentoSimple
    broker: Optional[str] = None
    fecha: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FechasHistorialInversionesOut(BaseModel):
    """Wrapper for the distinct dates that have an inversiones snapshot"""
    fechas: list[datetime]

    class Config:
        from_attributes = True


class InstrumentosSearchOut(BaseModel):
    """Wrapper for list of instrumentos with their latest prices"""
    instrumentos: list[InstrumentoConPreciosOut]

    class Config:
        from_attributes = True


class DolarCotizaciones(BaseModel):
    oficial: float = Field(gt=0)
    blue: float = Field(gt=0)
    bolsa: float = Field(gt=0)
    contadoconliqui: float = Field(gt=0)

    class Config:
        from_attributes = True


class DolarHistoricoCrear(DolarCotizaciones):
    fecha: datetime = Field(description="Día de la cotización")

    class Config:
        from_attributes = True


class DolarHistoricoOut(DolarHistoricoCrear):
    id: UUID
    active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DolaresHistoricosOut(BaseModel):
    """Wrapper for a list of daily dólar cotizaciones"""
    dolares_historicos: list[DolarHistoricoOut]

    class Config:
        from_attributes = True


class GetInstrumentosParams(BaseModel):
    id: Optional[UUID] = None
    nombre: Optional[str] = None
    codigo: Optional[str] = None
    tipo: Optional[str] = None
    active: Optional[bool] = True
    limit_precios: int = Field(50, description="Maximum number of latest prices to include per instrumento")


class ActualizarInstrumentoEndpointParams(BaseModel):
    id: UUID
    instrumento: InstrumentoOut


class ActualizarPrecioEndpointParams(BaseModel):
    id: UUID
    precio: PrecioOut


class ActualizarInversionParams(BaseModel):
    cantidad: float = Field(ge=0)


class GetPreciosParams(BaseModel):
    id: Optional[UUID] = None
    instrumento_id: Optional[UUID] = None
    fecha: Optional[datetime] = Field(None, description="Precios de ese día")
    desde_fecha: Optional[datetime] = None
    hasta_fecha: Optional[datetime] = None
    active: Optional[bool] = None
    page_size: Optional[int] = None
    page_number: int = 1

    @field_validator("page_number")
    @classmethod
    def clamp_page_number(cls, v):
        return max(1, v)


class GetInversionesParams(BaseModel):
    id: Optional[UUID] = None
    instrumento_id: Optional[UUID] = None
    active: Optional[bool] = None
    fecha: Optional[datetime] = Field(
        None,
        description="Return the snapshot for this day instead of the live inversiones",
    )
    page_size: Optional[int] = None
    page_number: int = 1

    @field_validator("page_number")
    @classmethod
    def clamp_page_number(cls, v):
        return max(1, v)


class GetDolaresHistoricosParams(BaseModel):
    id: Optional[UUID] = None
    fecha: Optional[datetime] = Field(None, description="Cotizaciones de ese día exacto")
    desde_fecha: Optional[datetime] = None
    hasta_fecha: Optional[datetime] = None
    active: Optional[bool] = None
    page_size: Optional[int] = None
    page_number: int = 1

    @field_validator("page_number")
    @classmethod
    def clamp_page_number(cls, v):
        return max(1, v)


class GetInversionesHistoricoParams(BaseModel):
    """Historico de inversiones entre dos fechas (inclusive)."""
    desde: datetime = Field(description="Fecha inicial (inclusive)")
    hasta: datetime = Field(description="Fecha final (inclusive)")

    class Config:
        from_attributes = True


class GuardarEstadoInversionesParams(BaseModel):
    """Snapshot request: for each inversión id, store a copy dated `fecha`."""
    inversion_ids: list[UUID]
    fecha: datetime
    sobreescribir: bool = Field(
        False,
        description="When an snapshot already exists for that date: overwrite it if True, leave it untouched if False",
    )
    dolar: DolarCotizaciones = Field(
        description="Cotizaciones del dólar del día, guardadas en dolar_historico junto al snapshot",
    )
