from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.database import database
from core.security import hash_password, verify_password, create_access_token

router = APIRouter()

# What data we expect from user
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

# Register endpoint
@router.post("/register")
async def register(request: RegisterRequest):
    # Step 1 - check if username already exists
    existing_user = await database.fetch_one(
        "SELECT id FROM users WHERE username = :username",
        {"username": request.username}
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken!")
    
    # Step 2 - hash the password
    hashed = hash_password(request.password)
    
    # Step 3 - save to database
    await database.execute(
        "INSERT INTO users (username, password) VALUES (:username, :password)",
        {"username": request.username, "password": hashed}
    )
    
    return {"message": "Account created successfully!"}

# Login endpoint
@router.post("/login")
async def login(request: LoginRequest):
    # Step 1 - check if user exists
    user = await database.fetch_one(
        "SELECT * FROM users WHERE username = :username",
        {"username": request.username}
    )
    if not user:
        raise HTTPException(status_code=400, detail="Username not found!")
    
    # Step 2 - verify password
    if not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=400, detail="Wrong password!")
    
    # Step 3 - create JWT token
    token = create_access_token({"username": user["username"]})
    
    return {"access_token": token, "token_type": "bearer"}