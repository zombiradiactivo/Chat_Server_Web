from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import enum
from app.config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class EncryptionMode(enum.Enum):
    DATABASE = "database"
    E2E = "e2e"


class ChannelType(enum.Enum):
    TEXT = "text"
    VOICE = "voice"
    CUSTOM = "custom"


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    invite_code = Column(String(20), unique=True, index=True)
    encryption_mode = Column(SQLEnum(EncryptionMode), default=EncryptionMode.DATABASE)
    owner_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="owned_servers")
    channels = relationship("Channel", back_populates="server", cascade="all, delete-orphan")
    members = relationship("ServerMember", back_populates="server", cascade="all, delete-orphan")
    roles = relationship("Role", back_populates="server", cascade="all, delete-orphan")
    invitations = relationship("Invitation", back_populates="server", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    avatar_url = Column(String(500), nullable=True)
    display_name = Column(String(100), nullable=True)
    status = Column(String(50), default="offline")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owned_servers = relationship("Server", back_populates="owner")
    server_members = relationship("ServerMember", back_populates="user", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="author", cascade="all, delete-orphan")
    direct_messages = relationship("DirectMessage", foreign_keys="DirectMessage.user1_id", back_populates="user1")
    direct_messages2 = relationship("DirectMessage", foreign_keys="DirectMessage.user2_id", back_populates="user2")
    voice_sessions = relationship("VoiceSession", back_populates="user")


class ServerMember(Base):
    __tablename__ = "server_members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    nickname = Column(String(100), nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="server_members")
    server = relationship("Server", back_populates="members")
    roles = relationship("UserRole", back_populates="member", cascade="all, delete-orphan")


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    color = Column(String(7), default="#000000")
    permissions = Column(Text, default="{}")
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    position = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    server = relationship("Server", back_populates="roles")
    user_roles = relationship("UserRole", back_populates="role")


class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("server_members.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)

    member = relationship("ServerMember", back_populates="roles")
    role = relationship("Role", back_populates="user_roles")


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    channel_type = Column(SQLEnum(ChannelType), nullable=False)
    description = Column(Text, nullable=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    required_role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)
    position = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    server = relationship("Server", back_populates="channels")
    messages = relationship("Message", back_populates="channel", cascade="all, delete-orphan")
    required_role = relationship("Role")
    owner = relationship("User")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=True)
    message_type = Column(String(50), default="text")
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    edited_at = Column(DateTime, nullable=True)

    channel = relationship("Channel", back_populates="messages")
    author = relationship("User", back_populates="messages")
    attachments = relationship("Attachment", back_populates="message", cascade="all, delete-orphan")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    message = relationship("Message", back_populates="attachments")


class DirectMessage(Base):
    __tablename__ = "direct_messages"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    message_type = Column(String(50), default="text")
    user1_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user2_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_read = Column(Boolean, default=False)

    user1 = relationship("User", foreign_keys=[user1_id], back_populates="direct_messages")
    user2 = relationship("User", foreign_keys=[user2_id], back_populates="direct_messages2")
    attachments = relationship("DMAttachment", back_populates="message", cascade="all, delete-orphan")


class DMAttachment(Base):
    __tablename__ = "dm_attachments"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    message_id = Column(Integer, ForeignKey("direct_messages.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    message = relationship("DirectMessage", back_populates="attachments")


class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, index=True, nullable=False)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    inviter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    max_uses = Column(Integer, nullable=True)
    uses = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    server = relationship("Server", back_populates="invitations")
    inviter = relationship("User")


class VoiceSession(Base):
    __tablename__ = "voice_sessions"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    channel = relationship("Channel")
    user = relationship("User")


class CustomApp(Base):
    __tablename__ = "custom_apps"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    command = Column(String(500), nullable=False)
    working_directory = Column(String(500), nullable=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=False)

    channel = relationship("Channel")


class TerminalSession(Base):
    __tablename__ = "terminal_sessions"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("custom_apps.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    app = relationship("CustomApp")
    user = relationship("User")
    output = relationship("TerminalOutput", back_populates="session", cascade="all, delete-orphan")


class TerminalOutput(Base):
    __tablename__ = "terminal_output"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("terminal_sessions.id"), nullable=False)
    output = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("TerminalSession", back_populates="output")


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()