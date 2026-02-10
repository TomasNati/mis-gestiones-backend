from datetime import datetime
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session, selectinload, with_loader_criteria
from typing import Optional, Sequence
from structure import (
    Categoria,
    Subcategoria,
    CategoriaDeletionError,
    SubcategoriaDeletionError,
    MovimientoGasto,
    DetalleSubcategoria
)
import uuid
import models

load_dotenv()

class Database():

    def __init__(self):
        DATABASE_URL = os.getenv("DATABASE_URL")
        self.engine = create_engine(DATABASE_URL)

database = Database()

def obtener_categorias(
        id: Optional[UUID] = None,
        nombre: Optional[str] = None,
        active: Optional[bool] = None
) -> Sequence[Categoria]:
    with Session(database.engine) as session:
        query = select(Categoria)

        if active is not None:
            query = query.options(
                selectinload(Categoria.subcategorias),
                with_loader_criteria(Subcategoria, lambda s: s.active == active, include_aliases=True)
            )
        else:
            query = query.options(selectinload(Categoria.subcategorias))

        if id is not None: query = query.where(Categoria.id == id)
        if nombre is not None: query = query.where(Categoria.nombre.ilike(f"%{nombre}%"))
        if active is not None: query = query.where(Categoria.active == active)

        result = session.execute(query)
        categorias = result.scalars().all()

    return categorias

def obtener_movimientos_gasto(
        id: Optional[UUID] = None,
        categoriaIds: Optional[Sequence[UUID]] = None,
        subcategoriaIds: Optional[Sequence[UUID]] = None,
        detalleSubcategoriaIds: Optional[Sequence[UUID]] = None,
        tiposDePago: Optional[Sequence[str]] = None,
        active: Optional[bool] = None,
        monto_min: Optional[float] = None,
        monto_max: Optional[float] = None,
        comentarios: Optional[str] = None,
        desde_fecha: Optional[datetime] = None,
        hasta_fecha: Optional[datetime] = None,
        page_size: Optional[int] = 50,
        page_number: Optional[int] = 1
) -> models.MovimientoGastoSearchResults:
    with Session(database.engine) as session:
        query = (
            select(MovimientoGasto)
            .options(
                selectinload(MovimientoGasto.subcategoria).options(
                    selectinload(Subcategoria.categoria)
                ),
                selectinload(MovimientoGasto.detalleSubcategoria).options(
                    selectinload(DetalleSubcategoria.subcategoria)
                )
            )
        )

        if id is not None: query = query.where(MovimientoGasto.id == id)
        if categoriaIds is not None and (len(categoriaIds) > 0): query = query.where(MovimientoGasto.subcategoria.has(Subcategoria.categoriaId.in_(categoriaIds)))
        if subcategoriaIds is not None and (len(subcategoriaIds) > 0): query = query.where(MovimientoGasto.subcategoriaId.in_(subcategoriaIds))
        if detalleSubcategoriaIds is not None and (len(detalleSubcategoriaIds) > 0): query = query.where(MovimientoGasto.detalleSubcategoriaId.in_(detalleSubcategoriaIds))
        if tiposDePago is not None and (len(tiposDePago) > 0): query = query.where(MovimientoGasto.tipoDePago.in_(tiposDePago))
        if active is not None: query = query.where(MovimientoGasto.active == active)
        if monto_min is not None: query = query.where(MovimientoGasto.monto >= monto_min)
        if monto_max is not None: query = query.where(MovimientoGasto.monto <= monto_max)
        if comentarios is not None: query = query.where(MovimientoGasto.comentarios.ilike(f"%{comentarios}%"))
        if desde_fecha is not None: query = query.where(MovimientoGasto.fecha >= desde_fecha)
        if hasta_fecha is not None: query = query.where(MovimientoGasto.fecha <= hasta_fecha)

        # Get total count before pagination
        total = session.execute(
            select(func.count()).select_from(query.subquery())
        ).scalar_one()

        if page_size is not None and page_number is not None:
            query = query.limit(page_size).offset(page_size * (page_number - 1))

        result = session.execute(query)
        movimientos = result.scalars().all()

    return models.MovimientoGastoSearchResults(
        total=total,
        page_number=page_number,
        page_size=page_size,
        movimientos=movimientos
    )

