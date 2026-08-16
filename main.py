import os
import jwt
import datetime
import requests
from bottle import Bottle, request, response, run
from passlib.context import CryptContext

app = Bottle()

# ============================================
# CONFIGURATION
# ============================================
SECRET_KEY = os.environ.get("SECRET_KEY", "your-fallback-secret-key")
ALGORITHM = "HS256"

# Fetch API key securely from environment variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6LCaydyEL0SpFOHrXlFgg4IRZeSPtERlGi_ax0kIvYijQ")

# Password hashing setup
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# In-memory database
users_db = {}

# ============================================
# CORS MIDDLEWARE
# ============================================
@app.hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, Authorization'

@app.route('/<path:path>', method='OPTIONS')
def options_handler(path):
    return {}

# ============================================
# AUTH HELPERS
# ============================================
def create_token(email, user_id):
    payload = {
        "sub": email,
        "id": user_id,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user():
    auth_header = request.get_header('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ')[1]
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None

# ============================================
# API ENDPOINTS
# ============================================

@app.get('/')
def root():
    return {"status": "Backend running successfully"}

# REGISTER (Handles both /api/register and /api/auth/register)
@app.post('/api/register')
@app.post('/api/auth/register')
def register():
    data = request.json or {}
    email = data.get('email')
    password = data.get('password')
    full_name = data.get('full_name', 'User')

    if not email or not password:
        response.status = 400
        return {"detail": "Email and password are required"}

    if email in users_db:
        response.status = 400
        return {"detail": "Account with this email already exists"}

    user_id = f"user_{len(users_db) + 1}"
    users_db[email] = {
        "id": user_id,
        "full_name": full_name,
        "email": email,
        "password": pwd_context.hash(password)
    }

    token = create_token(email, user_id)
    return {
        "access_token": token,
        "token": token,
        "user": {"id": user_id, "full_name": full_name, "email": email}
    }

# LOGIN (Handles both /api/login and /api/auth/login)
@app.post('/api/login')
@app.post('/api/auth/login')
def login():
    data = request.json or {}
    email = data.get('email')
    password = data.get('password')

    user = users_db.get(email)
    if not user or not pwd_context.verify(password, user["password"]):
        response.status = 400
        return {"detail": "Invalid email or password"}

    token = create_token(email, user["id"])
    return {
        "access_token": token,
        "token": token,
        "user": {"id": user["id"], "full_name": user["full_name"], "email": email}
    }

# CHAT ENDPOINT
@app.post('/api/chat')
def chat():
    user = get_current_user()
    if not user:
        response.status = 401
        return {"detail": "Unauthorized"}

    data = request.json or {}
    message = data.get('message', '')

    if not message:
        response.status = 400
        return {"detail": "Message is required"}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": message
                    }
                ]
            }
        ]
    }

    res = requests.post(url, json=payload, headers=headers)
    
    if res.status_code != 200:
        print("Gemini API Error details:", res.text)
        response.status = res.status_code
        return {"detail": f"AI request failed with status {res.status_code}"}

    res_data = res.json()
    ai_reply = res_data["candidates"][0]["content"]["parts"][0]["text"]
    return {"reply": ai_reply}

# ============================================
# SERVER STARTUP
# ============================================
if __name__ == '__main__':
    # Cloud providers pass the PORT environment variable dynamically
    port = int(os.environ.get("PORT", 8000))
    run(app, host='0.0.0.0', port=port)
