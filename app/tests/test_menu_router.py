from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.factories import MenuDocumentFactory
from app.models import MenuDocument
from app.main import app

SAMPLE_MENU_TEXT = "Margherita Pizza - $12\nCarbonara Pasta - $15"


@pytest.mark.asyncio
async def test_upload_pdf(async_client: AsyncClient, async_db: AsyncSession):
    """Upload a PDF — text is extracted and stored in the database."""
    pdf_content = b"%PDF-fake-content"

    with patch("app.routers.menu_router._extract_text", return_value=SAMPLE_MENU_TEXT):
        response = await async_client.post(
            "/api/menu/upload",
            files=[("files", ("menu.pdf", pdf_content, "application/pdf"))],
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["filename"] == "menu.pdf"

    result = await async_db.execute(select(MenuDocument))
    doc = result.scalar_one()
    assert doc.filename == "menu.pdf"
    assert doc.extracted_text == SAMPLE_MENU_TEXT


@pytest.mark.asyncio
async def test_upload_multiple_pdfs(async_client: AsyncClient, async_db: AsyncSession):
    """Upload multiple PDFs at once."""
    with patch("app.routers.menu_router._extract_text", return_value=SAMPLE_MENU_TEXT):
        response = await async_client.post(
            "/api/menu/upload",
            files=[
                ("files", ("lunch.pdf", b"%PDF-1", "application/pdf")),
                ("files", ("dinner.pdf", b"%PDF-2", "application/pdf")),
            ],
        )

    assert response.status_code == 200
    assert len(response.json()) == 2

    result = await async_db.execute(select(MenuDocument))
    docs = result.scalars().all()
    assert len(docs) == 2
    filenames = {d.filename for d in docs}
    assert filenames == {"lunch.pdf", "dinner.pdf"}


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf(async_client: AsyncClient):
    """Non-PDF files are rejected with 400."""
    response = await async_client.post(
        "/api/menu/upload",
        files=[("files", ("menu.txt", b"not a pdf", "text/plain"))],
    )

    assert response.status_code == 400
    assert "Only PDF" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_replaces_existing(
    async_client: AsyncClient, async_db: AsyncSession
):
    """Re-uploading a file with the same name replaces the old one."""
    await MenuDocumentFactory.create(
        async_db, filename="menu.pdf", extracted_text="Old menu"
    )

    new_text = "New menu content"
    with patch("app.routers.menu_router._extract_text", return_value=new_text):
        response = await async_client.post(
            "/api/menu/upload",
            files=[("files", ("menu.pdf", b"%PDF-new", "application/pdf"))],
        )

    assert response.status_code == 200

    result = await async_db.execute(select(MenuDocument))
    docs = result.scalars().all()
    assert len(docs) == 1
    assert docs[0].extracted_text == new_text


@pytest.mark.asyncio
async def test_list_menu_files(async_client: AsyncClient, async_db: AsyncSession):
    """GET /api/menu returns all uploaded files."""
    await MenuDocumentFactory.create(async_db, filename="lunch.pdf")
    await MenuDocumentFactory.create(async_db, filename="dinner.pdf")

    response = await async_client.get("/api/menu")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    filenames = {d["filename"] for d in data}
    assert filenames == {"lunch.pdf", "dinner.pdf"}


@pytest.mark.asyncio
async def test_list_empty(async_client: AsyncClient):
    """GET /api/menu returns empty list when no files uploaded."""
    response = await async_client.get("/api/menu")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_delete_menu_file(async_client: AsyncClient, async_db: AsyncSession):
    """DELETE /api/menu/{filename} removes the document."""
    await MenuDocumentFactory.create(async_db, filename="old_menu.pdf")

    response = await async_client.delete("/api/menu/old_menu.pdf")

    assert response.status_code == 204

    result = await async_db.execute(select(MenuDocument))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_nonexistent(async_client: AsyncClient):
    """DELETE on a filename that doesn't exist returns 404."""
    response = await async_client.delete("/api/menu/no_such_file.pdf")

    assert response.status_code == 404
