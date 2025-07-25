from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocketState
from src.api.video_stream import router as video_stream_router
from src.api.auth import router as auth_router
from typing import Dict, Any, Set
from pydantic import BaseModel, Field
from datetime import datetime

all_openapi_tags = [
    {
        "name": "video-stream",
        "description": "Endpoints for video stream metadata and lifecycle.",
    },
    {
        "name": "auth",
        "description": "Endpoints for user registration, login, JWT auth, and user profile.",
    },
    {
        "name": "realtime",
        "description": "Websocket endpoints for reactions, chat, and crowd/live sync.",
    }
]

app = FastAPI(
    title="OTT Backend API",
    description="Backend service for cricket match live stream, reactions, and AI endpoints.",
    version="0.1.0",
    openapi_tags=all_openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# == In-memory (process) "live" state for all streams. For demo/prototyping ONLY. == #
# { stream_id: { 'connections': set(ws), 'emoji_counts': {}, 'chat': [..], ... } }
STREAM_LIVE_STATE: Dict[str, Dict[str, Any]] = {}
# (Production: persist and scale this! For demo: process only.)

VALID_EMOJIS = ["❤️", "🔥", "😄", "😮", "👏", "😡", "👍"]

class ReactionEvent(BaseModel):
    type: str = Field(..., description="Type of event: 'emoji', 'chat', etc.")
    emoji: str = Field(..., description="Reacted emoji string.")
    sender: str = Field(..., description="Sender's display name or id.")  # must be provided by frontend

class ChatEvent(BaseModel):
    type: str = Field(..., description="Type of event: 'chat'")
    message: str = Field(..., description="Message content")
    sender: str = Field(..., description="Sender's display name or id.")
    timestamp: str = Field(..., description="Client or server timestamp (ISO8601)")

class BaseEvent(BaseModel):
    type: str = Field(..., description="Type of event e.g. 'emoji', 'chat', 'join', 'leave', 'init', ...")

# All connected sockets for given stream
def _get_state(stream_id) -> Dict[str, Any]:
    s = STREAM_LIVE_STATE.setdefault(stream_id, {"connections": set(), "emoji_counts": {}, "chat": []})
    for e in VALID_EMOJIS:
        s["emoji_counts"].setdefault(e, 0)
    return s

async def broadcast_stream(stream_id: str, data: dict):
    """Send JSON message to all connected sockets for this stream."""
    state = _get_state(stream_id)
    ws_to_remove: Set[WebSocket] = set()
    for ws in list(state["connections"]):
        try:
            if ws.application_state == WebSocketState.CONNECTED:
                await ws.send_json(data)
        except Exception:
            ws_to_remove.add(ws)
    for ws in ws_to_remove:
        state["connections"].discard(ws)

def _prepare_full_state(stream_id: str):
    state = _get_state(stream_id)
    return {
        "type": "sync",
        "emoji_counts": dict(state["emoji_counts"]),
        "watching": len(state["connections"]),
        "chat": state["chat"][-25:]  # last messages only
    }

# https://fastapi.tiangolo.com/advanced/websockets
# PUBLIC_INTERFACE
@app.websocket("/ws/{stream_id}")
async def ws_stream_sync(websocket: WebSocket, stream_id: str):
    """
    Websocket for live reactions, chat, and crowd count sync for a stream.

    - Connect: Receives initial snapshot ({emoji_counts, watching, chat}).
    - Send: 
        { "type": "emoji", "emoji": "<str>", "sender": "<user-name>" }
        { "type": "chat", "message": "<msg>", "sender": "<user-name>" }
    - All events broadcast to all clients on "{stream_id}" in real time.
    - On connect/disconnect, "watching" count is updated for all.
    - Open the socket from frontend with: ws://[host]/ws/cric001

    Returns:
        Real-time stream state and events for the given stream_id.

    Tags:
        - realtime

    See /docs/ws-help for schema usage example.
    """
    await websocket.accept()
    state = _get_state(stream_id)
    state["connections"].add(websocket)
    # Send initial snapshot
    await websocket.send_json(_prepare_full_state(stream_id))
    # Broadcast presence join
    await broadcast_stream(stream_id, {
        "type": "watching",
        "watching": len(state["connections"])
    })
    try:
        while True:
            data = await websocket.receive_json()
            if not isinstance(data, dict) or "type" not in data:
                # Ignore invalid or nonconforming messages
                continue
            event_type = data["type"]
            if event_type == "emoji":
                emoji = data.get("emoji")
                sender = data.get("sender", "anonymous")
                if emoji in VALID_EMOJIS:
                    state["emoji_counts"][emoji] = state["emoji_counts"].get(emoji, 0) + 1
                    evt = {
                        "type": "emoji",
                        "emoji": emoji,
                        "count": state["emoji_counts"][emoji],
                        "sender": sender,
                        "watching": len(state["connections"]),
                        "timestamp": datetime.utcnow().isoformat()+"Z"
                    }
                    await broadcast_stream(stream_id, evt)
            elif event_type == "chat":
                message = data.get("message")
                sender = data.get("sender", "anonymous")
                timestamp = datetime.utcnow().isoformat()+"Z"
                if message and isinstance(message, str):
                    chat_obj = {
                        "type": "chat",
                        "message": message,
                        "sender": sender,
                        "timestamp": timestamp,
                    }
                    state["chat"].append(chat_obj)
                    # Optionally: truncate chat history to last N
                    state["chat"] = state["chat"][-100:]
                    await broadcast_stream(stream_id, chat_obj)
            # Possible: handle more event types here in future
    except WebSocketDisconnect:
        pass
    finally:
        # Remove user from connections
        state["connections"].discard(websocket)
        # Broadcast presence leave
        await broadcast_stream(stream_id, {
            "type": "watching",
            "watching": len(state["connections"])
        })

# Provide OpenAPI "usage" docs for the websocket
@app.get("/docs/ws-help", tags=["realtime"])
async def ws_usage_help():
    """PUBLIC_INTERFACE
    Websocket schema usage guide for emoji reactions, live count, chat. Shows event payloads and connection usage.

    Returns:
        Dict with example payloads for all websocket events.
    """
    return {
        "url": "/ws/{stream_id}",
        "description": "Connect to real-time backend sync for a particular stream.\n"
            "Send JSON as `{type: 'emoji', emoji: '<str>', sender: '<name>'}` or `{type: 'chat', message: '<str>', sender: '<name>'}`.\n"
            "Receive JSON events for live emoji counts, chat messages, and crowd presence.",
        "client_example_js": 
"""const ws = new WebSocket("ws://localhost:8000/ws/cric001");
ws.onmessage = ev => { const msg = JSON.parse(ev.data); console.log(msg); };
// To send emoji:
ws.send(JSON.stringify({type:'emoji', emoji:'🔥', sender:'Alice'}));
// To send chat:
ws.send(JSON.stringify({type:'chat', message:'Hello world!', sender:'Bob'}));""",
        "event_types": [
            {
                "type": "sync",
                "schema": {
                    "emoji_counts": {"❤️": 123, "🔥": 45},
                    "watching": 3,
                    "chat": [
                        {"message": "Hi!", "sender": "User1", "timestamp": "2024-07-22T08:00:00Z"}
                    ]
                }
            },
            {
                "type": "emoji",
                "schema": {
                    "emoji": "🔥",
                    "count": 46,
                    "sender": "Alice",
                    "watching": 5,
                    "timestamp": "2024-07-22T08:01:05Z"
                }
            },
            {
                "type": "chat",
                "schema": {
                    "message": "Hi, world!",
                    "sender": "Bob",
                    "timestamp": "2024-07-22T08:01:20Z"
                }
            },
            {
                "type": "watching",
                "schema": {"watching": 8}
            }
        ],
        "valid_emojis": VALID_EMOJIS
    }

# Register routers
app.include_router(auth_router)
app.include_router(video_stream_router)

@app.get("/")
def health_check():
    """PUBLIC_INTERFACE
    Health check endpoint for the OTT backend service.

    Returns:
        Dict[str, str]: Simple message confirming service health.
    """
    return {"message": "Healthy"}
