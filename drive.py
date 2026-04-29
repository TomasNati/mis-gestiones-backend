import os
import io
import logging
import mimetypes
from typing import Optional, Iterator, BinaryIO, List, Dict

from fastapi import HTTPException

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
    from googleapiclient.errors import HttpError
except Exception:  # pragma: no cover - import-time in environments without libs
    service_account = None
    build = None
    MediaIoBaseDownload = None
    MediaIoBaseUpload = None
    HttpError = Exception

LOGGER = logging.getLogger(__name__)

GOOGLE_DRIVE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", "4000000"))


def _build_service():
    if service_account is None:
        raise RuntimeError("google libraries not installed")
    client_email = os.environ["GOOGLE_SA_CLIENT_EMAIL"]
    private_key = os.environ["GOOGLE_SA_PRIVATE_KEY"].replace("\\n", "\n")
    info = {
        "type": "service_account",
        "client_email": client_email,
        "private_key": private_key,
        "token_uri": "https://oauth2.googleapis.com/token",
        "project_id": os.environ.get("GOOGLE_SA_PROJECT_ID", "unknown-project"),
    }
    creds = service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive"])
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return service


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def map_http_error(e: HttpError) -> HTTPException:
    try:
        status_code = e.resp.status if hasattr(e, 'resp') and e.resp is not None else 502
    except Exception:
        status_code = 502
    LOGGER.error("Drive API error %s: %s", status_code, getattr(e, 'content', str(e)))
    if status_code == 404:
        return HTTPException(status_code=404, detail={"error": "Not Found", "message": "resource not found"})
    if status_code == 403:
        return HTTPException(status_code=403, detail={"error": "Forbidden", "message": "permission denied"})
    return HTTPException(status_code=502, detail={"error": "Drive Error", "message": "an error occurred communicating with Google Drive"})


def list_files(name_query: Optional[str] = None, folder_id: Optional[str] = None, created_from: Optional[str] = None, created_to: Optional[str] = None) -> List[Dict]:
    try:
        service = _build_service()
        # If a specific folder_id was provided, list its children; otherwise use the configured root folder
        if folder_id:
            q = f"'{_escape(folder_id)}' in parents and trashed = false"
        else:
            q = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed = false"
        if name_query:
            q += f" and name contains '{_escape(name_query)}'"
        if created_from:
            q += f" and createdTime >= '{_escape(created_from)}'"
        if created_to:
            q += f" and createdTime <= '{_escape(created_to)}'"
        fields = "files(id,name,mimeType,size,modifiedTime,createdTime)"
        resp = service.files().list(q=q, orderBy="modifiedTime desc", pageSize=100, supportsAllDrives=True, includeItemsFromAllDrives=True, fields=fields).execute()
        return resp.get("files", [])
    except HttpError as e:
        raise map_http_error(e)


def get_folder_id_by_path(path: str) -> Optional[str]:
    """Resolve a path (supports both '/' and '\\') relative to GOOGLE_DRIVE_FOLDER_ID to a folder id.
    Returns None if any segment does not exist.
    """
    try:
        service = _build_service()
        # Normalize backslashes to forward slashes so callers can use Windows-style paths like "FOLDER\\sub"
        normalized = path.replace("\\", "/")
        parts = [p for p in normalized.strip("/").split("/") if p]
        parent = GOOGLE_DRIVE_FOLDER_ID
        for part in parts:
            q = f"'{parent}' in parents and trashed = false and mimeType = 'application/vnd.google-apps.folder' and name = '{_escape(part)}'"
            resp = service.files().list(q=q, pageSize=1, supportsAllDrives=True, includeItemsFromAllDrives=True, fields="files(id)").execute()
            files = resp.get("files", [])
            if not files:
                return None
            parent = files[0]["id"]
        return parent
    except HttpError as e:
        raise map_http_error(e)


def get_file_in_folder(file_id: str, folder_id: Optional[str] = None) -> Optional[Dict]:
    """Return metadata for file_id only if it is a direct child of folder_id (or the configured root folder when folder_id is None).

    Uses files().get to avoid constructing complex q strings which can trigger "Invalid Value" errors.
    """
    try:
        service = _build_service()
        # Fetch file metadata directly
        fields = "id,name,mimeType,size,modifiedTime,parents"
        file = service.files().get(fileId=_escape(file_id), supportsAllDrives=True, fields=fields).execute()
        if not file:
            return None
        parent = folder_id or GOOGLE_DRIVE_FOLDER_ID
        parents = file.get("parents", []) or []
        # Check direct parent membership
        if parent in parents:
            return file
        else:
            return None
    except HttpError as e:
        raise map_http_error(e)


def is_google_native(mime_type: str) -> bool:
    return bool(mime_type and mime_type.startswith("application/vnd.google-apps."))


def download_stream(file_id: str) -> Iterator[bytes]:
    try:
        service = _build_service()
        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request, chunksize=262144)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            fh.seek(0)
            chunk = fh.read()
            fh.truncate(0)
            fh.seek(0)
            if chunk:
                yield chunk
    except HttpError as e:
        raise map_http_error(e)