def obtener_categoria_por_id(id: UUID, incluir_subcategorias: bool = False):
    with Session(database.engine) as session:
        query = (
            select(Categoria)
            .where(Categoria.id == id)
        )
        if incluir_subcategorias:
            query = query.options(selectinload(Categoria.subcategorias))

        result = session.execute(query)
        categoria = result.scalars().first()

    return categoria

def actualizar_categoria(id: UUID, categoria_update: models.CategoriaBasicOut) -> Categoria:
    with Session(database.engine) as session:
        categoria = session.get(Categoria, id)
        if categoria:
            categoria.nombre = categoria_update.nombre
            categoria.comentarios = categoria_update.comentarios
            categoria.active = categoria_update.active
            session.commit()
            session.refresh(categoria)
        return categoria

def crear_categoria(nombre: str) -> Categoria:
    with Session(database.engine) as session:
        categoria = Categoria(nombre=nombre)
        session.add(categoria)
        session.commit()
        session.refresh(categoria)
        return categoria

def eliminar_categoria(id: uuid.UUID, eliminar_subcategorias: bool = False ):
    with Session(database.engine) as session:
        categoria = session.execute(
            select(Categoria)
            .options(
                selectinload(Categoria.subcategorias),
                with_loader_criteria(Subcategoria, Subcategoria.active == True)
            )
            .where(Categoria.id == id)
        ).scalar_one_or_none()

        if categoria is None:
            raise CategoriaDeletionError(f"Categoria with id {id} not found.")
        
        has_children = bool(categoria.subcategorias)
        if  has_children and not eliminar_subcategorias:
            raise CategoriaDeletionError("Cannot delete Categoria with Subcategorias unless eliminar_subcategoria is True")
        
        if has_children and eliminar_subcategorias:
            for sub in categoria.subcategorias:
                sub.active = False

        categoria.active = False
        session.commit()

def crear_subcategoria(subcategoria: models.SubcategoriaCrear) -> Subcategoria:
    with Session(database.engine) as session:
        subcategoria = Subcategoria(
            nombre=subcategoria.nombre, 
            comentarios=subcategoria.comentarios,
            categoriaId=subcategoria.categoriaId)
        session.add(subcategoria)
        session.commit()
        session.refresh(subcategoria)
        return subcategoria

def actualizar_subcategoria(subcategoria: models.SubcategoriaOut) -> Subcategoria:
    with Session(database.engine) as session:
        subcategoriaDB = session.get(Subcategoria, subcategoria.id)
        if subcategoriaDB:
            subcategoriaDB.nombre = subcategoria.nombre
            subcategoriaDB.comentarios = subcategoria.comentarios
            subcategoriaDB.categoriaId = subcategoria.categoriaId
            subcategoriaDB.active = subcategoria.active
            session.commit()
            session.refresh(subcategoriaDB)
        return subcategoriaDB

def obtener_subcategoria_por_id(id: UUID) -> Subcategoria:
    with Session(database.engine) as session:
        query = (
            select(Subcategoria)
            .options(selectinload(Subcategoria.categoria))
            .where(Subcategoria.id == id)
        )

        result = session.execute(query)
        subcategoria = result.scalars().first()

        return subcategoria

def obtener_subcategorias(
        id: Optional[UUID] = None,
        nombre: Optional[str] = None,
        active: Optional[bool] = None
) -> Sequence[Subcategoria]:
    with Session(database.engine) as session:
        query = (
          select(Subcategoria)
          .options(selectinload(Subcategoria.categoria))
        )

        if id is not None: query = query.where(Subcategoria.id == id)
        if nombre is not None: query = query.where(Subcategoria.nombre.ilike(f"%{nombre}%"))
        if active is not None: query = query.where(Subcategoria.active == active)

        result = session.execute(query)
        subcategorias = result.scalars().all()

    return subcategorias

def eliminar_subcategoria(id: uuid.UUID):
    with Session(database.engine) as session:
        subcategoria = session.get(Subcategoria, id)

        if subcategoria is None:
            raise SubcategoriaDeletionError(f"Subcategoria with id {id} not found.")

        subcategoria.active = False
        session.commit()
