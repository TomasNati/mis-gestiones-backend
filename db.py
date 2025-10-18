from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, select, String, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from typing import Optional, Sequence
import uuid


load_dotenv()

class Database():

    def __init__(self):
        DATABASE_URL = os.getenv("DATABASE_URL")
        self.engine = create_engine(DATABASE_URL)

database = Database()

class Base(DeclarativeBase):
    pass

class Categoria(Base):
    __tablename__ = "finanzas_categoria"
    __table_args__ = { 'schema': 'misgestiones'}

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(255))
    comentarios: Mapped[Optional[str]] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


    def __repr__(self) -> str:
        return f'Categoria(id={self.id}, nombre={self.nombre}, comentarios={self.comentarios})'
    

def obtener_categorias() -> Sequence[Categoria]:
    with Session(database.engine) as session:
        result = session.execute(select(Categoria).where(Categoria.active == True))
        categorias_activas = result.scalars().all()

    return categorias_activas
    


