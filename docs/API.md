# API Documentation

## Base URL

```
http://localhost:8000/api
```

## Authentication

All endpoints (except register and login) require a JWT token in the Authorization header:

```
Authorization: Bearer <token>
```

---

## Endpoints

### 1. Authentication (`/auth`)

#### Register User

```
POST /auth/register
```

Request:
```json
{
  "username": "string",
  "email": "user@example.com",
  "display_name": "string (optional)",
  "password": "string (min 6 chars)"
}
```

Response:
```json
{
  "id": 1,
  "username": "string",
  "email": "user@example.com",
  "display_name": "string",
  "avatar_url": null,
  "status": "offline",
  "created_at": "2024-01-01T00:00:00"
}
```

#### Login

```
POST /auth/login
```

Request:
```json
{
  "username": "string",
  "password": "string"
}
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

#### Get Current User

```
GET /auth/me
```

Response:
```json
{
  "id": 1,
  "username": "string",
  "email": "user@example.com",
  "display_name": "string",
  "avatar_url": "/media/images/abc123.jpg",
  "status": "offline",
  "created_at": "2024-01-01T00:00:00"
}
```

#### Update Current User

```
PUT /auth/me
```

Request:
```json
{
  "display_name": "string (optional)",
  "avatar_url": "string (optional)",
  "status": "string (optional)"
}
```

Response: User object

#### Upload Avatar

```
POST /auth/avatar
```

Content-Type: `multipart/form-data`

Request:
```
file: (image file)
```

Response: User object with updated avatar_url

---

### 2. Servers (`/servers`)

#### Create Server

```
POST /servers/
```

Request:
```json
{
  "name": "string",
  "description": "string (optional)",
  "image_url": "string (optional)",
  "encryption_mode": "database" | "e2e"
}
```

Response:
```json
{
  "id": 1,
  "name": "My Server",
  "description": "A cool server",
  "image_url": null,
  "invite_code": "abc123def456",
  "encryption_mode": "database",
  "owner_id": 1,
  "created_at": "2024-01-01T00:00:00",
  "channels": [...]
}
```

#### Get User's Servers

```
GET /servers/
```

Response: Array of Server objects

#### Get Server

```
GET /servers/{server_id}
```

Response: Server object with channels

#### Update Server

```
PUT /servers/{server_id}
```

Request:
```json
{
  "name": "string (optional)",
  "description": "string (optional)",
  "image_url": "string (optional)"
}
```

Response: Updated Server object

#### Delete Server

```
DELETE /servers/{server_id}
```

Response: `{"message": "Server deleted"}`

#### Get Server Members

```
GET /servers/{server_id}/members
```

Response: Array of ServerMember objects

#### Join Server

```
POST /servers/{server_id}/join/{invite_code}
```

Response: `{"message": "Joined server successfully"}`

#### Leave Server

```
POST /servers/{server_id}/leave
```

Response: `{"message": "Left server successfully"}`

---

### 3. Roles (`/servers/{server_id}/roles`)

#### Create Role

```
POST /servers/{server_id}/roles
```

Request:
```json
{
  "name": "Moderator",
  "color": "#FF0000",
  "permissions": "{\"kick\": true, \"ban\": true}"
}
```

Response:
```json
{
  "id": 2,
  "name": "Moderator",
  "color": "#FF0000",
  "permissions": "{\"kick\": true, \"ban\": true}",
  "server_id": 1,
  "position": 1,
  "created_at": "2024-01-01T00:00:00"
}
```

#### Get Roles

```
GET /servers/{server_id}/roles
```

Response: Array of Role objects

#### Update Role

```
PUT /servers/{server_id}/roles/{role_id}
```

Request: RoleCreate object
Response: Updated Role object

#### Delete Role

```
DELETE /servers/{server_id}/roles/{role_id}
```

Response: `{"message": "Role deleted"}`

---

### 4. Channels (`/channels`)

#### Create Channel

```
POST /channels/
```

Request:
```json
{
  "name": "general",
  "channel_type": "text" | "voice" | "custom",
  "description": "string (optional)",
  "server_id": 1,
  "required_role_id": null
}
```

Response:
```json
{
  "id": 1,
  "name": "general",
  "channel_type": "text",
  "description": null,
  "server_id": 1,
  "owner_id": null,
  "position": 0,
  "created_at": "2024-01-01T00:00:00"
}
```

#### Get Channel

```
GET /channels/{channel_id}
```

Response: Channel object

#### Update Channel

```
PUT /channels/{channel_id}
```

Request:
```json
{
  "name": "string (optional)",
  "description": "string (optional)",
  "required_role_id": 1,
  "position": 0
}
```

Response: Updated Channel object

#### Delete Channel

```
DELETE /channels/{channel_id}
```

Response: `{"message": "Channel deleted"}`

---

### 5. Messages (`/channels/{channel_id}/messages`)

#### Get Messages

```
GET /channels/{channel_id}/messages?limit=50&offset=0
```

Query Parameters:
- `limit`: Max messages to return (default: 50)
- `offset`: Offset for pagination (default: 0)

Response: Array of Message objects

#### Send Message

```
POST /channels/{channel_id}/messages
```

Request:
```json
{
  "content": "Hello world!",
  "message_type": "text"
}
```

Response:
```json
{
  "id": 1,
  "content": "Hello world!",
  "message_type": "text",
  "channel_id": 1,
  "author_id": 1,
  "created_at": "2024-01-01T00:00:00",
  "edited_at": null,
  "author": {
    "id": 1,
    "username": "user",
    "display_name": "User",
    "avatar_url": null,
    "status": "offline",
    "created_at": "2024-01-01T00:00:00"
  },
  "attachments": []
}
```

#### Upload Attachment

```
POST /channels/{channel_id}/messages/{message_id}/attachments
```

Content-Type: `multipart/form-data`

Request:
```
file: (file to upload)
```

Response: Message object with attachment

---

### 6. Direct Messages (`/direct-messages`)

#### Get Conversations

```
GET /direct-messages/
```

Response: Array of DirectMessage objects (latest message per conversation)

#### Get Messages with User

```
GET /direct-messages/{user_id}?limit=50&offset=0
```

Response: Array of DirectMessage objects

#### Send Message

```
POST /direct-messages/
```

Request:
```json
{
  "content": "Hello!",
  "message_type": "text",
  "recipient_id": 2
}
```

Response: DirectMessage object

#### Upload Attachment

```
POST /direct-messages/{message_id}/attachments
```

Content-Type: `multipart/form-data`

Request:
```
file: (file to upload)
```

Response: DirectMessage object

---

### 7. Invitations (`/invitations`)

#### Create Invitation

```
POST /invitations/?server_id=1
```

Request:
```json
{
  "max_uses": 10,
  "expires_at": "2024-12-31T00:00:00"
}
```

Response:
```json
{
  "id": 1,
  "code": "abc123def456",
  "server_id": 1,
  "inviter_id": 1,
  "max_uses": 10,
  "uses": 0,
  "expires_at": "2024-12-31T00:00:00",
  "created_at": "2024-01-01T00:00:00"
}
```

#### Get Invitation Info

```
GET /invitations/{code}
```

Response:
```json
{
  "code": "abc123def456",
  "server_id": 1,
  "server_name": "My Server"
}
```

#### Join with Invitation

```
POST /invitations/{code}/join
```

Response: `{"message": "Joined server successfully"}`

#### Delete Invitation

```
DELETE /invitations/{invitation_id}
```

Response: `{"message": "Invitation deleted"}`

---

### 8. Custom Apps (`/custom-apps`)

#### Create Custom App

```
POST /custom-apps/
```

Request:
```json
{
  "name": "Game Server",
  "description": "Minecraft server",
  "command": "java -jar minecraft_server.jar",
  "working_directory": "/path/to/server",
  "channel_id": 1
}
```

Response:
```json
{
  "id": 1,
  "name": "Game Server",
  "description": "Minecraft server",
  "command": "java -jar minecraft_server.jar",
  "working_directory": "/path/to/server",
  "channel_id": 1,
  "created_by": 1,
  "is_active": false
}
```

#### Get Channel Apps

```
GET /custom-apps/channel/{channel_id}
```

Response: Array of CustomApp objects

#### Get Custom App

```
GET /custom-apps/{app_id}
```

Response: CustomApp object

#### Update Custom App

```
PUT /custom-apps/{app_id}
```

Request:
```json
{
  "name": "string (optional)",
  "description": "string (optional)",
  "command": "string (optional)",
  "working_directory": "string (optional)"
}
```

Response: Updated CustomApp object

#### Delete Custom App

```
DELETE /custom-apps/{app_id}
```

Response: `{"message": "App deleted"}`

#### Start Terminal Session

```
POST /custom-apps/{app_id}/terminal
```

Response:
```json
{
  "session_id": 1,
  "message": "Terminal session started"
}
```

#### End Terminal Session

```
DELETE /custom-apps/terminal/{session_id}
```

Response: `{"message": "Terminal session ended"}`

#### Get Terminal Output

```
GET /custom-apps/terminal/{session_id}/output
```

Response: Array of TerminalOutput objects

---

### 9. Media (`/media`)

#### Get Media File

```
GET /media/{file_type}/{filename}
```

Valid file types: `images`, `audio`, `files`, `servers`

Response: File stream

#### Delete Media File

```
DELETE /media/{file_type}/{filename}
```

Response: `{"message": "File deleted"}`

---

## WebSocket Endpoints

### Voice Channel

```
ws://host/ws/voice/{channel_id}?token={jwt_token}
```

Messages:
- `joined`: User joined the channel
- `user_left`: User left the channel
- `offer`/`answer`: WebRTC SDP exchange
- `ice_candidate`: WebRTC ICE candidates
- `media`: Audio/video data
- `mute`: Mute status change
- `camera`: Camera status change
- `screenshare`: Screen share status

### Chat Channel

```
ws://host/ws/chat/{channel_id}?token={jwt_token}
```

Messages:
- Real-time message updates
- `ping`/`pong`: Keep-alive

### Terminal

```
ws://host/ws/terminal/{app_id}?token={jwt_token}
```

Messages:
- `output`: Command output
- Input: Python code to execute

---

## Error Responses

All endpoints may return:

```json
{
  "detail": "Error message"
}
```

Common status codes:
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `422`: Validation Error
- `500`: Internal Server Error