from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid
import secrets
from app.database import get_db
from app.database import User, Server, ServerMember, Role, Channel, ChannelType, EncryptionMode, UserRole
from app.schemas import RoleResponse
from app.auth import get_current_user
from app.schemas import (
    ServerCreate, ServerResponse, ServerUpdate, ServerMemberResponse, RoleCreate, RoleResponse
)
from app.encryption import get_encryption_plugin

router = APIRouter(prefix="/servers", tags=["servers"])


@router.post("/", response_model=ServerResponse)
async def create_server(server_data: ServerCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    invite_code = secrets.token_hex(4)
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
    db.commit()
    db.refresh(member)
    
    admin_role = Role(
        name="Admin",
        color="#FF0000",
        permissions='{"can_create_channel": true, "can_manage_channels": true, "can_manage_roles": true, "can_invite": true, "can_kick": true}',
        server_id=server.id,
        position=999
    )
    db.add(admin_role)
    db.commit()
    
    default_role = Role(
        name="@everyone",
        color="#FFFFFF",
        permissions='{"can_create_channel": false, "can_manage_channels": false, "can_manage_roles": false, "can_invite": true, "can_kick": false}',
        server_id=server.id,
        position=0
    )
    db.add(default_role)
    db.commit()
    db.refresh(default_role)
    db.refresh(admin_role)
    
    user_role_admin = UserRole(member_id=member.id, role_id=admin_role.id)
    db.add(user_role_admin)
    user_role_default = UserRole(member_id=member.id, role_id=default_role.id)
    db.add(user_role_default)
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


@router.get("/{server_id}/channels")
async def get_server_channels(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    import json
    
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    is_owner = server.owner_id == current_user.id
    
    if not is_owner:
        member = db.query(ServerMember).filter(
            ServerMember.user_id == current_user.id,
            ServerMember.server_id == server_id
        ).first()
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this server")
        
        user_roles = db.query(UserRole).filter(UserRole.member_id == member.id).all()
        user_role_ids = [ur.role_id for ur in user_roles]
        
        user_has_manage_perm = False
        for ur in user_roles:
            role = db.query(Role).filter(Role.id == ur.role_id).first()
            if role:
                perms = json.loads(role.permissions)
                if perms.get('can_manage_channels', False):
                    user_has_manage_perm = True
                    break
    
    all_channels = db.query(Channel).filter(Channel.server_id == server_id).order_by(Channel.position).all()
    
    visible_channels = []
    for c in all_channels:
        if is_owner or user_has_manage_perm or not c.required_role_id or c.required_role_id in user_role_ids:
            visible_channels.append(c)
    
    return visible_channels


@router.get("/{server_id}/members")
async def get_server_members(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    member = db.query(ServerMember).filter(
        ServerMember.user_id == current_user.id,
        ServerMember.server_id == server_id
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this server")
    
    members = db.query(ServerMember).filter(ServerMember.server_id == server_id).all()
    
    result = []
    for m in members:
        user_roles = db.query(UserRole).filter(UserRole.member_id == m.id).all()
        roles_list = []
        for ur in user_roles:
            role = db.query(Role).filter(Role.id == ur.role_id).first()
            if role:
                roles_list.append({
                    "id": role.id,
                    "name": role.name,
                    "color": role.color,
                    "permissions": role.permissions,
                    "server_id": role.server_id,
                    "position": role.position,
                    "created_at": role.created_at.isoformat() if role.created_at else None
                })
        
        result.append({
            "id": m.id,
            "user_id": m.user_id,
            "nickname": m.nickname,
            "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            "user": {
                "id": m.user.id,
                "username": m.user.username,
                "display_name": m.user.display_name,
                "avatar_url": m.user.avatar_url
            },
            "roles": roles_list
        })
    
    return result


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
    db.refresh(member)
    
    default_role = db.query(Role).filter(Role.server_id == server_id, Role.position == 0).first()
    if default_role:
        user_role = UserRole(member_id=member.id, role_id=default_role.id)
        db.add(user_role)
    
    db.commit()
    return {"message": "Joined server successfully"}


@router.post("/join/{invite_code}")
async def join_server_by_code(invite_code: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.invite_code == invite_code).first()
    if not server:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    
    existing_member = db.query(ServerMember).filter(
        ServerMember.user_id == current_user.id,
        ServerMember.server_id == server.id
    ).first()
    if existing_member:
        raise HTTPException(status_code=400, detail="Already a member")
    
    member = ServerMember(user_id=current_user.id, server_id=server.id)
    db.add(member)
    db.commit()
    db.refresh(member)
    
    default_role = db.query(Role).filter(Role.server_id == server.id, Role.position == 0).first()
    if default_role:
        user_role = UserRole(member_id=member.id, role_id=default_role.id)
        db.add(user_role)
    
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


@router.post("/{server_id}/fix-roles")
async def fix_server_roles(server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    if server.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    admin_role = db.query(Role).filter(Role.server_id == server_id, Role.position == 999).first()
    default_role = db.query(Role).filter(Role.server_id == server_id, Role.position == 0).first()
    
    owner_member = db.query(ServerMember).filter(
        ServerMember.server_id == server_id,
        ServerMember.user_id == server.owner_id
    ).first()
    
    if owner_member and admin_role:
        existing = db.query(UserRole).filter(
            UserRole.member_id == owner_member.id,
            UserRole.role_id == admin_role.id
        ).first()
        if not existing:
            user_role = UserRole(member_id=owner_member.id, role_id=admin_role.id)
            db.add(user_role)
            db.commit()
    
    return {"message": "Roles fixed"}


@router.post("/{server_id}/members/{member_id}/roles/{role_id}")
async def toggle_member_role(server_id: int, member_id: int, role_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    import json
    
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    is_owner = server.owner_id == current_user.id
    
    if not is_owner:
        member = db.query(ServerMember).filter(
            ServerMember.user_id == current_user.id,
            ServerMember.server_id == server_id
        ).first()
        if not member:
            raise HTTPException(status_code=403, detail="Not a member")
        
        user_roles = db.query(UserRole).filter(UserRole.member_id == member.id).all()
        has_permission = False
        for ur in user_roles:
            role = db.query(Role).filter(Role.id == ur.role_id).first()
            if role:
                perms = json.loads(role.permissions)
                if perms.get('can_manage_roles', False):
                    has_permission = True
                    break
        if not has_permission:
            raise HTTPException(status_code=403, detail="No tienes permiso para gestionar roles")
    
    member = db.query(ServerMember).filter(ServerMember.id == member_id, ServerMember.server_id == server_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    role = db.query(Role).filter(Role.id == role_id, Role.server_id == server_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    existing = db.query(UserRole).filter(UserRole.member_id == member_id, UserRole.role_id == role_id).first()
    if existing:
        db.delete(existing)
        action = "removed"
    else:
        user_role = UserRole(member_id=member_id, role_id=role_id)
        db.add(user_role)
        action = "added"
    
    db.commit()
    return {"message": f"Role {action}", "action": action}