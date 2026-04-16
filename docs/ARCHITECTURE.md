# Architecture Documentation

## Overview

Chat Server Web is a real-time chat application built with FastAPI. It combines REST API endpoints for data management with WebSockets for real-time communication.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Web Client (index.html)                 │
│                  HTML/CSS/JS (vanilla)                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                    │
│  ┌─────────────┬──────────────┬──────────────────────────┐  │
│  │   Routers   │  WebSockets  │   Static Files           │  │
│  │   (REST)    │  (Real-time) │   /media, /static        │  │
│  └─────────────┴──────────────┴──────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Business Logic                           │
│  ┌──────────┬────────────┬─────────────┬───────────────┐    │
│  │  Auth    │  Database  │ Encryption  │  WebSocket    │    │
│  │  (JWT)   │  (SQLAlch.)│  (Plugins)  │  Managers     │    │
│  └──────────┴────────────┴─────────────┴───────────────┘    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              SQLite Database                         │   │
│  │  (Users, Servers, Channels, Messages, Files)         │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              File Storage                            │   │
│  │  ./media/{images,audio,files,servers}                │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Component Descriptions

### 1. Web Client (`app/frontend/index.html`)

Single-page application with:
- Login/Register screens
- Server sidebar with server icons
- Channel sidebar with channel list
- Chat area with messages and input
- Voice channel overlay
- Terminal modal for custom apps
- Settings panel
- Direct messages view

### 2. FastAPI Application (`app/main.py`)

Entry point that:
- Configures CORS middleware
- Registers all API routers
- Mounts static file directories
- Defines WebSocket endpoints

### 3. Authentication (`app/auth.py`)

JWT-based authentication:
- Token creation with expiry
- Token validation
- Password hashing with bcrypt
- OAuth2 Bearer token scheme

### 4. Database (`app/database.py`)

SQLAlchemy ORM models:
- User, Server, ServerMember
- Channel, Message, Attachment
- DirectMessage, DMAttachment
- Invitation
- VoiceSession
- CustomApp, TerminalSession
- Role, UserRole

### 5. Schemas (`app/schemas.py`)

Pydantic models for:
- Request validation
- Response serialization
- Type checking

### 6. Routers

| Router | Responsibility |
|--------|---------------|
| auth.py | User registration, login, profile |
| servers.py | Server CRUD, members, roles |
| channels.py | Channel CRUD, messages |
| direct_messages.py | DM functionality |
| invitations.py | Invite codes |
| custom_apps.py | App management |
| media.py | File serving |

### 7. WebSocket Managers (`app/websocket/voice.py`)

Connection managers for:
- Voice channels (WebRTC signaling)
- Chat channels (real-time messages)
- Terminal sessions (Python REPL)

### 8. Encryption Plugins (`app/encryption/`)

Extensible encryption:
- DatabaseEncryption: Fernet symmetric
- E2EEncryption: AES-GCM

## Data Flow

### Message Flow

1. Client sends message to `/api/channels/{id}/messages` (REST)
2. Server saves to database
3. Server broadcasts to channel via WebSocket
4. Other clients receive in real-time

### Voice Channel Flow

1. User connects to `/ws/voice/{channel_id}`
2. Server adds user to voice room
3. User sends SDP offer via WebSocket
4. Server forwards to target users
5. WebRTC connection established directly between peers
6. Media flows peer-to-peer

### Terminal Flow

1. User connects to `/ws/terminal/{app_id}`
2. Server creates Python REPL session
3. User sends Python code
4. Server executes and returns output

## Security

- Passwords hashed with bcrypt
- JWT tokens with HS256
- File upload size limits (100MB)
- CORS configured for all origins
- Channel access checks per user
- Server ownership verification

## Configuration (`app/config.py`)

- APP_NAME: Application name
- DEBUG: Debug mode
- SECRET_KEY: JWT signing key
- ACCESS_TOKEN_EXPIRE_MINUTES: Token expiry
- DATABASE_URL: Database connection
- MEDIA_DIR: File storage directory
- MAX_UPLOAD_SIZE: File size limit
- VOICE_PORT_START/END: Voice port range
- Encoding settings for video/audio

## Extensibility

### Adding New Routers

```python
# app/routers/new_feature.py
from fastapi import APIRouter

router = APIRouter(prefix="/new-feature", tags=["new-feature"])

@router.get("/")
async def get_items():
    ...
```

Then register in `app/main.py`:
```python
app.include_router(new_feature_router.router, prefix="/api")
```

### Adding Encryption Plugins

```python
# app/encryption/__init__.py
class MyEncryption(EncryptionPlugin):
    @property
    def name(self) -> str:
        return "my-encryption"

    def encrypt(self, data: str, key: str = None) -> str:
        ...

    def decrypt(self, data: str, key: str = None) -> str:
        ...

ENCRYPTION_PLUGINS["my-encryption"] = MyEncryption()
```

## Deployment

### Development
```bash
python -m uvicorn app.main:app --reload
```

### Production
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Environment Variables

Create `.env` file:
```env
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@localhost/chat_server
DEBUG=False
```