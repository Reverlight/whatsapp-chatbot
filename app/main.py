"""
WhatsApp webhook — main entry point.

Flow:
1. GET / — Meta webhook verification
2. POST / — Incoming messages routed through Redis-backed state machine
3. Admin replies — admin prefixes their reply with the customer phone number:
       380671234567 Hey, your table is confirmed!
   The bot strips the prefix and forwards the rest to that customer.
"""

import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from app import settings
from app.db import async_sessionmaker, engine
from app.handlers import HANDLERS
from app.models import Base
from fastapi.middleware.cors import CORSMiddleware
from app.redis_client import get_or_create_session, save_session
from app.senders import send_admin_reply_to_client, send_main_menu
from app.tables_router import router as tables_router
from app.reservations_router import router as reservations_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tables_router)
app.include_router(reservations_router)

# ── Webhook verification (GET) ────────────────────────────────────────────────

@app.get("/")
async def verify(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == settings.VERIFY_TOKEN:
        return Response(content=params.get("hub.challenge"))
    return Response(status_code=403)


# ── Incoming messages (POST) ──────────────────────────────────────────────────

@app.post("/")
async def receive(request: Request):
    signature = request.headers.get("X-Hub-Signature-256", "")
    body = await request.body()

    if not _verify_signature(body, signature):
        return Response(status_code=403)

    payload = json.loads(body)

    try:
        value = payload["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError):
        return {"status": "ok"}

    if "messages" not in value:
        return {"status": "ok"}

    message = value["messages"][0]
    phone: str = message["from"]
    text: str | None = _parse_text(message)

    if not text:
        return {"status": "ok"}

    await _route(phone, text)
    return {"status": "ok"}


# ── Message parser ────────────────────────────────────────────────────────────

def _parse_text(message: dict) -> str | None:
    if message["type"] == "text":
        return message["text"]["body"].strip()

    if message["type"] == "interactive":
        interactive = message["interactive"]
        if interactive["type"] == "list_reply":
            return interactive["list_reply"]["id"]
        if interactive["type"] == "button_reply":
            return interactive["button_reply"]["id"]

    return None


# ── Router ────────────────────────────────────────────────────────────────────

async def _route(phone: str, text: str) -> None:
    if _is_admin(phone):
        customer_phone = _extract_customer_phone(text)
        if customer_phone:
            reply_body = _strip_phone_prefix(text)
            send_admin_reply_to_client(customer_phone, phone, reply_body)
        return

    session = await get_or_create_session(phone)

    if text.strip().lower() == "back":
        from app.redis_client import go_back
        from app.handlers import _render_state
        go_back(session)
        await save_session(phone, session)
        _render_state(phone, session)
        return

    state = session.get("state", "MAIN_MENU")
    handler = HANDLERS.get(state)

    if handler is None:
        logger.warning(f"Unknown state '{state}' for {phone}, resetting to MAIN_MENU")
        session["state"] = "MAIN_MENU"
        send_main_menu(phone)
        await save_session(phone, session)
        return

    async with async_sessionmaker() as db:
        await handler(phone, session, text, db)

    await save_session(phone, session)


# ── Admin helpers ─────────────────────────────────────────────────────────────

def _is_admin(phone: str) -> bool:
    return phone.replace("+", "") in [a.replace("+", "") for a in settings.ADMIN_PHONES]


def _extract_customer_phone(text: str) -> str | None:
    """Admin reply format: '380671234567 Their reply here'"""
    first = text.strip().split()[0]
    digits = first.lstrip("+")
    return digits if digits.isdigit() and 7 <= len(digits) <= 15 else None


def _strip_phone_prefix(text: str) -> str:
    parts = text.strip().split(None, 1)
    return parts[1].strip() if len(parts) > 1 else text


# ── Signature verification ────────────────────────────────────────────────────

def _verify_signature(payload: bytes, signature: str) -> bool:
    if not settings.APP_SECRET:
        return True  # skip in local dev if secret not set
    expected = hmac.new(
        settings.APP_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)