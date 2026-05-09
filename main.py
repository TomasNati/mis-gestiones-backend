from typing import Optional, Union
from uuid import UUID
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, status, Header, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from db import (
    obtener_categoria_por_id,
    obtener_categorias,
    obtener_subcategorias,
    crear_instrumento,
    obtener_instrumentos,
    obtener_instrumento_por_id,
    actualizar_instrumento,
    crear_precio,
    obtener_precios,
    crear_inversion,
    obtener_inversiones,
)
from structure import CategoriaDeletionError, SubcategoriaDeletionError
import db
from models import CategoriaOut, CategoriasCrear, SubcategoriaOut, CategoriaBasicOut, InstrumentoCrear, InstrumentoOut, PrecioCrear, PrecioOut, InversionCrear, InversionOut
from enums import broker_values, instrumento_tipo_values, clase_renta_values, moneda_values
import models
import os
import hmac

from urllib.parse import quote
import logging
from dotenv import load_dotenv
import drive
from api.routers import base, cotizaciones

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="Vercel + FastAPI",
    description="Vercel + FastAPI",
    version="1.0.0"
)

origins = [
    "http://localhost:5173", # Default Vite dev server port
    "http://localhost:9999", # Custom port for testing
    "https://mis-gestiones-admin.vercel.app",
    "https://mis-gestiones-opal-kappa.vercel.app"
]

app.add_middleware( CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.post("/api/movimientos-gasto",  response_model=models.MovimientoGastoSearchResults, tags=["Movimiento Gasto"])
def buscar_movimientos_gasto(params: models.MovimientoGastoQueryParams):
    movimientos = db.obtener_movimientos_gasto(
        id=params.id,
        categoriaIds=params.categoriaIds,
        subcategoriaIds=params.subcategoriaIds,
        detalleSubcategoriaIds=params.detalleSubcategoriaIds,
        tiposDePago=params.tiposDePago,
        active=params.active,
        monto_min=params.monto_min,
        monto_max=params.monto_max,
        comentarios=params.comentarios,
        desde_fecha=params.desde_fecha,
        hasta_fecha=params.hasta_fecha,
        page_size=params.page_size,
        page_number=params.page_number,
        sort_by=params.sort_by,
        sort_direction=params.sort_direction,
    )
    return movimientos

@app.post("/api/vencimientos", response_model=models.VencimientoSearchResults, tags=["Vencimientos"])
def buscar_vencimientos(params: models.VencimientoQueryParams):
    if not params.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one query parameter must be provided"
        )
    vencimientos = db.obtener_vencimientos(
        id=params.id,
        categoriaIds=params.categoriaIds,
        subcategoriaIds=params.subcategoriaIds,
        esAnual=params.esAnual,
        fechaConfirmada=params.fechaConfirmada,
        pagado=params.pagado,
        active=params.active,
        monto_min=params.monto_min,
        monto_max=params.monto_max,
        comentarios=params.comentarios,
        desde_fecha=params.desde_fecha,
        hasta_fecha=params.hasta_fecha,
        page_size=params.page_size,
        page_number=params.page_number,
        sort_by=params.sort_by,
        sort_direction=params.sort_direction,
    )
    return vencimientos

@app.get("/api/categorias", response_model=list[CategoriaOut], tags=["Categoría"])
def get_categorias(
    id: Optional[UUID] = Query(None), 
    nombre: Optional[str] = Query(None),
    active: Optional[bool] = Query(None)
):
    categorias = obtener_categorias(id=id, nombre=nombre, active=active)
    return categorias

@app.get("/api/categoria/{id}", response_model=Union[CategoriaOut, CategoriaBasicOut], tags=["Categoría"])
def get_categoria(id: UUID, con_hijos: Optional[bool] = Query(None)):
    categoria = obtener_categoria_por_id(id, con_hijos)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    if con_hijos:
        return CategoriaOut.model_validate(categoria)
    else:
        return CategoriaBasicOut.model_validate(categoria)


@app.put("/api/categoria/{id}", response_model=CategoriaBasicOut, tags=["Categoría"])
def actualizar_categoria(id: str, categoria: CategoriaBasicOut):
    if str(categoria.id).lower() != id.lower():
        raise HTTPException(
            status_code=400,
            detail=f"ID mismatch: path ID is {id}, but body ID is {categoria.id}"
        )
    
    categoria = db.actualizar_categoria(id, categoria_update=categoria)
    
    return CategoriaBasicOut.model_validate(categoria)

