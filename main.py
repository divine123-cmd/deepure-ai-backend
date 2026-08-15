import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "deepure_secret_key_change_this_later")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

app = FastAPI(title="Deepure AI Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
os.makedirs(DATA_DIR, exist_ok=True)

def load_json(file_path, default=None):
    if default is None:
        default = []
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            json.dump(default, f)
        return default
    with open(file_path, "r") as f:
        return json.load(f)

def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    marketing_consent: bool = False

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ChatRequest(BaseModel):
    message: str
    mode: str = "simple"
    conversation_id: Optional[str] = None

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    users = load_json(USERS_FILE)
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

SYSTEM_PROMPT = """You are Deepure AI, a helpful, intelligent and patient AI assistant.

Your goal is to make difficult things easy to understand.

Always:
1. Understand the user's question first.
2. Give the direct answer.
3. Explain the answer clearly.
4. Break difficult ideas into smaller parts.
5. Use simple English unless the user requests advanced language.
6. Give examples where useful.
7. Use headings and bullet points when they improve readability.
8. Never intentionally give false information.
9. If you are uncertain, clearly say so.
10. Do not make up sources, facts, statistics or quotations.
11. Be respectful and encouraging.

When the user asks to learn something, teach rather than simply giving the final answer.
For mathematical or scientific problems, show the important steps.
For coding questions, explain what the code does and provide a practical solution."""

MODE_INSTRUCTIONS = {
    "simple": "Explain like you are teaching a complete beginner. Use very simple language.",
    "detailed": "Give a deeper explanation with examples and extra context.",
    "study": "Teach step by step. At the end ask 1 short practice question.",
    "coding": "Focus on clear code examples and explanations.",
    "creative": "Help with writing, ideas and creative thinking."
}

def generate_ai_reply(message: str, mode: str = "simple") -> str:
    if not GOOGLE_API_KEY:
        return "Error: Google API key is missing. Please add GOOGLE_API_KEY in the environment variables."

    mode_instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["simple"])
    full_prompt = f"{SYSTEM_PROMPT}\n\nCurrent mode: {mode_instruction}\n\nUser question: {message}"

    try:
        model = genai.GenerativeModel("gemini-1.5-flash-latest")
        response = model.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=2048,
            )
        )
        return response.text
    except Exception as e:
        return f"Sorry, I had a problem generating a reply. Please try again.\n\nError: {str(e)}"

@app.get("/")
def home():
    return {
        "status": "Deepure AI Backend is running",
        "ai": "Google Gemini"
    }

@app.post("/api/auth/register")
def register(data: RegisterRequest):
    users = load_json(USERS_FILE)

    if any(u["email"] == data.email.lower() for u in users):
        raise HTTPException(status_code=400, detail="Email already registered")

    if len(data.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    new_user = {
        "id": str(uuid.uuid4()),
        "full_name": data.full_name,
        "email": data.email.lower(),
        "password_hash": hash_password(data.password),
        "marketing_consent": data.marketing_consent,
        "created_at": datetime.utcnow().isoformat(),
        "last_login": datetime.utcnow().isoformat()
    }

    users.append(new_user)
    save_json(USERS_FILE, users)

    token = create_access_token({"sub": new_user["id"]})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": new_user["id"],
            "full_name": new_user["full_name"],
            "email": new_user["email"]
        }
    }

@app.post("/api/auth/login")
def login(data: LoginRequest):
    users = load_json(USERS_FILE)
    user = next((u for u in users if u["email"] == data.email.lower()), None)

    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user["last_login"] = datetime.utcnow().isoformat()
    save_json(USERS_FILE, users)

    token = create_access_token({"sub": user["id"]})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"]
        }
    }

@app.post("/api/chat")
def chat(data: ChatRequest, current_user: dict = Depends(get_current_user)):
    if not data.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    reply = generate_ai_reply(data.message, data.mode)

    return {
        "reply": reply,
        "mode": data.mode,
        "conversation_id": data.conversation_id
    }

@app.get("/api/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "full_name": current_user["full_name"],
        "email": current_user["email"]
}
