from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, List
import asyncio
import json
import base64
import numpy as np
import subprocess
import threading


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
# background processes per app_id: { app_id: { proc, session_id, buffer, websockets, read_task } }
background_processes = {}
MAX_BG_BUFFER = 1000


async def _handle_bg_line(app_id: int, session_id: int, stream_name: str, text: str):
    from app.database import SessionLocal, TerminalOutput
    entry = background_processes.get(app_id)
    if not entry:
        return
    # buffer
    try:
        entry['buffer'].append({'stream': stream_name, 'data': text})
        if len(entry['buffer']) > MAX_BG_BUFFER:
            entry['buffer'].pop(0)
    except Exception:
        pass

    # persist to DB
    db = SessionLocal()
    try:
        out = TerminalOutput(session_id=session_id, output=text)
        db.add(out)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass

    # broadcast to attached websockets
    for ws in list(entry.get('websockets', [])):
        try:
            await ws.send_json({"type": "output", "stream": stream_name, "data": text})
        except Exception:
            try:
                entry['websockets'].discard(ws)
            except Exception:
                pass


async def _background_process_finished(app_id: int):
    from app.database import SessionLocal, TerminalSession, CustomApp
    from datetime import datetime

    entry = background_processes.get(app_id)
    if not entry:
        return

    session_id = entry.get('session_id')
    db = SessionLocal()
    try:
        # mark session ended
        try:
            sess = db.query(TerminalSession).filter(TerminalSession.id == session_id).first()
            if sess:
                sess.ended_at = datetime.utcnow()
                sess.is_active = False
                db.add(sess)
                db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

        # mark app inactive
        try:
            app_row = db.query(CustomApp).filter(CustomApp.id == app_id).first()
            if app_row:
                app_row.is_active = False
                db.add(app_row)
                db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

        # notify attached websockets
        for ws in list(entry.get('websockets', [])):
            try:
                await ws.send_json({"type": "output", "stream": "system", "data": "[process exited]\n>>> "})
            except Exception:
                pass

    finally:
        try:
            db.close()
        except Exception:
            pass
        background_processes.pop(app_id, None)


def _start_background_process(app_id: int, tokens_bg, base_dir: str, websocket: WebSocket, app, user_id: int):
    """Start a background subprocess using subprocess.Popen and threads (compatible with Windows)."""
    from app.database import SessionLocal, TerminalSession

    db = SessionLocal()
    try:
        bg_session = TerminalSession(app_id=app_id, user_id=user_id)
        db.add(bg_session)
        db.commit()
        db.refresh(bg_session)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        bg_session = None
    finally:
        try:
            db.close()
        except Exception:
            pass

    try:
        if isinstance(tokens_bg, (list, tuple)):
            proc = subprocess.Popen(tokens_bg, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=base_dir, text=True, bufsize=1)
        else:
            # tokens_bg is a string; run via shell
            proc = subprocess.Popen(tokens_bg, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=base_dir, text=True, bufsize=1, shell=True)
    except Exception as e:
        return None, e

    entry = {
        'proc': proc,
        'session_id': bg_session.id if bg_session else None,
        'buffer': [],
        'websockets': set([websocket]),
        'read_threads': []
    }

    background_processes[app_id] = entry

    loop = asyncio.get_event_loop()

    def _reader(pipe, stream_name):
        try:
            for line in iter(pipe.readline, ''):
                if not line:
                    break
                loop.call_soon_threadsafe(asyncio.create_task, _handle_bg_line(app_id, entry['session_id'], stream_name, line))
        except Exception:
            pass
        finally:
            try:
                pipe.close()
            except Exception:
                pass

    t_out = threading.Thread(target=_reader, args=(proc.stdout, 'stdout'), daemon=True)
    t_err = threading.Thread(target=_reader, args=(proc.stderr, 'stderr'), daemon=True)
    t_out.start()
    t_err.start()
    entry['read_threads'].extend([t_out, t_err])

    def _waiter():
        try:
            proc.wait()
        except Exception:
            pass
        try:
            loop.call_soon_threadsafe(asyncio.create_task, _background_process_finished(app_id))
        except Exception:
            pass

    t_wait = threading.Thread(target=_waiter, daemon=True)
    t_wait.start()
    entry['read_threads'].append(t_wait)

    return entry, None



def get_chat_manager():
    return voice_manager


