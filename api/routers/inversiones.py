from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from db import (
    actualizar_instrumento, 
    actualizar_precio, 
    crear_instrumento, 
    crear_inversion,
    crear_precio, 
    obtener_instrumento_por_id, 
    obtener_inversiones, 
    obtener_precios, 
    obtener_instrumentos_con_precios
)
from enums import broker_values, clase_renta_values, instrumento_tipo_values, moneda_values
from models import InstrumentoCrear, InstrumentoOut, InversionCrear, InversionOut, PrecioCrear, PrecioOut


router = APIRouter(prefix="/api/inversiones", tags=["Inversiones"])


@router.get("/instrumentos", response_model=list[InstrumentoOut], tags=["Inversiones"])
def get_instrumentos(
    id: Optional[UUID] = Query(None),
    nombre: Optional[str] = Query(None),
    codigo: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    active: Optional[bool] = Query(None),
    limit_precios: int = Query(50, description="Maximum number of latest prices to include per instrumento"),
):
    """
    Get instrumentos with their latest N prices (default 50).
    Prices are ordered by fecha DESC (most recent first).
    """
    instrumentos = obtener_instrumentos_con_precios(
        id=id,
        nombre=nombre,
        codigo=codigo,
        tipo=tipo,
        active=active,
        limit_precios=limit_precios
    )
    return [InstrumentoOut.model_validate(i) for i in instrumentos]


@router.get("/instrumento/{id}", response_model=InstrumentoOut, tags=["Inversiones"])
def get_instrumento(id: UUID):
    instrumento = obtener_instrumento_por_id(id)
    if not instrumento:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")
    return InstrumentoOut.model_validate(instrumento)


@router.post("/instrumento", response_model=InstrumentoOut, tags=["Inversiones"])
def crear_instrumento_endpoint(instr: InstrumentoCrear):
    instrumento = crear_instrumento(instr)
    return InstrumentoOut.model_validate(instrumento)


@router.put("/instrumento/{id}", response_model=InstrumentoOut, tags=["Inversiones"])
def actualizar_instrumento_endpoint(id: UUID, instrumento: InstrumentoOut):
    if str(instrumento.id).lower() != str(id).lower():
        raise HTTPException(status_code=400, detail=f"ID mismatch: path ID is {id}, but body ID is {instrumento.id}")
    ins = actualizar_instrumento(id, instrumento_update=instrumento)
    return InstrumentoOut.model_validate(ins)


@router.delete("/instrumento/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Inversiones"])
def eliminar_instrumento(id: UUID):
    instrumento = obtener_instrumento_por_id(id)
    if not instrumento:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")
    # soft-delete
    instrumento.active = False
    actualizar_instrumento(id, instrumento_update=InstrumentoOut.model_validate(instrumento))


@router.post("/precio", response_model=PrecioOut, tags=["Inversiones"])
def crear_precio_endpoint(precio: PrecioCrear):
    p = crear_precio(precio)
    return PrecioOut.model_validate(p)


@router.put("/precio/{id}", response_model=PrecioOut, tags=["Inversiones"])
def actualizar_precio_endpoint(id: UUID, precio: PrecioOut):
    if str(precio.id).lower() != str(id).lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ID mismatch: path ID is {id}, but body ID is {precio.id}")
    p = actualizar_precio(id, precio_update=precio)
    return PrecioOut.model_validate(p)


@router.delete("/precio/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Inversiones"])
def eliminar_precio(id: UUID):
    precios = obtener_precios(id=id)
    if not precios:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Precio no encontrado")
    precio = precios[0]
    precio.active = False
    actualizar_precio(id, precio_update=PrecioOut.model_validate(precio))


@router.get("/precios", response_model=list[PrecioOut], tags=["Inversiones"])
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


@router.post("/inversion", response_model=InversionOut, tags=["Inversiones"])
def crear_inversion_endpoint(inv: InversionCrear):
    i = crear_inversion(inv)
    return InversionOut.model_validate(i)


@router.get("/inversiones", response_model=list[InversionOut], tags=["Inversiones"])
def get_inversiones(
    id: Optional[UUID] = Query(None),
    instrumento_id: Optional[UUID] = Query(None),
    active: Optional[bool] = Query(None),
    page_size: Optional[int] = Query(None),
    page_number: Optional[int] = Query(None),
):
    inversiones = obtener_inversiones(id=id, instrumento_id=instrumento_id, active=active, page_size=page_size, page_number=page_number)
    return [InversionOut.model_validate(inv) for inv in inversiones]


@router.get("/inversiones/meta", tags=["Inversiones"])
def inversiones_meta():
    """Return allowed enum values for instrumentos: tipo, clase_renta, moneda, brokers"""
    return {
        "tipo": instrumento_tipo_values(),
        "clase_renta": clase_renta_values(),
        "moneda": moneda_values(),
        "brokers": broker_values(),
    }

