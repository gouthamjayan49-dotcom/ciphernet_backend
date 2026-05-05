from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
###################################
# 1. ALLOWED_ORIGINS: Converts the string into a list for the CORS middleware
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", 
    "https://shadow-one-alpha.vercel.app,http://localhost:3000"
).split(",")

# 2. ENVIRONMENT: Helps the app know if it's on your laptop or the cloud[cite: 7]
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")