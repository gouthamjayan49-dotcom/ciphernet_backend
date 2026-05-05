from fastapi import APIRouter, Depends, HTTPException
from core.database import database
from core.security import get_current_user

router = APIRouter()

# Get my contacts
@router.get("/")
async def get_contacts(current_user: str = Depends(get_current_user)):
    contacts = await database.fetch_all(
        """
        SELECT u.id, u.username, u.about_user, u.profile_pic_url
        FROM contacts c
        JOIN users u ON c.contact_id = u.id
        WHERE c.owner_id = (SELECT id FROM users WHERE username = :username)
        """,
        {"username": current_user}
    )
    return contacts

# Add a contact
@router.post("/")
async def add_contact(contact_username: str, current_user: str = Depends(get_current_user)):
    user = await database.fetch_one(
        "SELECT id FROM users WHERE username = :username",
        {"username": contact_username}
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found!")
    
    await database.execute(
        """
        INSERT INTO contacts (owner_id, contact_id)
        VALUES (
            (SELECT id FROM users WHERE username = :owner),
            :contact_id
        )
        """,
        {"owner": current_user, "contact_id": user["id"]}
    )
    return {"message": "Contact added!"}

# Search users
@router.get("/search")
async def search_users(username: str, current_user: str = Depends(get_current_user)):
    users = await database.fetch_all(
        "SELECT id, username, about_user FROM users WHERE username ILIKE :username",
        {"username": f"%{username}%"}
    )
    return users

@router.patch("/nickname/{contact_username}")
async def update_nickname(contact_username: str, nickname: str, current_user: str = Depends(get_current_user)):
    await database.execute(
        """
        UPDATE contacts SET nickname = :nickname
        WHERE contact_id = (SELECT id FROM users WHERE username = :contact_username)
        AND owner_id = (SELECT id FROM users WHERE username = :username)
        """,
        {"nickname": nickname, "contact_username": contact_username, "username": current_user}
    )
    return {"message": "Nickname updated!"}

@router.get("/nickname/{contact_username}")
async def get_nickname(contact_username: str, current_user: str = Depends(get_current_user)):
    result = await database.fetch_one(
        """
        SELECT c.nickname FROM contacts c
        JOIN users u ON c.contact_id = u.id
        WHERE u.username = :contact_username
        AND c.owner_id = (SELECT id FROM users WHERE username = :username)
        """,
        {"contact_username": contact_username, "username": current_user}
    )
    return {"nickname": result["nickname"] if result else None}