from typing import Optional, Sequence
import uuid
from datetime import date, datetime
from enums import Moneda
from structure import (
    DolarHistorico,
    Instrumento,
    InversionDeletionError,
    Precio,
    Inversion
)
from sqlalchemy.orm import Session, selectinload, with_loader_criteria
from db.db import database
from sqlalchemy import func, select, asc, desc
import models.inversiones as modelos


def crear_instrumento(instr: modelos.InstrumentoCrear) -> Instrumento:
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

def actualizar_instrumento(id: uuid.UUID, instrumento_update: modelos.InstrumentoOut) -> Instrumento:
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

def crear_precio(precio: modelos.PrecioCrear) -> Precio:
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

def actualizar_precio(id: uuid.UUID, precio_update: modelos.PrecioOut) -> Precio:
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
        fecha: Optional[datetime] = None,
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
        if fecha is not None: query = query.where(func.date(Precio.fecha) == func.date(fecha))
        if desde_fecha is not None: query = query.where(Precio.fecha >= desde_fecha)
        if hasta_fecha is not None: query = query.where(Precio.fecha <= hasta_fecha)
        if active is not None: query = query.where(Precio.active == active)

        # pagination
        if page_size is not None and page_number is not None:
            query = query.limit(page_size).offset(page_size * (page_number - 1))

        result = session.execute(query)
        precios = result.scalars().all()
        return precios

def crear_inversion(inv: modelos.InversionCrear) -> Inversion:
    with Session(database.engine) as session:
        inversion = Inversion(cantidad=inv.cantidad, instrumentoId=inv.instrumento_id, broker=inv.broker, fecha=inv.fecha)
        session.add(inversion)
        session.commit()
        inversion = session.execute(
            select(Inversion).options(selectinload(Inversion.instrumento)).where(Inversion.id == inversion.id)
        ).scalar_one()
        return inversion

def actualizar_inversion(id: uuid.UUID, cantidad: float) -> Optional[Inversion]:
    with Session(database.engine) as session:
        inversion = session.get(Inversion, id)
        if inversion is None:
            return None

        inversion.cantidad = cantidad
        session.commit()

        return session.execute(
            select(Inversion).options(selectinload(Inversion.instrumento)).where(Inversion.id == id)
        ).scalar_one()

def obtener_inversiones(
        id: Optional[uuid.UUID] = None,
        instrumento_id: Optional[uuid.UUID] = None,
        active: Optional[bool] = None,
        fecha: Optional[datetime] = None,
        page_size: Optional[int] = None,
        page_number: Optional[int] = None
) -> Sequence[Inversion]:
    with Session(database.engine) as session:
        query = select(Inversion).options(selectinload(Inversion.instrumento))
        # Live inversiones are the ones without a fecha. Inversiones with a fecha are
        # snapshots (history), so `fecha` returns that day's snapshot instead of the
        # live rows. Compared by day, matching how guardar_estado_inversiones stores it.
        if fecha is None:
            query = query.where(Inversion.fecha.is_(None))
        else:
            query = query.where(func.date(Inversion.fecha) == func.date(fecha))
        if id is not None: query = query.where(Inversion.id == id)
        if instrumento_id is not None: query = query.where(Inversion.instrumentoId == instrumento_id)
        if active is not None: query = query.where(Inversion.active == active)

        if page_size is not None and page_number is not None:
            query = query.limit(page_size).offset(page_size * (page_number - 1))

        result = session.execute(query)
        inversiones = result.scalars().all()
        return inversiones

def obtener_fechas_historial_inversiones() -> Sequence[datetime]:
    with Session(database.engine) as session:
        result = session.scalars(
            select(Inversion.fecha)
            .where(
                Inversion.fecha.is_not(None),
                Inversion.active.is_(True),
            )
            .distinct()
            .order_by(Inversion.fecha.desc())
        ).all()

    return [fecha for fecha in result if fecha is not None]

