from sqlalchemy.orm import Session
from models import User


# ================= BASIC =================
def get_user_by_google_id(db: Session, google_id: str):
    return db.query(User).filter(User.google_id == google_id).first()


def get_user_by_id(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()


# ================= CREATE USER =================
def create_user(db: Session, userinfo: dict, refresh_token: str = None):
    """
    New Google user ko DB me save karta hai
    """
    user = User(
        google_id=userinfo.get("id"),
        email=userinfo.get("email"),
        name=userinfo.get("name"),
        picture=userinfo.get("picture"),
        verified_email=userinfo.get("verified_email", False),
        refresh_token=refresh_token,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ================= UPDATE REFRESH TOKEN =================
def update_refresh_token(db: Session, user: User, refresh_token: str):
    """
    Agar Google naya refresh_token de, to update karta hai
    """
    if refresh_token:
        user.refresh_token = refresh_token
        db.commit()
        db.refresh(user)
    return user
