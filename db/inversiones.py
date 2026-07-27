from typing import Optional, Sequence
import uuid
from structure import (
    Instrumento,
    InversionDeletionError,
    Precio,
    Inversion
)
from sqlalchemy.orm import Session, selectinload, with_loader_criteria
from db.db import database
from sqlalchemy import func, select, asc, desc
from datetime import datetime
import models.drive as drive


def crear_instrumento(instr: drive.InstrumentoCrear) -> Instrumento:
    with Session(database.engine) as session:
        # Ensure enum values are stored as strings in DB
        tipo_val = instr.tipo.value if hasattr(instr.tipo, 'value') else instr.tipo
        clase_val = instr.clase_renta.value if hasattr(instr.clase_renta, 'value') else instr.clase_renta
        moneda_val = instr.moneda.value if hasattr(instr.moneda, 'value') else instr.moneda

        instrumento = Instrumento(
            nombre=instr.nombre,
            codigo=instr.codigo,
            tipo=tipo_val,
            clase_renta=clase_val,
            moneda=moneda_val
        )
        session.add(instrumento)
        session.commit()
        session.refresh(instrumento)
        return instrumento

def obtener_instrumentos(
        id: Optional[uuid.UUID] = None,
        nombre: Optional[str] = None,
        codigo: Optional[str] = None,
        tipo: Optional[str] = None,
        active: Optional[bool] = None
) -> Sequence[Instrumento]:
    with Session(database.engine) as session:
        query = select(Instrumento)
        if id is not None: query = query.where(Instrumento.id == id)
        if nombre is not None: query = query.where(Instrumento.nombre.ilike(f"%{nombre}%"))
        if codigo is not None: query = query.where(Instrumento.codigo.ilike(f"%{codigo}%"))
        if tipo is not None: query = query.where(Instrumento.tipo == tipo)
        if active is not None: query = query.where(Instrumento.active == active)

        result = session.execute(query)
        instrumentos = result.scalars().all()

    return instrumentos

def obtener_instrumento_por_id(id: uuid.UUID) -> Instrumento:
    with Session(database.engine) as session:
        query = select(Instrumento).where(Instrumento.id == id).options(selectinload(Instrumento.precios))
        result = session.execute(query)
        instrumento = result.scalars().first()
        return instrumento

def actualizar_instrumento(id: uuid.UUID, instrumento_update: drive.InstrumentoOut) -> Instrumento:
    with Session(database.engine) as session:
        ins = session.get(Instrumento, id)
        if ins:
            ins.nombre = instrumento_update.nombre
            ins.codigo = instrumento_update.codigo
            # Accept Enum or raw string
            ins.tipo = instrumento_update.tipo.value if hasattr(instrumento_update.tipo, 'value') else instrumento_update.tipo
            ins.clase_renta = instrumento_update.clase_renta.value if hasattr(instrumento_update.clase_renta, 'value') else instrumento_update.clase_renta
            ins.moneda = instrumento_update.moneda.value if hasattr(instrumento_update.moneda, 'value') else instrumento_update.moneda
            ins.active = instrumento_update.active
            session.commit()
            session.refresh(ins)
        return ins

def crear_precio(precio: drive.PrecioCrear) -> Precio:
    with Session(database.engine) as session:
        existing = session.execute(
            select(Precio).where(
                Precio.instrumentoId == precio.instrumento_id,
                func.date(Precio.fecha) == func.date(precio.fecha)
            )
        ).scalar_one_or_none()
        if existing:
            existing.monto = precio.monto
            existing.fecha = precio.fecha
            existing.active = True
            session.commit()
            session.refresh(existing)
            return existing
        p = Precio(monto=precio.monto, fecha=precio.fecha, instrumentoId=precio.instrumento_id)
        session.add(p)
        session.commit()
        session.refresh(p)
        return p

def actualizar_precio(id: uuid.UUID, precio_update: drive.PrecioOut) -> Precio:
    with Session(database.engine) as session:
        p = session.get(Precio, id)
        if p:
            p.monto = precio_update.monto
            p.fecha = precio_update.fecha
            p.instrumentoId = precio_update.instrumentoId
            p.active = precio_update.active
            session.commit()
            session.refresh(p)
        return p

def obtener_precios(
        id: Optional[uuid.UUID] = None,
        instrumento_id: Optional[uuid.UUID] = None,
        desde_fecha: Optional[datetime] = None,
        hasta_fecha: Optional[datetime] = None,
        active: Optional[bool] = None,
        page_size: Optional[int] = None,
        page_number: Optional[int] = None
) -> Sequence[Precio]:
    with Session(database.engine) as session:
        query = select(Precio).options(selectinload(Precio.instrumento))
        if id is not None: query = query.where(Precio.id == id)
        if instrumento_id is not None: query = query.where(Precio.instrumentoId == instrumento_id)
        if desde_fecha is not None: query = query.where(Precio.fecha >= desde_fecha)
        if hasta_fecha is not None: query = query.where(Precio.fecha <= hasta_fecha)
        if active is not None: query = query.where(Precio.active == active)

        # pagination
        if page_size is not None and page_number is not None:
            query = query.limit(page_size).offset(page_size * (page_number - 1))

        result = session.execute(query)
        precios = result.scalars().all()
        return precios

