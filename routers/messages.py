from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from core.database import database
from core.security import get_current_user

router = APIRouter()


class MessageRequest(BaseModel):
    conversation_id: int
    content: str


class ConversationRequest(BaseModel):
    username: str


@router.get("/conversations")
async def get_conversations(current_user: str = Depends(get_current_user)):
    conversations = await database.fetch_all(
        """
        SELECT
            c.id,
            u1.username AS participant_1,
            u2.username AS participant_2,
            (
                SELECT content
                FROM messages m
                WHERE m.conversation_id = c.id
                ORDER BY m.created_at DESC
                LIMIT 1
            ) AS last_message,
            (
                SELECT created_at
                FROM messages m
                WHERE m.conversation_id = c.id
                ORDER BY m.created_at DESC
                LIMIT 1
            ) AS last_message_at,
            (
                SELECT COUNT(*)
                FROM messages m
                WHERE m.conversation_id = c.id
                  AND m.status != 'read'
                  AND m.sender_id != (SELECT id FROM users WHERE username = :username)
            ) AS unread_count,
            (
        SELECT ct.nickname FROM contacts ct
        WHERE ct.owner_id = (SELECT id FROM users WHERE username = :username)
        AND ct.contact_id = CASE 
            WHEN u1.username = :username THEN u2.id 
            ELSE u1.id 
        END
    ) AS nickname
        FROM conversations c
        JOIN users u1 ON c.participant_1 = u1.id
        JOIN users u2 ON c.participant_2 = u2.id
        WHERE u1.username = :username OR u2.username = :username
        ORDER BY last_message_at DESC NULLS LAST
        """,
        {"username": current_user},
    )
    return conversations


@router.post("/conversations")
async def create_or_get_conversation(
    request: ConversationRequest,
    current_user: str = Depends(get_current_user),
):
    if request.username == current_user:
        raise HTTPException(status_code=400, detail="Cannot start a conversation with yourself!")

    target = await database.fetch_one(
        "SELECT id FROM users WHERE username = :username",
        {"username": request.username},
    )
    if not target:
        raise HTTPException(status_code=404, detail="User not found!")

    me = await database.fetch_one(
        "SELECT id FROM users WHERE username = :username",
        {"username": current_user},
    )

    existing = await database.fetch_one(
        """
        SELECT id FROM conversations
        WHERE (participant_1 = :a AND participant_2 = :b)
           OR (participant_1 = :b AND participant_2 = :a)
        """,
        {"a": me["id"], "b": target["id"]},
    )
    if existing:
        return {"conversation_id": existing["id"], "created": False}

    row = await database.fetch_one(
        """
        INSERT INTO conversations (participant_1, participant_2)
        VALUES (:p1, :p2)
        RETURNING id
        """,
        {"p1": me["id"], "p2": target["id"]},
    )
    return {"conversation_id": row["id"], "created": True}


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    limit: int = 50,
    offset: int = 0,
    current_user: str = Depends(get_current_user),
):
    check = await database.fetch_one(
        """
        SELECT c.id FROM conversations c
        JOIN users u1 ON c.participant_1 = u1.id
        JOIN users u2 ON c.participant_2 = u2.id
        WHERE c.id = :cid
          AND (u1.username = :username OR u2.username = :username)
        """,
        {"cid": conversation_id, "username": current_user},
    )
    if not check:
        raise HTTPException(status_code=403, detail="Not a participant of this conversation!")

    messages = await database.fetch_all(
        """
        SELECT
            m.id,
            m.conversation_id,
            m.content,
            m.status,
            m.created_at,
            u.username AS sender_username
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE m.conversation_id = :cid
        ORDER BY m.created_at ASC
        LIMIT :limit OFFSET :offset
        """,
        {"cid": conversation_id, "limit": limit, "offset": offset},
    )

    await database.execute(
        """
        UPDATE messages
        SET status = 'read'
        WHERE conversation_id = :cid
          AND status != 'read'
          AND sender_id != (SELECT id FROM users WHERE username = :username)
        """,
        {"cid": conversation_id, "username": current_user},
    )

    return messages


@router.post("/messages")
async def send_message(
    request: MessageRequest,
    current_user: str = Depends(get_current_user),
):
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty!")

    me = await database.fetch_one(
        "SELECT id FROM users WHERE username = :username",
        {"username": current_user},
    )

    conversation = await database.fetch_one(
        """
        SELECT * FROM conversations
        WHERE id = :cid AND (participant_1 = :uid OR participant_2 = :uid)
        """,
        {"cid": request.conversation_id, "uid": me["id"]},
    )
    if not conversation:
        raise HTTPException(status_code=403, detail="Not a participant of this conversation!")

    row = await database.fetch_one(
        """
        INSERT INTO messages (conversation_id, sender_id, content, status)
        VALUES (:cid, :sid, :content, 'sent')
        RETURNING id, created_at
        """,
        {
            "cid": request.conversation_id,
            "sid": me["id"],
            "content": request.content.strip(),
        },
    )

    return {
        "message_id": row["id"],
        "conversation_id": request.conversation_id,
        "sender_username": current_user,
        "content": request.content.strip(),
        "status": "sent",
        "created_at": row["created_at"],
    }


@router.patch("/messages/{message_id}/status")
async def update_message_status(
    message_id: int,
    status: str,
    current_user: str = Depends(get_current_user),
):
    allowed = {"sent", "delivered", "read"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {allowed}")

    await database.execute(
        "UPDATE messages SET status = :status WHERE id = :id",
        {"status": status, "id": message_id},
    )
    return {"message_id": message_id, "status": status}