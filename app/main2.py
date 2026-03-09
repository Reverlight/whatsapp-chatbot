import os
import hmac
import hashlib
import json
import httpx
from fastapi import FastAPI, Request, Response
from dotenv import load_dotenv

load_dotenv()

APP_SECRET = os.getenv("WHATSAPP_SECRET")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL")
ADMIN_PHONES = os.getenv("ADMIN_PHONES", "").split(",")

app = FastAPI()


# -------------------------------------------------------------------
# Session store (replace with Redis later)
# -------------------------------------------------------------------
sessions: dict = {}

def get_session(phone: str) -> dict:
    if phone not in sessions:
        sessions[phone] = {"state": "MAIN_MENU", "stack": [], "current_context": {}}
    return sessions[phone]


# -------------------------------------------------------------------
# Navigation
# -------------------------------------------------------------------
def go_deeper(session: dict, next_state: str, context: dict = {}):
    session["stack"].append({
        "state": session["state"],
        "context": session.get("current_context", {})
    })
    session["state"] = next_state
    session["current_context"] = context

def go_back(session: dict):
    if session["stack"]:
        previous = session["stack"].pop()
        session["state"] = previous["state"]
        session["current_context"] = previous["context"]
    else:
        session["state"] = "MAIN_MENU"
        session["current_context"] = {}

def with_back(fn):
    """Decorator — intercepts 'back' before handler runs, navigates to previous state."""
    def wrapper(phone: str, session: dict, text: str):
        if text.lower() == "back":
            go_back(session)
            render_current_state(phone, session)
            return
        fn(phone, session, text)
    return wrapper

def render_current_state(phone: str, session: dict):
    """Re-render the menu for whatever state the user is now in."""
    STATE_RENDERERS.get(session["state"], send_main_menu)(phone)


# -------------------------------------------------------------------
# Handlers
# -------------------------------------------------------------------
def handle_main_menu(phone: str, session: dict, text: str):
    if text == "show_menu":
        send_text(phone, "🍽 Here's our menu: https://example.com/menu")
    elif text == "info":
        send_text(phone, "📍 123 Main St\n🕐 Mon-Sun 10:00-22:00\n📞 +380671234567")
    elif text == "contact":
        go_deeper(session, "CONTACT")
        send_contact_menu(phone)
    elif text == "reservation":
        go_deeper(session, "RESERVATION")
        send_text(phone, "📅 Let's book a table!\n\nEnter the date (e.g. 25.03.2025):\n\nType *back* to exit")
    elif text == "suggestions":
        go_deeper(session, "AI_SUGGESTIONS")
        send_text(phone, "🤖 Ask me anything about our menu!\n\nType *back* to exit")
    else:
        send_main_menu(phone)

@with_back
def handle_contact(phone: str, session: dict, text: str):
    if text == "chat":
        go_deeper(session, "CONTACT_CHAT")
        send_text(phone, "💬 You are now connected to support.\n\nType your message.\n\nType *back* to exit")
    elif text == "getinfo":
        send_text(phone, "📞 +380671234567\n📧 mario@restaurant.com\n📸 @marios_restaurant")
    else:
        send_contact_menu(phone)

@with_back
def handle_contact_chat(phone: str, session: dict, text: str):
    forward_to_admins(phone, text)
    send_text(phone, "✅ Message sent! We'll reply shortly.")

@with_back
def handle_reservation(phone: str, session: dict, text: str):
    send_text(phone, "🚧 Reservation flow coming soon!")

@with_back
def handle_ai_suggestions(phone: str, session: dict, text: str):
    send_text(phone, "🚧 AI suggestions coming soon!")


HANDLERS = {
    "MAIN_MENU":      handle_main_menu,
    "CONTACT":        handle_contact,
    "CONTACT_CHAT":   handle_contact_chat,
    "RESERVATION":    handle_reservation,
    "AI_SUGGESTIONS": handle_ai_suggestions,
}

# maps state → function that re-renders its menu (used by with_back)
STATE_RENDERERS = {
    "MAIN_MENU": send_main_menu,
    "CONTACT":   send_contact_menu,
}

def route(phone: str, text: str):
    session = get_session(phone)
    handler = HANDLERS.get(session["state"])
    if handler:
        handler(phone, session, text)


# -------------------------------------------------------------------
# Webhook
# -------------------------------------------------------------------
@app.get("/")
async def verify(request: Request):
    params = request.query_params
    if params.get("hub.verify_token") == VERIFY_TOKEN:
        return Response(content=params.get("hub.challenge"))
    return Response(status_code=403)

@app.post("/")
async def receive(request: Request):
    signature = request.headers.get("X-Hub-Signature-256", "")
    body = await request.body()

    if not verify_signature(body, signature):
        return Response(status_code=403)

    payload = json.loads(body)
    value = payload["entry"][0]["changes"][0]["value"]

    if "messages" not in value:
        return {"status": "ok"}

    message = value["messages"][0]
    phone = message["from"]

    if message["type"] == "text":
        text = message["text"]["body"]
    elif message["type"] == "interactive":
        interactive = message["interactive"]
        if interactive["type"] == "list_reply":
            text = interactive["list_reply"]["id"]
        elif interactive["type"] == "button_reply":
            text = interactive["button_reply"]["id"]
        else:
            return {"status": "ok"}
    else:
        return {"status": "ok"}

    route(phone, text)
    return {"status": "ok"}


# -------------------------------------------------------------------
# Senders
# -------------------------------------------------------------------
def send_text(phone: str, text: str):
    httpx.post(
        WHATSAPP_API_URL,
        headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"},
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"body": text},
        }
    )

def send_main_menu(phone: str):
    httpx.post(
        WHATSAPP_API_URL,
        headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"},
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": "Welcome to Mario's!\n\nWhat would you like to do?"},
                "action": {
                    "button": "Open Menu",
                    "sections": [{
                        "title": "Options",
                        "rows": [
                            {"id": "show_menu",   "title": "View Menu",        "description": "See our full menu"},
                            {"id": "reservation", "title": "Reservation",      "description": "Book a table"},
                            {"id": "contact",     "title": "Contact Us",       "description": "Chat with our team"},
                            {"id": "suggestions", "title": "Menu Suggestions", "description": "Get AI recommendations"},
                            {"id": "info",        "title": "Restaurant Info",  "description": "Address and hours"},
                        ]
                    }]
                }
            }
        }
    )

def send_contact_menu(phone: str):
    httpx.post(
        WHATSAPP_API_URL,
        headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"},
        json={
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "How can we help?"},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": "chat",    "title": "Chat with us"}},
                        {"type": "reply", "reply": {"id": "getinfo", "title": "Contact info"}},
                        {"type": "reply", "reply": {"id": "back",    "title": "Back"}},
                    ]
                }
            }
        }
    )

def forward_to_admins(customer_phone: str, text: str):
    for admin_phone in ADMIN_PHONES:
        httpx.post(
            WHATSAPP_API_URL,
            headers={"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"},
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": admin_phone.strip(),
                "type": "text",
                "text": {"body": f"💬 Message from +{customer_phone}:\n\n{text}"},
            }
        )


# -------------------------------------------------------------------
# Signature verification
# -------------------------------------------------------------------
def verify_signature(payload: bytes, signature: str) -> bool:
    expected = hmac.new(APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)