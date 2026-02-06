import datetime
from pydantic import BaseModel
from typing import Optional
import uuid

class MovimientoGastoQueryParams(BaseModel):
    id: Optional[uuid.UUID] = None
    categoriaId: Optional[uuid.UUID] = None
    subcategoriaId: Optional[uuid.UUID] = None
    detalleSubcategoriaId: Optional[uuid.UUID] = None
    tipoDePago: Optional[str] = None
    monto_min: Optional[float] = None
    monto_max: Optional[float] = None
    comentarios: Optional[str] = None
    desde_fecha: Optional[str] = None
    hasta_fecha: Optional[str] = None
    active: Optional[bool] = True
    page_size: Optional[int] = 50
    page_number: Optional[int] = 1

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