async def handle_voice_websocket(websocket: WebSocket, user_id: int, channel_id: int, db):
    from app.database import SessionLocal
    from app.database import Channel, ServerMember, User, Role, UserRole, Server
    import json
    
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
        
        server = db.query(Server).filter(Server.id == channel.server_id).first()
        is_owner = server.owner_id == user_id if server else False
        
        if not is_owner:
            member = db.query(ServerMember).filter(
                ServerMember.user_id == user_id,
                ServerMember.server_id == channel.server_id
            ).first()
            if not member:
                await websocket.send_json({"type": "error", "message": "Not a member"})
                return
            
            if channel.required_role_id:
                user_roles = db.query(UserRole).filter(UserRole.member_id == member.id).all()
                user_role_ids = [ur.role_id for ur in user_roles]
                
                user_has_perm = False
                for ur in user_roles:
                    role = db.query(Role).filter(Role.id == ur.role_id).first()
                    if role:
                        perms = json.loads(role.permissions)
                        if perms.get('can_manage_channels', False):
                            user_has_perm = True
                            break
                
                if channel.required_role_id not in user_role_ids and not user_has_perm:
                    await websocket.send_json({"type": "error", "message": "No tienes el rol requerido para este canal"})
                    return
        
        user_channel_id = channel_id
        
        if not hasattr(voice_manager, 'user_channels'):
            voice_manager.user_channels = {}
        voice_manager.user_channels[user_id] = user_channel_id
        
        if user_channel_id not in voice_manager.voice_rooms:
            voice_manager.voice_rooms[user_channel_id] = set()
        
        voice_manager.voice_rooms[user_channel_id].add(user_id)
        voice_manager.voice_connections[user_id] = websocket
        
        if not hasattr(voice_manager, 'voice_usernames'):
            voice_manager.voice_usernames = {}
        if not hasattr(voice_manager, 'username_to_id'):
            voice_manager.username_to_id = {}
        
        voice_manager.voice_usernames[user_id] = username
        voice_manager.username_to_id[username] = user_id
        
        current_users = list(voice_manager.voice_usernames.get(u) for u in voice_manager.voice_rooms.get(user_channel_id, []) if u in voice_manager.voice_usernames)
        
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
        }, channel_id)
        
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
                            "type": msg_type,
                            "sdp": data.get("sdp"),
                            "from_user_id": user_id,
                            "from_username": username
                        }, target_user)
                    else:
                        print(f"Could not find user_id for username: {target_username}")
                
                elif msg_type == "media":
                    await voice_manager.broadcast({
                        "type": "media",
                        "user_id": user_id,
                        "from_username": username,
                        "enabled": data.get("enabled")
                    }, user_channel_id)
                
                elif msg_type == "mute":
                    await voice_manager.broadcast({
                        "type": "mute",
                        "user_id": user_id,
                        "from_username": username,
                        "muted": data.get("muted")
                    }, user_channel_id)
                
                elif msg_type == "camera":
                    await voice_manager.broadcast({
                        "type": "camera",
                        "user_id": user_id,
                        "from_username": username,
                        "enabled": data.get("enabled")
                    }, user_channel_id)
                
                elif msg_type == "screenshare":
                    await voice_manager.broadcast({
                        "type": "user_screenshare",
                        "user_id": user_id,
                        "from_username": username,
                        "enabled": data.get("enabled")
                    }, user_channel_id)
                
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
            if user_channel_id in voice_manager.voice_rooms:
                voice_manager.voice_rooms[user_channel_id].discard(user_id)
                if not voice_manager.voice_rooms[user_channel_id]:
                    del voice_manager.voice_rooms[user_channel_id]
            if user_id in voice_manager.voice_connections:
                del voice_manager.voice_connections[user_id]
            if hasattr(voice_manager, 'user_channels'):
                voice_manager.user_channels.pop(user_id, None)
            if hasattr(voice_manager, 'voice_usernames'):
                voice_manager.voice_usernames.pop(user_id, None)
            if hasattr(voice_manager, 'username_to_id') and username in voice_manager.username_to_id:
                del voice_manager.username_to_id[username]
                
                current_users = []
                if hasattr(voice_manager, 'voice_usernames'):
                    current_users = list(voice_manager.voice_usernames.get(u) for u in voice_manager.voice_rooms.get(user_channel_id, []) if u in voice_manager.voice_usernames)
                
                await voice_manager.broadcast({
                    "type": "user_left",
                    "user_id": user_id,
                    "users": current_users
                }, user_channel_id)
    finally:
        db.close()


