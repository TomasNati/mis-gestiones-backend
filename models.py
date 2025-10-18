from pydantic import BaseModel
from typing import Optional
import uuid

class CategoriaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    comentarios: Optional[str]

    class Config:
        from_attributes = True