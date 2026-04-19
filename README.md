# Chat Server Web

A Discord-style chat application with real-time messaging, voice channels, and terminal integration.

## Features

- **Servers and Channels**: Create servers with text, voice, and custom channels
- **Direct Messaging**: Private messages between friends
- **Friend System**: Send friend requests, accept/reject, see online status
- **Voice/Video Channels**: Real-time communication via WebRTC
- **Custom Channels**: Execute CLI applications with integrated terminal
- **Roles and Permissions**: Role-based system with multiple roles per user
- **Invitations**: Share servers with invitation codes
- **File Sharing**: Share images, audio, and files in messages
- **User Profiles**: Custom avatar, display name, status (online/offline/busy/away), description
- **Real-time Updates**: Messages appear instantly via WebSocket
- **Web Interface**: Responsive Discord-style web client

## Requirements

- Python 3.10+
- Windows/Linux/MacOS

## Installation

```bash
pip install -r requirements.txt
```

## Running

```bash
# Windows
start.bat

# Windows/Linux/Mac
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Then open `http://localhost:8000` in your browser.

## Usage

1. **Register** in the application
2. **Create a server** by clicking "+ Create Server"
3. **Invite users** with the invitation code
4. **Create channels** for text, voice, or custom applications
5. **Share files** by dragging and dropping into text channels
6. **Join voice channels** for real-time communication
7. **Run applications** in custom channels with integrated terminal
8. **Add friends** from server members
9. **Send DMs** to friends via the Home or DMs sidebar

## Project Structure

```
Chat_Server_Web/
├── app/
│   ├── config.py           # Configuration
│   ├── database.py        # Database models
│   ├── auth.py            # JWT authentication
│   ├── schemas.py         # Pydantic schemas
│   ├── main.py           # FastAPI application
│   ├── routers/           # API endpoints
│   │   ├── auth.py       # Authentication
│   │   ├── servers.py    # Server management
│   │   ├── channels.py   # Channel management
│   │   ├── direct_messages.py  # DMs
│   │   ├── friends.py    # Friends system
│   │   ├── invitations.py # Invitations
│   │   ├── custom_apps.py # Custom apps
│   │   └── media.py      # File uploads
│   ├── websocket/         # WebSocket handlers
│   │   └── voice.py      # Voice, chat, and terminal
│   ├── encryption/       # Encryption plugins
│   └── frontend/
│       └── index.html    # Web client
├── docs/
│   ├── API.md           # API documentation
│   ├── ARCHITECTURE.md  # Architecture details
│   └── DATABASE.md     # Database schema
├── requirements.txt
├── start.bat
└── README.md
```

## API Overview

|Prefix|Resource|Description|
|------|---------|------------|
|/api/auth|Authentication|Register, login, profile, avatar|
|/api/servers|Servers|Create, join, leave, roles|
|/api/channels|Channels|Text, voice, custom|
|/api/direct-messages|Direct Messages|Private messaging|
|/api/friends|Friends|Friend requests and list|
|/api/invitations|Invitations|Share servers|
|/api/custom-apps|Custom Apps|Terminal apps|
|/api/media|Media|File uploads|
|/ws/voice|Voice|Real-time voice/video|
|/ws/chat|Chat|Real-time chat (channels and DMs)|
|/ws/terminal|Terminal|Python REPL|

## Technologies

- **Backend**: FastAPI, SQLAlchemy, JWT
- **Database**: SQLite (easily swappable to PostgreSQL)
- **Real-time**: WebSockets for chat, WebRTC for voice/video
- **Frontend**: HTML/CSS/JS vanilla