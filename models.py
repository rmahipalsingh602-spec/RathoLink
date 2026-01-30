from sqlalchemy import Column, Integer, String, Boolean, DateTime
from database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # Google se aane wali unique ID
    google_id = Column(String, unique=True, index=True)

    email = Column(String, unique=True, index=True)
    name = Column(String)
    picture = Column(String)

    verified_email = Column(Boolean, default=False)

    # ================= ADDED (NOTHING REMOVED) =================

    # Google refresh token (long-term access ke liye)
    refresh_token = Column(String, nullable=True)

    # Record timestamps (future analytics / investor-ready)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