def crear_inversion(inv: drive.InversionCrear) -> Inversion:
    with Session(database.engine) as session:
        inversion = Inversion(cantidad=inv.cantidad, instrumentoId=inv.instrumento_id, broker=inv.broker, fecha=inv.fecha)
        session.add(inversion)
        session.commit()
        inversion = session.execute(
            select(Inversion).options(selectinload(Inversion.instrumento)).where(Inversion.id == inversion.id)
        ).scalar_one()
        return inversion

def obtener_inversiones(
        id: Optional[uuid.UUID] = None,
        instrumento_id: Optional[uuid.UUID] = None,
        active: Optional[bool] = None,
        page_size: Optional[int] = None,
        page_number: Optional[int] = None
) -> Sequence[Inversion]:
    with Session(database.engine) as session:
        query = select(Inversion).options(selectinload(Inversion.instrumento))
        # Live inversiones are the ones without a fecha. Inversiones with a fecha are
        # snapshots (history)
        query = query.where(Inversion.fecha.is_(None))
        if id is not None: query = query.where(Inversion.id == id)
        if instrumento_id is not None: query = query.where(Inversion.instrumentoId == instrumento_id)
        if active is not None: query = query.where(Inversion.active == active)

        if page_size is not None and page_number is not None:
            query = query.limit(page_size).offset(page_size * (page_number - 1))

        result = session.execute(query)
        inversiones = result.scalars().all()
        return inversiones

def guardar_estado_inversiones(inversion_ids: list[uuid.UUID], fecha: datetime) -> Sequence[Inversion]:
    """
    Snapshot the current state of the given inversiones at `fecha`.

    For each inversión id: look up the original, then find an existing copy for
    that date (same instrumento, broker and date — ignoring hours/minutes/seconds).
    If a copy exists it is overwritten with the original's values; otherwise a new
    inversión is created from the original with `fecha` set to the day (no time).
    Returns the resulting copies with their instrumento loaded.
    """
    # Normalize to the day: store the copies at midnight, no hours/min/sec.
    fecha_dia = datetime(fecha.year, fecha.month, fecha.day)

    copia_ids: list[uuid.UUID] = []
    with Session(database.engine) as session:
        for inv_id in inversion_ids:
            original = session.get(Inversion, inv_id)
            if original is None:
                continue

            existing = session.execute(
                select(Inversion).where(
                    Inversion.instrumentoId == original.instrumentoId,
                    Inversion.broker == original.broker,
                    func.date(Inversion.fecha) == func.date(fecha_dia),
                )
            ).scalars().first()

            if existing is not None:
                existing.cantidad = original.cantidad
                existing.fecha = fecha_dia
                existing.active = True
                copia = existing
            else:
                copia = Inversion(
                    cantidad=original.cantidad,
                    instrumentoId=original.instrumentoId,
                    broker=original.broker,
                    fecha=fecha_dia,
                )
                session.add(copia)

            session.flush()
            copia_ids.append(copia.id)

        session.commit()

        if not copia_ids:
            return []

        result = session.execute(
            select(Inversion)
            .options(selectinload(Inversion.instrumento))
            .where(Inversion.id.in_(copia_ids))
        )
        return result.scalars().all()

def obtener_instrumentos_con_precios(
        id: Optional[uuid.UUID] = None,
        nombre: Optional[str] = None,
        codigo: Optional[str] = None,
        tipo: Optional[str] = None,
        active: Optional[bool] = None,
        limit_precios: int = 50
) -> Sequence[Instrumento]:
    """
    Fetch instrumentos with their latest N prices (default 50).
    Uses a ROW_NUMBER() window function so the DB returns at most
    `limit_precios` per instrumento, ordered by fecha DESC.
    """
    with Session(database.engine) as session:
        query = select(Instrumento)
        if id is not None: query = query.where(Instrumento.id == id)
        if nombre is not None: query = query.where(Instrumento.nombre.ilike(f"%{nombre}%"))
        if codigo is not None: query = query.where(Instrumento.codigo.ilike(f"%{codigo}%"))
        if tipo is not None: query = query.where(Instrumento.tipo == tipo)
        if active is not None: query = query.where(Instrumento.active == active)

        instrumentos = session.execute(query).scalars().all()

        if not instrumentos:
            return instrumentos

        instrumento_ids = [i.id for i in instrumentos]

        rn = func.row_number().over(
            partition_by=Precio.instrumentoId,
            order_by=desc(Precio.fecha)
        ).label('rn')

        ranked = (
            select(Precio.id, rn)
            .where(Precio.instrumentoId.in_(instrumento_ids))
            .where(Precio.active == True)
            .subquery()
        )

        precios = session.execute(
            select(Precio)
            .join(ranked, Precio.id == ranked.c.id)
            .where(ranked.c.rn <= limit_precios)
            .order_by(Precio.instrumentoId, desc(Precio.fecha))
        ).scalars().all()

        precios_map: dict[str, list] = {}
        for p in precios:
            precios_map.setdefault(str(p.instrumentoId), []).append(p)

        for instrumento in instrumentos:
            instrumento.precios = precios_map.get(str(instrumento.id), [])

        return instrumentos

def eliminar_inversion(id: uuid.UUID): 
    with Session(database.engine) as session:
        inversion = session.get(Inversion, id)
        if inversion is None:
            raise InversionDeletionError(f"Inversión with id {id} not found")
        
        inversion.active = False
        session.commit()
