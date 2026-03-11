"""
Tests for the WhatsApp webhook endpoints and message parsing (main.py).
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.main import _parse_text, _verify_signature, app


# ── Webhook payload builder ───────────────────────────────────────────────────

def _whatsapp_payload(phone: str, text: str) -> dict:
    """Build a minimal valid WhatsApp webhook payload with a text message."""
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": phone,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


def _interactive_payload(phone: str, reply_type: str, reply_id: str) -> dict:
    """Build a WhatsApp webhook payload with an interactive reply."""
    if reply_type == "list_reply":
        interactive = {"type": "list_reply", "list_reply": {"id": reply_id}}
    else:
        interactive = {"type": "button_reply", "button_reply": {"id": reply_id}}

    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": phone,
                                    "type": "interactive",
                                    "interactive": interactive,
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


# ── _parse_text ───────────────────────────────────────────────────────────────

def test_parse_text_message():
    msg = {"type": "text", "text": {"body": "  hello  "}}
    assert _parse_text(msg) == "hello"


def test_parse_list_reply():
    msg = {
        "type": "interactive",
        "interactive": {"type": "list_reply", "list_reply": {"id": "show_menu"}},
    }
    assert _parse_text(msg) == "show_menu"


def test_parse_button_reply():
    msg = {
        "type": "interactive",
        "interactive": {"type": "button_reply", "button_reply": {"id": "confirm_yes"}},
    }
    assert _parse_text(msg) == "confirm_yes"


def test_parse_unsupported_type():
    msg = {"type": "image"}
    assert _parse_text(msg) is None


def test_verify_signature_valid():
    import hashlib, hmac

    secret = "test_secret"
    payload = b'{"hello": "world"}'
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    with patch("app.modules.helpers.settings") as mock_settings:
        mock_settings.APP_SECRET = secret
        assert _verify_signature(payload, f"sha256={expected}") is True


def test_verify_signature_invalid():
    with patch("app.modules.helpers.settings") as mock_settings:
        mock_settings.APP_SECRET = "test_secret"
        assert _verify_signature(b"payload", "sha256=wrong") is False


# ── GET / (webhook verification) ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_webhook_verify_success(async_client: AsyncClient):
    with patch("app.main.settings") as mock_settings:
        mock_settings.VERIFY_TOKEN = "my_token"

        response = await async_client.get(
            "/",
            params={
                "hub.verify_token": "my_token",
                "hub.challenge": "challenge_123",
            },
        )
    assert response.status_code == 200
    assert response.text == "challenge_123"


@pytest.mark.asyncio
async def test_webhook_verify_bad_token(async_client: AsyncClient):
    with patch("app.main.settings") as mock_settings:
        mock_settings.VERIFY_TOKEN = "my_token"

        response = await async_client.get(
            "/",
            params={"hub.verify_token": "wrong"},
        )
    assert response.status_code == 403


# ── POST / (incoming messages) ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_receive_text_message(async_client: AsyncClient):
    """A valid text message is routed through the state machine."""
    payload = _whatsapp_payload("380991234567", "show_menu")

    with (
        patch("app.main._verify_signature", return_value=True),
        patch("app.main._route", new_callable=AsyncMock) as mock_route,
    ):
        response = await async_client.post("/", json=payload)

    assert response.status_code == 200
    mock_route.assert_called_once_with("380991234567", "show_menu")


@pytest.mark.asyncio
async def test_receive_interactive_message(async_client: AsyncClient):
    payload = _interactive_payload("380991234567", "button_reply", "confirm_yes")

    with (
        patch("app.main._verify_signature", return_value=True),
        patch("app.main._route", new_callable=AsyncMock) as mock_route,
    ):
        response = await async_client.post("/", json=payload)

    assert response.status_code == 200
    mock_route.assert_called_once_with("380991234567", "confirm_yes")


@pytest.mark.asyncio
async def test_receive_bad_signature(async_client: AsyncClient):
    payload = _whatsapp_payload("380991234567", "hi")

    with patch("app.main._verify_signature", return_value=False):
        response = await async_client.post("/", json=payload)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_receive_no_messages_key(async_client: AsyncClient):
    """Payload with no 'messages' key is acknowledged silently."""
    payload = {"entry": [{"changes": [{"value": {"statuses": []}}]}]}

    with patch("app.main._verify_signature", return_value=True):
        response = await async_client.post("/", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_receive_malformed_payload(async_client: AsyncClient):
    """Malformed entry is handled gracefully."""
    payload = {"entry": []}

    with patch("app.main._verify_signature", return_value=True):
        response = await async_client.post("/", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
