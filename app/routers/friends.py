from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db, FriendRequest, User
from app.schemas import FriendRequestCreate, FriendRequestResponse
from app.auth import get_current_user
from datetime import datetime

router = APIRouter()


@router.post("/friends", response_model=FriendRequestResponse)
async def send_friend_request(
    request: FriendRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if request.to_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="No puedes enviarte solicitud a ti mismo")
    
    to_user = db.query(User).filter(User.id == request.to_user_id).first()
    if not to_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    existing = db.query(FriendRequest).filter(
        ((FriendRequest.from_user_id == current_user.id) & (FriendRequest.to_user_id == request.to_user_id)) |
        ((FriendRequest.from_user_id == request.to_user_id) & (FriendRequest.to_user_id == current_user.id))
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una solicitud o amistad")
    
    friend_request = FriendRequest(
        from_user_id=current_user.id,
        to_user_id=request.to_user_id,
        status="pending"
    )
    db.add(friend_request)
    db.commit()
    db.refresh(friend_request)
    return friend_request


@router.get("/friends/requests", response_model=list[dict])
async def get_friend_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    requests = db.query(FriendRequest).filter(
        FriendRequest.to_user_id == current_user.id,
        FriendRequest.status == "pending"
    ).all()
    
    result = []
    for req in requests:
        from_user = db.query(User).filter(User.id == req.from_user_id).first()
        result.append({
            "id": req.id,
            "from_user_id": req.from_user_id,
            "to_user_id": req.to_user_id,
            "status": req.status,
            "created_at": req.created_at.isoformat() if req.created_at else None,
            "from_user": {
                "id": from_user.id,
                "username": from_user.username,
                "display_name": from_user.display_name,
                "avatar_url": from_user.avatar_url,
                "status": from_user.status
            } if from_user else None
        })
    return result


@router.get("/friends", response_model=list[dict])
async def get_friends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Get accepted friendships
    friends = []
    
    # Requests sent by current user that are accepted
    sent = db.query(FriendRequest).filter(
        FriendRequest.from_user_id == current_user.id,
        FriendRequest.status == "accepted"
    ).all()
    
    # Requests received by current user that are accepted
    received = db.query(FriendRequest).filter(
        FriendRequest.to_user_id == current_user.id,
        FriendRequest.status == "accepted"
    ).all()
    
    for f in sent:
        user = db.query(User).filter(User.id == f.to_user_id).first()
        if user:
            friends.append({
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "avatar_url": user.avatar_url,
                "status": user.status
            })
    
    for f in received:
        user = db.query(User).filter(User.id == f.from_user_id).first()
        if user:
            friends.append({
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "avatar_url": user.avatar_url,
                "status": user.status
            })
    
    return friends


@router.put("/friends/{request_id}/accept", response_model=FriendRequestResponse)
async def accept_friend_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    friend_request = db.query(FriendRequest).filter(
        FriendRequest.id == request_id,
        FriendRequest.to_user_id == current_user.id,
        FriendRequest.status == "pending"
    ).first()
    
    if not friend_request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    friend_request.status = "accepted"
    db.commit()
    db.refresh(friend_request)
    return friend_request


@router.put("/friends/{request_id}/reject", response_model=FriendRequestResponse)
async def reject_friend_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    friend_request = db.query(FriendRequest).filter(
        FriendRequest.id == request_id,
        FriendRequest.to_user_id == current_user.id,
        FriendRequest.status == "pending"
    ).first()
    
    if not friend_request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    friend_request.status = "rejected"
    db.commit()
    db.refresh(friend_request)
    return friend_request