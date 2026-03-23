from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app


@pytest.mark.asyncio
async def test_main(async_client: AsyncClient, async_db: AsyncSession):
    # """GET /api/menu returns all uploaded files."""
    # await MenuDocumentFactory.create(async_db, filename="lunch.pdf")
    # await MenuDocumentFactory.create(async_db, filename="dinner.pdf")

    response = await async_client.get("/api/main")

    assert response.status_code == 200
    data = response.json()
    assert data['result'] == 'API success'
