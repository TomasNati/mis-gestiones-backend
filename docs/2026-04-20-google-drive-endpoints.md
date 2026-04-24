# Google Drive Endpoints — Implementation Plan

> **Status:** DRAFT
> **Date:** 2026-04-20 (updated 2026-04-22)
> **Related:** `mis-gestiones-mobile/docs/google-drive-comprobantes.md`

## Specification

**Problem:** The mobile app and web app need to browse, fetch, and store payment receipts ("comprobantes") that live in a Google Drive folder. The mobile-side design proposes a backend proxy using a service account, but no endpoints exist yet in this FastAPI backend. The mobile doc scoped upload out of v1 — this plan expands the scope to include it for both clients.

**Goal:** Three endpoints on the existing Vercel + FastAPI service so both the mobile and web apps can:

- **List** files in the configured Drive folder (optional substring filter).
- **Download** a file by ID, streamed through the backend.
- **Upload** a file to the folder, with a query-param toggle for overwrite behavior when a file with the same name already exists.

Neither client (mobile nor web) talks to Google directly — credentials stay server-side on Vercel.

**Scope:**

In scope:

- Single hard-coded folder via `GOOGLE_DRIVE_FOLDER_ID` (matches the mobile design).
- Service-account auth via `GOOGLE_SA_CLIENT_EMAIL` + `GOOGLE_SA_PRIVATE_KEY`.
- Folder-membership check on download to prevent arbitrary-file reads if the SA is ever shared into another folder.
- Name-collision handling on upload via `?overwrite=true|false`.
- Consistent error shape (`{ "error": "...", "message": "..." }`).
- **Shared-secret header (`X-API-Key` against `BACKEND_SHARED_SECRET`) required on every Drive endpoint** — list, download, and upload alike. See D6.
- **Hard max upload size**, enforced server-side before any Drive call. Configurable via `MAX_UPLOAD_BYTES` env var (default 4,000,000 bytes ≈ 3.8 MB, safely under Vercel's ceiling once multipart overhead is counted). See D7.

Out of scope:

- Multi-folder / per-user access (single-user app).
- Auth on the existing (non-Drive) endpoints — their behavior is unchanged by this plan.
- Linking Drive files to `Vencimiento` records (deferred per mobile doc).
- Caching Drive responses.
- Resumable / chunked uploads — the size cap (D7) removes the need for both mobile and web clients.
- Downloading native Google file types (Docs / Sheets / Slides). Those require `files.export` with a target MIME type, not `alt=media`. The receipts folder should only hold PDFs/JPGs/PNGs; if a Google-native file ever slips in, the download endpoint returns 415 with a clear message.
- Client-specific behavior differences — both mobile and web use the same endpoints with identical semantics.

**Success Criteria:**

- [ ] `GET /api/drive/files` returns files in the configured folder with `id, name, mimeType, size, modifiedTime`, sorted by `modifiedTime desc`.
- [ ] `GET /api/drive/files?q=luz` filters by name substring (server-side).
- [ ] `GET /api/drive/files/{id}/download` streams the file bytes with correct `Content-Type` and `Content-Disposition`, and returns 404 if the file is not in the configured folder.
- [ ] `POST /api/drive/files?overwrite=false` with a multipart body creates a new file; returns 409 if a file with the same name already exists.
- [ ] `POST /api/drive/files?overwrite=true` updates the content of the existing file (same Drive ID) or creates it if not present.
- [ ] Drive API errors (403, 404, 5xx) map to appropriate HTTP statuses with the standard error shape.
- [ ] `q` and filename values containing `'` or `\` are safely escaped in Drive's query language.
- [ ] `modifiedTime` is returned as a timezone-aware ISO-8601 string (RFC-3339 `Z`).
- [ ] Requests to **any** Drive endpoint without a valid `X-API-Key` header return 401 before any Drive call is made.
- [ ] Uploads larger than `MAX_UPLOAD_BYTES` return 413 with the standard error shape, before any Drive call is made.
- [ ] README documents the required env vars and the one-time GCP setup.

## Key Decisions & Rationale

### D1 — Python client library

Use `google-api-python-client` + `google-auth` (not `googleapis`, which is the Node package referenced in the mobile design doc). These are the official Python SDKs and fit this backend's runtime.

### D2 — Overwrite semantics

When `overwrite=true` and a file with the same name exists:

- Call `files.update(fileId=..., media_body=...)` — this **preserves the Drive ID**, so any stored references, share links, and revision history remain valid.

When `overwrite=false` and a file with the same name exists:

- Return **409 Conflict** with `{ "error": "Conflict", "message": "a file named '<name>' already exists; pass overwrite=true to replace it" }`.

When no file with that name exists (either value of `overwrite`):

- Call `files.create(media_body=...)` — create a new file in the folder.

**Ambiguity:** Drive allows multiple files with the same name in one folder. If >1 match is found during an overwrite check, return **409** with a message asking the caller to resolve manually. We do not pick one arbitrarily. This keeps the behavior deterministic.

### D3 — Folder scope

All three endpoints operate **only** on `GOOGLE_DRIVE_FOLDER_ID`, which lives in the service account's **My Drive** (confirmed — not a Shared Drive). Upload targets this folder; list filters by `'<folderId>' in parents`; download confirms folder membership via a scoped `files.list(q="'<folderId>' in parents and ...")` lookup (more robust than inspecting `parents` on the metadata, because of shortcuts and future Shared Drive moves).

### D4 — Drive query escaping

Drive's query language is string-based; unescaped `'` in user input would break the query or allow injection (e.g., `q = "luz' and ..."`). Every user-provided value in a query string (`?q=`, filename for existence checks) MUST go through a single helper that escapes `\` → `\\` and `'` → `\'`.

### D5 — Streaming (sync route)

Use `fastapi.responses.StreamingResponse` for download so large files don't get buffered in memory. The Drive client's `MediaIoBaseDownload` is **synchronous and blocking**, so the download route must be declared `def`, not `async def` — otherwise every chunk fetch blocks the event loop. (Alternative: `run_in_threadpool` per chunk, but `def` is simpler and adequate for this workload.) The generator must tolerate client disconnects: rely on standard generator-close semantics and stop iterating when the response is cancelled.

### D6 — Auth on every Drive endpoint

All three endpoints (list, download, upload) require an `X-API-Key` header, validated against `BACKEND_SHARED_SECRET` (env var) via `hmac.compare_digest`. Missing or mismatched → 401 with the standard error body, rejected before any Drive call. Implemented as a single FastAPI dependency (`Depends(require_api_key)`) applied to every `/api/drive/*` route — not per-route, so it is impossible to forget.

This differs from the rest of the service (which has no auth), but Drive access is categorically different: the SA-owned folder contains personal receipts, and the endpoints both read private content and (on upload) burn quota / store attacker-controlled bytes that the backend would later serve. The shared-secret approach is ~10 lines and closes the realistic abuse vectors without introducing an auth framework.

Both the mobile app and web app must include the `X-API-Key` header on every Drive request. The web client should store the secret securely (environment variable at build time, not exposed in browser code).

### D7 — Hard upload size limit

`MAX_UPLOAD_BYTES` env var (default 4,000,000 bytes ≈ 3.8 MB) caps uploads. The limit is enforced **before** the file reaches Drive:

1. If the request has `Content-Length` and it exceeds the limit → 413 immediately.
2. Otherwise, read the `UploadFile` into a `BytesIO` while counting bytes and abort with 413 as soon as the running total passes the limit. Do not buffer the whole stream first and check afterwards — a malicious client could still exhaust `/tmp`.
3. Pass the already-buffered bytes to `files.create` / `files.update` via `MediaIoBaseUpload`.

Chosen over Vercel's nominal 4.5 MB because multipart encoding overhead (~3–5%) and Vercel's own safety margin make ~4 MB the realistic ceiling. Configurable via env var in case tuning is needed.

**Client implications:** The mobile app must compress/resize photos before upload (raw phone photos frequently exceed this). The web app should validate file size client-side before upload and show a clear error if the user selects a file exceeding the limit. Both clients will receive a 413 response with the exact limit if they exceed it.

## Constraints

- **Vercel body-size ceiling.** Serverless Python functions on Vercel cap request bodies at ~4.5 MB nominally, but the practical ceiling is lower once multipart encoding overhead (~3–5%) and `/tmp` spooling are accounted for. Above the ceiling, Vercel rejects the request before our code runs. The app-level cap (D7) sits below this on purpose so **we** reject cleanly with 413 instead of leaving the client with an opaque Vercel error.
- **Folder lives in My Drive** (confirmed). `supportsAllDrives=True` is still passed on every Drive API call as a cheap hedge against a future move to a Shared Drive, but the plan does not rely on Shared Drive semantics.
- **Cold starts.** Building the Drive client on every request is acceptable for a low-traffic, single-user app. Do not introduce a module-level singleton unless profiling shows it matters.
- **Private key in env var.** `GOOGLE_SA_PRIVATE_KEY` may be pasted with literal `\n` or with real newlines depending on who set it. Use `key.replace("\\n", "\n")` — idempotent either way.
- **MIME type on upload.** React Native / Expo multipart bodies and web browser uploads often arrive with `Content-Type: application/octet-stream` or no type at all. Fall back to `mimetypes.guess_type(filename)` when `file.content_type` is missing or generic; if that also fails, store as `application/octet-stream` — Drive accepts it. This handles both mobile and web uploads uniformly.
- **Upload race.** The `find_by_name` → `create` / `update` sequence is non-atomic. Two concurrent uploads of the same filename with `overwrite=false` could both pass the existence check and both create files. Accepted for a single-user app (whether the races come from mobile, web, or both); documented rather than engineered around.
- **CORS.** The existing FastAPI app already has CORS configured (verify in `main.py`). Ensure the allowed origins include the web app's domain, and that `X-API-Key` is in `allow_headers` so the browser can send it. If not already configured, this is a prerequisite before web client integration.

## Context Loading

Before implementation, an agent should read:

- `main.py` — FastAPI app, **CORS config** (must allow web app origin and `X-API-Key` header), existing endpoint patterns and error-handling shape.
- `models.py` — Pydantic response-model conventions (`class Config: from_attributes = True`).
- `db.py` — module-level singleton pattern (`database = Database()`) to decide whether Drive should mirror it.
- `requirements.txt` — to confirm current deps before adding new ones.
- `mis-gestiones-mobile/docs/google-drive-comprobantes.md` — upstream design decisions (folder ID scoping, error shape, streaming expectations).

**CORS verification:** Confirm that `main.py`'s CORS middleware includes:

- Web app origin in `allow_origins` (or uses `["*"]` for development).
- `"X-API-Key"` in `allow_headers` so the web browser can send the auth header.
- `expose_headers=["Content-Disposition"]` so the web client can read the download filename.
  If these are missing, add them before implementing the Drive endpoints.

## One-time GCP setup (server-side)

This comprehensive guide walks through setting up Google Cloud Platform and Google Drive to enable the backend to securely access a Drive folder via a service account.

### Prerequisites

- A Google account with access to Google Cloud Console (console.cloud.google.com)
- A Google Drive folder where you want to store receipts/comprobantes
- Access to create and configure GCP projects (or permissions in an existing project)

### Step 1: Create or select a GCP Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top of the page
3. Either:
   - **Create new project:** Click "New Project", give it a name (e.g., `mis-gestiones-backend`), and click "Create"
   - **Use existing project:** Select your existing project from the list
4. Wait for the project to be created (may take a few seconds)
5. Ensure the correct project is selected in the dropdown

### Step 2: Enable the Google Drive API

1. In the Google Cloud Console, go to **APIs & Services → Library** (or use the search bar and type "API Library")
2. In the search box, type `Google Drive API`
3. Click on **Google Drive API** from the results
4. Click the **Enable** button
5. Wait for the API to be enabled (you'll see a dashboard page once complete)

### Step 3: Create a Service Account

A service account is a special type of Google account that represents your application rather than an individual user.

1. In the Google Cloud Console, navigate to **IAM & Admin → Service Accounts**
   - URL: `https://console.cloud.google.com/iam-admin/serviceaccounts`
2. Click **+ Create Service Account** at the top
3. Fill in the service account details:
   - **Service account name:** `mis-gestiones-drive-proxy` (or your preferred name)
   - **Service account ID:** Will auto-populate (e.g., `mis-gestiones-drive-proxy`)
   - **Description:** (optional) "Service account for mis-gestiones backend to access Drive folder with receipts"
4. Click **Create and Continue**
5. **Grant this service account access to project (optional):**
   - You can skip this step (click "Continue") - we'll grant access directly to the Drive folder instead
6. **Grant users access to this service account (optional):**
   - Skip this step (click "Done")
7. You should now see your service account in the list

### Step 4: Create and Download Service Account Key

1. In the Service Accounts list, click on the service account you just created
2. Go to the **Keys** tab
3. Click **Add Key → Create new key**
4. Select **JSON** as the key type
5. Click **Create**
6. A JSON file will automatically download to your computer (e.g., `mis-gestiones-backend-abc123def456.json`)
7. **IMPORTANT:** Store this file securely - it contains credentials that grant access to your Drive folder. Never commit it to source control.

### Step 5: Extract Values from the JSON Key

Open the downloaded JSON file. It will look like this:

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg...\n-----END PRIVATE KEY-----\n",
  "client_email": "mis-gestiones-drive-proxy@your-project.iam.gserviceaccount.com",
  "client_id": "123456789...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  ...
}
```

You need two values:
- **`client_email`** - Copy this entire email address
- **`private_key`** - Copy this entire string (including the BEGIN/END markers and `\n` characters)

### Step 6: Prepare Your Google Drive Folder

1. Open [Google Drive](https://drive.google.com/)
2. Navigate to (or create) the folder where you want to store receipts
3. **Get the Folder ID:**
   - Open the folder
   - Look at the URL in your browser's address bar
   - The URL will look like: `https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz`
   - Copy the ID after `/folders/` (e.g., `1AbCdEfGhIjKlMnOpQrStUvWxYz`)
   - This is your `GOOGLE_DRIVE_FOLDER_ID`

### Step 7: Share the Folder with the Service Account

1. In Google Drive, right-click on your target folder
2. Click **Share**
3. In the "Add people and groups" field, paste the **`client_email`** from Step 5
   - It will look like: `mis-gestiones-drive-proxy@your-project.iam.gserviceaccount.com`
4. Set the permission level:
   - **Editor** - Required if you want to upload files (recommended for this project)
   - **Viewer** - Only if you need read-only access
5. **Uncheck** "Notify people" (the service account doesn't need email notifications)
6. Click **Share** or **Send**
7. The service account now has access to this folder

### Step 8: Generate a Shared Secret for API Authentication

The backend requires an API key that clients must send in the `X-API-Key` header to access Drive endpoints.

Run this command to generate a secure random secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Or in PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Save the output - this is your `BACKEND_SHARED_SECRET`.

### Step 9: Configure Environment Variables

#### For Local Development (.env file):

Create a `.env` file in your project root (or copy `.env.example` and fill it in):

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/misgestiones

# Google Drive API
GOOGLE_SA_CLIENT_EMAIL=mis-gestiones-drive-proxy@your-project.iam.gserviceaccount.com
GOOGLE_SA_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...\n-----END PRIVATE KEY-----\n
GOOGLE_DRIVE_FOLDER_ID=1AbCdEfGhIjKlMnOpQrStUvWxYz

# API Security
BACKEND_SHARED_SECRET=your-generated-secret-from-step-8

# Optional: Override default max upload size (default: 4000000 bytes = ~3.8 MB)
MAX_UPLOAD_BYTES=4000000
```

**Important:** Keep the literal `\n` characters in the `GOOGLE_SA_PRIVATE_KEY` value - the backend code will convert them to real newlines automatically.

#### For Vercel Deployment:

1. Go to your Vercel project dashboard
2. Navigate to **Settings → Environment Variables**
3. Add each variable:
   - `GOOGLE_SA_CLIENT_EMAIL` → Paste the service account email
   - `GOOGLE_SA_PRIVATE_KEY` → Paste the entire private key (with `\n` characters)
   - `GOOGLE_DRIVE_FOLDER_ID` → Paste the folder ID
   - `BACKEND_SHARED_SECRET` → Paste the generated secret
   - `MAX_UPLOAD_BYTES` → (optional) Enter custom value or leave unset for default
4. Select which environments need these variables (Production, Preview, Development)
5. Save and redeploy your application

#### For Other Platforms:

- **Heroku:** Use `heroku config:set VARIABLE_NAME="value"`
- **Azure:** Configure in App Settings → Application settings
- **AWS Lambda:** Set environment variables in the Lambda function configuration

### Step 10: Verify the Setup

1. Start your local development server:
   ```bash
   uvicorn main:app --reload --port 5001
   ```

2. Test the connection (replace `your-secret` with your actual `BACKEND_SHARED_SECRET`):
   ```bash
   curl -H "X-API-Key: your-secret" http://localhost:5001/api/drive/files
   ```

3. If successful, you should see a JSON response with `{"files": [...]}`

4. If you get errors:
   - **401 Unauthorized:** Check your `BACKEND_SHARED_SECRET` matches
   - **403 Forbidden:** Verify the service account has access to the folder
   - **404 Not Found:** Check your `GOOGLE_DRIVE_FOLDER_ID` is correct
   - **500 Internal Server Error:** Check your `GOOGLE_SA_CLIENT_EMAIL` and `GOOGLE_SA_PRIVATE_KEY` are correct

### Security Best Practices

- ✅ **Never commit** the service account JSON key or `.env` file to source control
- ✅ Add `.env` and `*service-account*.json` to your `.gitignore` file
- ✅ Use platform-specific secret storage (Vercel Environment Variables, Azure Key Vault, AWS Secrets Manager)
- ✅ Limit the service account's permissions to only what's needed (folder-level Editor access)
- ✅ **Do not** grant the service account project-level roles like Owner or Editor
- ✅ Rotate keys immediately if you suspect exposure
- ✅ Use different service accounts for different environments (dev/staging/production) if needed
- ✅ Store the `BACKEND_SHARED_SECRET` securely and never expose it in client-side code
- ✅ Monitor service account usage in GCP Console → IAM & Admin → Service Accounts → View activity

### Troubleshooting Common Issues

**Issue:** "The caller does not have permission"
- **Solution:** Ensure the service account email is shared with the folder with Editor permissions

**Issue:** "Invalid authentication credentials"
- **Solution:** Verify the `GOOGLE_SA_PRIVATE_KEY` is correct and includes BEGIN/END markers

**Issue:** "File not found" when listing files
- **Solution:** Double-check the `GOOGLE_DRIVE_FOLDER_ID` is correct (from the folder URL)

**Issue:** "Module not found" errors
- **Solution:** Run `pip install -r requirements.txt` to install dependencies

**Issue:** Vercel deployment succeeds but Drive endpoints fail
- **Solution:** Verify all environment variables are set in Vercel's Environment Variables settings

## Tasks

### Drive integration

Single subsystem. Keep tasks sequential — each depends on the previous.

---

#### Task 1: Add Drive service module

**Context:** `db.py` (module pattern), `structure.py` (custom-exceptions pattern), `requirements.txt`.

**Steps:**

1. [ ] Add to `requirements.txt`: `google-api-python-client`, `google-auth`, `python-multipart` (FastAPI's `UploadFile` / `File` needs it; it is not currently installed).
2. [ ] Create `drive.py` that owns all Google Drive concerns, including error mapping (so `main.py` never imports `googleapiclient`). Expose:
   - Module-level `GOOGLE_DRIVE_FOLDER_ID = os.environ["GOOGLE_DRIVE_FOLDER_ID"]` and `MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", "4000000"))` (read once, here — not in `main.py`).
   - `_build_service()` — loads `GOOGLE_SA_CLIENT_EMAIL` and `GOOGLE_SA_PRIVATE_KEY` from env, applies `key.replace("\\n", "\n")` (idempotent), returns a Drive v3 `Resource`.
   - `_escape(value: str) -> str` — escapes `\` and `'` for Drive query strings.
   - `list_files(name_query: Optional[str]) -> list[dict]` — `files.list(q="'<folderId>' in parents and trashed = false"` [+ `and name contains '<escaped>'`]`, orderBy="modifiedTime desc", supportsAllDrives=True, includeItemsFromAllDrives=True, fields="files(id,name,mimeType,size,modifiedTime)")`.
   - `get_file_in_folder(file_id: str) -> dict | None` — runs `files.list(q="'<folderId>' in parents and trashed = false and <fileId-match>", ...)` to both fetch metadata AND confirm membership in one call. Returns `None` if not in the folder. Replaces the earlier `parents`-based check (more reliable across My Drive / Shared Drive contexts).
   - `download_stream(file_id: str) -> Iterator[bytes]` — yields chunks via `MediaIoBaseDownload`. **Synchronous generator.** Stops when the caller closes it.
   - `find_by_name(name: str) -> list[dict]` — exact-name match in the folder, **must include `trashed = false`** in the query so soft-deleted duplicates don't produce spurious 409s.
   - `create_file(name: str, mime_type: str, data: BinaryIO) -> dict` — `files.create(..., supportsAllDrives=True)` with parent = folder ID.
   - `update_file_content(file_id: str, mime_type: str, data: BinaryIO) -> dict` — `files.update(..., supportsAllDrives=True)`, preserves the Drive ID.
   - `map_http_error(e: HttpError) -> HTTPException` — translates Drive `HttpError` to a `fastapi.HTTPException` using the project's standard error shape. Logs the error once at the boundary (status, reason, file_id if known); caller does not log again.
3. [ ] Define custom exceptions in `drive.py`:
   - `DriveFileNotInFolderError`
   - `DriveFileNameConflictError`
   - `DriveAmbiguousNameError` (more than one match when resolving overwrite).
4. [ ] Helper `is_google_native(mime_type: str) -> bool` to detect Docs/Sheets/Slides MIME types (`application/vnd.google-apps.*`). Used by the download route to 415 instead of producing a broken stream.

**Verify:**

- `pip install -r requirements.txt` succeeds.
- `python -c "import drive; print(drive._escape(\"a'b\"))"` prints `a\'b`.
- With env vars set locally: `python -c "import drive; drive._build_service().files().list(pageSize=1).execute(); print('ok')"` prints `ok`. If env vars are unset, skip this step and note it.

---

#### Task 2: Add Pydantic response models

**Context:** `models.py`.

**Steps:**

1. [ ] Add to `models.py`:
   - `DriveFileOut` — fields `id: str`, `name: str`, `mimeType: str`, `size: Optional[int]`, `modifiedTime: datetime.datetime`.
   - `DriveFileListOut` — `{ "files": list[DriveFileOut] }` (matches the universal API list-wrapper rule).
   - `DriveUploadOut` — `{ "file": DriveFileOut, "created": bool }` where `created=false` means the existing file was overwritten.
2. [ ] Confirm `datetime.datetime` parsing of Drive's ISO-8601 timestamps works with Pydantic defaults.

**Verify:** `python -c "from models import DriveFileListOut; print(DriveFileListOut(files=[]).model_dump())"` prints `{'files': []}`.

---

#### Task 3: Wire FastAPI endpoints

**Context:** `main.py`, `drive.py`, `models.py`.

**Steps:**

1. [ ] Add an API-key dependency in `main.py` (or a small `auth.py`): `def require_api_key(x_api_key: str = Header(...)) -> None` — compares against `BACKEND_SHARED_SECRET` via `hmac.compare_digest`, raises 401 with the standard error shape on mismatch or missing header. Apply via `Depends(require_api_key)` on **every** `/api/drive/*` route (including list and download).

2. [ ] `GET /api/drive/files` (`async def`):
   - Optional query param `q: Optional[str] = None`.
   - Calls `drive.list_files(q)` inside a `try` that routes `HttpError` through `drive.map_http_error`.
   - Returns `DriveFileListOut`.
   - Tag: `"Drive"`.

3. [ ] `GET /api/drive/files/{id}/download` — **declare `def`, not `async def`** (see D5):
   - Call `drive.get_file_in_folder(id)`. If `None` → `HTTPException(404, "file is not in the allowed folder")` (same message for both "doesn't exist" and "exists elsewhere" so we don't leak existence).
   - If `drive.is_google_native(metadata["mimeType"])` → `HTTPException(415, "google-native file types cannot be downloaded directly")`.
   - Return `StreamingResponse(drive.download_stream(id), media_type=metadata["mimeType"])` with header `Content-Disposition: attachment; filename="<name>"` (filename must be quoted/escaped — use `email.utils` or `urllib.parse.quote` for non-ASCII names).
   - `HttpError` → `drive.map_http_error`.
   - **Web client note:** Browser downloads will trigger automatically due to `Content-Disposition: attachment`. The web app can also use `fetch()` and read the blob if it wants to preview PDFs inline.

4. [ ] `POST /api/drive/files`:
   - Accepts `file: UploadFile = File(...)` and `overwrite: bool = Query(False)`.
   - **Size check (before Drive)**:
     - If `request.headers.get("content-length")` is present and > `drive.MAX_UPLOAD_BYTES` → 413 immediately, with `{ "error": "Payload Too Large", "message": "upload exceeds <N> bytes" }`.
     - Otherwise, read `file.file` into a `BytesIO` in chunks (e.g., 256 KB), tracking the running total. As soon as the total exceeds `MAX_UPLOAD_BYTES`, abort with 413. Only hand the buffered bytes to Drive after the full read completes under the limit.
   - Resolve MIME type: use `file.content_type` if non-empty and not `application/octet-stream`; else `mimetypes.guess_type(file.filename)[0]`; else `application/octet-stream`.
   - Call `drive.find_by_name(file.filename)`:
     - 0 matches → `create_file(...)`, respond `DriveUploadOut(file=..., created=True)`, status 201.
     - 1 match, `overwrite=true` → `update_file_content(existing["id"], ...)`, respond `DriveUploadOut(file=..., created=False)`, status 200.
     - 1 match, `overwrite=false` → `HTTPException(409, "a file named '<name>' already exists; pass overwrite=true to replace it")`.
     - > 1 matches → `HTTPException(409, "multiple files named '<name>' exist in the folder; resolve manually before uploading")`.
   - Tag: `"Drive"`.

5. [ ] Error mapping lives in `drive.py` (see Task 1). `main.py` catches `HttpError` raised by `drive.*` calls and re-raises via `drive.map_http_error(e)`. No logging in `main.py` — the mapper logs once at the boundary.

**Verify:**

- `uvicorn main:app --reload --port 5001`
- `curl localhost:5001/api/drive/files` (no header) → 401
- `curl localhost:5001/api/drive/files/<any-id>/download` (no header) → 401
- `curl -F "file=@./test.pdf" localhost:5001/api/drive/files` (no header) → 401
- With `-H "X-API-Key: $BACKEND_SHARED_SECRET"`:
  - `GET /api/drive/files` → 200 + `{ "files": [...] }`
  - `GET /api/drive/files/<bad-id>/download` → 404 with standard error shape
  - `POST /api/drive/files?overwrite=false` with a fresh filename → 201
  - Same POST again → 409
  - Same with `?overwrite=true` → 200, `created: false`
  - POST a file larger than `MAX_UPLOAD_BYTES` → 413, and confirm no object was created in Drive
- **CORS verification:** From the web app's origin, verify that:
  - Preflight OPTIONS requests succeed for all three endpoints
  - `X-API-Key` header is accepted
  - `Content-Disposition` header is readable on download responses

---

#### Task 4: Documentation

**Context:** `README.md`, this plan.

**Steps:**

1. [ ] Update `README.md` with:
   - New env vars: `GOOGLE_SA_CLIENT_EMAIL`, `GOOGLE_SA_PRIVATE_KEY`, `GOOGLE_DRIVE_FOLDER_ID`, `BACKEND_SHARED_SECRET`, `MAX_UPLOAD_BYTES` (optional, default 4,000,000).
   - Pointer to the one-time GCP setup in `mis-gestiones-mobile/docs/google-drive-comprobantes.md` (§ "One-time setup").
   - Note that all `/api/drive/*` endpoints require `X-API-Key`.
   - Note the upload size cap (`MAX_UPLOAD_BYTES`) and that it exists because Vercel's body-size ceiling is lower in practice than advertised.
   - Note that only non-Google-native file types can be downloaded (no Docs/Sheets/Slides).
   - **Client notes:** Both mobile and web clients must include `X-API-Key` on every request. The web client should store the secret in an environment variable at build time, not in browser code. Both clients should validate file sizes client-side before upload (mobile: compress photos; web: show clear error for oversized files).
2. [ ] Mark this plan's status as `IN_PROGRESS` when execution starts, `COMPLETED` once deployed.

**Verify:** Open `README.md` and confirm all five env vars appear along with the auth + size-cap notes.

## Open Questions

1. **Filename-based overwrite vs ID-based update.** The plan uses filename for overwrite because both mobile and web clients send a file with a name, not a Drive ID. If "update this specific file" ever becomes a use case (e.g., re-upload of a receipt tied to a vencimiento), that is a separate `PUT /api/drive/files/{id}` endpoint — deferred.
2. **Client-side size handling.** With `MAX_UPLOAD_BYTES` defaulting to ~3.8 MB:
   - **Mobile:** Must compress/resize photos before upload (raw phone photos frequently exceed this).
   - **Web:** Should validate file size client-side and show a clear error message before attempting upload.
   - Both are client-side concerns; this plan just ensures the backend fails cleanly with 413 when either client sends too much.

## Revision History

- **2026-04-22 rev 3** — Expanded scope to support **web app as a client** alongside mobile. Added CORS requirements (web origin, `X-API-Key` in `allow_headers`, `Content-Disposition` in `expose_headers`). Clarified that both clients use identical endpoints with no client-specific behavior. Updated client-side implications for size limits and auth header handling.
- **2026-04-20 rev 2** — Owner decisions: folder confirmed in **My Drive** (dropped Shared Drive tradeoffs); **all** Drive endpoints now require `X-API-Key` (not just upload); added a hard **`MAX_UPLOAD_BYTES` cap** enforced before any Drive call.

## Review Notes

Devil's-advocate review (2026-04-20) caught:

- **Missing `python-multipart` dependency** — FastAPI `UploadFile` would have 500'd on first upload. Added to Task 1.
- **Folder-membership check via `parents` is brittle** under Shared Drives and shortcuts. Replaced with a `files.list` parent-scoped lookup in `get_file_in_folder`.
- **`find_by_name` did not filter `trashed = false`** — would false-positive on soft-deleted duplicates. Fixed.
- **`MediaIoBaseDownload` is sync/blocking** — would stall the event loop inside an `async def` route. Download route is now explicitly `def`.
- **Vercel 4.5 MB limit was overstated as a guarantee.** Plan now says "empirically verify" and records the real number in the README.
- **No auth on upload was a real abuse vector**, not just a future concern. Added `X-API-Key` / `BACKEND_SHARED_SECRET` as in-scope for v1.
- **Error mapper belonged in `drive.py`**, not `main.py`, so the route layer never imports `googleapiclient`. Moved.
- **MIME fallback** for Expo multipart (`application/octet-stream` or missing type). Added `mimetypes.guess_type` fallback.
- **Google-native file types** (Docs/Sheets/Slides) can't be downloaded via `alt=media`. Added 415 response path + explicit out-of-scope note.
- Env-var read for `GOOGLE_DRIVE_FOLDER_ID` now lives only in `drive.py`, not `main.py`.
