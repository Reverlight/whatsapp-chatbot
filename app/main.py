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

app = FastAPI()


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

    # skip status updates (delivered, read) — they have no "messages" key
    value = payload["entry"][0]["changes"][0]["value"]
    if "messages" not in value:
        return {"status": "ok"}

    phone = value["messages"][0]["from"]
    send_main_menu(phone)

    return {"status": "ok"}


def send_main_menu(phone: str):
    httpx.post(
        WHATSAPP_API_URL,
        headers={
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
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
                    "sections": [
                        {
                            "title": "Options",
                            "rows": [
                                {"id": "show_menu", "title": "View Menu", "description": "See our full menu"},
                                {"id": "reservation", "title": "Reservation", "description": "Book a table"},
                                {"id": "contact", "title": "Contact Us", "description": "Chat with our team"},
                                {"id": "suggestions", "title": "Menu Suggestions", "description": "Get AI recommendations"},
                                {"id": "info", "title": "Restaurant Info", "description": "Address and hours"},
                            ]
                        }
                    ]
                }
            }
        }
    )
    print("WhatsApp API response:", response.status_code, response.text)


def verify_signature(payload: bytes, signature: str) -> bool:
    expected = hmac.new(
        APP_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)