import os
import jwt
import datetime
import requests
from bottle import Bottle, request, response, run
from passlib.context import CryptContext

app = Bottle()

SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6LCaydyEL0SpFOHrXlFgg4IRZeSPtERlGi_ax0kIvYijQ")

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
users_db = {}

# ============================================
# CORS HEADERS (Fixes "Failed to fetch")
# ============================================
@app.hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, PUT, DELETE'
    response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, Authorization, X-Requested-With'

@app.route('/<path:path>', method='OPTIONS')
def options_handler(path=''):
    return {}

@app.route('/', method='OPTIONS')
def options_root():
    return {}

# ============================================
# API ENDPOINTS
# ============================================

@app.get('/')
def root():
    return {"status": "Backend running successfully"}

@app.post('/api/register')
@app.post('/api/auth/register')
def register():
    data = request.json or {}
    email = data.get('email')
    password = data.get('password')
    full_name = data.get('full_name', 'User')

    if not email or not password:
        response.status = 400
        return {"detail": "Email and password required"}

    user_id = f"user_{len(users_db) + 1}"
    payload = {"sub": email, "id": user_id, "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {"access_token": token, "token": token, "user": {"id": user_id, "full_name": full_name, "email": email}}

@app.post('/api/login')
@app.post('/api/auth/login')
def login():
    data = request.json or {}
    email = data.get('email', 'user@example.com')
    user_id = "user_1"
    
    payload = {"sub": email, "id": user_id, "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)}
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    return {"access_token": token, "token": token, "user": {"id": user_id, "full_name": "User", "email": email}}

@app.post('/api/chat')
def chat():
    data = request.json or {}
    message = data.get('message', '')

    if not message:
        response.status = 400
        return {"detail": "Message is required"}

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": message}]}]}

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=30)
        if res.status_code != 200:
            response.status = res.status_code
            return {"detail": f"AI error: {res.text}"}

        res_data = res.json()
        ai_reply = res_data["candidates"][0]["content"]["parts"][0]["text"]
        return {"reply": ai_reply}
    except Exception as e:
        response.status = 500
        return {"detail": str(e)}

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    run(app, host='0.0.0.0', port=port)
