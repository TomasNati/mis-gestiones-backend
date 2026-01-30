import datetime
from pydantic import BaseModel
from typing import Optional
import uuid

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

class DetalleSubcategoriaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    subcategoriaId: uuid.UUID
    subcategoria: SubcategoriaBasicOut
    comentarios: Optional[str] = None
    active: bool

    class Config:
        from_attributes = True

class MovimientoGastoOut(BaseModel):
    id: uuid.UUID
    subcategoriaId: uuid.UUID
    subcategoria: SubcategoriaBasicOut
    detalleSubcategoriaId: Optional[uuid.UUID] = None
    detalleSubcategoria: Optional[DetalleSubcategoriaOut] = None
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
