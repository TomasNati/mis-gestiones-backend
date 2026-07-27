from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from db.inversiones import (
    actualizar_instrumento,
    actualizar_inversion,
    actualizar_precio,
    crear_instrumento,
    crear_inversion,
    crear_precio,
    guardar_estado_inversiones,
    obtener_instrumento_por_id,
    obtener_inversiones,
    obtener_precios,
    obtener_instrumentos_con_precios,
)
import db.inversiones
from enums import broker_values, clase_renta_values, instrumento_tipo_values, moneda_values
from models.drive import InstrumentoConPreciosOut, InstrumentoCrear, InstrumentoOut, InversionCrear, InversionOut, PrecioCrear, PrecioOut
from models.inversiones import (
    ActualizarInstrumentoEndpointParams,
    ActualizarInversionParams,
    ActualizarPrecioEndpointParams,
    GetInstrumentosParams,
    GetInversionesParams,
    GetPreciosParams,
    GuardarEstadoInversionesParams,
)
from structure import InversionDeletionError


router = APIRouter(prefix="/api/inversiones", tags=["Inversiones"])


@router.post("/instrumentos", response_model=list[InstrumentoConPreciosOut], tags=["Inversiones"])
def get_instrumentos(params: GetInstrumentosParams):
    """
    Get instrumentos with their latest N prices (default 50).
    Prices are ordered by fecha DESC (most recent first).
    """
    instrumentos = obtener_instrumentos_con_precios(**params.model_dump())
    return [InstrumentoConPreciosOut.model_validate(i) for i in instrumentos]


@router.get("/instrumento/{id}", response_model=InstrumentoConPreciosOut, tags=["Inversiones"])
def get_instrumento(id: UUID):
    instrumento = obtener_instrumento_por_id(id)
    if not instrumento:
        raise HTTPException(status_code=404, detail="Instrumento no encontrado")
    return InstrumentoConPreciosOut.model_validate(instrumento)


@router.post("/instrumento", response_model=InstrumentoOut, tags=["Inversiones"])
def crear_instrumento_endpoint(instr: InstrumentoCrear):
    instrumento = crear_instrumento(instr)
    return InstrumentoOut.model_validate(instrumento)


@router.put("/instrumento/{id}", response_model=InstrumentoOut, tags=["Inversiones"])
def actualizar_instrumento_endpoint(id: UUID, instrumento: InstrumentoOut):
    params = ActualizarInstrumentoEndpointParams(id=id, instrumento=instrumento)
    if str(params.instrumento.id).lower() != str(params.id).lower():
        raise HTTPException(status_code=400, detail=f"ID mismatch: path ID is {params.id}, but body ID is {params.instrumento.id}")
    ins = actualizar_instrumento(params.id, instrumento_update=params.instrumento)
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
    params = ActualizarPrecioEndpointParams(id=id, precio=precio)
    if str(params.precio.id).lower() != str(params.id).lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ID mismatch: path ID is {params.id}, but body ID is {params.precio.id}")
    p = actualizar_precio(params.id, precio_update=params.precio)
    return PrecioOut.model_validate(p)


@router.delete("/precio/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Inversiones"])
def eliminar_precio(id: UUID):
    precios = obtener_precios(id=id)
    if not precios:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Precio no encontrado")
    precio = precios[0]
    precio.active = False
    actualizar_precio(id, precio_update=PrecioOut.model_validate(precio))


@router.post("/precios", response_model=list[PrecioOut], tags=["Inversiones"])
def get_precios(params: GetPreciosParams):
    precios = obtener_precios(**params.model_dump())
    return [PrecioOut.model_validate(p) for p in precios]


@router.post("/inversion", response_model=InversionOut, tags=["Inversiones"])
def crear_inversion_endpoint(inv: InversionCrear):
    i = crear_inversion(inv)
    return InversionOut.model_validate(i)


@router.put("/inversion/{id}", response_model=InversionOut, tags=["Inversiones"])
def actualizar_inversion_endpoint(id: UUID, params: ActualizarInversionParams):
    inversion = actualizar_inversion(id, cantidad=params.cantidad)
    if inversion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inversión no encontrada")
    return InversionOut.model_validate(inversion)


@router.post("/inversiones", response_model=list[InversionOut], tags=["Inversiones"])
def get_inversiones(params: GetInversionesParams):
    inversiones = obtener_inversiones(**params.model_dump())
    return [InversionOut.model_validate(inv) for inv in inversiones]


@router.post("/inversiones/estado", response_model=list[InversionOut], tags=["Inversiones"])
def guardar_estado_inversiones_endpoint(params: GuardarEstadoInversionesParams):
    """
    Save a snapshot of the given inversiones at the provided date. Returns the
    copies that were created/updated (used for debugging for now).
    """
    copias = guardar_estado_inversiones(params.inversion_ids, params.fecha)
    return [InversionOut.model_validate(c) for c in copias]


@router.get("/inversiones/meta", tags=["Inversiones"])
def inversiones_meta():
    """Return allowed enum values for instrumentos: tipo, clase_renta, moneda, brokers"""
    return {
        "tipo": instrumento_tipo_values(),
        "clase_renta": clase_renta_values(),
        "moneda": moneda_values(),
        "brokers": broker_values(),
    }

@router.delete("/inversion/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Inversiones"])
def eliminar_inversion(id: UUID):
    try:
        db.inversiones.eliminar_inversion(id)
    except InversionDeletionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
