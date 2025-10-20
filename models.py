from pydantic import BaseModel
from typing import Optional
import uuid

class CategoriBasicOut(BaseModel):
    id: uuid.UUID
    nombre: str
    comentarios: Optional[str]

class CategoriaOut(CategoriBasicOut):
    subcategorias: list['SubcategoriaBasicOut']

    class Config:
        from_attributes = True

class SubcategoriaBasicOut(BaseModel):
    id: uuid.UUID
    nombre: str
    comentarios: Optional[str]

class SubcategoriaOut(SubcategoriaBasicOut):
    categoria: CategoriBasicOut

    class Config:
        from_attributes = True
