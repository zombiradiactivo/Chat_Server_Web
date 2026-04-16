from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, List
import asyncio
import json
import base64
import numpy as np


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.voice_connections: Dict[int, WebSocket] = {}
        self.voice_rooms: Dict[int, Set[int]] = {}
        self.terminal_sessions: Dict[int, asyncio.subprocess.Process] = {}
        self.chat_channel_connections: Dict[int, Set[int]] = {}
        self.chat_user_connections: Dict[int, int] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket
    
    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        if user_id in self.voice_connections:
            del self.voice_connections[user_id]
        for room_id in list(self.voice_rooms.keys()):
            if user_id in self.voice_rooms[room_id]:
                self.voice_rooms[room_id].remove(user_id)
                if not self.voice_rooms[room_id]:
                    del self.voice_rooms[room_id]
        if user_id in self.terminal_sessions:
            del self.terminal_sessions[user_id]
        for channel_id in list(self.chat_channel_connections.keys()):
            self.chat_channel_connections[channel_id].discard(user_id)
        if user_id in self.chat_user_connections:
            del self.chat_user_connections[user_id]
    
    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(message)
    
    async def send_voice_message(self, message: dict, user_id: int):
        if user_id in self.voice_connections:
            await self.voice_connections[user_id].send_json(message)
    
    async def broadcast(self, message: dict, room_id: int, exclude_user: int = None):
        if room_id in self.voice_rooms:
            for user_id in self.voice_rooms[room_id]:
                if user_id != exclude_user and user_id in self.active_connections:
                    await self.active_connections[user_id].send_json(message)
                if user_id != exclude_user and user_id in self.voice_connections:
                    await self.voice_connections[user_id].send_json(message)
    
    async def connect_chat_channel(self, websocket: WebSocket, user_id: int, channel_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        if channel_id not in self.chat_channel_connections:
            self.chat_channel_connections[channel_id] = set()
        self.chat_channel_connections[channel_id].add(user_id)
        self.chat_user_connections[user_id] = channel_id
    
    async def broadcast_to_channel(self, channel_id: int, message: dict, exclude_user: int = None):
        if channel_id in self.chat_channel_connections:
            for user_id in self.chat_channel_connections[channel_id]:
                if user_id != exclude_user and user_id in self.active_connections:
                    try:
                        await self.active_connections[user_id].send_json(message)
                    except:
                        pass
    
    def disconnect_chat_channel(self, user_id: int, channel_id: int = None):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        if channel_id is None:
            channel_id = self.chat_user_connections.get(user_id)
        if channel_id and channel_id in self.chat_channel_connections:
            self.chat_channel_connections[channel_id].discard(user_id)
        if user_id in self.chat_user_connections:
            del self.chat_user_connections[user_id]


voice_manager = ConnectionManager()
terminal_manager = ConnectionManager()


def get_chat_manager():
    return voice_manager


async def handle_voice_websocket(websocket: WebSocket, user_id: int, channel_id: int, db):
    from app.database import SessionLocal
    from app.database import Channel, ServerMember, User
    
    await websocket.accept()
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            await websocket.send_json({"type": "error", "message": "User not found"})
            return
        
        username = user.username
        
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
        voice_manager.voice_connections[user_id] = websocket
        
        if not hasattr(voice_manager, 'voice_usernames'):
            voice_manager.voice_usernames = {}
        if not hasattr(voice_manager, 'username_to_id'):
            voice_manager.username_to_id = {}
        
        voice_manager.voice_usernames[user_id] = username
        voice_manager.username_to_id[username] = user_id
        
        current_users = list(voice_manager.voice_usernames.get(u) for u in voice_manager.voice_rooms.get(channel.server_id, []) if u in voice_manager.voice_usernames)
        
        print(f"User {username} (id: {user_id}) joined channel {channel_id}, users: {current_users}")
        
        await voice_manager.send_personal_message({
            "type": "joined",
            "channel_id": channel_id,
            "users": current_users
        }, user_id)
        
        await voice_manager.broadcast({
            "type": "user_joined",
            "user_id": user_id,
            "username": username,
            "users": current_users
        }, channel.server_id)
        
        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")
                
                if msg_type == "offer" or msg_type == "answer":
                    target_username = data.get("target_user_id")
                    target_user = None
                    if hasattr(voice_manager, 'username_to_id'):
                        target_user = voice_manager.username_to_id.get(target_username)
                    
                    if target_user:
                        await voice_manager.send_voice_message({
                            "type": msg_type,
                            "sdp": data.get("sdp"),
                            "from_user_id": user_id,
                            "from_username": username
                        }, target_user)
                    else:
                        print(f"Could not find user_id for username: {target_username}")
                
                elif msg_type == "ice_candidate":
                    target_username = data.get("target_user_id")
                    target_user = None
                    if hasattr(voice_manager, 'username_to_id'):
                        target_user = voice_manager.username_to_id.get(target_username)
                    
                    if target_user:
                        await voice_manager.send_voice_message({
                            "type": "ice_candidate",
                            "candidate": data.get("candidate"),
                            "from_user_id": user_id,
                            "from_username": username
                        }, target_user)
                    else:
                        print(f"Could not find user_id for username: {target_username}")
                
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
                        "from_username": username,
                        "enabled": data.get("enabled")
                    }, channel.server_id)
                
                elif msg_type == "settings":
                    pass
                    
        except WebSocketDisconnect:
            pass
        finally:
            if channel.server_id in voice_manager.voice_rooms:
                voice_manager.voice_rooms[channel.server_id].discard(user_id)
                if user_id in voice_manager.voice_connections:
                    del voice_manager.voice_connections[user_id]
                if hasattr(voice_manager, 'voice_usernames'):
                    voice_manager.voice_usernames.pop(user_id, None)
                if hasattr(voice_manager, 'username_to_id') and username in voice_manager.username_to_id:
                    del voice_manager.username_to_id[username]
                
                current_users = []
                if hasattr(voice_manager, 'voice_usernames'):
                    current_users = list(voice_manager.voice_usernames.get(u) for u in voice_manager.voice_rooms.get(channel.server_id, []) if u in voice_manager.voice_usernames)
                
                await voice_manager.broadcast({
                    "type": "user_left",
                    "user_id": user_id,
                    "users": current_users
                }, channel.server_id)
    finally:
        db.close()


