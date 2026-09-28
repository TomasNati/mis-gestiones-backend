# Comprobantes de pago — endpoints

> **Status:** IMPLEMENTADO (upload / download por path). El resto de la feature
> (tabla `finanzas_comprobante_pago`, listado por vencimiento, rename, delete)
> sigue pendiente.
>
> **Diseño y plan:** `mis-gestiones/docs/comprobantes_pago/Design.md` y `Plan.md`.
> Este documento describe solo lo que hay implementado hoy.

## Qué hace

Almacena los comprobantes de pago como archivos en el repo privado
`TomasNati/comprobantes-pago`, y los sirve a través del backend. Los archivos se
guardan en la **rama `main` del repo, versionados con git**: cada subida es un
commit, y el path dentro del repo es la dirección del archivo.

Los dos endpoints son **por path**, no por id de base de datos: no hay tabla
todavía. Cuando exista `finanzas_comprobante_pago`, estos endpoints pasan a ser
la capa de storage y se les agrega el router por `vencimiento_id` del plan.

## Auth

Los tres endpoints requieren el header `X-API-Key` con el valor de
`BACKEND_SHARED_SECRET`. Se valida con `hmac.compare_digest` en
`api/security.py`, como dependencia del router completo, así que no se puede
olvidar en un endpoint nuevo. El token **nunca** sale del backend: ni URLs de
`raw.githubusercontent.com` ni el PAT llegan al cliente.

> Un header `X-API-Key` ausente devuelve **422** (FastAPI no encuentra el
> parámetro requerido), no 401. Es el comportamiento que ya tenía el router de
> Drive y no se cambió. El 401 es para key presente pero incorrecta.

## Variables de entorno

| Variable | Default | Para qué |
|---|---|---|
| `GITHUB_TOKEN` | — | Fine-grained PAT con `Contents: Read and write` **solo** sobre este repo |
| `GITHUB_REPO_OWNER` | — | `TomasNati` |
| `GITHUB_REPO_NAME` | — | `comprobantes-pago` |
| `GITHUB_REPO_BRANCH` | `main` | Rama donde se escribe |
| `GITHUB_COMMIT_AUTHOR_NAME` | `mis-gestiones-backend` | Identidad del commit |
| `GITHUB_COMMIT_AUTHOR_EMAIL` | `...@users.noreply.github.com` | Identidad del commit |
| `MAX_UPLOAD_BYTES` | `2000000` | Tope de tamaño, con tope duro de `4000000` |

### `MAX_UPLOAD_BYTES`

Se resuelve **una sola vez**, al importar `github.py`, no en cada request.

- Default **2.000.000** bytes (2MB) si no está definida, no parsea, o es `<= 0`.
- **Tope duro de 4.000.000** bytes: si se configura algo mayor, se recorta a 4MB
  y se avisa por log. El motivo es que el body de una función de Vercel no
  puede pasar de 4.5MB, así que un valor más alto solo produciría un 413 opaco
  de la plataforma en vez de un 413 limpio nuestro.
- El mismo cap aplica a la **descarga**, porque la descarga también es una
  response de la función.

## Endpoints

### `POST /api/comprobantes`

`multipart/form-data`:

| Campo | Tipo | Descripción |
|---|---|---|
| `path` | string | Carpeta destino dentro del repo, p.ej. `edese/2026/09` |
| `files` | archivos | Uno o más. Se pueden repetir para subir varios |

Todos los archivos del request van en **un solo commit**, resueltos con la
**Git Data API** (`ref → commit → tree → blobs → tree → commit → ref`). Por eso
una subida múltiple es atómica y no N commits con rollback manual.

**No hace falta que la carpeta exista.** En git las carpetas no son objetos: la
Git Data API arma los directorios intermedios sola a partir del path del blob.
Subir a `edese/2026/09` la primera vez crea la carpeta, y las siguientes subidas
a la misma carpeta también funcionan. La única colisión posible es un **archivo**
que ya ocupe el path exacto, o un archivo que esté en el medio de una carpeta a
crear — en ambos casos es `409`, nunca un error de GitHub.

Respuesta `201`:

```json
{
  "commit": "9bdd6a8...",
  "archivos": [
    { "path": "edese/2026/09/comprobante.pdf", "nombre": "comprobante.pdf", "size": 33 }
  ],
  "max_upload_bytes": 2000000
}
```

