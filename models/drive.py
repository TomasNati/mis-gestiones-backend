import datetime
from pydantic import BaseModel
from typing import Optional

class DriveFileOut(BaseModel):
    id: str
    name: str
    mimeType: str
    size: Optional[int] = None
    modifiedTime: datetime.datetime

    class Config:
        from_attributes = True


class DriveFileListOut(BaseModel):
    files: list[DriveFileOut]

    class Config:
        from_attributes = True


class DriveUploadOut(BaseModel):
    file: DriveFileOut
    created: bool

    class Config:
        from_attributes = True
