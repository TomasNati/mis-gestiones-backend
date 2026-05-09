from typing import Optional, Union
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from models import CategoriaOut, CategoriasCrear, SubcategoriaOut, CategoriaBasicOut

import db
import models

from db import (
    obtener_categoria_por_id,
    obtener_categorias,
    obtener_subcategorias,
)
from structure import CategoriaDeletionError, SubcategoriaDeletionError

router = APIRouter()


@router.post("/api/movimientos-gasto",  response_model=models.MovimientoGastoSearchResults, tags=["Movimiento Gasto"])
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

@router.post("/api/vencimientos", response_model=models.VencimientoSearchResults, tags=["Vencimientos"])
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

@router.get("/api/categorias", response_model=list[models.CategoriaOut], tags=["Categoría"])
def get_categorias(
    id: Optional[UUID] = Query(None), 
    nombre: Optional[str] = Query(None),
    active: Optional[bool] = Query(None)
):
    categorias = obtener_categorias(id=id, nombre=nombre, active=active)
    return categorias

@router.get("/api/categoria/{id}", response_model=Union[CategoriaOut, CategoriaBasicOut], tags=["Categoría"])
def get_categoria(id: UUID, con_hijos: Optional[bool] = Query(None)):
    categoria = obtener_categoria_por_id(id, con_hijos)
    if not categoria:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    if con_hijos:
        return CategoriaOut.model_validate(categoria)
    else:
        return CategoriaBasicOut.model_validate(categoria)


@router.put("/api/categoria/{id}", response_model=CategoriaBasicOut, tags=["Categoría"])
def actualizar_categoria(id: str, categoria: CategoriaBasicOut):
    if str(categoria.id).lower() != id.lower():
        raise HTTPException(
            status_code=400,
            detail=f"ID mismatch: path ID is {id}, but body ID is {categoria.id}"
        )
    
    categoria = db.actualizar_categoria(id, categoria_update=categoria)
    
    return CategoriaBasicOut.model_validate(categoria)

@router.post("/api/categoria", response_model=CategoriaBasicOut, tags=["Categoría"])
def crear_categoria(categoria: CategoriasCrear):
    categoria = db.crear_categoria(nombre=categoria.nombre)
    return CategoriaBasicOut.model_validate(categoria)

@router.delete("/api/categoria/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Categoría"])
def eliminar_categoria(id: UUID, eliminar_subcategorias: Optional[bool] = Query(None)):
    try:
        db.eliminar_categoria(id, eliminar_subcategorias=eliminar_subcategorias)
    except CategoriaDeletionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/api/subcategoria", response_model=models.SubcategoriaBasicOut, tags=["Subcategoría"])
def crear_subcategoria(subcategoria: models.SubcategoriaCrear):
    subcategoria = db.crear_subcategoria(subcategoria=subcategoria)
    return models.SubcategoriaBasicOut.model_validate(subcategoria)

@router.put("/api/subcategoria", response_model=models.SubcategoriaBasicOut, tags=["Subcategoría"])
def actualizar_subcategoria(subcategoria: models.SubcategoriaBasicOut):
    subcategoria = db.actualizar_subcategoria(subcategoria=subcategoria)
    return models.SubcategoriaBasicOut.model_validate(subcategoria)

@router.get("/api/subcategoria/{id}", response_model=models.SubcategoriaOut, tags=["Subcategoría"])
def get_subcategoria(id: UUID):
    subcategoria = db.obtener_subcategoria_por_id(id)
    if not subcategoria:
        raise HTTPException(status_code=404, detail="Subcategoria no encontrada")

    return models.SubcategoriaOut.model_validate(subcategoria)

@router.get("/api/subcategorias", response_model=list[SubcategoriaOut], tags=["Subcategoría"])
def get_subcategorias(
    id: Optional[UUID] = Query(None), 
    nombre: Optional[str] = Query(None),
    active: Optional[bool] = Query(None)
):
    subcategorias = obtener_subcategorias(id=id, nombre=nombre, active=active)
    return subcategorias

@router.delete("/api/subcategoria/{id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Subcategoría"])
def eliminar_subcategoria(id: UUID):
    try:
        db.eliminar_subcategoria(id)
    except SubcategoriaDeletionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

