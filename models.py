from pydantic import BaseModel
from typing import Optional
import uuid

class CategoriaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    comentarios: Optional[str]
    subcategorias: list['SubcategoriaChildOut']

    class Config:
        from_attributes = True

class SubcategoriaChildOut(BaseModel):
    id: uuid.UUID
    nombre: str
    comentarios: Optional[str]

    class Config:
        from_attributes = True


class CategoriParentOut(BaseModel):
    id: uuid.UUID
    nombre: str
    comentarios: Optional[str]

class SubcategoriaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    comentarios: Optional[str]
    categoria: CategoriParentOut

    class Config:
        from_attributes = True

