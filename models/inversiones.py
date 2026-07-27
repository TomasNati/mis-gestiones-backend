from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from models.drive import InstrumentoOut, PrecioOut


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
    page_size: Optional[int] = None
    page_number: int = 1

    @field_validator("page_number")
    @classmethod
    def clamp_page_number(cls, v):
        return max(1, v)


class GuardarEstadoInversionesParams(BaseModel):
    """Snapshot request: for each inversión id, store a copy dated `fecha`."""
    inversion_ids: list[UUID]
    fecha: datetime
