from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import uuid
import os
import aiofiles
from app.database import get_db
from app.database import User, DirectMessage, DMAttachment
from app.auth import get_current_user
from app.schemas import DirectMessageCreate, DirectMessageResponse
from app.config import settings

router = APIRouter(prefix="/direct-messages", tags=["direct-messages"])


@router.get("/", response_model=List[DirectMessageResponse])
async def get_conversations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    messages = db.query(DirectMessage).filter(
        (DirectMessage.user1_id == current_user.id) | (DirectMessage.user2_id == current_user.id)
    ).order_by(DirectMessage.created_at.desc()).limit(100).all()
    
    conversation_map = {}
    for msg in messages:
        other_id = msg.user2_id if msg.user1_id == current_user.id else msg.user1_id
        if other_id not in conversation_map:
            conversation_map[other_id] = msg
    
    return list(conversation_map.values())


@router.get("/{user_id}", response_model=List[DirectMessageResponse])
async def get_messages_with_user(user_id: int, limit: int = 50, offset: int = 0, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    other_user = db.query(User).filter(User.id == user_id).first()
    if not other_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    messages = db.query(DirectMessage).filter(
        ((DirectMessage.user1_id == current_user.id) & (DirectMessage.user2_id == user_id)) |
        ((DirectMessage.user1_id == user_id) & (DirectMessage.user2_id == current_user.id))
    ).order_by(DirectMessage.created_at.desc()).offset(offset).limit(limit).all()
    
    return messages


@router.post("/", response_model=DirectMessageResponse)
async def send_message(message_data: DirectMessageCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recipient = db.query(User).filter(User.id == message_data.recipient_id).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    
    message = DirectMessage(
        content=message_data.content,
        message_type=message_data.message_type,
        user1_id=current_user.id,
        user2_id=message_data.recipient_id
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.post("/{message_id}/attachments", response_model=DirectMessageResponse)
async def upload_attachment(message_id: int, file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    message = db.query(DirectMessage).filter(DirectMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if message.user1_id != current_user.id and message.user2_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    file_ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{file_ext}"
    
    if file.content_type.startswith("image/"):
        subdir = "images"
    elif file.content_type.startswith("audio/"):
        subdir = "audio"
    else:
        subdir = "files"
    
    file_path = os.path.join(settings.MEDIA_DIR, subdir, filename)
    
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        if len(content) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400, detail="File too large")
        await f.write(content)
    
    attachment = DMAttachment(
        filename=file.filename,
        file_type=file.content_type,
        file_path=f"/media/{subdir}/{filename}",
        file_size=len(content),
        message_id=message_id
    )
    db.add(attachment)
    db.commit()
    
    return message