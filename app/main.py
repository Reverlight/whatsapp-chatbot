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

from app.modules.helpers import (
    _extract_customer_phone,
    _is_admin,
    _parse_text,
    _route,
    _strip_phone_prefix,
    _verify_signature,
)
from fastapi import FastAPI, Request, Response

from app import settings
from app.db import async_sessionmaker, engine
from app.modules.handlers import HANDLERS
from app.models import Base
from fastapi.middleware.cors import CORSMiddleware
from app.routers.tables_router import router as tables_router
from app.routers.reservations_router import router as reservations_router
from app.routers.menu_router import router as menu_router

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
app.include_router(menu_router)


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
