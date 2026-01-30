from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ================= DATABASE CONFIG =================
DATABASE_URL = "sqlite:///./ratholink.db"

# ================= ENGINE =================
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite threading fix
    echo=False  # production me False, debugging ke liye True kar sakte ho
)

# ================= SESSION =================
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ================= BASE =================
Base = declarative_base()

# ================= OPTIONAL HELPER (ADDED, SAFE) =================
# Isko future me FastAPI dependencies me use kar sakte ho
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
