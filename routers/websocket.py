from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from core.config import SECRET_KEY, ALGORITHM
from core.database import database

router = APIRouter()


# ──────────────────────────────────────────────
# Connection manager — tracks who is online
# ──────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: dict[int, WebSocket] = {}  # user_id -> WebSocket

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active[user_id] = websocket

    def disconnect(self, user_id: int):
        self.active.pop(user_id, None)

    def is_online(self, user_id: int) -> bool:
        return user_id in self.active

    async def send(self, user_id: int, data: dict):
        ws = self.active.get(user_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(user_id)


manager = ConnectionManager()


# ──────────────────────────────────────────────
# JWT auth for WebSocket
# ──────────────────────────────────────────────
async def authenticate_ws(websocket: WebSocket):
    token = websocket.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("username")
        if not username:
            return None
        user = await database.fetch_one(
            "SELECT id, username FROM users WHERE username = :username",
            {"username": username},
        )
        return dict(user) if user else None
    except JWTError:
        return None


# ──────────────────────────────────────────────
# WebSocket endpoint  —  ws://host/ws?token=<jwt>
#
# Frontend sends JSON with a "type" field:
#
#   Send message:
#   { "type": "message", "conversation_id": 1, "content": "hey" }
#
#   Typing indicator:
#   { "type": "typing", "conversation_id": 1, "is_typing": true }
#
#   Mark as read:
#   { "type": "read", "conversation_id": 1 }
# ──────────────────────────────────────────────
@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
):
    user = await authenticate_ws(websocket)
    if not user:
        await websocket.close(code=4001)
        return

    user_id: int = user["id"]
    username: str = user["username"]

    await manager.connect(websocket, user_id)
    await manager.send(user_id, {"type": "connected", "user_id": user_id})

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            # ── Send message ────────────────────────────────
            if msg_type == "message":
                conversation_id = data.get("conversation_id")
                content = (data.get("content") or "").strip()

                if not conversation_id or not content:
                    await manager.send(user_id, {
                        "type": "error",
                        "detail": "Missing conversation_id or content"
                    })
                    continue

                # Verify sender is a participant
                conversation = await database.fetch_one(
                    """
                    SELECT * FROM conversations
                    WHERE id = :cid
                      AND (participant_1 = :uid OR participant_2 = :uid)
                    """,
                    {"cid": conversation_id, "uid": user_id},
                )
                if not conversation:
                    await manager.send(user_id, {
                        "type": "error",
                        "detail": "Not a participant of this conversation"
                    })
                    continue

                recipient_id = (
                    conversation["participant_2"]
                    if conversation["participant_1"] == user_id
                    else conversation["participant_1"]
                )

                # If recipient is online → delivered, else → sent
                status = "delivered" if manager.is_online(recipient_id) else "sent"

                # Save to DB
                row = await database.fetch_one(
                    """
                    INSERT INTO messages (conversation_id, sender_id, content, status)
                    VALUES (:cid, :sid, :content, :status)
                    RETURNING id, created_at
                    """,
                    {
                        "cid": conversation_id,
                        "sid": user_id,
                        "content": content,
                        "status": status,
                    },
                )

                payload = {
                    "type": "message",
                    "message_id": row["id"],
                    "conversation_id": conversation_id,
                    "sender_id": user_id,
                    "sender_username": username,
                    "content": content,
                    "status": status,
                    "created_at": row["created_at"].isoformat(),
                }

                # Send to recipient if online
                await manager.send(recipient_id, payload)

                # Echo back to sender to confirm + get message_id
                await manager.send(user_id, payload)

            # ── Typing indicator ────────────────────────────
            elif msg_type == "typing":
                conversation_id = data.get("conversation_id")
                is_typing = data.get("is_typing", False)

                if not conversation_id:
                    continue

                conversation = await database.fetch_one(
                    "SELECT * FROM conversations WHERE id = :cid",
                    {"cid": conversation_id},
                )
                if not conversation:
                    continue

                recipient_id = (
                    conversation["participant_2"]
                    if conversation["participant_1"] == user_id
                    else conversation["participant_1"]
                )

                await manager.send(recipient_id, {
                    "type": "typing",
                    "conversation_id": conversation_id,
                    "username": username,
                    "is_typing": is_typing,
                })

            # ── Read receipt ────────────────────────────────
            elif msg_type == "read":
                conversation_id = data.get("conversation_id")

                if not conversation_id:
                    continue

                # Mark all unread messages from the other person as read
                await database.execute(
                    """
                    UPDATE messages
                    SET status = 'read'
                    WHERE conversation_id = :cid
                      AND status != 'read'
                      AND sender_id != :uid
                    """,
                    {"cid": conversation_id, "uid": user_id},
                )

                conversation = await database.fetch_one(
                    "SELECT * FROM conversations WHERE id = :cid",
                    {"cid": conversation_id},
                )
                if not conversation:
                    continue

                recipient_id = (
                    conversation["participant_2"]
                    if conversation["participant_1"] == user_id
                    else conversation["participant_1"]
                )

                # Notify the other person their messages were seen
                await manager.send(recipient_id, {
                    "type": "read_receipt",
                    "conversation_id": conversation_id,
                    "read_by": username,
                })

    except WebSocketDisconnect:
        manager.disconnect(user_id)