async def handle_terminal_websocket(websocket: WebSocket, user_id: int, app_id: int):
    from app.database import SessionLocal
    from app.database import CustomApp, TerminalSession
    import io
    import sys
    from builtins import compile
    import os
    import builtins
    import shlex
    from app.config import settings
    
    await websocket.accept()
    
    db = SessionLocal()
    app = None
    
    try:
        app = db.query(CustomApp).filter(CustomApp.id == app_id).first()
        if not app:
            await websocket.send_json({"type": "error", "message": "App not found"})
            return
        # determine storage directory for this app's server
        base_dir = None
        try:
            from app.database import Channel, Server
            channel = db.query(Channel).filter(Channel.id == app.channel_id).first()
        except Exception:
            channel = None

        if channel and getattr(channel, 'server_id', None):
            server = db.query(Server).filter(Server.id == channel.server_id).first()
            if server:
                # sanitize server name
                safe_name = ''.join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in (server.name or 'server'))
                safe_name = safe_name.replace(' ', '_')
                base_dir = os.path.join(settings.MEDIA_DIR, 'servers', f"{server.id}_{safe_name}", 'customapps')

        if not base_dir:
            # fallback location for apps not tied to a server
            base_dir = os.path.join(settings.MEDIA_DIR, 'customapps', f"app_{app.id}")

        try:
            os.makedirs(base_dir, exist_ok=True)
        except Exception:
            pass

        # Prepare to override builtins.open so relative paths write into base_dir
        prev_open = builtins.open
        def open_override(path, *args, **kwargs):
            try:
                # only rewrite string/PathLike relative paths
                if isinstance(path, (str,)):
                    if not os.path.isabs(path):
                        path = os.path.join(base_dir, path)
                return prev_open(path, *args, **kwargs)
            except Exception:
                return prev_open(path, *args, **kwargs)

        # install override and expose variable to REPL locals
        builtins.open = open_override
        
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

        # If a background process exists for this app, attach this websocket to it and replay buffer
        try:
            if app_id in background_processes:
                entry = background_processes[app_id]
                # attach websocket
                entry['websockets'].add(websocket)
                # replay buffered output (limit to last N entries)
                start = max(0, len(entry['buffer']) - MAX_BG_BUFFER)
                for item in entry['buffer'][start:]:
                    try:
                        await websocket.send_json({"type": "output", "stream": item['stream'], "data": item['data']})
                    except Exception:
                        pass
                await websocket.send_json({"type": "output", "stream": "system", "data": ">>> "})
        except Exception:
            pass
        
        local_vars = {}
        # expose location helpers to the REPL
        local_vars['CUSTOM_APP_DIR'] = base_dir
        local_vars['MEDIA_DIR'] = settings.MEDIA_DIR
        
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

                # detect background run requests: `bg <cmd>` or trailing ` &`
                try:
                    txt = data.strip()
                    bg_cmd = None
                    if txt.startswith('bg '):
                        bg_cmd = txt[3:].strip()
                    elif txt.endswith(' &'):
                        bg_cmd = txt[:-2].strip()
                    if bg_cmd:
                        try:
                            tokens_bg = shlex.split(bg_cmd)
                        except Exception:
                            # fallback: pass raw string to run with shell=True
                            tokens_bg = bg_cmd

                        try:
                            entry, err = _start_background_process(app_id, tokens_bg, base_dir, websocket, app, user_id)
                            if err:
                                await websocket.send_json({"type": "output", "stream": "stderr", "data": f"{type(err).__name__}: {err}\n>>> "})
                                continue

                            # mark app active
                            try:
                                app.is_active = True
                                db.add(app)
                                db.commit()
                            except Exception:
                                db.rollback()

                            proc = entry.get('proc')
                            await websocket.send_json({"type": "output", "stream": "system", "data": f"Started background process (pid={getattr(proc, 'pid', '?')})\n>>> "})
                        except Exception as e:
                            await websocket.send_json({"type": "output", "stream": "stderr", "data": f"{type(e).__name__}: {e}\n>>> "})
                        continue
                except Exception:
                    pass

                # detect `python -c "..."` invocations and run them as subprocesses
                try:
                    tokens = shlex.split(data)
                except Exception:
                    tokens = None

                if tokens and len(tokens) >= 3 and tokens[0] in ('python', 'python3', 'py') and tokens[1] == '-c':
                    script = tokens[2]
                    # run the python -c script as a subprocess in the app base_dir so relative paths resolve there
                    try:
                        import subprocess as _sub

                        def _run_cmd():
                            return _sub.run([tokens[0], '-c', script], stdout=_sub.PIPE, stderr=_sub.PIPE, cwd=base_dir, text=True)

                        proc = await asyncio.to_thread(_run_cmd)

                        if proc.stdout:
                            for line in proc.stdout.splitlines(keepends=True):
                                try:
                                    await websocket.send_json({"type": "output", "stream": "stdout", "data": line})
                                except Exception:
                                    pass

                        if proc.stderr:
                            for line in proc.stderr.splitlines(keepends=True):
                                try:
                                    await websocket.send_json({"type": "output", "stream": "stderr", "data": line})
                                except Exception:
                                    pass

                        await websocket.send_json({"type": "output", "stream": "system", "data": ">>> "})
                    except Exception as e:
                        await websocket.send_json({"type": "output", "stream": "stderr", "data": f"{type(e).__name__}: {e}\n>>> "})
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
        # restore builtins.open if we overrode it for this session
        try:
            if 'prev_open' in locals() and prev_open is not None:
                builtins.open = prev_open
        except Exception:
            pass

        if app:
            try:
                # If there's a background process for this app still running, keep app.is_active True
                proc_entry = background_processes.get(app_id)
                if proc_entry and proc_entry.get('proc') is not None and getattr(proc_entry.get('proc'), 'returncode', None) is None:
                    pass
                else:
                    app.is_active = False
                    db.add(app)
                    db.commit()
            except Exception:
                try:
                    app.is_active = False
                    db.add(app)
                    db.commit()
                except Exception:
                    db.rollback()
        db.close()