async def handle_terminal_websocket(websocket: WebSocket, user_id: int, app_id: int):
    from app.database import SessionLocal
    from app.database import CustomApp, TerminalSession
    import io
    import sys
    from builtins import compile
    
    await websocket.accept()
    
    db = SessionLocal()
    app = None
    
    try:
        app = db.query(CustomApp).filter(CustomApp.id == app_id).first()
        if not app:
            await websocket.send_json({"type": "error", "message": "App not found"})
            return
        
        session = TerminalSession(app_id=app_id, user_id=user_id)
        db.add(session)
        db.commit()
        
        app.is_active = True
        db.commit()
        
        await websocket.send_json({
            "type": "output",
            "stream": "system",
            "data": f"Python REPL - {app.name}\nType 'exit' to quit\n\n>>> "
        })
        
        local_vars = {}
        
        while True:
            try:
                data = await websocket.receive_text()
                
                if data.strip() == "exit":
                    await websocket.send_json({
                        "type": "output",
                        "stream": "system",
                        "data": "Goodbye!\n"
                    })
                    break
                
                if data.strip() == "clear":
                    await websocket.send_json({
                        "type": "output",
                        "stream": "system",
                        "data": "\n>>> "
                    })
                    continue
                
                old_stdout = sys.stdout
                sys.stdout = captured = io.StringIO()
                
                try:
                    exec(compile(data, '<input>', 'exec'), local_vars)
                    output = captured.getvalue()
                    
                    if output:
                        await websocket.send_json({
                            "type": "output",
                            "stream": "stdout",
                            "data": output + ">>> "
                        })
                    else:
                        await websocket.send_json({
                            "type": "output",
                            "stream": "stdout",
                            "data": ">>> "
                        })
                except SyntaxError:
                    try:
                        result = eval(data, local_vars)
                        await websocket.send_json({
                            "type": "output",
                            "stream": "stdout",
                            "data": f"{result}\n>>> "
                        })
                    except Exception as e:
                        await websocket.send_json({
                            "type": "output",
                            "stream": "stderr",
                            "data": f"{type(e).__name__}: {e}\n>>> "
                        })
                except Exception as e:
                    await websocket.send_json({
                        "type": "output",
                        "stream": "stderr",
                        "data": f"{type(e).__name__}: {e}\n>>> "
                    })
                finally:
                    sys.stdout = old_stdout
                    
            except Exception:
                break
        
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        try:
            await websocket.send_json({
                "type": "error",
                "message": error_msg
            })
        except:
            pass
        
    finally:
        if app:
            app.is_active = False
            db.commit()
        db.close()