import json
from unittest.mock import MagicMock, patch

import pytest

from app.openai_client import (
    ACTION_FETCH_CLIENT,
    ACTION_FETCH_ORDER,
    ACTION_REFUND_ORDER,
    OpenAIClient,
)

# ── Helpers ────────────────────────────────────────────────────────────────────


def make_completion(content: str) -> MagicMock:
    """Build a mock OpenAI ChatCompletion response."""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    completion = MagicMock()
    completion.choices = [choice]
    return completion


SAMPLE_THREAD = """--- Email 1 ---
From: Sarah Mitchell <sarah.mitchell@example.com>
Subject: Refund request for order #4821
Date: 2026-02-28 10:14:00+00:00

Hi, I'd like a refund for order #4821. My email is sarah.mitchell@example.com."""


@pytest.fixture
def client():
    with patch("app.openai_client.OPENAI_API_KEY", "sk-test"):
        with patch("app.openai_client.OpenAI"):
            return OpenAIClient()


# ── Init ───────────────────────────────────────────────────────────────────────


def test_init_raises_without_api_key():
    with patch("app.openai_client.OPENAI_API_KEY", None):
        with pytest.raises(Exception, match="OPENAI_API_KEY is not set"):
            OpenAIClient()


def test_init_sets_correct_model():
    with patch("app.openai_client.OPENAI_API_KEY", "sk-test"):
        with patch("app.openai_client.OpenAI"):
            c = OpenAIClient()
            assert c.model == "gpt-4o-mini"


# ── determine_actions ──────────────────────────────────────────────────────────


def test_determine_actions_returns_all_three(client):
    payload = json.dumps(
        {
            "actions": [
                {"type": "fetch_order_detail", "order_id": "4821"},
                {
                    "type": "fetch_client_detail",
                    "customer_email": "sarah.mitchell@example.com",
                },
                {"type": "refund_order", "order_id": "4821"},
            ]
        }
    )
    client.client.chat.completions.create.return_value = make_completion(payload)

    result = client.determine_actions(SAMPLE_THREAD)

    assert len(result) == 3
    types = [a["type"] for a in result]
    assert ACTION_FETCH_ORDER in types
    assert ACTION_FETCH_CLIENT in types
    assert ACTION_REFUND_ORDER in types


def test_determine_actions_single_fetch_order(client):
    payload = json.dumps(
        {"actions": [{"type": "fetch_order_detail", "order_id": "1099"}]}
    )
    client.client.chat.completions.create.return_value = make_completion(payload)

    result = client.determine_actions(SAMPLE_THREAD)

    assert len(result) == 1
    assert result[0]["type"] == ACTION_FETCH_ORDER
    assert result[0]["order_id"] == "1099"


def test_determine_actions_single_fetch_client(client):
    payload = json.dumps(
        {
            "actions": [
                {"type": "fetch_client_detail", "customer_email": "john@example.com"}
            ]
        }
    )
    client.client.chat.completions.create.return_value = make_completion(payload)

    result = client.determine_actions(SAMPLE_THREAD)

    assert len(result) == 1
    assert result[0]["type"] == ACTION_FETCH_CLIENT
    assert result[0]["customer_email"] == "john@example.com"


def test_determine_actions_single_refund(client):
    payload = json.dumps({"actions": [{"type": "refund_order", "order_id": "5555"}]})
    client.client.chat.completions.create.return_value = make_completion(payload)

    result = client.determine_actions(SAMPLE_THREAD)

    assert len(result) == 1
    assert result[0]["type"] == ACTION_REFUND_ORDER


def test_determine_actions_empty_list(client):
    payload = json.dumps({"actions": []})
    client.client.chat.completions.create.return_value = make_completion(payload)

    result = client.determine_actions(SAMPLE_THREAD)

    assert result == []


def test_determine_actions_filters_unknown_types(client):
    payload = json.dumps(
        {
            "actions": [
                {"type": "fetch_order_detail", "order_id": "1"},
                {"type": "delete_everything"},
                {"type": "unknown_action"},
            ]
        }
    )
    client.client.chat.completions.create.return_value = make_completion(payload)

    result = client.determine_actions(SAMPLE_THREAD)

    assert len(result) == 1
    assert result[0]["type"] == ACTION_FETCH_ORDER


def test_determine_actions_missing_actions_key(client):
    payload = json.dumps({"something_else": "value"})
    client.client.chat.completions.create.return_value = make_completion(payload)

    result = client.determine_actions(SAMPLE_THREAD)

    assert result == []


def test_determine_actions_null_params_preserved(client):
    payload = json.dumps(
        {"actions": [{"type": "fetch_order_detail", "order_id": None}]}
    )
    client.client.chat.completions.create.return_value = make_completion(payload)

    result = client.determine_actions(SAMPLE_THREAD)

    assert len(result) == 1
    assert result[0]["order_id"] is None


def test_determine_actions_uses_correct_openai_params(client):
    payload = json.dumps({"actions": []})
    client.client.chat.completions.create.return_value = make_completion(payload)

    client.determine_actions(SAMPLE_THREAD)

    kwargs = client.client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["temperature"] == 0
    assert kwargs["response_format"] == {"type": "json_object"}


def test_determine_actions_prompt_contains_thread(client):
    payload = json.dumps({"actions": []})
    client.client.chat.completions.create.return_value = make_completion(payload)

    client.determine_actions(SAMPLE_THREAD)

    messages = client.client.chat.completions.create.call_args.kwargs["messages"]
    assert any(SAMPLE_THREAD in m["content"] for m in messages)


# ── summarize_thread ───────────────────────────────────────────────────────────


def test_summarize_returns_stripped_string(client):
    client.client.chat.completions.create.return_value = make_completion(
        "  Customer requested a refund for order #4821.  "
    )

    result = client.summarize_thread(SAMPLE_THREAD)

    assert result == "Customer requested a refund for order #4821."


def test_summarize_empty_whitespace_response(client):
    client.client.chat.completions.create.return_value = make_completion("   ")

    result = client.summarize_thread(SAMPLE_THREAD)

    assert result == ""


def test_summarize_uses_correct_model_and_temperature(client):
    client.client.chat.completions.create.return_value = make_completion("Summary.")

    client.summarize_thread(SAMPLE_THREAD)

    kwargs = client.client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs["temperature"] == 0.3


def test_summarize_does_not_use_json_response_format(client):
    client.client.chat.completions.create.return_value = make_completion("Summary.")

    client.summarize_thread(SAMPLE_THREAD)

    kwargs = client.client.chat.completions.create.call_args.kwargs
    assert "response_format" not in kwargs


def test_summarize_prompt_contains_thread(client):
    client.client.chat.completions.create.return_value = make_completion("Summary.")

    client.summarize_thread(SAMPLE_THREAD)

    messages = client.client.chat.completions.create.call_args.kwargs["messages"]
    assert any(SAMPLE_THREAD in m["content"] for m in messages)


def test_summarize_preserves_multiline_response(client):
    summary = "Line one.\nLine two.\nLine three."
    client.client.chat.completions.create.return_value = make_completion(summary)

    result = client.summarize_thread(SAMPLE_THREAD)

    assert result == summary
