import datetime
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.factories import EmailFactory
from app.models import Email
from app.main import app
import json
from unittest.mock import MagicMock, patch

import pytest

from app.openai_client import (
    ACTION_FETCH_CLIENT,
    ACTION_FETCH_ORDER,
    ACTION_REFUND_ORDER,
    OpenAIClient,
)

{
    "thread_id": "123",
    "summary": "Sarah Mitchell requested a full refund for order #4821, which she placed on February 24th for a pair of running shoes that arrived on February 27th. She reported quality issues, including a sole that was coming apart and rough stitching. The support team acknowledged her request on February 28th and stated they would review it within 24 hours. As of March 1st, Sarah has followed up, seeking confirmation on the status of her refund.",
}

"""
--- Email 1 ---
From: Sarah Mitchell <sarah.mitchell@example.com>
Subject: Refund request for order #4821
Date: 2026-02-28 10:14:00+00:00

Hi,

I placed an order (#4821) on February 24th for a pair of running shoes, size 42.
The shoes arrived yesterday but the quality is nothing like what was shown on the website —
the sole is already coming apart and the stitching looks very rough.

I've been a customer for 2 years and this is the first time I've been disappointed.
I'd like to request a full refund and will send the item back.

My account email is sarah.mitchell@example.com.

Thanks,
Sarah

--- Email 2 ---
From: Support <support@ourstore.com>
Subject: Re: Refund request for order #4821
Date: 2026-02-28 11:30:00+00:00

Hi Sarah,

Thank you for reaching out. We're sorry to hear about the quality issue.
We've logged your refund request for order #4821 and our team will review it within 24 hours.

Best regards,
Support Team

--- Email 3 ---
From: Sarah Mitchell <sarah.mitchell@example.com>
Subject: Re: Refund request for order #4821
Date: 2026-03-01 09:05:00+00:00

Hi, it's been over 24 hours and I haven't heard back.
Can you please confirm when the refund will be processed?

Thanks,
Sarah
"""

MOCK_SUMMARY = (
    "Customer Sarah requested a refund for order #4821 due to quality issues."
)

"""
{
  "thread_id": "1",
  "actions": [
    {
      "type": "fetch_order_detail",
      "order_id": "4821"
    },
    {
      "type": "fetch_client_detail",
      "customer_email": "sarah.mitchell@example.com"
    },
    {
      "type": "refund_order",
      "order_id": "4821"
    }
  ]
}
"""


