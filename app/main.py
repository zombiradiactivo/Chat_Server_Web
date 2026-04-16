from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth_router, servers_router, channels_router, direct_messages_router, invitations_router, custom_apps_router, media_router
from app.websocket import voice
from app.config import settings
import os

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/api")
app.include_router(servers_router.router, prefix="/api")
app.include_router(channels_router.router, prefix="/api")
app.include_router(direct_messages_router.router, prefix="/api")
app.include_router(invitations_router.router, prefix="/api")
app.include_router(custom_apps_router.router, prefix="/api")
app.include_router(media_router.router, prefix="/api")


@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("app/frontend/index.html")


@app.websocket("/ws/voice/{channel_id}")
async def voice_websocket(websocket: WebSocket, channel_id: int, token: str):
    from app.auth import decode_token
    from app.database import SessionLocal
    
    payload = decode_token(token)
    if not payload:
        await websocket.close()
        return
    
    user_id = payload.get("sub")
    db = SessionLocal()
    try:
        await voice.handle_voice_websocket(websocket, user_id, channel_id, db)
    finally:
        db.close()


@app.websocket("/ws/terminal/{app_id}")
async def terminal_websocket(websocket: WebSocket, app_id: int, token: str):
    from app.auth import decode_token
    
    payload = decode_token(token)
    if not payload:
        await websocket.close()
        return
    
    user_id = payload.get("sub")
    await voice.handle_terminal_websocket(websocket, user_id, app_id)


if os.path.exists("app/frontend/static"):
    app.mount("/static", StaticFiles(directory="app/frontend/static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)