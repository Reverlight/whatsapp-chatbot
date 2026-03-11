from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.ai_service import (
    BASE_SYSTEM_PROMPT,
    _build_system_prompt,
    get_ai_suggestion,
)


@pytest.mark.asyncio
async def test_build_prompt_no_menu():
    """Without menu documents, the base prompt is returned as-is."""
    with patch(
        "app.modules.ai_service._load_menu_context",
        new_callable=AsyncMock,
        return_value="",
    ):
        prompt = await _build_system_prompt()

    assert prompt == BASE_SYSTEM_PROMPT
    assert "RESTAURANT MENU" not in prompt


@pytest.mark.asyncio
async def test_build_prompt_with_menu():
    """When menu documents exist, their text is appended to the prompt."""
    menu_text = "=== menu.pdf ===\nMargherita Pizza - $12"

    with patch(
        "app.modules.ai_service._load_menu_context",
        new_callable=AsyncMock,
        return_value=menu_text,
    ):
        prompt = await _build_system_prompt()

    assert "--- RESTAURANT MENU ---" in prompt
    assert "Margherita Pizza - $12" in prompt
    assert "--- END MENU ---" in prompt


@pytest.mark.asyncio
async def test_build_prompt_db_error_falls_back():
    """If loading menu context fails, the base prompt is used."""
    with patch(
        "app.modules.ai_service._load_menu_context",
        new_callable=AsyncMock,
        side_effect=Exception("DB down"),
    ):
        prompt = await _build_system_prompt()

    assert prompt == BASE_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_get_ai_suggestion_returns_reply():
    """get_ai_suggestion calls OpenAI and returns reply + updated history."""
    mock_choice = MagicMock()
    mock_choice.message.content = "  Try our Margherita!  "
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with (
        patch(
            "app.modules.ai_service._build_system_prompt",
            new_callable=AsyncMock,
            return_value="system prompt",
        ),
        patch("app.modules.ai_service._client") as mock_client,
    ):
        mock_client.chat.completions.create.return_value = mock_response

        reply, history = await get_ai_suggestion([], "What pizza do you have?")

    assert reply == "Try our Margherita!"
    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "What pizza do you have?"}
    assert history[1] == {"role": "assistant", "content": "Try our Margherita!"}


@pytest.mark.asyncio
async def test_get_ai_suggestion_preserves_history():
    """Existing history is passed through and appended to."""
    existing = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
    ]

    mock_choice = MagicMock()
    mock_choice.message.content = "Sure, we have pasta!"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with (
        patch(
            "app.modules.ai_service._build_system_prompt",
            new_callable=AsyncMock,
            return_value="prompt",
        ),
        patch("app.modules.ai_service._client") as mock_client,
    ):
        mock_client.chat.completions.create.return_value = mock_response

        reply, history = await get_ai_suggestion(existing, "Any pasta?")

    assert len(history) == 4
    # Original history preserved
    assert history[0] == {"role": "user", "content": "Hi"}
    assert history[1] == {"role": "assistant", "content": "Hello!"}
    # New turn appended
    assert history[2] == {"role": "user", "content": "Any pasta?"}
    assert history[3] == {"role": "assistant", "content": "Sure, we have pasta!"}


@pytest.mark.asyncio
async def test_get_ai_suggestion_caps_history_at_40():
    """History is trimmed to last 40 entries to avoid token bloat."""
    # 42 entries = 21 turns → should be trimmed to 40
    long_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
        for i in range(42)
    ]

    mock_choice = MagicMock()
    mock_choice.message.content = "reply"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with (
        patch(
            "app.modules.ai_service._build_system_prompt",
            new_callable=AsyncMock,
            return_value="prompt",
        ),
        patch("app.modules.ai_service._client") as mock_client,
    ):
        mock_client.chat.completions.create.return_value = mock_response

        _, history = await get_ai_suggestion(long_history, "more")

    # 42 + 2 (new turn) = 44, trimmed to 40
    assert len(history) == 40
