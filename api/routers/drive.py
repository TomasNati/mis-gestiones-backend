import datetime
import hmac
import os
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from fastapi.responses import StreamingResponse

import drive
import models


router = APIRouter(prefix="/api/drive", tags=["Drive"])


def require_api_key(x_api_key: str = Header(...)) -> None:
    secret = os.getenv("BACKEND_SHARED_SECRET")
    if not secret or not hmac.compare_digest(x_api_key, secret):
        raise HTTPException(status_code=401, detail={"error": "Unauthorized", "message": "invalid or missing X-API-Key"})


@router.get("/api/drive/files", response_model=models.DriveFileListOut, tags=["Drive"], dependencies=[Depends(require_api_key)])
async def list_drive_files(
    path: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    created_from: Optional[str] = Query(None),
    created_to: Optional[str] = Query(None),
):
    # validate created_from/created_to are ISO 8601 dates or datetimes
    def _normalize_dt(s: Optional[str]) -> Optional[str]:
        if s is None:
            return None
        s2 = s
        # accept trailing Z by converting to +00:00
        if s2.endswith('Z'):
            s2 = s2[:-1] + '+00:00'
        # allow date-only (YYYY-MM-DD)
        if len(s2) == 10:
            s2 = s2 + 'T00:00:00'
        try:
            datetime.fromisoformat(s2)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid date format: '{s}'. Use ISO 8601 date or datetime.")
        return s2

    created_from = _normalize_dt(created_from)
    created_to = _normalize_dt(created_to)

    folder_id = None
    if path:
        folder_id = drive.get_folder_id_by_path(path)
        if folder_id is None:
            return {"files": []}
    files = drive.list_files(name_query=name, folder_id=folder_id, created_from=created_from, created_to=created_to)
    return {"files": [models.DriveFileOut.model_validate(f) for f in files]}


@router.get("/api/drive/files/{file_id}/download", tags=["Drive"])
def download_drive_file(file_id: str, path: Optional[str] = Query(None), x_api_key: str = Header(...)):
    # validate API key
    require_api_key(x_api_key)
    folder_id = None
    if path:
        folder_id = drive.get_folder_id_by_path(path)
        if folder_id is None:
            raise HTTPException(status_code=404, detail={"error": "Not Found", "message": "requested path does not exist"})
    metadata = drive.get_file_in_folder(file_id, folder_id=folder_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail={"error": "Not Found", "message": "file is not in the allowed folder"})
    if drive.is_google_native(metadata.get("mimeType", "")):
        raise HTTPException(status_code=415, detail={"error": "Unsupported Media Type", "message": "google-native file types cannot be downloaded directly"})
    filename = metadata.get("name", "file")
    headers = {"Content-Disposition": f'attachment; filename="{quote(filename)}"'}
    return StreamingResponse(drive.download_stream(file_id), media_type=metadata.get("mimeType", "application/octet-stream"), headers=headers)



