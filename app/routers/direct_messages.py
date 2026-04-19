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
from app.websocket.voice import get_chat_manager

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
    from app.schemas import DirectMessageResponse
    
    other_user = db.query(User).filter(User.id == user_id).first()
    if not other_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    messages = db.query(DirectMessage).filter(
        ((DirectMessage.user1_id == current_user.id) & (DirectMessage.user2_id == user_id)) |
        ((DirectMessage.user1_id == user_id) & (DirectMessage.user2_id == current_user.id))
    ).order_by(DirectMessage.created_at.desc()).offset(offset).limit(limit).all()
    
    result = []
    for msg in messages:
        attachments = db.query(DMAttachment).filter(DMAttachment.message_id == msg.id).all()
        msg_data = DirectMessageResponse(
            id=msg.id,
            content=msg.content,
            message_type=msg.message_type,
            user1_id=msg.user1_id,
            user2_id=msg.user2_id,
            created_at=msg.created_at,
            is_read=msg.is_read,
            attachments=[{"id": a.id, "filename": a.filename, "file_path": a.file_path, "file_type": a.file_type} for a in attachments]
        )
        result.append(msg_data)
    
    return result


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
    
    # Don't broadcast for file uploads (content is placeholder) - will broadcast after upload
    if message_data.content and message_data.content.strip():
        # Broadcast to recipient via WebSocket using a shared room based on both users
        chat_manager = get_chat_manager()
        user_ids = sorted([current_user.id, message_data.recipient_id])
        room_key = f"dm_{user_ids[0]}_{user_ids[1]}"
        print(f"Broadcasting DM to room: {room_key}, recipients: {chat_manager.chat_channel_connections.get(room_key, set())}")
        await chat_manager.broadcast_to_channel(room_key, {
            "type": "new_dm",
            "message": {
                "id": message.id,
                "content": message.content,
                "message_type": message.message_type,
                "user1_id": message.user1_id,
                "user2_id": message.user2_id,
                "created_at": message.created_at.isoformat() if message.created_at else None,
                "is_read": message.is_read
            },
            "from_user": {
                "id": current_user.id,
                "username": current_user.username,
                "display_name": current_user.display_name,
                "avatar_url": current_user.avatar_url
            }
        }, exclude_user=current_user.id)
    
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
    db.refresh(message)
    
    # Fetch the attachments to include in the broadcast and response
    attachments = db.query(DMAttachment).filter(DMAttachment.message_id == message.id).all()
    
    # Broadcast the updated message with attachments
    other_user_id = message.user2_id if message.user1_id == current_user.id else message.user1_id
    user_ids = sorted([current_user.id, other_user_id])
    room_key = f"dm_{user_ids[0]}_{user_ids[1]}"
    chat_manager = get_chat_manager()
    await chat_manager.broadcast_to_channel(room_key, {
        "type": "new_dm",
        "message": {
            "id": message.id,
            "content": message.content,
            "message_type": message.message_type,
            "user1_id": message.user1_id,
            "user2_id": message.user2_id,
            "created_at": message.created_at.isoformat() if message.created_at else None,
            "is_read": message.is_read,
            "attachments": [{"id": a.id, "filename": a.filename, "file_path": a.file_path, "file_type": a.file_type} for a in attachments]
        },
        "from_user": {
            "id": current_user.id,
            "username": current_user.username,
            "display_name": current_user.display_name,
            "avatar_url": current_user.avatar_url
        }
    }, exclude_user=current_user.id)
    
    # Return message with attachments as dict
    from app.schemas import DirectMessageResponse
    return DirectMessageResponse(
        id=message.id,
        content=message.content,
        message_type=message.message_type,
        user1_id=message.user1_id,
        user2_id=message.user2_id,
        created_at=message.created_at,
        is_read=message.is_read,
        attachments=[{"id": a.id, "filename": a.filename, "file_path": a.file_path, "file_type": a.file_type} for a in attachments]
    )