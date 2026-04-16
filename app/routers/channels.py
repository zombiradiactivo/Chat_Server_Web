from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import os
import aiofiles
from app.database import get_db
from app.database import User, Server, ServerMember, Channel, ChannelType, Message, Attachment, Role, UserRole
from app.auth import get_current_user
from app.schemas import (
    ChannelCreate, ChannelResponse, ChannelUpdate, MessageCreate, MessageResponse, AttachmentResponse
)
from app.config import settings

router = APIRouter(prefix="/channels", tags=["channels"])


def check_channel_access(channel: Channel, user: User, db: Session) -> bool:
    if channel.server_id:
        member = db.query(ServerMember).filter(
            ServerMember.user_id == user.id,
            ServerMember.server_id == channel.server_id
        ).first()
        if not member:
            return False
        if channel.required_role_id:
            user_roles = db.query(UserRole).filter(UserRole.member_id == member.id).all()
            role_ids = [ur.role_id for ur in user_roles]
            if channel.required_role_id not in role_ids:
                return False
    elif channel.owner_id != user.id:
        return False
    return True


@router.post("/", response_model=ChannelResponse)
async def create_channel(channel_data: ChannelCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if channel_data.server_id:
        server = db.query(Server).filter(Server.id == channel_data.server_id).first()
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        member = db.query(ServerMember).filter(
            ServerMember.user_id == current_user.id,
            ServerMember.server_id == channel_data.server_id
        ).first()
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this server")
    
    channel = Channel(
        name=channel_data.name,
        channel_type=channel_data.channel_type,
        description=channel_data.description,
        server_id=channel_data.server_id,
        owner_id=current_user.id if not channel_data.server_id else None,
        required_role_id=channel_data.required_role_id
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(channel_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if not check_channel_access(channel, current_user, db):
        raise HTTPException(status_code=403, detail="No access to this channel")
    
    return channel


@router.put("/{channel_id}", response_model=ChannelResponse)
async def update_channel(channel_id: int, channel_update: ChannelUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if channel.server_id:
        server = db.query(Server).filter(Server.id == channel.server_id).first()
        if server.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    elif channel.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if channel_update.name is not None:
        channel.name = channel_update.name
    if channel_update.description is not None:
        channel.description = channel_update.description
    if channel_update.required_role_id is not None:
        channel.required_role_id = channel_update.required_role_id
    if channel_update.position is not None:
        channel.position = channel_update.position
    
    db.commit()
    db.refresh(channel)
    return channel


@router.delete("/{channel_id}")
async def delete_channel(channel_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if channel.server_id:
        server = db.query(Server).filter(Server.id == channel.server_id).first()
        if server.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    elif channel.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db.delete(channel)
    db.commit()
    return {"message": "Channel deleted"}


@router.get("/{channel_id}/messages", response_model=List[MessageResponse])
async def get_messages(channel_id: int, limit: int = 50, offset: int = 0, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if not check_channel_access(channel, current_user, db):
        raise HTTPException(status_code=403, detail="No access to this channel")
    
    messages = db.query(Message).filter(Message.channel_id == channel_id).order_by(Message.created_at.desc()).offset(offset).limit(limit).all()
    return messages


@router.post("/{channel_id}/messages", response_model=MessageResponse)
async def create_message(channel_id: int, message_data: MessageCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if not check_channel_access(channel, current_user, db):
        raise HTTPException(status_code=403, detail="No access to this channel")
    
    message = Message(
        content=message_data.content,
        message_type=message_data.message_type,
        channel_id=channel_id,
        author_id=current_user.id
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.post("/{channel_id}/messages/{message_id}/attachments", response_model=MessageResponse)
async def upload_attachment(channel_id: int, message_id: int, file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if not check_channel_access(channel, current_user, db):
        raise HTTPException(status_code=403, detail="No access to this channel")
    
    message = db.query(Message).filter(Message.id == message_id, Message.channel_id == channel_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if message.author_id != current_user.id:
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
    
    attachment = Attachment(
        filename=file.filename,
        file_type=file.content_type,
        file_path=f"/media/{subdir}/{filename}",
        file_size=len(content),
        message_id=message_id
    )
    db.add(attachment)
    db.commit()
    
    return message