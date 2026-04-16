from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, List
import asyncio
import json
import base64
import numpy as np


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.voice_rooms: Dict[int, Set[int]] = {}
        self.terminal_sessions: Dict[int, asyncio.subprocess.Process] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket
    
    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        for room_id in list(self.voice_rooms.keys()):
            if user_id in self.voice_rooms[room_id]:
                self.voice_rooms[room_id].remove(user_id)
                if not self.voice_rooms[room_id]:
                    del self.voice_rooms[room_id]
        if user_id in self.terminal_sessions:
            del self.terminal_sessions[user_id]
    
    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(message)
    
    async def broadcast(self, message: dict, room_id: int, exclude_user: int = None):
        if room_id in self.voice_rooms:
            for user_id in self.voice_rooms[room_id]:
                if user_id != exclude_user and user_id in self.active_connections:
                    await self.active_connections[user_id].send_json(message)


voice_manager = ConnectionManager()
terminal_manager = ConnectionManager()


async def handle_voice_websocket(websocket: WebSocket, user_id: int, channel_id: int, db):
    from app.database import SessionLocal
    from app.database import Channel, ServerMember, User
    
    await websocket.accept()
    
    db = SessionLocal()
    try:
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel or channel.channel_type.value != "voice":
            await websocket.send_json({"type": "error", "message": "Invalid channel"})
            return
        
        member = db.query(ServerMember).filter(
            ServerMember.user_id == user_id,
            ServerMember.server_id == channel.server_id
        ).first()
        if not member:
            await websocket.send_json({"type": "error", "message": "Not a member"})
            return
        
        if channel.server_id not in voice_manager.voice_rooms:
            voice_manager.voice_rooms[channel.server_id] = set()
        voice_manager.voice_rooms[channel.server_id].add(user_id)
        
        await voice_manager.send_personal_message({
            "type": "joined",
            "channel_id": channel_id,
            "users": list(voice_manager.voice_rooms.get(channel.server_id, []))
        }, user_id)
        
        await voice_manager.broadcast({
            "type": "user_joined",
            "user_id": user_id,
            "users": list(voice_manager.voice_rooms.get(channel.server_id, []))
        }, channel.server_id)
        
        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")
                
                if msg_type == "offer" or msg_type == "answer":
                    target_user = data.get("target_user_id")
                    await voice_manager.send_personal_message({
                        "type": msg_type,
                        "sdp": data.get("sdp"),
                        "from_user_id": user_id
                    }, target_user)
                
                elif msg_type == "ice_candidate":
                    target_user = data.get("target_user_id")
                    await voice_manager.send_personal_message({
                        "type": "ice_candidate",
                        "candidate": data.get("candidate"),
                        "from_user_id": user_id
                    }, target_user)
                
                elif msg_type == "media":
                    await voice_manager.broadcast({
                        "type": "media",
                        "user_id": user_id,
                        "data": data.get("data"),
                        "media_type": data.get("media_type")
                    }, channel.server_id, exclude_user=user_id)
                
                elif msg_type == "mute":
                    await voice_manager.broadcast({
                        "type": "user_muted",
                        "user_id": user_id,
                        "muted": data.get("muted")
                    }, channel.server_id)
                
                elif msg_type == "camera":
                    await voice_manager.broadcast({
                        "type": "user_camera",
                        "user_id": user_id,
                        "enabled": data.get("enabled")
                    }, channel.server_id)
                
                elif msg_type == "screenshare":
                    await voice_manager.broadcast({
                        "type": "user_screenshare",
                        "user_id": user_id,
                        "enabled": data.get("enabled")
                    }, channel.server_id)
                
                elif msg_type == "settings":
                    pass
                    
        except WebSocketDisconnect:
            pass
        finally:
            if channel.server_id in voice_manager.voice_rooms:
                voice_manager.voice_rooms[channel.server_id].discard(user_id)
                await voice_manager.broadcast({
                    "type": "user_left",
                    "user_id": user_id,
                    "users": list(voice_manager.voice_rooms.get(channel.server_id, []))
                }, channel.server_id)
    finally:
        db.close()


async def handle_terminal_websocket(websocket: WebSocket, user_id: int, app_id: int):
    from app.database import SessionLocal
    from app.database import CustomApp, TerminalSession, TerminalOutput
    
    await websocket.accept()
    
    db = SessionLocal()
    try:
        app = db.query(CustomApp).filter(CustomApp.id == app_id).first()
        if not app:
            await websocket.send_json({"type": "error", "message": "App not found"})
            return
        
        session = TerminalSession(
            app_id=app_id,
            user_id=user_id
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        app.is_active = True
        db.commit()
        
        terminal_manager.terminal_sessions[session.id] = None
        
        try:
            proc = await asyncio.create_subprocess_shell(
                app.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
                cwd=app.working_directory
            )
            terminal_manager.terminal_sessions[session.id] = proc
            
            async def read_output(stream, stream_type: str):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    output = line.decode()
                    await websocket.send_json({
                        "type": "output",
                        "stream": stream_type,
                        "data": output
                    })
                    
                    term_output = TerminalOutput(
                        session_id=session.id,
                        output=f"[{stream_type}] {output}"
                    )
                    db.add(term_output)
                    db.commit()
            
            asyncio.create_task(read_output(proc.stdout, "stdout"))
            asyncio.create_task(read_output(proc.stderr, "stderr"))
            
            while True:
                data = await websocket.receive_text()
                if proc.stdin:
                    proc.stdin.write(data.encode())
                    await proc.stdin.drain()
                    
        except WebSocketDisconnect:
            pass
        finally:
            if session.id in terminal_manager.terminal_sessions:
                proc = terminal_manager.terminal_sessions[session.id]
                if proc and proc.returncode is None:
                    proc.terminate()
                    await proc.wait()
                del terminal_manager.terminal_sessions[session.id]
            
            session.is_active = False
            session.ended_at = datetime.utcnow()
            app.is_active = False
            db.commit()
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        db.close()


from datetime import datetime