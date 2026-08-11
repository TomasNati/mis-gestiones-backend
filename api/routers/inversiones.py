from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from db.inversiones import (
    actualizar_dolar_historico,
    actualizar_instrumento,
    actualizar_inversion,
    actualizar_precio,
    crear_dolar_historico,
    crear_instrumento,
    crear_inversion,
    crear_precio,
    eliminar_dolar_historico,
    guardar_estado_inversiones,
    obtener_dolares_historicos,
    obtener_fechas_historial_inversiones,
    obtener_instrumento_por_id,
    obtener_inversiones,
    obtener_precios,
    obtener_instrumentos_con_precios,
    obtener_historico_inversiones,
)
import db.inversiones
from enums import broker_values, clase_renta_values, instrumento_tipo_values, moneda_values
from models.inversiones import (
    ActualizarInstrumentoEndpointParams,
    ActualizarInversionParams,
    ActualizarPrecioEndpointParams,
    DolarHistoricoCrear,
    DolarHistoricoOut,
    DolaresHistoricosOut,
    FechasHistorialInversionesOut,
    GetDolaresHistoricosParams,
    GetInstrumentosParams,
    GetInversionesHistoricoParams,
    GetInversionesParams,
    GetPreciosParams,
    GuardarEstadoInversionesParams,
    InstrumentoConPreciosOut,
    InstrumentoCrear,
    InstrumentoOut,
    InversionCrear,
    InversionOut,
    PrecioCrear,
    PrecioOut,
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


@router.post("/inversiones-historico", tags=["Inversiones"])
def get_inversiones_historico(params: GetInversionesHistoricoParams):
    """Historico de inversiones entre dos fechas. Placeholder por ahora."""
    inversiones, _ = obtener_historico_inversiones(desde=params.desde, hasta=params.hasta)
    return {
        "message": "Historico de inversiones: endpoint en desarrollo",
        "desde": params.desde,
        "hasta": params.hasta,
        "total_inversiones": len(inversiones),
    }


@router.post("/inversiones/estado", response_model=list[InversionOut], tags=["Inversiones"])
def guardar_estado_inversiones_endpoint(params: GuardarEstadoInversionesParams):
    copias = guardar_estado_inversiones(
        params.inversion_ids, params.fecha, params.dolar, params.sobreescribir
    )
    return [InversionOut.model_validate(c) for c in copias]


@router.get("/inversiones/historial/fechas", response_model=FechasHistorialInversionesOut, tags=["Inversiones"])
def get_fechas_historial_inversiones():
    """
    Return the distinct dates that have an inversiones snapshot, most recent
    first. Live inversiones (the ones without a fecha) are not included.
    """
    fechas = obtener_fechas_historial_inversiones()
    return FechasHistorialInversionesOut(fechas=fechas)


@router.get("/inversiones/meta", tags=["Inversiones"])
def inversiones_meta():
    """Return allowed enum values for instrumentos: tipo, clase_renta, moneda, brokers"""
    return {
        "tipo": instrumento_tipo_values(),
        "clase_renta": clase_renta_values(),
        "moneda": moneda_values(),
        "brokers": broker_values(),
    }

@router.post("/dolar-historico", response_model=DolarHistoricoOut, tags=["Inversiones"])
def crear_dolar_historico_endpoint(dolar: DolarHistoricoCrear):
    """
    Guardar las cotizaciones del dólar de un día. Si ya existe la de esa fecha, se
    actualiza con los valores recibidos.
    """
    d = crear_dolar_historico(dolar)
    return DolarHistoricoOut.model_validate(d)


@router.post("/dolares-historicos", response_model=DolaresHistoricosOut, tags=["Inversiones"])
def get_dolares_historicos(params: GetDolaresHistoricosParams):
    """Cotizaciones del dólar por día, de la más reciente a la más antigua."""
    dolares = obtener_dolares_historicos(**params.model_dump())
    return DolaresHistoricosOut(
        dolares_historicos=[DolarHistoricoOut.model_validate(d) for d in dolares]
    )


@router.get("/dolar-historico/{id}", response_model=DolarHistoricoOut, tags=["Inversiones"])
def get_dolar_historico(id: UUID):
    dolares = obtener_dolares_historicos(id=id)
    if not dolares:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cotización no encontrada")
    return DolarHistoricoOut.model_validate(dolares[0])


@router.put("/dolar-historico/{id}", response_model=DolarHistoricoOut, tags=["Inversiones"])
def actualizar_dolar_historico_endpoint(id: UUID, dolar: DolarHistoricoOut):
    if str(dolar.id).lower() != str(id).lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ID mismatch: path ID is {id}, but body ID is {dolar.id}")
    d = actualizar_dolar_historico(id, dolar_update=dolar)
    if d is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cotización no encontrada")
    return DolarHistoricoOut.model_validate(d)


@router.delete("/dolar-historico/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Inversiones"])
def eliminar_dolar_historico_endpoint(id: UUID):
    # soft-delete
    if not eliminar_dolar_historico(id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cotización no encontrada")


@router.delete("/inversion/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Inversiones"])
def eliminar_inversion(id: UUID):
    try:
        db.inversiones.eliminar_inversion(id)
    except InversionDeletionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
