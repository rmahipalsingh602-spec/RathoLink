from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

import os, requests
from datetime import datetime
from dotenv import load_dotenv

from database import SessionLocal, engine
from models import Base, User
from crud import get_user_by_google_id, create_user, update_refresh_token

# ================= ENV =================
load_dotenv()

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# ================= APP =================
app = FastAPI(title="RathoLink")

app.add_middleware(
    SessionMiddleware,
    secret_key="ratholink-secret-key",
    same_site="lax",
    https_only=False  # production → True
)

# ================= DB =================
Base.metadata.create_all(bind=engine)

# ================= STATIC =================
app.mount("/static", StaticFiles(directory="../frontend"), name="static")

# ================= HELPERS =================
def refresh_access_token(user: User):
    if not user.refresh_token:
        return None

    res = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": user.refresh_token,
            "grant_type": "refresh_token",
        },
    ).json()

    return res.get("access_token")


def require_login(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None, RedirectResponse("/")
    return user_id, None

# ================= HOME =================
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <h1>RathoLink</h1>
    <p>One link for all your Google work</p>
    <a href="/auth/google"><button>Connect Google</button></a>
    """

# ================= GOOGLE LOGIN =================
@app.get("/auth/google")
def google_login():
    scope = (
        "openid email profile "
        "https://www.googleapis.com/auth/drive.readonly "
        "https://www.googleapis.com/auth/gmail.readonly "
        "https://www.googleapis.com/auth/calendar.readonly"
    )

    url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        "&response_type=code"
        f"&scope={scope}"
        "&access_type=offline"
        "&prompt=consent"
    )
    return RedirectResponse(url)

# ================= CALLBACK (FIXED) =================
@app.get("/auth/google/callback")
def google_callback(request: Request, code: str):
    token_res = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    ).json()

    access_token = token_res.get("access_token")
    refresh_token = token_res.get("refresh_token")

    userinfo = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    ).json()

    # ✅ FINAL SAFE GOOGLE ID FIX
    google_id = userinfo.get("id") or userinfo.get("sub")
    if not google_id:
        return HTMLResponse("<h1>Google Login Failed</h1>", status_code=400)

    userinfo["google_id"] = google_id

    db = SessionLocal()
    user = get_user_by_google_id(db, google_id)

    if not user:
        user = create_user(db, userinfo, refresh_token)
    elif refresh_token:
        update_refresh_token(db, user, refresh_token)

    db.close()

    request.session["user_id"] = user.id
    request.session["access_token"] = access_token

    return RedirectResponse("/dashboard")

# ================= DASHBOARD =================
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user_id, redirect = require_login(request)
    if redirect:
        return redirect

    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    db.close()

    return f"""
    <h1>Welcome, {user.name}</h1>
    <p>{user.email}</p>

    <ul>
      <li><a href="/drive">Google Drive</a></li>
      <li><a href="/gmail">Gmail Inbox</a></li>
      <li><a href="/calendar">Calendar Events</a></li>
    </ul>

    <a href="/logout">Logout</a>
    """
@app.get("/api/me")
def me(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return {}

    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    db.close()

    return {
        "name": user.name,
        "email": user.email,
        "picture": user.picture,
    }

# ================= DRIVE =================
@app.get("/drive", response_class=HTMLResponse)
def drive(request: Request):
    user_id, redirect = require_login(request)
    if redirect:
        return redirect

    db = SessionLocal()
    user = db.query(User).filter(User.id == user_id).first()

    token = request.session.get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    res = requests.get(
        "https://www.googleapis.com/drive/v3/files",
        headers=headers,
        params={"pageSize": 10, "fields": "files(name,mimeType)"}
    )

    if res.status_code == 401:
        token = refresh_access_token(user)
        request.session["access_token"] = token
        headers["Authorization"] = f"Bearer {token}"
        res = requests.get(
            "https://www.googleapis.com/drive/v3/files",
            headers=headers,
            params={"pageSize": 10, "fields": "files(name,mimeType)"}
        )

    db.close()

    files = res.json().get("files", [])
    items = "".join([f"<li>{f['name']} ({f['mimeType']})</li>" for f in files])

    return f"<h1>Drive Files</h1><ul>{items}</ul><a href='/dashboard'>Back</a>"

# ================= GMAIL =================
@app.get("/gmail", response_class=HTMLResponse)
def gmail(request: Request):
    user_id, redirect = require_login(request)
    if redirect:
        return redirect

    token = request.session.get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    res = requests.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        headers=headers,
        params={"maxResults": 10}
    )

    items = ""
    for msg in res.json().get("messages", []):
        msg_id = msg["id"]
        msg_data = requests.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}",
            headers=headers,
            params={"format": "metadata", "metadataHeaders": ["Subject", "From"]}
        ).json()

        headers_list = msg_data.get("payload", {}).get("headers", [])
        subject = next((h["value"] for h in headers_list if h["name"] == "Subject"), "No Subject")
        sender = next((h["value"] for h in headers_list if h["name"] == "From"), "Unknown")

        items += f"<li><b>{subject}</b><br>{sender}</li><br>"

    return f"<h1>Gmail Inbox</h1><ul>{items}</ul><a href='/dashboard'>Back</a>"

# ================= CALENDAR =================
@app.get("/calendar", response_class=HTMLResponse)
def calendar(request: Request):
    user_id, redirect = require_login(request)
    if redirect:
        return redirect

    token = request.session.get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    now = datetime.utcnow().isoformat() + "Z"

    res = requests.get(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers=headers,
        params={
            "maxResults": 10,
            "orderBy": "startTime",
            "singleEvents": True,
            "timeMin": now,
        }
    )

    items = ""
    for ev in res.json().get("items", []):
        start = ev.get("start", {}).get("dateTime", "")
        title = ev.get("summary", "No Title")
        items += f"<li>{title}<br>{start}</li><br>"

    return f"<h1>Calendar</h1><ul>{items}</ul><a href='/dashboard'>Back</a>"

# ================= LOGOUT =================
@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")
