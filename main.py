import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from pydantic import BaseModel

app = FastAPI()

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

class AuthRequest(BaseModel):
    email: str
    password: str
    full_name: str = "User"

@app.get("/")
def read_root():
    return {"status": "Backend running"}

# Mock authentication endpoints so frontend auth.js works smoothly
@app.post("/api/register")
@app.post("/api/login")
def mock_auth(req: AuthRequest):
    return {
        "token": "mock_token_12345",
        "user": {
            "id": "1",
            "full_name": req.full_name,
            "email": req.email
        }
    }

@app.post("/api/chat")
def chat(req: ChatRequest):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured in Railway environment variables.")

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=req.message,
        )
        return {"reply": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
