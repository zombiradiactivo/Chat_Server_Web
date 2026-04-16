# Database Documentation

## Overview

Chat Server Web uses SQLite with SQLAlchemy ORM. The database can be easily switched to PostgreSQL or other databases by changing the `DATABASE_URL` in configuration.

## Entity Relationship Diagram

```
┌──────────┐       ┌───────────────┐       ┌──────────┐
│   User   │◄──────│ServerMember   │──────►│  Server  │
└──────────┘       └───────────────┘       └──────────┘
      │                     │                 │
      │              ┌──────┴──────┐          │
      │              │             │          │
      ▼              ▼             ▼          ▼
┌──────────┐   ┌───────┐    ┌──────┐   ┌────────┐
│UserRole  │   │ Role  │    │Member│   │ Channel│
└──────────┘   └───────┘    └──────┘   └────────┘
      │                                     │
      │                  ┌────────────────┐─┴┐
      ▼                  ▼                ▼  ▼
┌──────────┐       ┌──────────┐         ┌─────────┐
│  Voice   │       │ Message  │         │CustomApp│
│ Session  │       └──────────┘         └─────────┘
└──────────┘             │
                   ┌─────┴─────┐
                   │Attachment │
                   └───────────┘
```

## Tables

### 1. users

Stores user accounts.

| Column | Type | Constraints | Description |
|--------|------|------------|------------|
| id | INTEGER | PK | Auto-increment |
| username | VARCHAR(100) | UNIQUE, NOT NULL | Login username |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Email address |
| hashed_password | VARCHAR(255) | NOT NULL | Bcrypt hash |
| avatar_url | VARCHAR(500) | NULL | Profile image path |
| display_name | VARCHAR(100) | NULL | Display name |
| status | VARCHAR(50) | DEFAULT 'offline' | online/offline/dnd |
| created_at | DATETIME | DEFAULT NOW | Creation timestamp |
| updated_at | DATETIME | UPDATED NOW | Last update |

**Indexes:**
- `idx_users_username`
- `idx_users_email`

---

### 2. servers

Community/guild.

| Column | Type | Constraints | Description |
|--------|------|------------|------------|
| id | INTEGER | PK | Auto-increment |
| name | VARCHAR(255) | NOT NULL | Server name |
| description | TEXT | NULL | Server description |
| image_url | VARCHAR(500) | NULL | Server icon |
| invite_code | VARCHAR(20) | UNIQUE | Invitation code |
| encryption_mode | ENUM | DEFAULT 'database' | database/e2e |
| owner_id | INTEGER | FK → users.id | Owner user |
| created_at | DATETIME | DEFAULT NOW | Creation timestamp |
| updated_at | DATETIME | UPDATED NOW | Last update |

**Indexes:**
- `idx_servers_invite_code`

**Relationships:**
- Owner: 1 User (one-to-many)
- Channels: N Channel (cascade delete)
- Members: N ServerMember (cascade delete)
- Roles: N Role (cascade delete)
- Invitations: N Invitation (cascade delete)

---

### 3. server_members

Junction table for Users ↔ Servers (many-to-many).

| Column | Type | Constraints | Description |
|--------|------|------------|------------|
| id | INTEGER | PK | Auto-increment |
| user_id | INTEGER | FK → users.id, NOT NULL | Member |
| server_id | INTEGER | FK → servers.id, NOT NULL | Server |
| nickname | VARCHAR(100) | NULL | Server nickname |
| joined_at | DATETIME | DEFAULT NOW | Join timestamp |

**Indexes:**
- `idx_server_members_user_server` (user_id, server_id)

---

### 4. roles

Server-specific roles with permissions.

