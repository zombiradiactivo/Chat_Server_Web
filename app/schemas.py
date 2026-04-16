from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime
from app.database import EncryptionMode, ChannelType


class UserBase(BaseModel):
    username: str
    email: EmailStr
    display_name: Optional[str] = None


class UserCreate(UserBase):
    password: str

    @validator('password')
    def password_min_length(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    status: Optional[str] = None


class UserResponse(UserBase):
    id: int
    avatar_url: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class RoleBase(BaseModel):
    name: str
    color: str = "#000000"
    permissions: str = "{}"


class RoleCreate(RoleBase):
    pass


class RoleResponse(RoleBase):
    id: int
    server_id: int
    position: int
    created_at: datetime

    class Config:
        from_attributes = True


class ServerBase(BaseModel):
    name: str
    description: Optional[str] = None


class ServerCreate(ServerBase):
    image_url: Optional[str] = None
    encryption_mode: EncryptionMode = EncryptionMode.DATABASE


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None


class ServerResponse(ServerBase):
    id: int
    image_url: Optional[str] = None
    invite_code: Optional[str] = None
    encryption_mode: EncryptionMode
    owner_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ServerMemberResponse(BaseModel):
    id: int
    user_id: int
    nickname: Optional[str] = None
    joined_at: datetime
    user: UserResponse
    roles: List[RoleResponse] = []

    class Config:
        from_attributes = True


class ChannelBase(BaseModel):
    name: str
    channel_type: ChannelType
    description: Optional[str] = None
    required_role_id: Optional[int] = None


class ChannelCreate(ChannelBase):
    server_id: Optional[int] = None


class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    required_role_id: Optional[int] = None
    position: Optional[int] = None


class ChannelResponse(ChannelBase):
    id: int
    server_id: Optional[int] = None
    owner_id: Optional[int] = None
    position: int
    created_at: datetime

    class Config:
        from_attributes = True


class AttachmentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    file_path: str
    file_size: int

    class Config:
        from_attributes = True


class MessageBase(BaseModel):
    content: Optional[str] = None


class MessageCreate(MessageBase):
    message_type: str = "text"


class MessageResponse(MessageBase):
    id: int
    message_type: str
    channel_id: int
    author_id: int
    created_at: datetime
    edited_at: Optional[datetime] = None
    author: UserResponse
    attachments: List[AttachmentResponse] = []

    class Config:
        from_attributes = True


class DirectMessageCreate(BaseModel):
    content: str
    message_type: str = "text"
    recipient_id: int


class DirectMessageResponse(BaseModel):
    id: int
    content: str
    message_type: str
    sender_id: int
    created_at: datetime
    is_read: bool

    class Config:
        from_attributes = True


class InvitationCreate(BaseModel):
    max_uses: Optional[int] = None
    expires_at: Optional[datetime] = None


class InvitationResponse(BaseModel):
    id: int
    code: str
    server_id: int
    inviter_id: int
    max_uses: Optional[int] = None
    uses: int
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class VoiceSettings(BaseModel):
    video_quality: str = "medium"
    audio_quality: str = "high"
    video_codec: str = "libx264"
    audio_codec: str = "opus"
    video_bitrate: int = 2500000
    audio_bitrate: int = 128000
    video_device: Optional[str] = None
    audio_input: Optional[str] = None
    audio_output: Optional[str] = None


class VoiceSessionResponse(BaseModel):
    id: int
    channel_id: int
    user_id: int
    is_active: bool

    class Config:
        from_attributes = True


class CustomAppBase(BaseModel):
    name: str
    description: Optional[str] = None
    command: str
    working_directory: Optional[str] = None


class CustomAppCreate(CustomAppBase):
    channel_id: int


class CustomAppResponse(CustomAppBase):
    id: int
    channel_id: int
    created_by: int
    is_active: bool

    class Config:
        from_attributes = True


class TerminalOutputResponse(BaseModel):
    id: int
    output: str
    timestamp: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str