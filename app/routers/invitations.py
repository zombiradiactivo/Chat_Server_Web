from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import secrets
from datetime import datetime, timedelta
from app.database import get_db
from app.database import User, Server, ServerMember, Invitation
from app.auth import get_current_user
from app.schemas import InvitationCreate, InvitationResponse

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.post("/", response_model=InvitationResponse)
async def create_invitation(invite_data: InvitationCreate, server_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    member = db.query(ServerMember).filter(
        ServerMember.user_id == current_user.id,
        ServerMember.server_id == server_id
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this server")
    
    code = secrets.token_hex(4)
    expires = invite_data.expires_at if invite_data.expires_at else datetime.utcnow() + timedelta(days=7)
    
    invitation = Invitation(
        code=code,
        server_id=server_id,
        inviter_id=current_user.id,
        max_uses=invite_data.max_uses,
        expires_at=expires
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation


@router.get("/{code}")
async def get_invitation(code: str, db: Session = Depends(get_db)):
    invitation = db.query(Invitation).filter(Invitation.code == code).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    if invitation.expires_at and invitation.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invitation expired")
    
    if invitation.max_uses and invitation.uses >= invitation.max_uses:
        raise HTTPException(status_code=400, detail="Invitation already used")
    
    server = db.query(Server).filter(Server.id == invitation.server_id).first()
    return {"code": code, "server_id": invitation.server_id, "server_name": server.name if server else None}


@router.post("/{code}/join")
async def join_with_invitation(code: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    invitation = db.query(Invitation).filter(Invitation.code == code).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    if invitation.expires_at and invitation.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invitation expired")
    
    if invitation.max_uses and invitation.uses >= invitation.max_uses:
        raise HTTPException(status_code=400, detail="Invitation already used")
    
    existing_member = db.query(ServerMember).filter(
        ServerMember.user_id == current_user.id,
        ServerMember.server_id == invitation.server_id
    ).first()
    if existing_member:
        raise HTTPException(status_code=400, detail="Already a member")
    
    member = ServerMember(user_id=current_user.id, server_id=invitation.server_id)
    db.add(member)
    db.commit()
    db.refresh(member)
    
    default_role = db.query(Role).filter(Role.server_id == invitation.server_id, Role.position == 0).first()
    if default_role:
        user_role = UserRole(member_id=member.id, role_id=default_role.id)
        db.add(user_role)
    
    invitation.uses += 1
    db.commit()
    
    return {"message": "Joined server successfully"}


@router.delete("/{invitation_id}")
async def delete_invitation(invitation_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    invitation = db.query(Invitation).filter(Invitation.id == invitation_id).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    server = db.query(Server).filter(Server.id == invitation.server_id).first()
    if not server or server.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    db.delete(invitation)
    db.commit()
    return {"message": "Invitation deleted"}