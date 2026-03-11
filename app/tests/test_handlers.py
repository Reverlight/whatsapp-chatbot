"""
Tests for the WhatsApp state machine handlers.
All WhatsApp API calls (senders) are mocked.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.handlers import (
    handle_ai_suggestions,
    handle_contact,
    handle_contact_chat,
    handle_main_menu,
)


def _fresh_session(state: str = "MAIN_MENU") -> dict:
    return {"state": state, "stack": [], "current_context": {}, "ai_history": []}


# ── MAIN_MENU ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.modules.handlers.send_text")
async def test_main_menu_show_menu(mock_send: MagicMock):
    session = _fresh_session()
    await handle_main_menu("380991234567", session, "show_menu", AsyncMock())

    mock_send.assert_called_once()
    body = mock_send.call_args[0][1]
    assert "menu" in body.lower()


@pytest.mark.asyncio
@patch("app.modules.handlers.send_text")
async def test_main_menu_info(mock_send: MagicMock):
    session = _fresh_session()
    await handle_main_menu("380991234567", session, "info", AsyncMock())

    mock_send.assert_called_once()


@pytest.mark.asyncio
@patch("app.modules.handlers.send_contact_menu")
async def test_main_menu_contact(mock_send: MagicMock):
    session = _fresh_session()
    await handle_main_menu("380991234567", session, "contact", AsyncMock())

    assert session["state"] == "CONTACT"
    mock_send.assert_called_once_with("380991234567")


@pytest.mark.asyncio
@patch("app.modules.handlers.send_reservation_date_prompt")
async def test_main_menu_reservation(mock_send: MagicMock):
    session = _fresh_session()
    await handle_main_menu("380991234567", session, "reservation", AsyncMock())

    assert session["state"] == "RESERVATION"
    mock_send.assert_called_once_with("380991234567")


@pytest.mark.asyncio
@patch("app.modules.handlers.send_text")
async def test_main_menu_suggestions(mock_send: MagicMock):
    session = _fresh_session()
    await handle_main_menu("380991234567", session, "suggestions", AsyncMock())

    assert session["state"] == "AI_SUGGESTIONS"
    mock_send.assert_called_once()
    body = mock_send.call_args[0][1]
    assert "AI Menu Assistant" in body


@pytest.mark.asyncio
@patch("app.modules.handlers.send_main_menu")
async def test_main_menu_unknown_text(mock_send: MagicMock):
    session = _fresh_session()
    await handle_main_menu("380991234567", session, "gibberish", AsyncMock())

    mock_send.assert_called_once_with("380991234567")


# ── CONTACT ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.modules.handlers.send_text")
async def test_contact_chat_admin(mock_send: MagicMock):
    session = _fresh_session("CONTACT")
    session["stack"] = [{"state": "MAIN_MENU", "context": {}}]

    await handle_contact("380991234567", session, "chat_admin", AsyncMock())

    assert session["state"] == "CONTACT_CHAT"
    mock_send.assert_called_once()


@pytest.mark.asyncio
@patch("app.modules.handlers.send_text")
async def test_contact_get_info(mock_send: MagicMock):
    session = _fresh_session("CONTACT")
    await handle_contact("380991234567", session, "get_info", AsyncMock())

    mock_send.assert_called_once()
    body = mock_send.call_args[0][1]
    assert "Contact Information" in body


@pytest.mark.asyncio
@patch("app.modules.handlers.send_main_menu")
async def test_contact_back(mock_send: MagicMock):
    session = _fresh_session("CONTACT")
    session["stack"] = [{"state": "MAIN_MENU", "context": {}}]

    await handle_contact("380991234567", session, "back", AsyncMock())

    assert session["state"] == "MAIN_MENU"
    mock_send.assert_called_once()


# ── CONTACT_CHAT ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.modules.handlers.send_text")
@patch("app.modules.handlers.forward_to_admins")
async def test_contact_chat_forwards(mock_forward: MagicMock, mock_send: MagicMock):
    session = _fresh_session("CONTACT_CHAT")
    session["stack"] = [
        {"state": "MAIN_MENU", "context": {}},
        {"state": "CONTACT", "context": {}},
    ]

    await handle_contact_chat("380991234567", session, "I need help", AsyncMock())

    mock_forward.assert_called_once_with("380991234567", "I need help")
    mock_send.assert_called_once()
    body = mock_send.call_args[0][1]
    assert "message has been sent" in body.lower()


@pytest.mark.asyncio
@patch("app.modules.handlers.send_contact_menu")
async def test_contact_chat_back(mock_send: MagicMock):
    session = _fresh_session("CONTACT_CHAT")
    session["stack"] = [
        {"state": "MAIN_MENU", "context": {}},
        {"state": "CONTACT", "context": {}},
    ]

    await handle_contact_chat("380991234567", session, "back", AsyncMock())

    assert session["state"] == "CONTACT"
    mock_send.assert_called_once()


# ── AI_SUGGESTIONS ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.modules.handlers.send_text")
@patch("app.modules.handlers.get_ai_suggestion", new_callable=AsyncMock)
async def test_ai_suggestions_reply(mock_ai: AsyncMock, mock_send: MagicMock):
    mock_ai.return_value = ("Try our pizza!", [
        {"role": "user", "content": "What's good?"},
        {"role": "assistant", "content": "Try our pizza!"},
    ])

    session = _fresh_session("AI_SUGGESTIONS")
    session["stack"] = [{"state": "MAIN_MENU", "context": {}}]

    await handle_ai_suggestions("380991234567", session, "What's good?", AsyncMock())

    mock_send.assert_called_once_with("380991234567", "Try our pizza!")
    assert len(session["ai_history"]) == 2


@pytest.mark.asyncio
@patch("app.modules.handlers.send_text")
@patch("app.modules.handlers.get_ai_suggestion", new_callable=AsyncMock)
async def test_ai_suggestions_error(mock_ai: AsyncMock, mock_send: MagicMock):
    mock_ai.side_effect = Exception("OpenAI down")

    session = _fresh_session("AI_SUGGESTIONS")
    session["stack"] = [{"state": "MAIN_MENU", "context": {}}]

    await handle_ai_suggestions("380991234567", session, "hello", AsyncMock())

    mock_send.assert_called_once()
    body = mock_send.call_args[0][1]
    assert "unavailable" in body.lower()


@pytest.mark.asyncio
@patch("app.modules.handlers.send_main_menu")
async def test_ai_suggestions_back(mock_send: MagicMock):
    session = _fresh_session("AI_SUGGESTIONS")
    session["stack"] = [{"state": "MAIN_MENU", "context": {}}]

    await handle_ai_suggestions("380991234567", session, "back", AsyncMock())

    assert session["state"] == "MAIN_MENU"
    mock_send.assert_called_once()
