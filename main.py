import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routes import auth, chat, calls
import socketio
import database

# Load .env file for local development
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Initialize database
database.init_db()

FRONTEND_URL = os.environ.get("FRONTEND_URL", "*")

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.include_router(auth.router, prefix="/api/auth")
app.include_router(chat.router, prefix="/api/chat")
app.include_router(calls.router, prefix="/api/calls")

# In-memory store for active sessions
active_users = {}  # name -> {sid, name, last_seen}

@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
    # Find and remove from active users
    disconnected_org = None
    for name, data in list(active_users.items()):
        if data.get("sid") == sid:
            disconnected_org = data.get("organization")
            del active_users[name]
            break
    
    # Notify remaining users in the same organization
    if disconnected_org:
        org_users = [u for u in active_users.values() if u.get("organization") == disconnected_org]
        for user_key, user_data in active_users.items():
            if user_data.get("organization") == disconnected_org:
                await sio.emit("users_update", org_users, to=user_data["sid"])

@sio.event
async def join(sid, data):
    # Case-insensitive: convert to lowercase
    name = data.get("name", "").strip().lower()
    organization = data.get("organization", "").strip().lower()
    active_users[f"{name}@{organization}"] = {
        "sid": sid, 
        "name": name, 
        "organization": organization,
        "last_seen": None
    }
    await sio.save_session(sid, {"name": name, "organization": organization})
    
    # Send users update to ALL users in the same organization
    org_users = [u for u in active_users.values() if u.get("organization") == organization]
    
    # Broadcast to all users in this organization
    for user_key, user_data in active_users.items():
        if user_data.get("organization") == organization:
            await sio.emit("users_update", org_users, to=user_data["sid"])

@sio.event
async def send_message(sid, data):
    import datetime
    session = await sio.get_session(sid)
    from_user = session.get("name")
    organization = session.get("organization")
    to_user = data.get("to")
    text = data.get("text")
    attachment = data.get("attachment")
    
    # Save to database
    msg_id = database.add_message(from_user, to_user, organization, text, attachment)
    
    msg = {
        "id": msg_id,
        "from": from_user,
        "to": to_user,
        "organization": organization,
        "text": text,
        "attachment": attachment,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    
    # Update last seen
    user_key = f"{from_user}@{organization}"
    if user_key in active_users:
        active_users[user_key]["last_seen"] = msg["timestamp"]
    
    # Send only to sender and recipient in same org
    await sio.emit("new_message", msg, to=sid)
    to_key = f"{to_user}@{organization}"
    if to_key in active_users:
        await sio.emit("new_message", msg, to=active_users[to_key]["sid"])

@sio.event
async def call_user(sid, data):
    session = await sio.get_session(sid)
    organization = session.get("organization")
    target = data.get("to")
    target_key = f"{target}@{organization}"
    target_sid = active_users.get(target_key, {}).get("sid")
    if target_sid:
        await sio.emit("incoming_call", {
            "from": session.get("name"),
            "type": data.get("type", "audio"),
            "offer": data.get("offer")
        }, to=target_sid)

@sio.event
async def call_answer(sid, data):
    session = await sio.get_session(sid)
    organization = session.get("organization")
    caller = data.get("to")
    caller_key = f"{caller}@{organization}"
    caller_sid = active_users.get(caller_key, {}).get("sid")
    if caller_sid:
        await sio.emit("call_answered", {"answer": data.get("answer")}, to=caller_sid)

@sio.event
async def ice_candidate(sid, data):
    session = await sio.get_session(sid)
    organization = session.get("organization")
    target = data.get("to")
    target_key = f"{target}@{organization}"
    target_sid = active_users.get(target_key, {}).get("sid")
    if target_sid:
        await sio.emit("ice_candidate", {"candidate": data.get("candidate")}, to=target_sid)

socket_app = socketio.ASGIApp(sio, app)
