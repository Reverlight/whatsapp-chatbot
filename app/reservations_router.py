"""
Admin REST API for reservation management.

Endpoints:
    GET    /api/reservations              — list reservations (filters: date, status, phone)
    POST   /api/reservations              — create a reservation (auto-assigns table if not given)
    GET    /api/reservations/{id}         — get a single reservation
    PATCH  /api/reservations/{id}         — update a reservation
    DELETE /api/reservations/{id}         — delete (hard-delete) a reservation
    POST   /api/reservations/{id}/cancel  — cancel a reservation (soft status change)
"""

import datetime
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_async_db_session
from app.models import Reservation, ReservationStatus, RestaurantTable
from app.reservation_service import (
    ReservationError,
    find_free_table,
    validate_date,
)
from app.schemas import ReservationCreate, ReservationRead, ReservationUpdate

router = APIRouter(prefix="/api/reservations", tags=["reservations"])

# Matches optional '+' followed by 7-15 digits — nothing else allowed
_PHONE_RE = re.compile(r"^\+?\d{7,15}$")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _validate_and_normalize_phone(raw: str) -> str:
    """
    Validate that `raw` looks like a phone number (optional '+' prefix,
    7-15 digits). Returns the digits-only form without '+'.
    Raises HTTPException 422 on bad format.
    """
    cleaned = raw.strip()
    if not _PHONE_RE.match(cleaned):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid phone number '{cleaned}'. "
                "Expected 7-15 digits with an optional leading '+'."
            ),
        )
    return cleaned.lstrip("+")


def _reservation_query():
    """Base query that eagerly loads the related table."""
    return select(Reservation).options(selectinload(Reservation.table))


# ── LIST ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ReservationRead])
async def list_reservations(
    date: Optional[datetime.date] = Query(None, description="Filter by reservation date"),
    status: Optional[ReservationStatus] = Query(None, description="Filter by status"),
    phone: Optional[str] = Query(None, description="Filter by guest phone (partial match)"),
    upcoming: bool = Query(False, description="Only future confirmed reservations"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_db_session),
):
    stmt = _reservation_query()

    if date:
        stmt = stmt.where(Reservation.reservation_date == date)
    if status:
        stmt = stmt.where(Reservation.status == status)
    if phone:
        stmt = stmt.where(Reservation.phone.contains(phone))
    if upcoming:
        stmt = stmt.where(
            Reservation.status == ReservationStatus.CONFIRMED,
            Reservation.reservation_date >= datetime.date.today(),
        )

    stmt = (
        stmt
        .order_by(Reservation.reservation_date.desc(), Reservation.start_time.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(stmt)
    return result.scalars().all()


# ── CREATE ───────────────────────────────────────────────────────────────────

@router.post("", response_model=ReservationRead, status_code=201)
async def create_reservation(
    body: ReservationCreate,
    db: AsyncSession = Depends(get_async_db_session),
):
    # Validate the date is allowed
    try:
        validate_date(body.reservation_date)
    except ReservationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Determine the table
    if body.table_id:
        table = await db.get(RestaurantTable, body.table_id)
        if not table:
            raise HTTPException(status_code=404, detail="Table not found.")
        if not table.is_active:
            raise HTTPException(status_code=422, detail="Table is currently inactive.")
        if table.capacity < body.guests:
            raise HTTPException(
                status_code=422,
                detail=f"Table {table.name} seats {table.capacity}, but {body.guests} guests requested.",
            )
    else:
        try:
            table = await find_free_table(
                db, body.reservation_date, body.start_time, body.end_time, body.guests,
            )
        except ReservationError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    reservation = Reservation(
        guest_name=body.guest_name.strip(),
        phone=_validate_and_normalize_phone(body.phone),
        reservation_date=body.reservation_date,
        start_time=body.start_time,
        end_time=body.end_time,
        guests=body.guests,
        table_id=table.id,
        status=ReservationStatus.CONFIRMED,
    )
    db.add(reservation)
    await db.commit()

    # Re-fetch with table relationship loaded
    result = await db.execute(
        _reservation_query().where(Reservation.id == reservation.id)
    )
    return result.scalar_one()


# ── GET ONE ──────────────────────────────────────────────────────────────────

@router.get("/{reservation_id}", response_model=ReservationRead)
async def get_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    result = await db.execute(
        _reservation_query().where(Reservation.id == reservation_id)
    )
    reservation = result.scalar_one_or_none()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found.")
    return reservation


# ── UPDATE ───────────────────────────────────────────────────────────────────

@router.patch("/{reservation_id}", response_model=ReservationRead)
async def update_reservation(
    reservation_id: int,
    body: ReservationUpdate,
    db: AsyncSession = Depends(get_async_db_session),
):
    result = await db.execute(
        _reservation_query().where(Reservation.id == reservation_id)
    )
    reservation = result.scalar_one_or_none()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found.")

    updates = body.model_dump(exclude_unset=True)

    # If changing table, validate it exists and fits
    if "table_id" in updates and updates["table_id"] is not None:
        table = await db.get(RestaurantTable, updates["table_id"])
        if not table:
            raise HTTPException(status_code=404, detail="Table not found.")
        guest_count = updates.get("guests", reservation.guests)
        if table.capacity < guest_count:
            raise HTTPException(
                status_code=422,
                detail=f"Table {table.name} seats {table.capacity}, but {guest_count} guests requested.",
            )

    # If changing date, validate
    if "reservation_date" in updates:
        try:
            validate_date(updates["reservation_date"])
        except ReservationError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    for field, value in updates.items():
        if field == "guest_name" and isinstance(value, str):
            value = value.strip()
        if field == "phone" and isinstance(value, str):
            value = value.strip().lstrip("+")
        setattr(reservation, field, value)

    await db.commit()

    # Re-fetch with table loaded
    result = await db.execute(
        _reservation_query().where(Reservation.id == reservation_id)
    )
    return result.scalar_one()


# ── CANCEL ───────────────────────────────────────────────────────────────────

@router.post("/{reservation_id}/cancel", response_model=ReservationRead)
async def cancel_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    result = await db.execute(
        _reservation_query().where(Reservation.id == reservation_id)
    )
    reservation = result.scalar_one_or_none()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found.")

    if reservation.status == ReservationStatus.CANCELLED:
        raise HTTPException(status_code=405, detail="Reservation is already cancelled.")

    reservation.status = ReservationStatus.CANCELLED
    await db.commit()
    await db.refresh(reservation)

    # Re-fetch with table
    result = await db.execute(
        _reservation_query().where(Reservation.id == reservation_id)
    )
    return result.scalar_one()


# ── DELETE ───────────────────────────────────────────────────────────────────

@router.delete("/{reservation_id}", status_code=204)
async def delete_reservation(
    reservation_id: int,
    db: AsyncSession = Depends(get_async_db_session),
):
    reservation = await db.get(Reservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found.")

    await db.delete(reservation)
    await db.commit()