| Column | Type | Constraints | Description |
|--------|------|------------|------------|
| id | INTEGER | PK | Auto-increment |
| name | VARCHAR(100) | NOT NULL | Role name |
| color | VARCHAR(7) | DEFAULT '#000000' | Hex color (e.g., #FF0000) |
| permissions | TEXT | DEFAULT '{}' | JSON permissions object |
| server_id | INTEGER | FK → servers.id, NOT NULL | Server |
| position | INTEGER | DEFAULT 0 | Display order |
| created_at | DATETIME | DEFAULT NOW | Creation timestamp |

**Default roles created on server creation:**
1. `Admin` - Full permissions, color #FF0000
2. `@everyone` - Read/write, color #FFFFFF

---

### 5. user_roles

Junction table for ServerMembers ↔ Roles (many-to-many).

| Column | Type | Constraints | Description |
|--------|------|------------|------------|
| id | INTEGER | PK | Auto-increment |
| member_id | INTEGER | FK → server_members.id | Member |
| role_id | INTEGER | FK → roles.id | Role |

---

### 6. channels

Communication channels within servers or DM.

| Column | Type | Constraints | Description |
|--------|------|------------|------------|
| id | INTEGER | PK | Auto-increment |
| name | VARCHAR(100) | NOT NULL | Channel name |
| channel_type | ENUM | NOT NULL | text/voice/custom |
| description | TEXT | NULL | Channel description |
| server_id | INTEGER | FK → servers.id, NULL | Server (NULL for DM) |
| owner_id | INTEGER | FK → users.id, NULL | Owner for DM channels |
| required_role_id | INTEGER | FK → roles.id, NULL | Role required |
| position | INTEGER | DEFAULT 0 | Display order |
| created_at | DATETIME | DEFAULT NOW | Creation timestamp |

**Channel types:**
- `text`: Text messaging
- `voice`: Voice/video communication
- `custom`: Terminal/CLI applications

---

### 7. messages

Text messages in channels.

| Column | Type | Constraints | Description |
|--------|------|------------|------------|
| id | INTEGER | PK | Auto-increment |
| content | TEXT | NULL | Message content |
| message_type | VARCHAR(50) | DEFAULT 'text' | text/system |
| channel_id | INTEGER | FK → channels.id, NOT NULL | Channel |
| author_id | INTEGER | FK → users.id, NOT NULL | Author |
| created_at | DATETIME | DEFAULT NOW | Creation timestamp |
| edited_at | DATETIME | NULL | Edit timestamp |

**Relationships:**
- Attachments: N Attachment (cascade delete)

---

### 8. attachments

Files attached to messages.

| Column | Type | Constraints | Description |
|--------|------|------------|------------|
| id | INTEGER | PK | Auto-increment |
| filename | VARCHAR(255) | NOT NULL | Original filename |
| file_type | VARCHAR(50) | NOT NULL | MIME type |
| file_path | VARCHAR(500) | NOT NULL | Storage path |
| file_size | INTEGER | NOT NULL | Size in bytes |
| message_id | INTEGER | FK → messages.id, NOT NULL | Message |
| created_at | DATETIME | DEFAULT NOW | Upload timestamp |

---

### 9. direct_messages

Private messages between users.

| Column | Type | Constraints | Description |
|--------|------|------------|------------|
| id | INTEGER | PK | Auto-increment |
| content | TEXT | NOT NULL | Message content |
| message_type | VARCHAR(50) | DEFAULT 'text' | text/system |
| user1_id | INTEGER | FK → users.id, NOT NULL | Sender |
| user2_id | INTEGER | FK → users.id, NOT NULL | Recipient |
| created_at | DATETIME | DEFAULT NOW | Creation timestamp |
| is_read | BOOLEAN | DEFAULT FALSE | Read status |

---

### 10. dm_attachments

Files attached to direct messages.

| Column | Type | Constraints | Description |
|--------|------|------------|------------|
| id | INTEGER | PK | Auto-increment |
| filename | VARCHAR(255) | NOT NULL | Original filename |
| file_type | VARCHAR(50) | NOT NULL | MIME type |
| file_path | VARCHAR(500) | NOT NULL | Storage path |
| file_size | INTEGER | NOT NULL | Size in bytes |
| message_id | INTEGER | FK → direct_messages.id | Message |
| created_at | DATETIME | DEFAULT NOW | Upload timestamp |

---

### 11. invitations

Server invitation codes.

| Column | Type | Constraints | Description |
|--------|------|------------|------------|
| id | INTEGER | PK | Auto-increment |
| code | VARCHAR(20) | UNIQUE, NOT NULL | Invitation code |
| server_id | INTEGER | FK → servers.id, NOT NULL | Server |
| inviter_id | INTEGER | FK → users.id, NOT NULL | Created by |
| max_uses | INTEGER | NULL | Max uses (null=unlimited) |
| uses | INTEGER | DEFAULT 0 | Use count |
| expires_at | DATETIME | NULL | Expiration |
| created_at | DATETIME | DEFAULT NOW | Creation timestamp |

**Indexes:**
- `idx_invitations_code`

---

### 12. voice_sessions

Active voice channel sessions.

| Column | Type | Constraints | Description |
|--------|------|------------|------------|
| id | INTEGER | PK | Auto-increment |
| channel_id | INTEGER | FK → channels.id, NOT NULL | Channel |
| user_id | INTEGER | FK → users.id, NOT NULL | User |
| started_at | DATETIME | DEFAULT NOW | Start timestamp |
| ended_at | DATETIME | NULL | End timestamp |
| is_active | BOOLEAN | DEFAULT TRUE | Active status |

---

### 13. custom_apps

Custom applications/CLI tools.

| Column | Type | Constraints | Description |
|--------|------|------------|------------|
| id | INTEGER | PK | Auto-increment |
| name | VARCHAR(100) | NOT NULL | App name |
| description | TEXT | NULL | App description |
| command | VARCHAR(500) | NOT NULL | Command to execute |
| working_directory | VARCHAR(500) | NULL | Working directory |
| channel_id | INTEGER | FK → channels.id, NOT NULL | Channel |
| created_by | INTEGER | FK → users.id, NOT NULL | Creator |
| created_at | DATETIME | DEFAULT NOW | Creation timestamp |
| is_active | BOOLEAN | DEFAULT FALSE | Running status |

---

### 14. terminal_sessions

Active terminal sessions.

| Column | Type | Constraints | Description |
|--------|------|------------|------------|
| id | INTEGER | PK | Auto-increment |
| app_id | INTEGER | FK → custom_apps.id, NOT NULL | App |
| user_id | INTEGER | FK → users.id, NOT NULL | User |
| started_at | DATETIME | DEFAULT NOW | Start timestamp |
| ended_at | DATETIME | NULL | End timestamp |
| is_active | BOOLEAN | DEFAULT TRUE | Active status |

---

### 15. terminal_output

Terminal session output history.

| Column | Type | Constraints | Description |
|--------|------|------------|------------|
| id | INTEGER | PK | Auto-increment |
| session_id | INTEGER | FK → terminal_sessions.id | Session |
| output | TEXT | NOT NULL | Output text |
| timestamp | DATETIME | DEFAULT NOW | Timestamp |

---

## Enums

### EncryptionMode

```python
class EncryptionMode(enum.Enum):
    DATABASE = "database"
    E2E = "e2e"
```

### ChannelType

```python
class ChannelType(enum.Enum):
    TEXT = "text"
    VOICE = "voice"
    CUSTOM = "custom"
```

---

## Database Connection

SQLite is used by default:
```
sqlite:///./chat_server.db
```

For PostgreSQL:
```
postgresql://user:password@localhost/chat_server
```

---

## Migrations

For database migrations, use SQLAlchemy's migrate or alembic:

```bash
# Install alembic
pip install alembic

# Initialize
alembic init alembic

# Create migration
alembic revision --autogenerate -m "add field"

# Apply migration
alembic upgrade head
```

---

## File Storage

Uploaded files are stored in:
```
./media/
├── images/     # Profile/server images
├── audio/     # Audio files
├── files/     # Generic files
└── servers/   # Server icons
```

Max upload size: 100MB (configurable)