def obtener_historico_inversiones(
        desde: datetime,
        hasta: datetime,
) -> dict:
    """Inversiones activas entre dos fechas (inclusive), agrupadas por día.

    Cada inversión se valora en todas las monedas (peso, dólar oficial, dólar
    CCL y dólar bolsa) con la misma lógica que `calcularValorInversion` del
    frontend (src/hooks/inversiones/useInversiones.ts), siempre que ese día
    exista cotización de dólar y precio del instrumento. Las inversiones a las
    que les falta alguno van en una colección separada.
    """
    with Session(database.engine) as session:
        inversiones = session.scalars(
            select(Inversion)
            .options(selectinload(Inversion.instrumento))
            .where(
                Inversion.active.is_(True),
                Inversion.fecha.is_not(None),
                func.date(Inversion.fecha) >= func.date(desde),
                func.date(Inversion.fecha) <= func.date(hasta),
            )
            .order_by(Inversion.fecha.desc())
        ).all()

        dolares = session.scalars(
            select(DolarHistorico)
            .where(
                DolarHistorico.active.is_(True),
                func.date(DolarHistorico.fecha) >= func.date(desde),
                func.date(DolarHistorico.fecha) <= func.date(hasta),
            )
            .order_by(DolarHistorico.fecha.desc())
        ).all()

        instrumento_ids = {inv.instrumentoId for inv in inversiones}
        precios: Sequence[Precio] = []
        if instrumento_ids:
            precios = session.scalars(
                select(Precio)
                .where(
                    Precio.instrumentoId.in_(instrumento_ids),
                    Precio.active.is_(True),
                    func.date(Precio.fecha) >= func.date(desde),
                    func.date(Precio.fecha) <= func.date(hasta),
                )
                .order_by(Precio.fecha.desc())
            ).all()

    dolar_por_dia = {d.fecha.date(): d for d in dolares}
    # Precio más reciente de cada instrumento dentro de cada día.
    precio_por_dia: dict[tuple[str, date], Precio] = {}
    for p in precios:
        precio_por_dia.setdefault((str(p.instrumentoId), p.fecha.date()), p)

    inversiones_por_dia: dict[date, list[Inversion]] = {}
    for inv in inversiones:
        inversiones_por_dia.setdefault(inv.fecha.date(), []).append(inv)

    por_fecha: list[dict] = []
    incompletas: list[dict] = []
    for dia in sorted(inversiones_por_dia.keys(), reverse=True):
        dolar = dolar_por_dia.get(dia)
        valorizadas: list[dict] = []
        for inv in inversiones_por_dia[dia]:
            precio = precio_por_dia.get((str(inv.instrumentoId), dia))
            if precio is None or dolar is None:
                incompletas.append({
                    'fecha': inv.fecha,
                    'inversion': inv,
                    'motivo': 'sin_precio' if precio is None else 'sin_dolar',
                })
                continue
            valorizadas.append({
                'inversion': inv,
                'precio': precio.monto,
                'valor': _calcular_valores(inv, precio.monto, dolar),
            })
        por_fecha.append({
            'fecha': datetime(dia.year, dia.month, dia.day),
            'dolar': dolar,
            'inversiones': valorizadas,
        })

    return {'por_fecha': por_fecha, 'inversiones_incompletas': incompletas}


MONEDAS_DOLAR = (Moneda.DOLAR_BOLSA.value, Moneda.DOLAR_CCL.value)


def _calcular_valores(inv: Inversion, monto: float, dolar: DolarHistorico) -> dict:
    """Valor de una inversión en todas las monedas a la vez. Misma lógica que
    `calcularValorInversion` (src/hooks/inversiones/useInversiones.ts), que solo
    devuelve el valor para una moneda, pero para todas.
    """
    valor_nativo = inv.cantidad * monto
    if inv.instrumento.moneda in MONEDAS_DOLAR:
        dolar_instrumento = (
            dolar.bolsa
            if inv.instrumento.moneda == Moneda.DOLAR_BOLSA.value
            else dolar.contadoconliqui
        )
        valor_pesos = valor_nativo * dolar_instrumento
    else:
        valor_pesos = valor_nativo

    return {
        'peso': valor_pesos,
        'dolar_oficial': valor_pesos / dolar.oficial,
        'dolar_ccl': valor_pesos / dolar.contadoconliqui,
        'dolar_bolsa': valor_pesos / dolar.bolsa,
    }


