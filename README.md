# Chat Server Web

Aplicación de mensajería avanzada estilo Discord con servidor y cliente web.

## Características

- **Servidores y Canales**: Crea servidores, canales de texto, voz y personalizados
- **Mensajería Directa**: Mensajes privados entre usuarios
- **Canales de Voz/Video**: Comunicación en tiempo real con WebRTC
- **Canales Personalizados**: Ejecuta aplicaciones CLI (servidores de juegos, bots) con terminal integrada
- **Roles y Permisos**: Sistema de roles con múltiples roles por usuario
- **Encriptación**: Modo base de datos o E2E (extensible con plugins)
- **Invitaciones**: Comparte servidores con códigos de invitación
- **Archivos**: Comparte imágenes, audios, archivos en mensajes
- **Interfaz Web**: Cliente web responsive estilo Discord

## Requisitos

- Python 3.10+
- Windows/Linux/MacOS

## Instalación

```bash
pip install -r requirements.txt
```

## Ejecución

```bash
# Windows
start.bat

# Linux/Mac
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Luego abre `http://localhost:8000` en tu navegador.

## Uso

1. **Regístrate** en la aplicación
2. **Crea un servidor** haciendo clic en "+ Crear Servidor"
3. **Invita usuarios** con el código de invitación
4. **Crea canales** de texto, voz o personalizados
5. **Comparte archivos** arrastrando y soltando en los canales de texto
6. **Únete a canales de voz** para hablar en tiempo real
7. **Ejecuta aplicaciones** en canales personalizados con terminal integrada

## Estructura del Proyecto

```
Chat_Server_Web/
├── app/
│   ├── config.py          # Configuración
│   ├── database.py         # Modelos de base de datos
│   ├── auth.py            # Autenticación JWT
│   ├── schemas.py         # Esquemas Pydantic
│   ├── main.py            # Aplicación FastAPI
│   ├── routers/           # Endpoints API
│   │   ├── auth.py
│   │   ├── servers.py
│   │   ├── channels.py
│   │   ├── direct_messages.py
│   │   ├── invitations.py
│   │   ├── custom_apps.py
│   │   └── media.py
│   ├── websocket/         # WebSockets
│   │   └── voice.py       # Voz y terminal
│   ├── encryption/        # Plugins de encriptación
│   └── frontend/
│       └── index.html    # Interfaz de usuario
├── requirements.txt
└── start.bat
```

## Tecnologías

- **Backend**: FastAPI, SQLAlchemy, JWT
- **Base de datos**: SQLite (fácil cambio a PostgreSQL)
- **Tiempo real**: WebSockets, WebRTC
- **Frontend**: HTML/CSS/JS vanilla