@app.post("/api/categoria", response_model=CategoriaBasicOut, tags=["Categoría"])
def crear_categoria(categoria: CategoriasCrear):
    categoria = db.crear_categoria(nombre=categoria.nombre)
    return CategoriaBasicOut.model_validate(categoria)

@app.delete("/api/categoria/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Categoría"])
def eliminar_categoria(id: UUID, eliminar_subcategorias: Optional[bool] = Query(None)):
    try:
        db.eliminar_categoria(id, eliminar_subcategorias=eliminar_subcategorias)
    except CategoriaDeletionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@app.post("/api/subcategoria", response_model=models.SubcategoriaBasicOut, tags=["Subcategoría"])
def crear_subcategoria(subcategoria: models.SubcategoriaCrear):
    subcategoria = db.crear_subcategoria(subcategoria=subcategoria)
    return models.SubcategoriaBasicOut.model_validate(subcategoria)

@app.put("/api/subcategoria", response_model=models.SubcategoriaBasicOut, tags=["Subcategoría"])
def actualizar_subcategoria(subcategoria: models.SubcategoriaBasicOut):
    subcategoria = db.actualizar_subcategoria(subcategoria=subcategoria)
    return models.SubcategoriaBasicOut.model_validate(subcategoria)

@app.get("/api/subcategoria/{id}", response_model=models.SubcategoriaOut, tags=["Subcategoría"])
def get_subcategoria(id: UUID):
    subcategoria = db.obtener_subcategoria_por_id(id)
    if not subcategoria:
        raise HTTPException(status_code=404, detail="Subcategoria no encontrada")

    return models.SubcategoriaOut.model_validate(subcategoria)

@app.get("/api/subcategorias", response_model=list[SubcategoriaOut], tags=["Subcategoría"])
def get_subcategorias(
    id: Optional[UUID] = Query(None), 
    nombre: Optional[str] = Query(None),
    active: Optional[bool] = Query(None)
):
    subcategorias = obtener_subcategorias(id=id, nombre=nombre, active=active)
    return subcategorias

@app.delete("/api/subcategoria/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Subcategoría"])
def eliminar_subcategoria(id: UUID):
    try:
        db.eliminar_subcategoria(id)
    except SubcategoriaDeletionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# INVERSIONES endpoints

@app.get("/api/instrumentos", response_model=list[InstrumentoOut], tags=["Inversiones"])
def get_instrumentos(
    id: Optional[UUID] = Query(None),
    nombre: Optional[str] = Query(None),
    codigo: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    active: Optional[bool] = Query(None),
):
    instrumentos = obtener_instrumentos(id=id, nombre=nombre, codigo=codigo, tipo=tipo, active=active)
    return [InstrumentoOut.model_validate(i) for i in instrumentos]


@app.get("/api/instrumento/{id}", response_model=InstrumentoOut, tags=["Inversiones"])
def get_instrumento(id: UUID):
    instrumento = obtener_instrumento_por_id(id)
    if not instrumento:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")
    return InstrumentoOut.model_validate(instrumento)


@app.post("/api/instrumento", response_model=InstrumentoOut, tags=["Inversiones"])
def crear_instrumento_endpoint(instr: InstrumentoCrear):
    instrumento = crear_instrumento(instr)
    return InstrumentoOut.model_validate(instrumento)


@app.put("/api/instrumento/{id}", response_model=InstrumentoOut, tags=["Inversiones"])
def actualizar_instrumento_endpoint(id: UUID, instrumento: InstrumentoOut):
    if str(instrumento.id).lower() != str(id).lower():
        raise HTTPException(status_code=400, detail=f"ID mismatch: path ID is {id}, but body ID is {instrumento.id}")
    ins = actualizar_instrumento(id, instrumento_update=instrumento)
    return InstrumentoOut.model_validate(ins)


@app.delete("/api/instrumento/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Inversiones"])
def eliminar_instrumento(id: UUID):
    instrumento = obtener_instrumento_por_id(id)
    if not instrumento:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")
    # soft-delete
    instrumento.active = False
    actualizar_instrumento(id, instrumento_update=InstrumentoOut.model_validate(instrumento))


@app.post("/api/precio", response_model=PrecioOut, tags=["Inversiones"])
def crear_precio_endpoint(precio: PrecioCrear):
    p = crear_precio(precio)
    return PrecioOut.model_validate(p)


