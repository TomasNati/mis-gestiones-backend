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
        "client_email": client_email,
        "private_key": private_key,
        "type": "service_account",
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


def list_files(name_query: Optional[str] = None) -> List[Dict]:
    try:
        service = _build_service()
        q = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed = false"
        if name_query:
            q += f" and name contains '{_escape(name_query)}'"
        fields = "files(id,name,mimeType,size,modifiedTime)"
        resp = service.files().list(q=q, orderBy="modifiedTime desc", pageSize=100, supportsAllDrives=True, includeItemsFromAllDrives=True, fields=f"files({fields})").execute()
        return resp.get("files", [])
    except HttpError as e:
        raise map_http_error(e)


def get_file_in_folder(file_id: str) -> Optional[Dict]:
    try:
        service = _build_service()
        q = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed = false and id = '{_escape(file_id)}'"
        fields = "files(id,name,mimeType,size,modifiedTime)"
        resp = service.files().list(q=q, pageSize=1, supportsAllDrives=True, includeItemsFromAllDrives=True, fields=f"files({fields})").execute()
        files = resp.get("files", [])
        return files[0] if files else None
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


def find_by_name(name: str) -> List[Dict]:
    try:
        service = _build_service()
        q = f"'{GOOGLE_DRIVE_FOLDER_ID}' in parents and trashed = false and name = '{_escape(name)}'"
        fields = "files(id,name,mimeType,size,modifiedTime)"
        resp = service.files().list(q=q, supportsAllDrives=True, includeItemsFromAllDrives=True, fields=f"files({fields})").execute()
        return resp.get("files", [])
    except HttpError as e:
        raise map_http_error(e)


def create_file(name: str, mime_type: str, data: BinaryIO) -> Dict:
    try:
        service = _build_service()
        if hasattr(data, 'seek'):
            data.seek(0)
        media = MediaIoBaseUpload(data, mimetype=mime_type, resumable=False)
        body = {"name": name, "parents": [GOOGLE_DRIVE_FOLDER_ID]}
        file = service.files().create(body=body, media_body=media, supportsAllDrives=True, fields="id,name,mimeType,size,modifiedTime").execute()
        return file
    except HttpError as e:
        raise map_http_error(e)


def update_file_content(file_id: str, mime_type: str, data: BinaryIO) -> Dict:
    try:
        service = _build_service()
        if hasattr(data, 'seek'):
            data.seek(0)
        media = MediaIoBaseUpload(data, mimetype=mime_type, resumable=False)
        file = service.files().update(fileId=file_id, media_body=media, supportsAllDrives=True, fields="id,name,mimeType,size,modifiedTime").execute()
        return file
    except HttpError as e:
        raise map_http_error(e)
