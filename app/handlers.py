"""
State machine handlers.

Each handler receives (phone, session, text) and is responsible for:
1. Reacting to the user's input
2. Mutating session state if navigating
3. Sending the appropriate WhatsApp message(s)

Handlers do NOT save the session — that is done by the router after the
handler returns, so we only write to Redis once per request.
"""

import datetime
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app import settings
from app.ai_service import get_ai_suggestion
from app.redis_client import go_back, go_deeper
from app.reservation_service import (
    ReservationError,
    cancel_reservation,
    create_reservation,
    find_free_table,
    get_active_reservation,
    validate_date,
)
from app.senders import (
    forward_to_admins,
    send_cancel_reservation_menu,
    send_contact_menu,
    send_main_menu,
    send_reservation_confirm,
    send_reservation_date_prompt,
    send_reservation_end_time_prompt,
    send_reservation_guests_prompt,
    send_reservation_name_prompt,
    send_reservation_time_prompt,
    send_text,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_back(text: str) -> bool:
    return text.strip().lower() == "back"


def _render_state(phone: str, session: dict) -> None:
    """Re-render the current state's entry menu (used after go_back)."""
    renderers = {
        "MAIN_MENU": lambda: send_main_menu(phone),
        "CONTACT":   lambda: send_contact_menu(phone),
        "RESERVATION": lambda: send_reservation_date_prompt(phone),
    }
    fn = renderers.get(session["state"])
    if fn:
        fn()
    else:
        send_main_menu(phone)


# ---------------------------------------------------------------------------
# MAIN_MENU
# ---------------------------------------------------------------------------

async def handle_main_menu(phone: str, session: dict, text: str, db: AsyncSession) -> None:
    if text == "show_menu":
        send_text(phone, f"🍽 Here's our full menu:\n{settings.MENU_URL}")

    elif text == "info":
        send_text(phone, f"ℹ️ *{settings.RESTAURANT_NAME}*\n\n{settings.RESTAURANT_INFO}")

    elif text == "contact":
        go_deeper(session, "CONTACT")
        send_contact_menu(phone)

    elif text == "reservation":
        go_deeper(session, "RESERVATION")
        send_reservation_date_prompt(phone)

    elif text == "suggestions":
        go_deeper(session, "AI_SUGGESTIONS")
        send_text(
            phone,
            "🤖 *AI Menu Assistant*\n\n"
            "Hi! I can help you pick the perfect dish.\n"
            "Ask me anything about our menu — dietary options, popular dishes, pairings...\n\n"
            "Type *back* to return to the main menu.",
        )

    else:
        send_main_menu(phone)


# ---------------------------------------------------------------------------
# CONTACT
# ---------------------------------------------------------------------------

async def handle_contact(phone: str, session: dict, text: str, db: AsyncSession) -> None:
    if _is_back(text):
        go_back(session)
        _render_state(phone, session)
        return

    if text == "chat_admin":
        go_deeper(session, "CONTACT_CHAT")
        send_text(
            phone,
            "💬 *You're now connected to our support team.*\n\n"
            "Type your message and we'll get back to you as soon as possible.\n\n"
            "Type *back* to return.",
        )

    elif text == "get_info":
        send_text(phone, f"📋 *Contact Information*\n\n{settings.RESTAURANT_INFO}")

    else:
        send_contact_menu(phone)


# ---------------------------------------------------------------------------
# CONTACT_CHAT
# ---------------------------------------------------------------------------

async def handle_contact_chat(phone: str, session: dict, text: str, db: AsyncSession) -> None:
    if _is_back(text):
        go_back(session)
        _render_state(phone, session)
        return

    forward_to_admins(phone, text)
    send_text(
        phone,
        "✅ Your message has been sent! Our team will reply shortly.\n\n"
        "You can keep sending messages — type *back* when done.",
    )


# ── RESERVATION step handlers ─────────────────────────────────────────────────

async def _reservation_date(phone, ctx, text, db, session):
    existing = await get_active_reservation(db, phone)
    if existing:
        send_cancel_reservation_menu(phone, _fmt(existing.reservation_date), existing.guests)
        ctx.update(step="has_existing", existing_id=existing.id)
        return

    date = _parse_date(phone, text)
    if date is None:
        return

    ctx.update(date=date.isoformat(), step="time")
    send_reservation_time_prompt(phone, _fmt(date))


async def _reservation_time(phone, ctx, text, db, session):
    if _is_back(text):
        ctx["step"] = "date"
        send_reservation_date_prompt(phone)
        return

    start_time = _parse_time(phone, text)
    if start_time is None:
        return

    ctx.update(start_time=start_time.isoformat(), step="end_time")
    send_reservation_end_time_prompt(phone, start_time)


async def _reservation_end_time(phone, ctx, text, db, session):
    if _is_back(text):
        ctx["step"] = "time"
        send_reservation_time_prompt(phone, ctx["date"])
        return

    end_time = _parse_time(phone, text)
    if end_time is None:
        return

    start_time = datetime.time.fromisoformat(ctx["start_time"])
    if end_time <= start_time:
        send_text(phone, "⚠️ End time must be after start time.")
        return

    ctx.update(end_time=end_time.isoformat(), step="guests")
    send_reservation_guests_prompt(phone)


async def _reservation_guests(phone, ctx, text, db, session):
    if _is_back(text):
        ctx["step"] = "end_time"
        send_reservation_end_time_prompt(phone, datetime.time.fromisoformat(ctx["start_time"]))
        return

    guests = _parse_guests(phone, text)
    if guests is None:
        return

    # Check table availability before proceeding — no point asking for a name if no table fits
    try:
        await find_free_table(
            db,
            date=datetime.date.fromisoformat(ctx["date"]),
            start_time=datetime.time.fromisoformat(ctx["start_time"]),
            end_time=datetime.time.fromisoformat(ctx["end_time"]),
            guests=guests,
        )
    except ReservationError as e:
        send_text(phone, str(e))
        return

    ctx.update(guests=guests, step="guest_name")
    send_reservation_name_prompt(phone)


async def _reservation_guest_name(phone, ctx, text, db, session):
    if _is_back(text):
        ctx["step"] = "guests"
        send_reservation_guests_prompt(phone)
        return

    name = text.strip()
    if not name:
        send_text(phone, "⚠️ Please enter your name.")
        return

    ctx.update(guest_name=name, step="confirm")
    send_reservation_confirm(
        phone,
        date=ctx["date"],
        start_time=ctx["start_time"],
        end_time=ctx["end_time"],
        guests=ctx["guests"],
        guest_name=name,
    )


async def _reservation_confirm(phone, ctx, text, db, session):
    if _is_back(text):
        ctx["step"] = "guest_name"
        send_reservation_name_prompt(phone)
        return

    if text != "confirm_yes":
        send_reservation_confirm(
            phone,
            date=ctx["date"],
            start_time=ctx["start_time"],
            end_time=ctx["end_time"],
            guests=ctx["guests"],
            guest_name=ctx["guest_name"],
        )
        return

    try:
        reservation, table = await create_reservation(
            db,
            phone=phone,
            guest_name=ctx["guest_name"],
            date=datetime.date.fromisoformat(ctx["date"]),
            start_time=datetime.time.fromisoformat(ctx["start_time"]),
            end_time=datetime.time.fromisoformat(ctx["end_time"]),
            guests=ctx["guests"],
        )
        send_text(phone, _confirmed_message(reservation, table))
        go_back(session)
    except ReservationError as e:
        send_text(phone, str(e))
        ctx["step"] = "date"
        send_reservation_date_prompt(phone)


async def _reservation_has_existing(phone, ctx, text, db, session):
    if text == "cancel_reservation":
        existing = await get_active_reservation(db, phone)
        if existing:
            await cancel_reservation(db, existing)
        ctx.clear()
        ctx["step"] = "date"
        send_text(phone, "✅ Reservation cancelled. Let's book a new one!")
        send_reservation_date_prompt(phone)
    elif _is_back(text):
        go_back(session)
        _render_state(phone, session)
    else:
        existing = await get_active_reservation(db, phone)
        if existing:
            send_cancel_reservation_menu(phone, _fmt(existing.reservation_date), existing.guests)


# ── Parsers ───────────────────────────────────────────────────────────────────

def _parse_date(phone: str, text: str) -> datetime.date | None:
    try:
        date = datetime.datetime.strptime(text.strip(), "%d.%m.%Y").date()
        validate_date(date)
        return date
    except ValueError:
        send_text(phone, "⚠️ Invalid format. Please use DD.MM.YYYY (e.g. 25.03.2025).")
    except ReservationError as e:
        send_text(phone, str(e))
    return None


def _parse_time(phone: str, text: str) -> datetime.time | None:
    for fmt in ("%H:%M", "%H%M"):
        try:
            return datetime.datetime.strptime(text.strip(), fmt).time()
        except ValueError:
            continue
    send_text(phone, "⚠️ Invalid time. Please use HH:MM (e.g. 19:00).")
    return None


def _parse_guests(phone: str, text: str) -> int | None:
    try:
        guests = int(text.strip())
        if 1 <= guests <= 20:
            return guests
    except ValueError:
        pass
    send_text(phone, "⚠️ Please enter a number between 1 and 20.")
    return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(date: datetime.date) -> str:
    return date.strftime("%d.%m.%Y")


def _confirmed_message(r, table) -> str:
    return (
        f"🎉 *Reservation Confirmed!*\n\n"
        f"📅 {r.reservation_date.strftime('%d.%m.%Y')}"
        f"  🕐 {r.start_time.strftime('%H:%M')} — {r.end_time.strftime('%H:%M')}\n"
        f"👤 {r.guest_name}  👥 {r.guests} guests\n"
        f"🪑 Table: {table.name}\n\n"
        f"We look forward to seeing you! 🍽\n\n"
        f"Type *back* to return to the main menu."
    )


# ── RESERVATION dispatcher (defined after step functions so names are resolved) ──

RESERVATION_STEP_HANDLERS = {
    "date":         _reservation_date,
    "time":         _reservation_time,
    "end_time":     _reservation_end_time,
    "guests":       _reservation_guests,
    "guest_name":   _reservation_guest_name,
    "confirm":      _reservation_confirm,
    "has_existing": _reservation_has_existing,
}


async def handle_reservation(phone: str, session: dict, text: str, db: AsyncSession) -> None:
    ctx = session.setdefault("current_context", {})
    step = ctx.get("step", "date")
    handler = RESERVATION_STEP_HANDLERS.get(step)
    if handler:
        await handler(phone, ctx, text, db, session)


# ---------------------------------------------------------------------------
# AI_SUGGESTIONS
# ---------------------------------------------------------------------------

async def handle_ai_suggestions(phone: str, session: dict, text: str, db: AsyncSession) -> None:
    if _is_back(text):
        go_back(session)
        _render_state(phone, session)
        return

    history = session.get("ai_history", [])

    try:
        reply, updated_history = await get_ai_suggestion(history, text)
        session["ai_history"] = updated_history
        send_text(phone, reply)
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        send_text(phone, "⚠️ Sorry, the AI assistant is temporarily unavailable. Please try again later.")


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

HANDLERS = {
    "MAIN_MENU":      handle_main_menu,
    "CONTACT":        handle_contact,
    "CONTACT_CHAT":   handle_contact_chat,
    "RESERVATION":    handle_reservation,
    "AI_SUGGESTIONS": handle_ai_suggestions,
}