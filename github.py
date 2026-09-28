import base64
import logging
import os
from typing import Dict, Iterator, List, Optional, Sequence, Tuple
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

LOGGER = logging.getLogger(__name__)

API_ROOT = "https://api.github.com"
API_VERSION = "2022-11-28"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO_OWNER = os.getenv("GITHUB_REPO_OWNER")
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO_NAME")
GITHUB_REPO_BRANCH = os.getenv("GITHUB_REPO_BRANCH", "main")

COMMIT_AUTHOR_NAME = os.getenv("GITHUB_COMMIT_AUTHOR_NAME", "mis-gestiones-backend")
COMMIT_AUTHOR_EMAIL = os.getenv("GITHUB_COMMIT_AUTHOR_EMAIL", "mis-gestiones-backend@users.noreply.github.com")

HARD_MAX_UPLOAD_BYTES = 4_000_000
DEFAULT_MAX_UPLOAD_BYTES = 2_000_000


def _resolve_max_upload_bytes() -> int:
    """Lee MAX_UPLOAD_BYTES una sola vez, al importar el modulo.

    Default 2MB si no esta definida o no parsea. Si supera el tope duro se
    recorta a 4MB y se avisa por log, porque el body de la funcion no aguanta mas.
    """
    raw = os.getenv("MAX_UPLOAD_BYTES")
    if raw is None or not raw.strip():
        return DEFAULT_MAX_UPLOAD_BYTES
    try:
        value = int(raw.strip())
    except ValueError:
        LOGGER.warning("MAX_UPLOAD_BYTES=%r no es un entero; se usa el default de %d bytes", raw, DEFAULT_MAX_UPLOAD_BYTES)
        return DEFAULT_MAX_UPLOAD_BYTES
    if value <= 0:
        LOGGER.warning("MAX_UPLOAD_BYTES=%d es <= 0; se usa el default de %d bytes", value, DEFAULT_MAX_UPLOAD_BYTES)
        return DEFAULT_MAX_UPLOAD_BYTES
    if value > HARD_MAX_UPLOAD_BYTES:
        LOGGER.warning("MAX_UPLOAD_BYTES=%d supera el tope duro de %d; se recorta", value, HARD_MAX_UPLOAD_BYTES)
        return HARD_MAX_UPLOAD_BYTES
    return value


MAX_UPLOAD_BYTES = _resolve_max_upload_bytes()

# GitHub rechaza paths de arbol mas largos que esto.
MAX_PATH_LENGTH = 1000

# Streaming: 256KB, el mismo tamano que usaba el upload de Drive.
CHUNK_SIZE = 262144


class GithubError(HTTPException):
    """Error de la API de GitHub mapeado a un status de la API propia."""


def _mapear_response(resp: httpx.Response, detalle: str) -> HTTPException:
    LOGGER.error("GitHub API error %s %s: %s", resp.status_code, detalle, resp.text[:500])
    return map_http_error(httpx.HTTPStatusError("github error", request=resp.request, response=resp), detalle=detalle)


def map_http_error(e: httpx.HTTPError, detalle: str = "") -> HTTPException:
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        LOGGER.error("GitHub API error %s %s: %s", status, detalle, e.response.text[:500])
    else:
        status = 502
        LOGGER.error("GitHub API error %s: %s", detalle, e)
    if status == 404:
        return HTTPException(status_code=404, detail={"error": "Not Found", "message": "resource not found in the repository"})
    if status == 403:
        return HTTPException(status_code=403, detail={"error": "Forbidden", "message": "permission denied on the repository"})
    if status == 401:
        return HTTPException(status_code=502, detail={"error": "Github Error", "message": "the configured GITHUB_TOKEN was rejected"})
    if status == 409 or status == 422:
        return HTTPException(status_code=409, detail={"error": "Conflict", "message": "github rejected the request as conflicting or invalid"})
    return HTTPException(status_code=502, detail={"error": "Github Error", "message": "an error occurred communicating with GitHub"})


