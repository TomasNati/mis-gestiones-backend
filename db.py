from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, select, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session, relationship, selectinload, with_loader_criteria
from typing import Optional, Sequence
import uuid
import models

load_dotenv()

class Database():

    def __init__(self):
        DATABASE_URL = os.getenv("DATABASE_URL")
        self.engine = create_engine(DATABASE_URL)

database = Database()

class CategoriaDeletionError(Exception):
    pass

class SubcategoriaDeletionError(Exception):
    pass

class Base(DeclarativeBase):
    pass

class Categoria(Base):
    __tablename__ = "finanzas_categoria"
    __table_args__ = { 'schema': 'misgestiones'}

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(255))
    comentarios: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    subcategorias: Mapped[list['Subcategoria']] = relationship(back_populates='categoria')

    def __repr__(self) -> str:
        return f'Categoria(id={self.id}, nombre={self.nombre}, comentarios={self.comentarios})'

class Subcategoria(Base):
    __tablename__ = "finanzas_subcategoria"
    __table_args__ = { 'schema': 'misgestiones'}

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(255))
    tipoDeGasto: Mapped[str] = mapped_column("tipodegasto", String(255))
    comentarios: Mapped[Optional[str]] = mapped_column(Text)
    categoriaId: Mapped[str] = mapped_column('categoria', ForeignKey("misgestiones.finanzas_categoria.id"))
    categoria: Mapped[Categoria] = relationship(back_populates='subcategorias')
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f'Subcategoria(id={self.id}, nombre={self.nombre}, comentarios={self.comentarios})'
    

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
            .options(selectinload(Categoria.subcategorias))
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
    