def guardar_estado_inversiones(
    inversion_ids: list[uuid.UUID],
    fecha: datetime,
    dolar: modelos.DolarCotizaciones,
    sobreescribir: bool = False,
) -> Sequence[Inversion]:
    # Normalize to the day: store the copies at midnight, no hours/min/sec.
    fecha_dia = datetime(fecha.year, fecha.month, fecha.day)

    copia_ids: list[uuid.UUID] = []
    with Session(database.engine) as session:
        _guardar_dolar_historico(session, dolar, fecha_dia, sobreescribir)

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

            if existing is not None and not sobreescribir:
                continue

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

def _guardar_dolar_historico(
        session: Session,
        cotizaciones: modelos.DolarCotizaciones,
        fecha_dia: datetime,
        sobreescribir: bool,
) -> Optional[DolarHistorico]:
    existing = session.execute(
        select(DolarHistorico).where(DolarHistorico.fecha == fecha_dia)
    ).scalar_one_or_none()

    if existing is not None and not sobreescribir:
        return None

    if existing is not None:
        existing.oficial = cotizaciones.oficial
        existing.blue = cotizaciones.blue
        existing.bolsa = cotizaciones.bolsa
        existing.contadoconliqui = cotizaciones.contadoconliqui
        existing.active = True
        return existing

    d = DolarHistorico(
        oficial=cotizaciones.oficial,
        blue=cotizaciones.blue,
        bolsa=cotizaciones.bolsa,
        contadoconliqui=cotizaciones.contadoconliqui,
        fecha=fecha_dia,
    )
    session.add(d)
    return d

def crear_dolar_historico(dolar: modelos.DolarHistoricoCrear) -> DolarHistorico:
    fecha_dia = datetime(dolar.fecha.year, dolar.fecha.month, dolar.fecha.day)
    with Session(database.engine) as session:
        d = _guardar_dolar_historico(session, dolar, fecha_dia, sobreescribir=True)
        session.commit()
        session.refresh(d)
        return d

def actualizar_dolar_historico(
        id: uuid.UUID,
        dolar_update: modelos.DolarHistoricoOut
) -> Optional[DolarHistorico]:
    with Session(database.engine) as session:
        d = session.get(DolarHistorico, id)
        if d is None:
            return None

        d.oficial = dolar_update.oficial
        d.blue = dolar_update.blue
        d.bolsa = dolar_update.bolsa
        d.contadoconliqui = dolar_update.contadoconliqui
        d.fecha = datetime(dolar_update.fecha.year, dolar_update.fecha.month, dolar_update.fecha.day)
        d.active = dolar_update.active
        session.commit()
        session.refresh(d)
        return d

def obtener_dolares_historicos(
        id: Optional[uuid.UUID] = None,
        fecha: Optional[datetime] = None,
        desde_fecha: Optional[datetime] = None,
        hasta_fecha: Optional[datetime] = None,
        active: Optional[bool] = None,
        page_size: Optional[int] = None,
        page_number: Optional[int] = None
) -> Sequence[DolarHistorico]:
    with Session(database.engine) as session:
        query = select(DolarHistorico)
        if id is not None: query = query.where(DolarHistorico.id == id)
        if fecha is not None: query = query.where(func.date(DolarHistorico.fecha) == func.date(fecha))
        if desde_fecha is not None: query = query.where(DolarHistorico.fecha >= desde_fecha)
        if hasta_fecha is not None: query = query.where(DolarHistorico.fecha <= hasta_fecha)
        if active is not None: query = query.where(DolarHistorico.active == active)

        query = query.order_by(DolarHistorico.fecha.desc())

        if page_size is not None and page_number is not None:
            query = query.limit(page_size).offset(page_size * (page_number - 1))

        result = session.execute(query)
        return result.scalars().all()

def eliminar_dolar_historico(id: uuid.UUID) -> bool:
    """Soft-delete: marca la cotización como inactiva. False si no existe."""
    with Session(database.engine) as session:
        d = session.get(DolarHistorico, id)
        if d is None:
            return False

        d.active = False
        session.commit()
        return True

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
