from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.database import User, Channel, ChannelType, CustomApp, TerminalSession, TerminalOutput
from app.auth import get_current_user
from app.schemas import CustomAppCreate, CustomAppResponse, TerminalOutputResponse
from datetime import datetime

router = APIRouter(prefix="/custom-apps", tags=["custom-apps"])


class CustomAppUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    command: Optional[str] = None
    working_directory: Optional[str] = None


@router.post("/", response_model=CustomAppResponse)
async def create_custom_app(app_data: CustomAppCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == app_data.channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if channel.channel_type != ChannelType.CUSTOM:
        raise HTTPException(status_code=400, detail="Channel must be a custom channel")
    
    if channel.server_id:
        from app.database import Server, ServerMember, Role, UserRole
        server = db.query(Server).filter(Server.id == channel.server_id).first()
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")
        member = db.query(ServerMember).filter(
            ServerMember.user_id == current_user.id,
            ServerMember.server_id == channel.server_id
        ).first()
        if not member:
            raise HTTPException(status_code=403, detail="Not a member")
        
        user_roles = db.query(UserRole).filter(UserRole.member_id == member.id).all()
        role_ids = [ur.role_id for ur in user_roles]
        
        admin_role = db.query(Role).filter(
            Role.server_id == channel.server_id,
            Role.name == "Admin"
        ).first()
        
        if server.owner_id != current_user.id and (not admin_role or admin_role.id not in role_ids):
            raise HTTPException(status_code=403, detail="Not authorized to create apps in this channel")
    elif channel.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    custom_app = CustomApp(
        name=app_data.name,
        description=app_data.description,
        command=app_data.command,
        working_directory=app_data.working_directory,
        channel_id=app_data.channel_id,
        created_by=current_user.id
    )
    db.add(custom_app)
    db.commit()
    db.refresh(custom_app)
    return custom_app


@router.get("/channel/{channel_id}", response_model=List[CustomAppResponse])
async def get_channel_apps(channel_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    apps = db.query(CustomApp).filter(CustomApp.channel_id == channel_id).all()
    return apps


@router.get("/{app_id}", response_model=CustomAppResponse)
async def get_custom_app(app_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    app = db.query(CustomApp).filter(CustomApp.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return app


@router.put("/{app_id}", response_model=CustomAppResponse)
async def update_custom_app(app_id: int, app_data: CustomAppUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    app = db.query(CustomApp).filter(CustomApp.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    channel = db.query(Channel).filter(Channel.id == app.channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if channel.server_id:
        from app.database import Server
        server = db.query(Server).filter(Server.id == channel.server_id).first()
        if not server or server.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    elif channel.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if app_data.name is not None:
        app.name = app_data.name
    if app_data.description is not None:
        app.description = app_data.description
    if app_data.command is not None:
        app.command = app_data.command
    if app_data.working_directory is not None:
        app.working_directory = app_data.working_directory
    
    db.commit()
    db.refresh(app)
    return app


@router.delete("/{app_id}")
async def delete_custom_app(app_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    app = db.query(CustomApp).filter(CustomApp.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    channel = db.query(Channel).filter(Channel.id == app.channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if channel.server_id:
        from app.database import Server
        server = db.query(Server).filter(Server.id == channel.server_id).first()
        if not server or server.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")
    elif channel.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db.delete(app)
    db.commit()
    return {"message": "App deleted"}


@router.post("/{app_id}/terminal", response_model=dict)
async def start_terminal_session(app_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    app = db.query(CustomApp).filter(CustomApp.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    session = TerminalSession(
        app_id=app_id,
        user_id=current_user.id
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    app.is_active = True
    db.commit()
    
    return {"session_id": session.id, "message": "Terminal session started"}


@router.delete("/terminal/{session_id}")
async def end_terminal_session(session_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(TerminalSession).filter(TerminalSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    session.is_active = False
    session.ended_at = datetime.utcnow()
    
    app = db.query(CustomApp).filter(CustomApp.id == session.app_id).first()
    if app:
        app.is_active = False
    
    db.commit()
    return {"message": "Terminal session ended"}


@router.get("/terminal/{session_id}/output", response_model=List[TerminalOutputResponse])
async def get_terminal_output(session_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    session = db.query(TerminalSession).filter(TerminalSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    outputs = db.query(TerminalOutput).filter(TerminalOutput.session_id == session_id).order_by(TerminalOutput.timestamp.asc()).all()
    return outputs