@app.get("/api/precios", response_model=list[PrecioOut], tags=["Inversiones"])
def get_precios(
    id: Optional[UUID] = Query(None),
    instrumento_id: Optional[UUID] = Query(None),
    desde_fecha: Optional[datetime] = Query(None),
    hasta_fecha: Optional[datetime] = Query(None),
    active: Optional[bool] = Query(None),
    page_size: Optional[int] = Query(None),
    page_number: Optional[int] = Query(None),
):
    precios = obtener_precios(id=id, instrumento_id=instrumento_id, desde_fecha=desde_fecha, hasta_fecha=hasta_fecha, active=active, page_size=page_size, page_number=page_number)
    return [PrecioOut.model_validate(p) for p in precios]


@app.post("/api/inversion", response_model=InversionOut, tags=["Inversiones"])
def crear_inversion_endpoint(inv: InversionCrear):
    i = crear_inversion(inv)
    return InversionOut.model_validate(i)


@app.get("/api/inversiones", response_model=list[InversionOut], tags=["Inversiones"])
def get_inversiones(
    id: Optional[UUID] = Query(None),
    precio_id: Optional[UUID] = Query(None),
    ultima: Optional[bool] = Query(None),
    active: Optional[bool] = Query(None),
    page_size: Optional[int] = Query(None),
    page_number: Optional[int] = Query(None),
):
    inversiones = obtener_inversiones(id=id, precio_id=precio_id, ultima=ultima, active=active, page_size=page_size, page_number=page_number)
    return [InversionOut.model_validate(inv) for inv in inversiones]


@app.get("/api/inversiones/meta", tags=["Inversiones"])
def inversiones_meta():
    """Return allowed enum values for instrumentos: tipo, clase_renta, moneda, brokers"""
    return {
        "tipo": instrumento_tipo_values(),
        "clase_renta": clase_renta_values(),
        "moneda": moneda_values(),
        "brokers": broker_values(),
    }


# Drive endpoints

def require_api_key(x_api_key: str = Header(...)) -> None:
    secret = os.getenv("BACKEND_SHARED_SECRET")
    if not secret or not hmac.compare_digest(x_api_key, secret):
        raise HTTPException(status_code=401, detail={"error": "Unauthorized", "message": "invalid or missing X-API-Key"})


@app.get("/api/drive/files", response_model=models.DriveFileListOut, tags=["Drive"], dependencies=[Depends(require_api_key)])
async def list_drive_files(
    path: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    created_from: Optional[str] = Query(None),
    created_to: Optional[str] = Query(None),
):
    # validate created_from/created_to are ISO 8601 dates or datetimes
    def _normalize_dt(s: Optional[str]) -> Optional[str]:
        if s is None:
            return None
        s2 = s
        # accept trailing Z by converting to +00:00
        if s2.endswith('Z'):
            s2 = s2[:-1] + '+00:00'
        # allow date-only (YYYY-MM-DD)
        if len(s2) == 10:
            s2 = s2 + 'T00:00:00'
        try:
            datetime.fromisoformat(s2)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid date format: '{s}'. Use ISO 8601 date or datetime.")
        return s2

    created_from = _normalize_dt(created_from)
    created_to = _normalize_dt(created_to)

    folder_id = None
    if path:
        folder_id = drive.get_folder_id_by_path(path)
        if folder_id is None:
            return {"files": []}
    files = drive.list_files(name_query=name, folder_id=folder_id, created_from=created_from, created_to=created_to)
    return {"files": [models.DriveFileOut.model_validate(f) for f in files]}


@app.get("/api/drive/files/{file_id}/download", tags=["Drive"])
def download_drive_file(file_id: str, path: Optional[str] = Query(None), x_api_key: str = Header(...)):
    # validate API key
    require_api_key(x_api_key)
    folder_id = None
    if path:
        folder_id = drive.get_folder_id_by_path(path)
        if folder_id is None:
            raise HTTPException(status_code=404, detail={"error": "Not Found", "message": "requested path does not exist"})
    metadata = drive.get_file_in_folder(file_id, folder_id=folder_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail={"error": "Not Found", "message": "file is not in the allowed folder"})
    if drive.is_google_native(metadata.get("mimeType", "")):
        raise HTTPException(status_code=415, detail={"error": "Unsupported Media Type", "message": "google-native file types cannot be downloaded directly"})
    filename = metadata.get("name", "file")
    headers = {"Content-Disposition": f'attachment; filename="{quote(filename)}"'}
    return StreamingResponse(drive.download_stream(file_id), media_type=metadata.get("mimeType", "application/octet-stream"), headers=headers)




# ============================================================================
# COTIZACIONES / MARKET QUOTES ENDPOINTS
# ============================================================================

app.include_router(base.router)
app.include_router(cotizaciones.router)