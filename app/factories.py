import datetime

from app.db import AsyncSession
from app.models import Email


class AsyncBaseFactory:
    model = None
    defaults = {}

    @classmethod
    async def create(cls, session: AsyncSession, **kwargs):
        data = {**cls.defaults, **kwargs}
        obj = cls.model(**data)
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj

    @classmethod
    async def create_batch(cls, session: AsyncSession, size: int, **kwargs):
        return [await cls.create(session, **kwargs) for _ in range(size)]


# --- factories ---


class EmailFactory(AsyncBaseFactory):
    model = Email
    defaults = {
        "google_id": "msg_001",
        "thread_id": "thread_001",
        "title": "Test Email",
        "text": "Test body",
        "sender": "test@example.com",
        "received_date": datetime.datetime(2024, 1, 15, 10, 30, 0),
    }
