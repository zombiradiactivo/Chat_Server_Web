from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid
import secrets
from app.database import get_db
from app.database import User, Server, ServerMember, Role, Channel, ChannelType, EncryptionMode
from app.auth import get_current_user
from app.schemas import (
    ServerCreate, ServerResponse, ServerUpdate, ServerMemberResponse, RoleCreate, RoleResponse
)
from app.encryption import get_encryption_plugin

router = APIRouter(prefix="/servers", tags=["servers"])


@router.post("/", response_model=ServerResponse)
async def create_server(server_data: ServerCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    invite_code = secrets.token_urlsafe(12)
    server = Server(
        name=server_data.name,
        description=server_data.description,
        image_url=server_data.image_url,
        invite_code=invite_code,
        encryption_mode=server_data.encryption_mode,
        owner_id=current_user.id
    )
    db.add(server)
    db.commit()
    db.refresh(server)
    
    member = ServerMember(user_id=current_user.id, server_id=server.id)
    db.add(member)
    
    admin_role = Role(
        name="Admin",
        color="#FF0000",
        permissions='{"all": true}',
        server_id=server.id,
        position=999
    )
    db.add(admin_role)
    
    default_role = Role(
        name="@everyone",
        color="#FFFFFF",
        permissions='{"read": true, "write": true}',
        server_id=server.id,
        position=0
    )
    db.add(default_role)
    db.commit()
    
    general_channel = Channel(
        name="general",
        channel_type=ChannelType.TEXT,
        server_id=server.id,
        position=0
    )
    db.add(general_channel)
    db.commit()
    
    return server


@router.get("/", response_model=List[ServerResponse])
async def get_servers(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    members = db.query(ServerMember).filter(ServerMember.user_id == current_user.id).all()
    servers = [m.server for m in members]
    return servers


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member = db.query(ServerMember).filter(
        ServerMember.user_id == current_user.id,
        ServerMember.server_id == server_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Server not found")
    return member.server


@router.put("/{server_id}", response_model=ServerResponse)
async def update_server(server_id: int, server_update: ServerUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    if server.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    if server_update.name is not None:
        server.name = server_update.name
    if server_update.description is not None:
        server.description = server_update.description
    if server_update.image_url is not None:
        server.image_url = server_update.image_url
    
    db.commit()
    db.refresh(server)
    return server


@router.delete("/{server_id}")
async def delete_server(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    if server.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db.delete(server)
    db.commit()
    return {"message": "Server deleted"}


@router.get("/{server_id}/members", response_model=List[ServerMemberResponse])
async def get_server_members(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member = db.query(ServerMember).filter(
        ServerMember.user_id == current_user.id,
        ServerMember.server_id == server_id
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this server")
    
    members = db.query(ServerMember).filter(ServerMember.server_id == server_id).all()
    return members


@router.post("/{server_id}/join/{invite_code}")
async def join_server(server_id: int, invite_code: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server or server.invite_code != invite_code:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    
    existing_member = db.query(ServerMember).filter(
        ServerMember.user_id == current_user.id,
        ServerMember.server_id == server_id
    ).first()
    if existing_member:
        raise HTTPException(status_code=400, detail="Already a member")
    
    member = ServerMember(user_id=current_user.id, server_id=server_id)
    db.add(member)
    db.commit()
    return {"message": "Joined server successfully"}


@router.post("/{server_id}/leave")
async def leave_server(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member = db.query(ServerMember).filter(
        ServerMember.user_id == current_user.id,
        ServerMember.server_id == server_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Not a member of this server")
    
    server = db.query(Server).filter(Server.id == server_id).first()
    if server.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Owner cannot leave the server")
    
    db.delete(member)
    db.commit()
    return {"message": "Left server successfully"}


@router.post("/{server_id}/roles", response_model=RoleResponse)
async def create_role(server_id: int, role_data: RoleCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server or server.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    role = Role(
        name=role_data.name,
        color=role_data.color,
        permissions=role_data.permissions,
        server_id=server_id
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.get("/{server_id}/roles", response_model=List[RoleResponse])
async def get_roles(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member = db.query(ServerMember).filter(
        ServerMember.user_id == current_user.id,
        ServerMember.server_id == server_id
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member")
    
    roles = db.query(Role).filter(Role.server_id == server_id).all()
    return roles


@router.put("/{server_id}/roles/{role_id}", response_model=RoleResponse)
async def update_role(server_id: int, role_id: int, role_data: RoleCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server or server.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    role = db.query(Role).filter(Role.id == role_id, Role.server_id == server_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    role.name = role_data.name
    role.color = role_data.color
    role.permissions = role_data.permissions
    
    db.commit()
    db.refresh(role)
    return role


@router.delete("/{server_id}/roles/{role_id}")
async def delete_role(server_id: int, role_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server or server.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    role = db.query(Role).filter(Role.id == role_id, Role.server_id == server_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    db.delete(role)
    db.commit()
    return {"message": "Role deleted"}