class TestSummarizeThread:
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, async_db, async_client):
        self.thread_id = "thread_001"
        self.other_thread_id = "thread_002"

        self.email1 = await EmailFactory.create(
            async_db,
            google_id="msg_001",
            thread_id=self.thread_id,
            title="Refund request for order #4821",
            text="I would like a refund for order #4821.",
            sender="sarah@example.com",
            received_date=datetime.datetime(2026, 2, 28, 10, 0, 0),
        )
        self.email2 = await EmailFactory.create(
            async_db,
            google_id="msg_002",
            thread_id=self.thread_id,
            title="Re: Refund request for order #4821",
            text="Thank you, we will review within 24 hours.",
            sender="support@store.com",
            received_date=datetime.datetime(2026, 2, 28, 11, 0, 0),
        )
        self.other_email = await EmailFactory.create(
            async_db,
            google_id="msg_003",
            thread_id=self.other_thread_id,
            title="Unrelated email",
            text="This should not appear in the summary.",
            sender="other@example.com",
            received_date=datetime.datetime(2026, 2, 28, 12, 0, 0),
        )

    @pytest.fixture
    def mock_chatgpt(self):
        with patch("app.routes.ai_actions.OpenAIClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.summarize_thread.return_value = MOCK_SUMMARY
            yield mock_instance  # 👈 yield the instance, not the class

    @pytest.mark.asyncio
    async def test_summarize_returns_summary(self, async_client, mock_chatgpt):
        summarize_path = app.url_path_for("openai:summarize", thread_id=self.thread_id)
        response = await async_client.post(summarize_path)

        assert response.status_code == 200
        assert response.json() == {
            "thread_id": self.thread_id,
            "summary": MOCK_SUMMARY,
        }

    @pytest.mark.asyncio
    async def test_summarize_calls_chatgpt_with_formatted_thread(
        self, async_client, mock_chatgpt
    ):
        summarize_path = app.url_path_for("openai:summarize", thread_id=self.thread_id)
        response = await async_client.post(summarize_path)

        mock_chatgpt.summarize_thread.assert_called_once()
        call_arg = mock_chatgpt.summarize_thread.call_args[0][0]
        assert "sarah@example.com" in call_arg
        assert "support@store.com" in call_arg
        assert "other@example.com" not in call_arg

    @pytest.mark.asyncio
    async def test_summarize_emails_ordered_by_date(self, async_client, mock_chatgpt):
        summarize_path = app.url_path_for("openai:summarize", thread_id=self.thread_id)
        response = await async_client.post(summarize_path)

        call_arg = mock_chatgpt.summarize_thread.call_args[0][0]
        assert call_arg.index("sarah@example.com") < call_arg.index("support@store.com")

    @pytest.mark.asyncio
    async def test_summarize_thread_not_found(self, async_client, mock_chatgpt):
        summarize_path = app.url_path_for("openai:summarize", thread_id="not_existing")
        response = await async_client.post(summarize_path)

        assert response.status_code == 404
        assert response.json()["detail"] == "Thread not found"

    @pytest.mark.asyncio
    async def test_summarize_returns_summary(self, async_client, mock_chatgpt):
        summarize_path = app.url_path_for("openai:summarize", thread_id=self.thread_id)
        response = await async_client.post(summarize_path)
        print(response.status_code)
        print(response.json())  # 👈 add this
        assert response.status_code == 200


MOCK_ACTIONS = [
    {"type": "fetch_order_detail", "order_id": "4821"},
    {"type": "fetch_client_detail", "customer_email": "sarah.mitchell@example.com"},
    {"type": "refund_order", "order_id": "4821"},
]


class TestDetectActions:
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, async_db, async_client):
        self.thread_id = "thread_001"

        self.email1 = await EmailFactory.create(
            async_db,
            google_id="msg_001",
            thread_id=self.thread_id,
            title="Refund request for order #4821",
            text="I would like a refund for order #4821.",
            sender="sarah.mitchell@example.com",
            received_date=datetime.datetime(2026, 2, 28, 10, 0, 0),
        )
        self.email2 = await EmailFactory.create(
            async_db,
            google_id="msg_002",
            thread_id=self.thread_id,
            title="Re: Refund request for order #4821",
            text="Thank you, we will review within 24 hours.",
            sender="support@store.com",
            received_date=datetime.datetime(2026, 2, 28, 11, 0, 0),
        )

    @pytest.fixture
    def mock_chatgpt(self):
        with patch("app.routes.ai_actions.OpenAIClient") as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.determine_actions.return_value = MOCK_ACTIONS
            yield mock_instance

    @pytest.mark.asyncio
    async def test_detect_actions_returns_actions(self, async_client, mock_chatgpt):
        detect_actions_path = app.url_path_for(
            "openai:detect_actions", thread_id=self.thread_id
        )
        response = await async_client.post(detect_actions_path)

        assert response.status_code == 200
        assert response.json() == {
            "thread_id": self.thread_id,
            "actions": MOCK_ACTIONS,
        }

    @pytest.mark.asyncio
    async def test_detect_actions_calls_chatgpt_with_formatted_thread(
        self, async_client, mock_chatgpt
    ):
        detect_actions_path = app.url_path_for(
            "openai:detect_actions", thread_id=self.thread_id
        )
        response = await async_client.post(detect_actions_path)

        mock_chatgpt.determine_actions.assert_called_once()
        call_arg = mock_chatgpt.determine_actions.call_args[0][0]
        assert "sarah.mitchell@example.com" in call_arg
        assert "support@store.com" in call_arg
        assert response.json().get("thread_id") == self.thread_id
        assert "fetch_order_detail" in response.json().get("actions")[0].values()

    @pytest.mark.asyncio
    async def test_detect_actions_thread_not_found(self, async_client, mock_chatgpt):
        detect_actions_path = app.url_path_for(
            "openai:detect_actions", thread_id="nonexistent_thread"
        )
        response = await async_client.post(detect_actions_path)

        assert response.status_code == 404
        assert response.json()["detail"] == "Thread not found"
