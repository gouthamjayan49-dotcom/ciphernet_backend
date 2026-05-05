from fastapi import FastAPI 
from fastapi.middleware.cors import CORSMiddleware 
from core.database import database 
from routers import auth, contacts, messages, websocket

app = FastAPI(title="CipherNet API") #creates an object of FastAPI class

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,              
    allow_credentials=True,           
    allow_methods=["*"],              
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

#includes the files in the router folder
app.include_router(auth.router,     prefix="/auth",     tags=["Auth"])
app.include_router(contacts.router, prefix="/contacts", tags=["Contacts"])
app.include_router(messages.router, prefix="/messages", tags=["Messages"])
app.include_router(websocket.router,                    tags=["WebSocket"])

@app.get("/")
async def read_root():
    return {"message": "CipherNet backend is alive!"}