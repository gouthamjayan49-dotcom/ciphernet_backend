from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel
from core.database import database
from core.security import get_current_user 

router = APIRouter()

class MessageRequest(BaseModel):
    conversation_id: int
    content: str

#get all the conversation for logged in user
@router.get("/conversations")
async def get_conversations(current_user: str=Depends(get_current_user)):
    conversations = await database.fetch_all(
        """
        SELECT c.id, 
               u1.username as participant_1,
               u2.username as participant_2
        FROM conversations c
        JOIN users u1 ON c.participant_1 = u1.id
        JOIN users u2 ON c.participant_2 = u2.id
        WHERE u1.username = :username OR u2.username = :username
        """,
        {"username": current_user}
    )
    return conversations