# Comprobantes de pago — endpoints

> **Status:** upload por `vencimiento_id`, que crea el registro de
> `finanzas_comprobante_pago`; download por path. Listado por vencimiento, rename
> y delete siguen pendientes.
>
> **Diseño y plan:** `mis-gestiones/docs/comprobantes_pago/Design.md` y `Plan.md`.
> Este documento describe solo lo que hay implementado hoy.

## Qué hace

Almacena los comprobantes de pago como archivos en el repo privado
`TomasNati/comprobantes-pago`, y los sirve a través del backend. Los archivos se
guardan en la **rama `main` del repo, versionados con git**: cada subida es un
commit, y el path dentro del repo es la dirección del archivo.

El upload es **por `vencimiento_id`**: valida que el vencimiento exista y tenga
pago registrado, escribe el blob, y crea la fila de `finanzas_comprobante_pago`
que lo apunta. El download sigue siendo **por path**, porque todavía no hay
endpoint que resuelva el `base_path` desde el id.

## Auth

**No hay auth.** Los tres endpoints son públicos, igual que los routers de
`finanzas`, `inversiones` y `cotizaciones`. A tener en cuenta:

- El PAT de GitHub **nunca** sale del backend: ni URLs de
  `raw.githubusercontent.com` ni el token llegan al cliente.
- Lo único que separa "cualquiera que conozca la URL" de los comprobantes de
  pago es el CORS, y el CORS **no es auth**: frena al JS del browser de leer la
  response, no un `curl` directo. Cualquiera que pegue a la URL sube y baja
  comprobantes.
- Quien llega a la URL ya tiene que haber pasado el basic auth de la web app
  (que es del lado de Vercel, no de este backend), pero el backend no lo
  comprueba: es un servicio público detrás de un dominio con contraseña.

> Cuando se quiera volver a cerrar, el lugar es un router-level
> `dependencies=[Depends(require_api_key)]` como el que tenía este router hasta
> ahora, para que no se pueda olvidar en un endpoint nuevo.

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

`multipart/form-data`. Sube **un** comprobante y crea el registro de
`finanzas_comprobante_pago` que lo apunta.

| Campo | Tipo | Descripción |
|---|---|---|
| `vencimiento_id` | string | UUID del vencimiento. Tiene que existir y estar pagado |
| `base_path` | string | Carpeta principal del comprobante, p.ej. `aguas-de-santiago` (viene de `subcategoria.comprobantes_path`) |
| `subpath` | string | Nombre dentro de esa carpeta, p.ej. `2026/09-factura.pdf`. Máximo 256 caracteres (el ancho de la columna) |
| `file` | archivo | El comprobante. Uno solo por request |

El path final dentro del repo es `base_path/subpath`. **El nombre del blob sale
del `subpath`, no del `filename` que manda el cliente**: así el path guardado en
la base y el del repo son siempre el mismo string, sin depender de que el
cliente los mande consistentes.

**Orden de las operaciones, a propósito:** se valida el vencimiento, se escribe
el blob, y recién al final se inserta la fila. Si el commit de git falla no
queda registro; el caso inverso (fila apuntando a un blob inexistente) es el que
se evita.

`base_path` y `subpath` los decide el cliente, que es el contrato de esta tanda.
La validación dura que sí se hace es que **el vencimiento exista y tenga pago
registrado** (`pagoId IS NOT NULL`): no hay comprobante de pago de un
vencimiento sin pagar. Cerrar el path (derivarlo de `comprobantes_path` en vez de
aceptarlo) queda para el endpoint por `vencimiento_id`.

Un commit por request, resuelto con la **Git Data API**
(`ref → commit → tree → blobs → tree → commit → ref`).

**No hace falta que la carpeta exista.** En git las carpetas no son objetos: la
Git Data API arma los directorios intermedios sola a partir del path del blob.
La única colisión posible es un **archivo** que ya ocupe el path exacto, o un
archivo que esté en el medio de una carpeta a crear — en ambos casos es `409`,
nunca un error de GitHub.

Respuesta `201`:

```json
{
  "id": "d9f72348-383a-4356-854d-b678f7c1ef70",
  "commit": "e3cf635...",
  "path": "aguas-de-santiago/2026/09-factura.pdf",
  "nombre": "09-factura.pdf",
  "size": 33,
  "subpath": "2026/09-factura.pdf",
  "max_upload_bytes": 2000000
}
```

`id` es el id de `finanzas_comprobante_pago` recién creado, que es lo que usan
después el rename y el delete.

### `GET /api/comprobantes/descargar?path=<path completo>`

Devuelve los bytes del archivo con `Content-Disposition: attachment` y el
`Content-Type` deducido del nombre. La lectura usa la Contents API con
`Accept: application/vnd.github.raw`, o sea **un request y bytes directos**,
sin base64 y sin el límite de 1MB que tiene la respuesta JSON.

Sigue siendo **por path**, no por id. Cuando se implemente
`GET /api/comprobantes?vencimiento_ids=…` pasa a filtrar por `active` y a
resolver el `base_path` desde la base.

### `GET /api/comprobantes/limites`

Devuelve `max_upload_bytes` (y el repo y la rama configurados) para que la UI
valide el tamaño en el cliente antes de subir, en vez de recibir un 413 seco.

## Errores

Shape uniforme: `{"detail": {"error": "...", "message": "..."}}`.

| Status | Cuándo |
|---|---|
| `400` | `base_path` o `subpath` vacíos, `..` en el path, caracteres no permitidos, path > 1000 chars, `subpath` > 256 chars, `subpath` sin nombre de archivo al final, archivo vacío |
| `404` | No hay archivo en ese path (descarga), **o no existe el `vencimiento_id`** (subida) |
| `409` | Ya existe un archivo en el path destino, hay un archivo donde va una carpeta, **o el vencimiento no tiene pago registrado** |
| `413` | El body, o el archivo, pasa `MAX_UPLOAD_BYTES` — en la subida y en la descarga |
| `415` | Extensión fuera de la allowlist (`.pdf`, `.jpg`, `.jpeg`, `.png`, `.heic`) |
| `422` | Falta `vencimiento_id`, `base_path`, `subpath` o `file` (validación de FastAPI), o `vencimiento_id` no es un UUID |
| `502` | GitHub no configurado, token rechazado, error de la API de GitHub, o error de transporte (timeout, DNS) |

### Tamaño: cómo se aplica

1. `Content-Length` del request contra el límite → `413` inmediato, sin llegar
   a GitHub.
2. Después, el archivo se lee en chunks de 256KB contando bytes y abortando
   con `413` en cuanto se excede. No se bufferea el archivo entero para
   checkear después: un cliente hostil igual agotaría la memoria del proceso.

Los paths se validan con `normalizar_path`: se aceptan separadores Windows y
Unix, se descartan barras duplicadas, y se rechazan `..`, segmentos ocultos
(`.algo`), `:` y globbing. Sin esto, un path con traversal escribiría fuera
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
curl http://localhost:5001/api/comprobantes/limites
```

Matriz de `curl` usada para validar la implementación (subida simple y múltiple,
round-trip de bytes con `cmp`, 409, 413 de subida y de descarga, 404, 415, 400 de
path). Después de las pruebas hay que confirmar que el repo quedó sin archivos de
prueba.
