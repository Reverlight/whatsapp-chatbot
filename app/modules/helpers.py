import hashlib
import hmac
import logging

from app import settings
from app.modules.handlers import HANDLERS
from app.modules.redis_client import get_or_create_session, save_session
from app.senders import send_admin_reply_to_client, send_main_menu
from app.db import async_sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


async def _route(phone: str, text: str) -> None:
    # Admin reply format: "380671234567 message here" — forward to customer
    if _is_admin(phone):
        customer_phone = _extract_customer_phone(text)
        if customer_phone:
            reply_body = _strip_phone_prefix(text)
            send_admin_reply_to_client(customer_phone, phone, reply_body)
            return

    # Normal flow — admins also go through the state machine as regular users
    session = await get_or_create_session(phone)

    if text.strip().lower() == "back":
        from app.modules.redis_client import go_back
        from app.modules.handlers import _render_state

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


def _verify_signature(payload: bytes, signature: str) -> bool:
    if not settings.APP_SECRET:
        return True  # skip in local dev if secret not set
    expected = hmac.new(
        settings.APP_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
