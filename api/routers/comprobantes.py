import mimetypes
import uuid
from urllib.parse import quote

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

import db.gestiones as gestos
import github
import models.comprobantes as comprobantes

router = APIRouter(prefix="/api/comprobantes", tags=["Comprobantes"])

EXTENSIONES_PERMITIDAS = {".pdf", ".jpg", ".jpeg", ".png", ".heic"}


def _content_length(request: Request) -> int:
    crudo = request.headers.get("content-length")
    return int(crudo) if crudo and crudo.isdigit() else 0


def _validar_extension(nombre: str) -> None:
    punto = nombre.rfind(".")
    extension = nombre[punto:].lower() if punto > 0 else ""
    if extension not in EXTENSIONES_PERMITIDAS:
        permitidas = ", ".join(sorted(EXTENSIONES_PERMITIDAS))
        raise HTTPException(status_code=415, detail={"error": "Unsupported Media Type", "message": f"extension '{extension or '(ninguna)'}' not allowed; use one of: {permitidas}"})


def _leer_con_limite(upload: UploadFile, nombre: str) -> bytes:
    """Lee el archivo abortando en cuanto pasa el limite, sin bufferear de mas.

    El patron es `Content-Length` primero, y despues
    conteo por chunks de 256KB que corta el request con 413 en el momento en que
    se excede, en vez de dejar que el cliente agote la memoria del proceso.
    """
    partes = []
    total = 0
    while True:
        chunk = upload.file.read(github.CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > github.MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"error": "Payload Too Large", "message": f"'{nombre}' exceeds the maximum of {github.MAX_UPLOAD_BYTES} bytes"},
            )
        partes.append(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail={"error": "Bad Request", "message": f"'{nombre}' is empty"})
    return b"".join(partes)


def _validar_vencimiento_pagado(vencimiento_id: uuid.UUID) -> None:
    """El vencimiento tiene que existir y estar pagado antes de guardar un comprobante.
    """
    vencimientos = gestos.obtener_vencimientos(id=vencimiento_id, page_size=1)
    vencimiento = vencimientos.vencimientos[0] if vencimientos.vencimientos else None
    if vencimiento is None:
        raise HTTPException(status_code=404, detail={"error": "Not Found", "message": f"no vencimiento with id '{vencimiento_id}'"})
    if vencimiento.pagoId is None:
        raise HTTPException(
            status_code=409,
            detail={"error": "Conflict", "message": f"vencimiento '{vencimiento_id}' has no payment registered; a comprobante requires one"},
        )


@router.post("", response_model=comprobantes.ComprobanteSubidaOut, status_code=201)
def subir_comprobante(
    request: Request,
    vencimiento_id: str = Form(...),
    base_path: str = Form(...),
    subpath: str = Form(...),
    file: UploadFile = File(...),
):
    """Sube **un** comprobante y registra el `finanzas_comprobante_pago` que lo apunta.

    El path final dentro del repo es `base_path/subpath`, ambos decididos por el
    cliente: `base_path` es la carpeta principal del comprobante
    (`subcategoria.comprobantes_path`) y `subpath` el nombre dentro de ella
    (`2026/09-factura.pdf`).
    """
    if _content_length(request) > github.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"error": "Payload Too Large", "message": f"upload exceeds the maximum of {github.MAX_UPLOAD_BYTES} bytes"},
        )

    try:
        vencimiento_uuid = uuid.UUID(vencimiento_id)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=422, detail={"error": "Unprocessable Entity", "message": f"vencimiento_id '{vencimiento_id}' is not a valid uuid"})

    base = base_path.replace("\\", "/").strip().strip("/")
    if not base:
        raise HTTPException(status_code=400, detail={"error": "Bad Request", "message": "base_path is required and must reference a folder inside the repository"})

    sub = subpath.replace("\\", "/").strip().strip("/")
    if not sub:
        raise HTTPException(status_code=400, detail={"error": "Bad Request", "message": "subpath is required"})
    if len(sub) > 256:
        raise HTTPException(
            status_code=400,
            detail={"error": "Bad Request", "message": f"subpath is {len(sub)} characters, over the column limit of 256"},
        )

    nombre = sub.rsplit("/", 1)[-1].strip()
    if not nombre or nombre in (".", ".."):
        raise HTTPException(status_code=400, detail={"error": "Bad Request", "message": "subpath must end with a filename"})
    _validar_extension(nombre)

    contenido = _leer_con_limite(file, nombre)

    try:
        ruta = github.normalizar_path(f"{base}/{sub}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "Bad Request", "message": str(e)})

    _validar_vencimiento_pagado(vencimiento_uuid)

    try:
        commit = github.escribir_paths([{"path": ruta, "content": contenido}], f"subir comprobante: {nombre}")
    except httpx.HTTPError as e:
        # github mapea los status de la API de GitHub; aca solo quedan los
        # errores de transporte (timeout, DNS, conexion caida), que sin esto
        # escaping como 500 con stack trace.
        raise github.map_http_error(e, detalle=f"subir {nombre}")

    comprobante = gestos.crear_comprobante_pago(vencimiento_uuid, sub)

    return {
        "id": comprobante.id,
        "commit": commit,
        "path": ruta,
        "nombre": nombre,
        "size": len(contenido),
        "subpath": sub,
        "max_upload_bytes": github.MAX_UPLOAD_BYTES,
    }


@router.get("/descargar")
def descargar_archivo(path: str):
    """Descarga un archivo del repo por path completo.

    Devuelve 404 si no hay ningun archivo en ese path, y 413 si el archivo
    existe pero pasa `MAX_UPLOAD_BYTES` (la descarga es una response de la
    funcion, con el mismo techo que el request).
    """
    try:
        ruta = github.normalizar_path(path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "Bad Request", "message": str(e)})

    encontrado = github.leer_archivo(ruta)
    if encontrado is None:
        raise HTTPException(status_code=404, detail={"error": "Not Found", "message": f"no file at '{ruta}'"})
    largo, generador = encontrado
    if largo is not None and largo > github.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"error": "Payload Too Large", "message": f"'{ruta}' is {largo} bytes, over the maximum of {github.MAX_UPLOAD_BYTES}"},
        )

    nombre = github.nombre_de_archivo(ruta)
    media_type, _ = mimetypes.guess_type(nombre)
    headers = {"Content-Disposition": f'attachment; filename="{quote(nombre)}"'}
    if largo is not None:
        headers["Content-Length"] = str(largo)
    return StreamingResponse(generador, media_type=media_type or "application/octet-stream", headers=headers)


@router.get("/limites", response_model=comprobantes.ComprobanteLimitesOut)
def limites():
    """Limite efectivo de upload, para que la UI valide antes de subir en vez de
    recibir un 413 seco."""
    repo = f"{github.GITHUB_REPO_OWNER}/{github.GITHUB_REPO_NAME}" if github.GITHUB_REPO_OWNER and github.GITHUB_REPO_NAME else None
    return {"max_upload_bytes": github.MAX_UPLOAD_BYTES, "repo": repo, "branch": github.GITHUB_REPO_BRANCH}