def normalizar_path(path: str) -> str:
    """Normaliza un path de archivo dentro del repo.

    Acepta separadores Windows y Unix, descarta barras duplicadas y rechaza
    cualquier intento de salir del repo ('..') o de escribir en la raiz.
    """
    if path is None:
        raise ValueError("path is required")
    normalizado = path.replace("\\", "/").strip()
    partes = [p for p in normalizado.split("/") if p not in ("", ".")]
    if not partes:
        raise ValueError("path must reference a file inside the repository")
    for parte in partes:
        if parte == "..":
            raise ValueError("path must not contain '..'")
        if parte.startswith(".") or ":" in parte or any(c in parte for c in '*?"<>|'):
            raise ValueError(f"path segment '{parte}' contains characters that are not allowed")
    limpio = "/".join(partes)
    if len(limpio) > MAX_PATH_LENGTH:
        raise ValueError(f"path must be at most {MAX_PATH_LENGTH} characters")
    return limpio


def nombre_de_archivo(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _headers(accept: str = "application/vnd.github+json") -> Dict[str, str]:
    if not GITHUB_TOKEN:
        raise HTTPException(status_code=502, detail={"error": "Configuration Error", "message": "GITHUB_TOKEN is not configured"})
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": accept,
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "mis-gestiones-backend",
    }


def _url(*partes: str) -> str:
    return "/".join([API_ROOT, "repos", GITHUB_REPO_OWNER or "", GITHUB_REPO_NAME or "", *partes])


def _client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(30.0, read=60.0))


def _check(resp: httpx.Response, detalle: str) -> httpx.Response:
    """Valida la respuesta pasando por `map_http_error`.

    Sin esto, un `raise_for_status()` crudo se escapa como
    `httpx.HTTPStatusError` y FastAPI lo convierte en un 500 con stack trace,
    en vez de un 404/409/502 con el shape de error de la API.
    """
    if resp.status_code >= 400:
        raise _mapear_response(resp, detalle)
    return resp


def obtener_sha_de_rama(client: httpx.Client) -> str:
    resp = _check(client.get(_url("git", "ref", "heads", GITHUB_REPO_BRANCH), headers=_headers()), "GET ref")
    return resp.json()["object"]["sha"]


def obtener_arbol_recursivo(client: httpx.Client, commit_sha: str) -> Dict:
    """Devuelve el arbol del commit con `truncated` resuelto.

    Sirve para dos cosas: conocer el `base_tree` de la escritura y saber que
    paths ya existen, en un solo request. `entradas` es `path -> tipo` con
    `blob` y `tree`: hace falta distinguir un archivo de una carpeta porque un
    blob no puede actuar de carpeta.
    """
    resp = _check(client.get(_url("git", "commits", commit_sha), headers=_headers()), "GET commit")
    root_tree_sha = resp.json()["tree"]["sha"]

    resp = _check(client.get(_url("git", "trees", root_tree_sha), headers=_headers(), params={"recursive": "1"}), "GET tree")
    arbol = resp.json()
    if arbol.get("truncated"):
        LOGGER.warning("El arbol del repo %s/%s vino truncado de la API de GitHub", GITHUB_REPO_OWNER, GITHUB_REPO_NAME)
    entradas = {e["path"]: e.get("type") for e in arbol.get("tree", []) if e.get("type") in ("blob", "tree")}
    return {"sha": root_tree_sha, "entradas": entradas}


def crear_blob(client: httpx.Client, contenido: bytes) -> str:
    resp = _check(
        client.post(
            _url("git", "blobs"),
            headers=_headers(),
            json={"content": base64.b64encode(contenido).decode("ascii"), "encoding": "base64"},
        ),
        "POST blob",
    )
    return resp.json()["sha"]


def crear_arbol(client: httpx.Client, base_tree_sha: str, entradas: Sequence[Dict]) -> str:
    resp = _check(
        client.post(
            _url("git", "trees"),
            headers=_headers(),
            json={"base_tree": base_tree_sha, "tree": list(entradas)},
        ),
        "POST tree",
    )
    return resp.json()["sha"]


def crear_commit(client: httpx.Client, parents: Sequence[str], tree: str, mensaje: str) -> str:
    resp = _check(
        client.post(
            _url("git", "commits"),
            headers=_headers(),
            json={
                "message": mensaje,
                "tree": tree,
                "parents": list(parents),
                "author": {"name": COMMIT_AUTHOR_NAME, "email": COMMIT_AUTHOR_EMAIL},
                "committer": {"name": COMMIT_AUTHOR_NAME, "email": COMMIT_AUTHOR_EMAIL},
            },
        ),
        "POST commit",
    )
    return resp.json()["sha"]


def actualizar_ref(client: httpx.Client, sha: str) -> None:
    _check(
        client.patch(
            _url("git", "refs", "heads", GITHUB_REPO_BRANCH),
            headers=_headers(),
            json={"sha": sha, "force": False},
        ),
        "PATCH ref",
    )


