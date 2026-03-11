import io
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_db_session
from app.models import MenuDocument

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/menu", tags=["menu"])


def _extract_text(pdf_bytes: bytes) -> str:
    """Extract all text from a PDF file."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text and text.strip():
            pages.append(text.strip())
    return "\n\n".join(pages)


@router.get("")
async def list_menu_files(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[dict]:
    result = await db.execute(
        select(
            MenuDocument.id, MenuDocument.filename, MenuDocument.created_at
        ).order_by(MenuDocument.created_at.desc())
    )
    return [
        {"id": row.id, "filename": row.filename, "created_at": str(row.created_at)}
        for row in result.all()
    ]


@router.post("/upload")
async def upload_menu_files(
    files: list[UploadFile],
    db: AsyncSession = Depends(get_async_db_session),
) -> list[dict]:
    results = []

    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"Only PDF files are accepted. Got: {file.filename}",
            )

        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail=f"Empty file: {file.filename}")

        extracted = _extract_text(pdf_bytes)
        if not extracted:
            raise HTTPException(
                status_code=400,
                detail=f"Could not extract any text from: {file.filename}",
            )

        # Replace existing document with same filename
        existing = await db.execute(
            select(MenuDocument).where(MenuDocument.filename == file.filename)
        )
        old = existing.scalar_one_or_none()
        if old:
            await db.delete(old)

        doc = MenuDocument(filename=file.filename, extracted_text=extracted)
        db.add(doc)
        await db.flush()
        results.append({"filename": file.filename, "id": doc.id})

    await db.commit()
    return results


@router.delete("/{filename}", status_code=204)
async def delete_menu_file(
    filename: str,
    db: AsyncSession = Depends(get_async_db_session),
) -> None:
    result = await db.execute(
        select(MenuDocument).where(MenuDocument.filename == filename)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="File not found.")

    await db.delete(doc)
    await db.commit()
