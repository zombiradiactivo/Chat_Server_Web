from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os
from app.database import get_db
from app.config import settings

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/{file_type}/{filename}")
async def get_media(file_type: str, filename: str):
    valid_types = ["images", "audio", "files", "servers"]
    if file_type not in valid_types:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    file_path = os.path.join(settings.MEDIA_DIR, file_type, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)


@router.delete("/{file_type}/{filename}")
async def delete_media(file_type: str, filename: str):
    valid_types = ["images", "audio", "files", "servers"]
    if file_type not in valid_types:
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    file_path = os.path.join(settings.MEDIA_DIR, file_type, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    os.remove(file_path)
    return {"message": "File deleted"}