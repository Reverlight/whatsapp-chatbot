import base64
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.factories import EmailFactory
from app.models import Email
from app.main import app

html_body = "<html><body><p>Hello, this is a test email.</p></body></html>"
encoded_body = base64.urlsafe_b64encode(html_body.encode()).decode()

# threads.list() response — 10 threads
THREADS_LIST_RESPONSE = {
    "threads": [
        {"id": "19ca22380a9f911d", "historyId": "1"},
        {"id": "19ca1d69e0d54097", "historyId": "2"},
        {"id": "19c9febbade0e372", "historyId": "3"},
        {"id": "19c9fe5ef4b1a8aa", "historyId": "4"},
        {"id": "19c9f0227789a6b1", "historyId": "5"},
        {"id": "19c9e6f2086ed2e5", "historyId": "6"},
        {"id": "19c9e4747f24a2c4", "historyId": "7"},
        {"id": "19c9e3cd8d69c64d", "historyId": "8"},
        {"id": "19c9e3600af89827", "historyId": "9"},
        {"id": "19c9df4951e8d42b", "historyId": "10"},
    ],
    "nextPageToken": "15290425416408154659",
    "resultSizeEstimate": 201,
}


def make_thread_response(thread_id: str, message_id: str) -> dict:
    """Build a threads.get() response with a single message inside."""
    return {
        "id": thread_id,
        "messages": [
            {
                "id": message_id,
                "threadId": thread_id,
                "snippet": "After tomorrow, this rate is gone forever...",
                "internalDate": "1772246761000",
                "payload": {
                    "mimeType": "multipart/alternative",
                    "headers": [
                        {
                            "name": "Subject",
                            "value": "24 hours left to lock in 35% off Boost",
                        },
                        {"name": "From", "value": "vidIQ <hello@send.vidiq.com>"},
                        {"name": "Date", "value": "Sat, 28 Feb 2026 02:46:01 +0000"},
                    ],
                    "body": {"size": 0},
                    "parts": [
                        {
                            "partId": "0",
                            "mimeType": "text/plain",
                            "body": {"size": 2761, "data": encoded_body},
                        },
                    ],
                },
            }
        ],
    }


@pytest.mark.asyncio
async def test_sync_emails(async_client: AsyncClient, async_db: AsyncSession):
    thread_ids = [t["id"] for t in THREADS_LIST_RESPONSE["threads"]]

    with (
        patch("app.email_client.os.path.exists", return_value=True),
        patch("app.email_client.Credentials.from_authorized_user_file"),
        patch("app.email_client.build") as mock_build,
    ):
        mock_service = mock_build.return_value
        users = mock_service.users.return_value
        threads = users.threads.return_value

        # Mock threads.list()
        threads.list.return_value.execute.return_value = THREADS_LIST_RESPONSE

        # Mock threads.get() — each call returns a thread with 1 message
        threads.get.return_value.execute.side_effect = [
            make_thread_response(tid, tid) for tid in thread_ids
        ]

        response = await async_client.post(app.url_path_for("emails:sync_emails"))

    assert response.status_code == 201, response.json()
    data = response.json()
    assert data.get("saved") == 10, data

    result = await async_db.execute(select(Email))
    emails = result.scalars().all()
    assert len(emails) == 10
    assert emails[0].text == html_body


@pytest.mark.asyncio
async def test_get_emails(async_client: AsyncClient, async_db: AsyncSession):
    # Seed emails across 2 threads
    for i in range(5):
        await EmailFactory.create(
            async_db,
            google_id=f"google_id_{i}",
            thread_id="thread_abc",
            title=f"Subject {i}",
            received_date=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
        )
    for i in range(5, 10):
        await EmailFactory.create(
            async_db,
            google_id=f"google_id_{i}",
            thread_id="thread_xyz",
            title=f"Subject {i}",
            received_date=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
        )

    response = await async_client.get(app.url_path_for("emails:get_emails"))
    assert response.status_code == 200

    data = response.json()
    threads = data["threads"]

    assert len(threads) == 2

    # thread_xyz has more recent emails, so it should come first
    assert threads[0]["thread_id"] == "thread_xyz"
    assert threads[1]["thread_id"] == "thread_abc"

    assert len(threads[0]["messages"]) == 5
    assert len(threads[1]["messages"]) == 5

    # Messages sorted oldest → newest within thread
    dates = [m["received_date"] for m in threads[1]["messages"]]
    assert dates == sorted(dates)

    # Subject comes from first message in thread
    assert threads[1]["subject"] == "Subject 0"

    # Check message shape
    msg = threads[0]["messages"][0]
    assert all(
        k in msg
        for k in ("id", "google_id", "sender", "title", "text", "received_date")
    )
