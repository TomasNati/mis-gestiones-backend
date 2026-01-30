from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import DateTime, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from typing import Optional
from datetime import datetime
import uuid

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
    
class DetalleSubcategoria(Base):
    __tablename__ = "finanzas_detallesubcategoria"
    __table_args__ = { 'schema': 'misgestiones'}

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(255))
    subcategoriaId: Mapped[str] = mapped_column('subcategoria', ForeignKey("misgestiones.finanzas_subcategoria.id"))
    subcategoria: Mapped[Subcategoria] = relationship()
    comentarios: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    

class MovimientoGasto(Base):
    __tablename__ = "finanzas_movimientogasto"
    __table_args__ = { 'schema': 'misgestiones'}

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subcategoriaId: Mapped[str] = mapped_column('subcategoria', ForeignKey("misgestiones.finanzas_subcategoria.id"))
    subcategoria: Mapped[Subcategoria] = relationship()
    detalleSubcategoriaId: Mapped[Optional[str]] = mapped_column('detallesubcategoria', ForeignKey("misgestiones.finanzas_detallesubcategoria.id"), nullable=True)
    detalleSubcategoria: Mapped[Optional[DetalleSubcategoria]] = relationship()
    tipoDePago: Mapped[str] = mapped_column("tipodepago", String(255))
    monto: Mapped[float] = mapped_column()
    comentarios: Mapped[Optional[str]] = mapped_column(Text)
    fecha: Mapped[Optional[datetime]] = mapped_column(DateTime)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
