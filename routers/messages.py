from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel
from core.database import database
from core.security import get_current_user

router=APIRouter()

class MessageRequest(BaseModel):
    conversation_id: int
    content: str

class ConversationRequest(BaseModel):
    username: str

@router.get("/conversations")
async def get_conversations(current_user: str=Depends(get_current_user)):
    conversations=await database.fetch_all(
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
            ) AS unread_count
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
    request:ConversationRequest,
    current_user: str = Depends(get_current_user),
):
if request.username == current_user:
    raise HTTPException(status_code=400,detail="cannot start a conversation with yourself!")
    target = await database.fetch_one(
        "SELECT id FROM users WHERE username = :username",
        {"username": request.username},
        
    )
    if not target:
        raise HTTPException(status_code=404,detail="User not found!")

        me =  await database.fetch_one(
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

    