def leer_archivo(ruta: str) -> Optional[Tuple[Optional[int], Iterator[bytes]]]:
    """Abre un archivo del repo en modo raw (sin base64, sin limite de 1MB).

    Devuelve `None` si no hay ningun archivo en `ruta`; si existe, devuelve
    `(content_length, generador)`, donde `content_length` es None si GitHub no
    lo manda. El generador aborta si el contenido pasa MAX_UPLOAD_BYTES.
    """
    url = _url("contents", quote(ruta, safe="/"))
    headers = _headers(accept="application/vnd.github.raw")
    client = _client()
    resp = client.send(client.build_request("GET", url, headers=headers), stream=True)
    if resp.status_code == 404:
        resp.close()
        return None
    if resp.status_code >= 400:
        cuerpo = resp.read()
        request = resp.request
        resp.close()
        raise _mapear_response(httpx.Response(resp.status_code, content=cuerpo, request=request), detalle=f"GET contents {ruta}")

    content_type = resp.headers.get("content-type", "").lower()
    if content_type.startswith("application/json"):
        LOGGER.warning("contents %s devolvio JSON en vez de bytes (directorio o no servible en crudo)", ruta)
        resp.close()
        return None

    def _generador() -> Iterator[bytes]:
        try:
            total = 0
            for chunk in resp.iter_bytes(CHUNK_SIZE):
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    LOGGER.error("El archivo %s supera MAX_UPLOAD_BYTES (%d); se corta el stream", ruta, MAX_UPLOAD_BYTES)
                    break
                yield chunk
        finally:
            resp.close()

    largo = resp.headers.get("content-length")
    return (int(largo) if largo and largo.isdigit() else None), _generador()


def listar_paths() -> List[str]:
    """Paths de todos los archivos del repo. Util para diagnostico."""
    with _client() as client:
        commit_sha = obtener_sha_de_rama(client)
        entradas = obtener_arbol_recursivo(client, commit_sha)["entradas"]
        return sorted(p for p, tipo in entradas.items() if tipo == "blob")


def escribir_paths(entradas: Sequence[Dict], mensaje: str) -> str:
    """Sube N archivos en **un solo commit**.

    `entradas` es una secuencia de `{"path": str, "content": bytes}`. Resuelve
    rama -> arbol -> blobs -> arbol -> commit -> ref, siempre en serie: GitHub
    documenta que escrituras concurrentes entran en conflicto.

    Las carpetas no hace falta crearlas: en git no existen como objetos, y la
    Git Data API las arma sola a partir del path del blob. Por eso la unica
    colision posible es un **archivo** que ya ocupe el path exacto, o un archivo
    que este en el medio de una carpeta que hay que crear.
    """
    if not entradas:
        raise ValueError("no hay archivos para escribir")
    vistos = set()
    for entrada in entradas:
        if entrada["path"] in vistos:
            raise ValueError(f"el path '{entrada['path']}' viene repetido en la misma subida")
        vistos.add(entrada["path"])

    with _client() as client:
        commit_sha = obtener_sha_de_rama(client)
        arbol = obtener_arbol_recursivo(client, commit_sha)
        blobs = {p for p, tipo in arbol["entradas"].items() if tipo == "blob"}

        existentes = sorted(p for p in vistos if p in blobs)
        if existentes:
            raise HTTPException(
                status_code=409,
                detail={"error": "Conflict", "message": f"ya existe un archivo en: {', '.join(existentes)}"},
            )

        bloqueos = set()
        for ruta in vistos:
            partes = ruta.split("/")
            for i in range(1, len(partes)):
                prefijo = "/".join(partes[:i])
                if prefijo in blobs:
                    bloqueos.add(prefijo)
        if bloqueos:
            raise HTTPException(
                status_code=409,
                detail={"error": "Conflict", "message": f"ya hay un archivo donde va una carpeta: {', '.join(sorted(bloqueos))}"},
            )

        nodos = []
        for entrada in entradas:
            blob_sha = crear_blob(client, entrada["content"])
            nodos.append({"path": entrada["path"], "mode": "100644", "type": "blob", "sha": blob_sha})

        tree_sha = crear_arbol(client, arbol["sha"], nodos)
        nuevo_commit = crear_commit(client, [commit_sha], tree_sha, mensaje)
        actualizar_ref(client, nuevo_commit)
        return nuevo_commit
