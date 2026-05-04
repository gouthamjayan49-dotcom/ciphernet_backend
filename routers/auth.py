from fastapi import APIRouter, HTTPException,Depends,Response,Request
from pydantic import BaseModel
from core.database import database
from core.security import hash_password, verify_password, create_access_token,get_current_user

router = APIRouter()

# What data we expect from user
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class UpdateProfileRequest(BaseModel):
    about_user: str

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
async def login(request: LoginRequest, response: Response):
    user = await database.fetch_one(
        "SELECT * FROM users WHERE username = :username",
        {"username": request.username}
    )
    if not user:
        raise HTTPException(status_code=400, detail="Username not found!")
    
    if not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=400, detail="Wrong password!")
    
    token = create_access_token({"username": user["username"]})
    
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=86400
    )
    return {"message": "Logged in!", "username": user["username"]}

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out!"}


@router.get("/me")
async def get_me(current_user: str = Depends(get_current_user)):
    user = await database.fetch_one(
        "SELECT id, username, about_user, profile_pic_url FROM users WHERE username = :username",
        {"username": current_user}
    )
    return dict(user)

@router.patch("/me")
async def update_profile(request: UpdateProfileRequest, current_user: str = Depends(get_current_user)):
    await database.execute(
        "UPDATE users SET about_user = :about WHERE username = :username",
        {"about": request.about_user, "username": current_user}
    )
    return {"message": "Profile updated!"}