from typing import List, Optional

from pydantic import BaseModel


class ComprobanteArchivoOut(BaseModel):
    path: str
    nombre: str
    size: int

    class Config:
        from_attributes = True


class ComprobanteSubidaOut(BaseModel):
    commit: str
    archivos: List[ComprobanteArchivoOut]
    max_upload_bytes: int

    class Config:
        from_attributes = True


class ComprobanteLimitesOut(BaseModel):
    max_upload_bytes: int
    repo: Optional[str] = None
    branch: Optional[str] = None

    class Config:
        from_attributes = True
