"""
All WhatsApp Cloud API send helpers.
Every function is synchronous (httpx.post) to keep things simple —
swap for httpx.AsyncClient if you move to fully async handlers.
"""

import httpx

from app import settings

_HEADERS = {
    "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


def _post(payload: dict) -> None:
    resp = httpx.post(settings.WHATSAPP_API_URL, headers=_HEADERS, json=payload)
    if resp.status_code >= 400:
        print(f"[WhatsApp API error] {resp.status_code}: {resp.text}")


# ---------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------


def send_text(phone: str, text: str) -> None:
    _post(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"body": text},
        }
    )


# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------


def send_main_menu(phone: str) -> None:
    _post(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {
                    "text": f"👋 Welcome to {settings.RESTAURANT_NAME}!\n\nHow can we help you today?"
                },
                "action": {
                    "button": "Open Menu",
                    "sections": [
                        {
                            "title": "Options",
                            "rows": [
                                {
                                    "id": "show_menu",
                                    "title": "📋 View Menu",
                                    "description": "See our full menu",
                                },
                                {
                                    "id": "reservation",
                                    "title": "📅 Reservation",
                                    "description": "Book a table",
                                },
                                {
                                    "id": "contact",
                                    "title": "💬 Contact Us",
                                    "description": "Chat with our team",
                                },
                                {
                                    "id": "suggestions",
                                    "title": "🤖 AI Suggestions",
                                    "description": "Get personalised recommendations",
                                },
                                {
                                    "id": "info",
                                    "title": "ℹ️ Restaurant Info",
                                    "description": "Address, hours & contacts",
                                },
                            ],
                        }
                    ],
                },
            },
        }
    )


def send_contact_menu(phone: str) -> None:
    _post(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "📞 How can we help?\n\nChoose an option below:"},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": "chat_admin",
                                "title": "💬 Chat with Admin",
                            },
                        },
                        {
                            "type": "reply",
                            "reply": {"id": "get_info", "title": "📋 Get Contact Info"},
                        },
                        {"type": "reply", "reply": {"id": "back", "title": "⬅️ Back"}},
                    ],
                },
            },
        }
    )


def send_reservation_date_prompt(phone: str) -> None:
    send_text(
        phone,
        "📅 *Table Reservation*\n\n"
        "Please enter the date you'd like to visit.\n"
        "Format: *DD.MM.YYYY*  (e.g. 25.03.2025)\n\n"
        "Type *back* to return.",
    )


def send_reservation_time_prompt(phone: str, date_str: str) -> None:
    send_text(
        phone,
        f"✅ Date: *{date_str}*\n\n"
        "What time would you like to arrive?\n"
        "Format: *HH:MM*  (e.g. 19:00)\n\n"
        "Type *back* to pick a different date.",
    )


def send_reservation_end_time_prompt(phone: str, start_time) -> None:
    start_str = (
        start_time.strftime("%H:%M")
        if hasattr(start_time, "strftime")
        else str(start_time)
    )
    send_text(
        phone,
        f"✅ Arrival: *{start_str}*\n\n"
        "What time will you be leaving?\n"
        "Format: *HH:MM*  (e.g. 21:00)\n\n"
        "Type *back* to change arrival time.",
    )


def send_reservation_guests_prompt(phone: str) -> None:
    send_text(
        phone,
        "👥 How many guests? (1–20)\n\n" "Type *back* to change the time.",
    )


def send_reservation_name_prompt(phone: str) -> None:
    send_text(
        phone,
        "👤 Please enter the name for the reservation.\n\n"
        "Type *back* to change the number of guests.",
    )


def send_reservation_confirm(
    phone: str,
    date: str,
    start_time: str,
    end_time: str,
    guests: int,
    guest_name: str,
) -> None:
    import datetime as dt

    # Format times nicely if they're ISO strings
    try:
        start_fmt = dt.time.fromisoformat(start_time).strftime("%H:%M")
        end_fmt = dt.time.fromisoformat(end_time).strftime("%H:%M")
        date_fmt = dt.date.fromisoformat(date).strftime("%d.%m.%Y")
    except ValueError:
        start_fmt, end_fmt, date_fmt = start_time, end_time, date

    _post(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": (
                        f"🗓 *Confirm Reservation*\n\n"
                        f"📅 {date_fmt}  🕐 {start_fmt} — {end_fmt}\n"
                        f"👤 {guest_name}  👥 {guests} guests\n\n"
                        "Shall we confirm this booking?"
                    )
                },
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": "confirm_yes", "title": "✅ Confirm"},
                        },
                        {"type": "reply", "reply": {"id": "back", "title": "✏️ Edit"}},
                    ],
                },
            },
        }
    )


def send_cancel_reservation_menu(phone: str, date_str: str, guests: int) -> None:
    _post(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": (
                        f"📅 You already have a reservation:\n\n"
                        f"*Date:* {date_str}\n"
                        f"*Guests:* {guests}\n\n"
                        "You can only hold one reservation at a time.\n"
                        "Cancel it to make a new one?"
                    )
                },
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": "cancel_reservation",
                                "title": "❌ Cancel it",
                            },
                        },
                        {
                            "type": "reply",
                            "reply": {"id": "back", "title": "⬅️ Keep it"},
                        },
                    ],
                },
            },
        }
    )


# ---------------------------------------------------------------------------
# Admin forwarding
# ---------------------------------------------------------------------------


def forward_to_admins(customer_phone: str, text: str) -> None:
    """Send a customer message to all configured admin phones."""
    for admin in settings.ADMIN_PHONES:
        _post(
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": admin,
                "type": "text",
                "text": {
                    "body": f"📩 *Support message from +{customer_phone}:*\n\n{text}"
                },
            }
        )


def send_admin_reply_to_client(
    customer_phone: str, admin_phone: str, reply_text: str
) -> None:
    """Forward an admin's reply back to the original customer."""
    send_text(
        customer_phone,
        f"💬 *Reply from our team:*\n\n{reply_text}",
    )
