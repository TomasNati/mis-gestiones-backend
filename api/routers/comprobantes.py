import mimetypes
from typing import List
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

import github
import models.comprobantes as comprobantes
from api.security import require_api_key

router = APIRouter(prefix="/api/comprobantes", tags=["Comprobantes"], dependencies=[Depends(require_api_key)])

EXTENSIONES_PERMITIDAS = {".pdf", ".jpg", ".jpeg", ".png", ".heic"}
GENERICOS = ("", "application/octet-stream", "binary/octet-stream")


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

    Es el mismo patron del upload de Drive: `Content-Length` primero, y despues
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


@router.post("", response_model=comprobantes.ComprobanteSubidaOut, status_code=201)
def subir_archivos(
    request: Request,
    path: str = Form(...),
    files: List[UploadFile] = File(...),
):
    """Sube uno o mas archivos al repo, en un unico commit.

    `path` es la carpeta destino dentro del repo (por ejemplo `edese/2024/06`);
    cada archivo conserva su nombre. Falla con 409 si alguno de los paths
    destino ya existe, y con 413 si algun archivo pasa `MAX_UPLOAD_BYTES`.
    """
    if _content_length(request) > github.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"error": "Payload Too Large", "message": f"upload exceeds the maximum of {github.MAX_UPLOAD_BYTES} bytes"},
        )
    if not files:
        raise HTTPException(status_code=400, detail={"error": "Bad Request", "message": "at least one file is required"})

    # Se valida la carpeta destino por separado: si se armara el path completo
    # con un `path` vacio, `normalizar_path` caeria a la raiz del repo en
    # silencio en vez de rechazar el request.
    carpeta = path.replace("\\", "/").strip().strip("/")
    if not carpeta:
        raise HTTPException(status_code=400, detail={"error": "Bad Request", "message": "path is required and must reference a folder inside the repository"})

    entradas = []
    for upload in files:
        nombre = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not nombre or nombre in (".", ".."):
            raise HTTPException(status_code=400, detail={"error": "Bad Request", "message": "every file needs a filename"})
        _validar_extension(nombre)
        entradas.append({"path": f"{carpeta}/{nombre}", "content": _leer_con_limite(upload, nombre)})

    try:
        rutas = [github.normalizar_path(e["path"]) for e in entradas]
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "Bad Request", "message": str(e)})

    repetidos = sorted({r for r in rutas if rutas.count(r) > 1})
    if repetidos:
        raise HTTPException(status_code=400, detail={"error": "Bad Request", "message": f"same file name twice in one upload: {', '.join(repetidos)}"})
    for entrada, ruta in zip(entradas, rutas):
        entrada["path"] = ruta

    nombres = [e["path"].rsplit("/", 1)[-1] for e in entradas]
    try:
        commit = github.escribir_paths(entradas, f"subir comprobantes: {', '.join(nombres)}")
    except httpx.HTTPError as e:
        # github mapea los status de la API de GitHub; acá solo quedan los
        # errores de transporte (timeout, DNS, conexion caída), que sin esto
        # escaping como 500 con stack trace.
        raise github.map_http_error(e, detalle=f"subir {', '.join(nombres)}")

    return {
        "commit": commit,
        "archivos": [{"path": e["path"], "nombre": e["path"].rsplit("/", 1)[-1], "size": len(e["content"])} for e in entradas],
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
