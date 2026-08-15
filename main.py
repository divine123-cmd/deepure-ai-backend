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
SECRET_KEY = "your-secret-key-change-this-in-production"
ALGORITHM = "HS256"

# Your API Key from Google AI Studio
GEMINI_API_KEY = "AQ.Ab8RN6LCaydyEL0SpFOHrXlFgg4IRZeSPtERlGi_ax0kIvYijQ"

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
        response.status = 401
        return None
    token = auth_header.split(' ')[1]
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        response.status = 401
        return None

# ============================================
# API ENDPOINTS
# ============================================

# REGISTER
@app.post('/api/auth/register')
def register():
    data = request.json or {}
    email = data.get('email')
    password = data.get('password')
    full_name = data.get('full_name', '')

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
        "user": {"id": user_id, "full_name": full_name, "email": email}
    }

# LOGIN
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
        "user": {"id": user["id"], "full_name": user["full_name"], "email": email}
    }

# CHAT ENDPOINT (Matching your cURL command)
@app.post('/api/chat')
def chat():
    user = get_current_user()
    if not user:
        return {"detail": "Unauthorized"}

    data = request.json or {}
    message = data.get('message', '')

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
    
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY
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
    run(app, host='0.0.0.0', port=8000)
