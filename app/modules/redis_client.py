"""
Redis-backed session store.

Key format : client__(phone_number)
Value format: JSON-encoded session dict

Session schema:
{
    "state": "MAIN_MENU",
    "stack": [{"state": "...", "context": {...}}, ...],
    "current_context": {},
    "ai_history": [{"role": "user"|"assistant", "content": "..."}, ...]
}

Stack works like a navigation history — push on go_deeper, pop on go_back.
"""

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app import settings

logger = logging.getLogger(__name__)

# Module-level client — initialised once at startup
_redis: aioredis.Redis | None = None

SESSION_TTL = 60 * 60 * 6  # 6 hours of inactivity before session expires


def _key(phone: str) -> str:
    return f"client__{phone}"


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            decode_responses=True,
        )
    return _redis


# ---------------------------------------------------------------------------
# Low-level set / get / delete
# ---------------------------------------------------------------------------


async def set_state(phone: str, session: dict) -> None:
    r = await get_redis()
    await r.set(_key(phone), json.dumps(session), ex=SESSION_TTL)


async def get_state(phone: str) -> dict | None:
    r = await get_redis()
    raw = await r.get(_key(phone))
    if raw is None:
        return None
    return json.loads(raw)


async def delete_state(phone: str) -> None:
    r = await get_redis()
    await r.delete(_key(phone))


# ---------------------------------------------------------------------------
# High-level session helpers
# ---------------------------------------------------------------------------


def _default_session() -> dict:
    return {
        "state": "MAIN_MENU",
        "stack": [],
        "current_context": {},
        "ai_history": [],
    }


async def get_or_create_session(phone: str) -> dict:
    session = await get_state(phone)
    if session is None:
        session = _default_session()
        await set_state(phone, session)
    return session


async def save_session(phone: str, session: dict) -> None:
    await set_state(phone, session)


async def reset_session(phone: str) -> dict:
    session = _default_session()
    await set_state(phone, session)
    return session


# ---------------------------------------------------------------------------
# Navigation helpers (operate in-memory; caller must call save_session)
# ---------------------------------------------------------------------------


def go_deeper(session: dict, next_state: str, context: dict | None = None) -> None:
    session["stack"].append(
        {
            "state": session["state"],
            "context": session.get("current_context", {}),
        }
    )
    session["state"] = next_state
    session["current_context"] = context or {}
    # Clear AI history when entering a new flow
    if next_state != "AI_SUGGESTIONS":
        session["ai_history"] = []


def go_back(session: dict) -> None:
    if session["stack"]:
        previous = session["stack"].pop()
        session["state"] = previous["state"]
        session["current_context"] = previous["context"]
    else:
        session["state"] = "MAIN_MENU"
        session["current_context"] = {}
    session["ai_history"] = []


def current_state(session: dict) -> str:
    return session.get("state", "MAIN_MENU")
