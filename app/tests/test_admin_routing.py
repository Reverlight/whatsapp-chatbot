from unittest.mock import AsyncMock, patch

import pytest

from app.modules.helpers import _is_admin, _extract_customer_phone, _route

ADMIN_PHONE = "380991234567"
CUSTOMER_PHONE = "380667654321"


# ── Unit tests for helper functions ───────────────────────────────────────────


def test_is_admin_positive():
    with patch("app.modules.helpers.settings") as mock_settings:
        mock_settings.ADMIN_PHONES = ["380991234567"]
        assert _is_admin("380991234567") is True


def test_is_admin_negative():
    with patch("app.modules.helpers.settings") as mock_settings:
        mock_settings.ADMIN_PHONES = ["380991234567"]
        assert _is_admin("380667654321") is False


def test_is_admin_strips_plus():
    with patch("app.modules.helpers.settings") as mock_settings:
        mock_settings.ADMIN_PHONES = ["+380991234567"]
        assert _is_admin("380991234567") is True


def test_extract_customer_phone_valid():
    assert _extract_customer_phone("380667654321 Hello there") == "380667654321"


def test_extract_customer_phone_no_phone():
    """Normal text like menu commands should NOT be detected as a phone."""
    assert _extract_customer_phone("show_menu") is None
    assert _extract_customer_phone("suggestions") is None
    assert _extract_customer_phone("back") is None
    assert _extract_customer_phone("reservation") is None


# ── Integration tests for _route ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_reply_forwards_to_customer():
    """Admin message with phone prefix forwards reply and returns early."""
    with (
        patch("app.modules.helpers.settings") as mock_settings,
        patch("app.modules.helpers.send_admin_reply_to_client") as mock_forward,
        patch(
            "app.modules.helpers.get_or_create_session", new_callable=AsyncMock
        ) as mock_session,
    ):
        mock_settings.ADMIN_PHONES = [ADMIN_PHONE]

        await _route(ADMIN_PHONE, f"{CUSTOMER_PHONE} Your table is ready!")

        mock_forward.assert_called_once_with(
            CUSTOMER_PHONE, ADMIN_PHONE, "Your table is ready!"
        )
        mock_session.assert_not_called()


@pytest.mark.asyncio
async def test_admin_normal_message_enters_user_flow():
    """Admin sending a non-reply message (e.g. 'show_menu') is treated as a regular user."""
    with (
        patch("app.modules.helpers.settings") as mock_settings,
        patch("app.modules.helpers.send_admin_reply_to_client") as mock_forward,
        patch(
            "app.modules.helpers.get_or_create_session", new_callable=AsyncMock
        ) as mock_session,
        patch("app.modules.helpers.save_session", new_callable=AsyncMock),
        patch("app.modules.helpers.HANDLERS") as mock_handlers,
        patch("app.modules.helpers.async_sessionmaker") as mock_db_factory,
    ):
        mock_settings.ADMIN_PHONES = [ADMIN_PHONE]
        mock_session.return_value = {"state": "MAIN_MENU", "stack": []}

        mock_handler = AsyncMock()
        mock_handlers.get.return_value = mock_handler

        mock_db = AsyncMock()
        mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        await _route(ADMIN_PHONE, "show_menu")

        mock_forward.assert_not_called()
        mock_session.assert_called_once_with(ADMIN_PHONE)
        mock_handler.assert_called_once()


@pytest.mark.asyncio
async def test_regular_user_enters_user_flow():
    """Regular user messages always go through the state machine."""
    with (
        patch("app.modules.helpers.settings") as mock_settings,
        patch("app.modules.helpers.send_admin_reply_to_client") as mock_forward,
        patch(
            "app.modules.helpers.get_or_create_session", new_callable=AsyncMock
        ) as mock_session,
        patch("app.modules.helpers.save_session", new_callable=AsyncMock),
        patch("app.modules.helpers.HANDLERS") as mock_handlers,
        patch("app.modules.helpers.async_sessionmaker") as mock_db_factory,
    ):
        mock_settings.ADMIN_PHONES = [ADMIN_PHONE]
        mock_session.return_value = {"state": "MAIN_MENU", "stack": []}

        mock_handler = AsyncMock()
        mock_handlers.get.return_value = mock_handler

        mock_db = AsyncMock()
        mock_db_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        await _route(CUSTOMER_PHONE, "show_menu")

        mock_forward.assert_not_called()
        mock_session.assert_called_once_with(CUSTOMER_PHONE)
        mock_handler.assert_called_once()
