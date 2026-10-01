from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class ComprobanteArchivoOut(BaseModel):
    path: str
    nombre: str
    size: int

    class Config:
        from_attributes = True


class ComprobanteSubidaOut(BaseModel):
    """Alta de un comprobante: un archivo, y el registro que lo referencia.

    `id` es el id de `finanzas_comprobante_pago` recien creado, que es lo que
    despues usan el rename y el delete. `commit` sigue siendo el sha de git del
    commit que escribio el blob.
    """

    id: UUID
    commit: str
    path: str
    nombre: str
    size: int
    subpath: str
    max_upload_bytes: int

    class Config:
        from_attributes = True


class ComprobanteLimitesOut(BaseModel):
    max_upload_bytes: int
    repo: Optional[str] = None
    branch: Optional[str] = None

    class Config:
        from_attributes = True


class ComprobanteOut(BaseModel):
    """A comprobante as the grid needs it.
    """

    id: UUID
    vencimiento_id: UUID
    subpath: str
    path: Optional[str]
    nombre: str
    activo: bool

    class Config:
        from_attributes = True


class ComprobantesDeVencimientoOut(BaseModel):
    vencimiento_id: UUID
    comprobantes: list[ComprobanteOut]


class ComprobanteSearchResults(BaseModel):
    total: int
    comprobantes: list[ComprobantesDeVencimientoOut]

    class Config:
        from_attributes = True


class ComprobanteEliminadoOut(BaseModel):
    id: UUID
    path: Optional[str]
    nombre: str
    subpath: str
    borrado: bool

    class Config:
        from_attributes = True