### `GET /api/comprobantes/descargar?path=<path completo>`

Devuelve los bytes del archivo con `Content-Disposition: attachment` y el
`Content-Type` deducido del nombre. La lectura usa la Contents API con
`Accept: application/vnd.github.raw`, o sea **un request y bytes directos**,
sin base64 y sin el límite de 1MB que tiene la respuesta JSON.

### `GET /api/comprobantes/limites`

Devuelve `max_upload_bytes` (y el repo y la rama configurados) para que la UI
valide el tamaño en el cliente antes de subir, en vez de recibir un 413 seco.

## Errores

Shape uniforme: `{"detail": {"error": "...", "message": "..."}}`.

| Status | Cuándo |
|---|---|
| `400` | `path` vacío, `..` en el path, caracteres no permitidos, path > 1000 chars, archivo vacío, mismo nombre dos veces en un request |
| `401` | `X-API-Key` presente pero incorrecto |
| `404` | No hay archivo en ese path (descarga) |
| `409` | Ya existe un archivo en el path destino, **o** hay un archivo donde va una carpeta. **Rechaza el request completo**, no sube una parte |
| `413` | El body, o algún archivo, pasa `MAX_UPLOAD_BYTES` — en la subida y en la descarga |
| `415` | Extensión fuera de la allowlist (`.pdf`, `.jpg`, `.jpeg`, `.png`, `.heic`) |
| `422` | Falta `path` o `files` en el body (validación de FastAPI) |
| `502` | GitHub no configurado, token rechazado, error de la API de GitHub, o error de transporte (timeout, DNS) |

### Tamaño: cómo se aplica

1. `Content-Length` del request contra el límite → `413` inmediato, sin llegar
   a GitHub.
2. Después, cada archivo se lee en chunks de 256KB contando bytes y abortando
   con `413` en cuanto se excede. No se bufferea el archivo entero para
   checkear después: un cliente hostil igual agotaría la memoria del proceso.

Los paths se validan con `normalizar_path`: se aceptan separadores Windows y
Unix, se descartan barras duplicadas, y se rechazan `..`, segmentos ocultos
(`.algo`), `:` y globbing. Sin esto, un `path` con traversal escribiría fuera
del repo.

## Detalles de implementación que conviene no romper

- **Escrituras siempre en serie.** GitHub documenta que escrituras concurrentes
  entran en conflicto. No paralelizar las escrituras de un mismo request.
- **Todo `raise_for_status()` pasa por `_check`.** Un `raise_for_status()` crudo
  se escapa como `httpx.HTTPStatusError` y FastAPI lo convierte en un 500 con
  stack trace. `_check` lo traduce al status mapeado. Los errores de
  transporte (que no son `HTTPStatusError`) los mapea el router, porque `_check`
  solo ve status.
- **Un JSON en la descarga es un directorio, no un archivo.** GitHub ignora el
  media type `raw` cuando la ruta es un directorio y devuelve el metadata en
  JSON, que trae un `download_url` **con el token del PAT embebido**. Por eso
  `leer_archivo` descarta cualquier respuesta `application/json` y la reporta
  como 404. Este chequeo no es opcional: sin él, `GET /descargar?path=<carpeta>`
  filtra el token.
- **El cap de descarga se chequea con `Content-Length` antes de leer el body**,
  y además el generador corta el stream si el contenido real pasa el límite.
- **La ruta de subida se valida separada del path completo.** Si se armara
  `path + "/" + nombre` con `path` vacío, `normalizar_path` caería a la raíz del
  repo en silencio en lugar de rechazar el request.

## Estado del repo de comprobantes

Los commits los crea el token, no una persona, y el repo no tiene identidad de
git configurada, así que la identidad va explícita en el payload del commit
(`GITHUB_COMMIT_AUTHOR_NAME` / `GITHUB_COMMIT_AUTHOR_EMAIL`).

## Verificación

```bash
uvicorn main:app --reload --port 5001
curl -H "X-API-Key: $BACKEND_SHARED_SECRET" http://localhost:5001/api/comprobantes/limites
```

Matriz de `curl` usada para validar la implementación (subida simple y múltiple,
round-trip de bytes con `cmp`, 409, 413 de subida y de descarga, 404, 415, 400 de
path, 401/422 de auth). Después de las pruebas hay que confirmar que el repo
quedó sin archivos de prueba.
