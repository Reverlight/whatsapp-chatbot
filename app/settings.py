import os
from dotenv import load_dotenv

load_dotenv()

# --- WhatsApp ---
APP_SECRET = os.getenv("WHATSAPP_SECRET", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "")
ADMIN_PHONES: list[str] = [
    p.strip() for p in os.getenv("ADMIN_PHONES", "").split(",") if p.strip()
]

# --- Postgres ---
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_DB = os.getenv("POSTGRES_DB", "mydb")

SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true"
SQLALCHEMY_DATABASE_URL = (
    f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)


TEST_POSTGRES_DB = os.getenv("TEST_POSTGRES_DB")
TEST_POSTGRES_PORT = os.getenv("TEST_POSTGRES_PORT")
TEST_POSTGRES_HOST = os.getenv("TEST_POSTGRES_HOST")
TEST_POSTGRES_USER = os.getenv("TEST_POSTGRES_USER")
TEST_POSTGRES_PASSWORD = os.getenv("TEST_POSTGRES_PASSWORD")
TEST_DATABASE_URL = f"postgresql+psycopg2://{TEST_POSTGRES_USER}:{TEST_POSTGRES_PASSWORD}@{TEST_POSTGRES_HOST}:{TEST_POSTGRES_PORT}/{TEST_POSTGRES_DB}"
TEST_SQLALCHEMY_DATABASE_URL = f"postgresql+asyncpg://{TEST_POSTGRES_USER}:{TEST_POSTGRES_PASSWORD}@{TEST_POSTGRES_HOST}:{TEST_POSTGRES_PORT}/{TEST_POSTGRES_DB}"


# --- Redis ---
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# --- OpenAI ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# --- Restaurant config ---
RESTAURANT_NAME = os.getenv("RESTAURANT_NAME", "Mario's")
RESTAURANT_INFO = os.getenv(
    "RESTAURANT_INFO",
    "📍 123 Main St\n🕐 Mon-Sun 10:00–22:00\n📞 +380671234567\n📧 mario@restaurant.com",
)
MENU_URL = os.getenv("MENU_URL", "https://example.com/menu")

# --- Reservation config ---
# How many seats are available per slot
RESERVATION_CAPACITY = int(os.getenv("RESERVATION_CAPACITY", "20"))
# Comma-separated weekday numbers (0=Mon … 6=Sun) when restaurant is open
RESERVATION_OPEN_DAYS: list[int] = [
    int(d.strip())
    for d in os.getenv("RESERVATION_OPEN_DAYS", "0,1,2,3,4,5,6").split(",")
    if d.strip()
]
# Max advance days a reservation can be made
RESERVATION_MAX_ADVANCE_DAYS = int(os.getenv("RESERVATION_MAX_ADVANCE_DAYS", "30"))

# --- CORS ---
CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
