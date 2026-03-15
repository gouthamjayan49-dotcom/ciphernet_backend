from fastapi import FastAPI
from core.database import database
from routers import auth

app = FastAPI()

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

app.include_router(auth.router, prefix="/auth")

@app.get("/")
async def read_root():
    return {"message": "CipherNet backend is alive!"}