from pydantic import BaseModel
from typing import Optional
import uuid

class CategoriasCrear(BaseModel):
    nombre: str
    comentarios: Optional[str] = None

class CategoriaBasicOut(CategoriasCrear):
    id: uuid.UUID

    class Config:
        from_attributes = True

class CategoriaOut(CategoriaBasicOut):
    subcategorias: list['SubcategoriaBasicOut']

    class Config:
        from_attributes = True

class SubcategoriaBasicOut(BaseModel):
    id: uuid.UUID
    nombre: str
    comentarios: Optional[str]

    class Config:
        from_attributes = True

class SubcategoriaOut(SubcategoriaBasicOut):
    categoria: CategoriaBasicOut

    class Config:
        from_attributes = True
