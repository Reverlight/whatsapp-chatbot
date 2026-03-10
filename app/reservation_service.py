"""
Reservation business logic.

Rules:
- A customer can only hold 1 active future reservation at a time.
- They must cancel it (or wait for it to pass) before booking a new one.
- Capacity per day is controlled by settings.RESERVATION_CAPACITY.
- Restaurant is only open on days listed in settings.RESERVATION_OPEN_DAYS.
- Reservations can only be made up to settings.RESERVATION_MAX_ADVANCE_DAYS ahead.
"""

import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import settings
from app.models import Reservation, ReservationStatus


# ── Exceptions ────────────────────────────────────────────────────────────────

class ReservationError(Exception):
    """Raised when a reservation cannot be made."""


# ── Queries ───────────────────────────────────────────────────────────────────

async def get_active_reservation(session: AsyncSession, phone: str) -> Optional[Reservation]:
    """Return the customer's single active future reservation, if any."""
    result = await session.execute(
        select(Reservation)
        .where(
            Reservation.phone == phone,
            Reservation.status == ReservationStatus.CONFIRMED,
            Reservation.reservation_date >= datetime.date.today(),
        )
        .order_by(Reservation.reservation_date, Reservation.start_time)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_guests_on_date(session: AsyncSession, date: datetime.date) -> int:
    """Total guests booked on a given date (confirmed reservations only)."""
    result = await session.execute(
        select(func.coalesce(func.sum(Reservation.guests), 0))
        .where(
            Reservation.reservation_date == date,
            Reservation.status == ReservationStatus.CONFIRMED,
        )
    )
    return result.scalar_one()


# ── Validation ────────────────────────────────────────────────────────────────

def validate_date(date: datetime.date) -> None:
    today = datetime.date.today()

    if date < today:
        raise ReservationError("❌ That date is in the past. Please pick a future date.")

    max_date = today + datetime.timedelta(days=settings.RESERVATION_MAX_ADVANCE_DAYS)
    if date > max_date:
        raise ReservationError(
            f"❌ Reservations can only be made up to "
            f"{settings.RESERVATION_MAX_ADVANCE_DAYS} days in advance."
        )

    if date.weekday() not in settings.RESERVATION_OPEN_DAYS:
        raise ReservationError(
            f"❌ Sorry, we're closed on {date.strftime('%A')}s. Please pick another day."
        )


async def validate_capacity(session: AsyncSession, date: datetime.date, guests: int) -> None:
    booked = await count_guests_on_date(session, date)
    remaining = settings.RESERVATION_CAPACITY - booked

    if remaining <= 0:
        raise ReservationError(
            f"❌ Sorry, we're fully booked on {date.strftime('%d.%m.%Y')}. "
            "Please choose another date."
        )
    if guests > remaining:
        raise ReservationError(
            f"❌ Only {remaining} seat(s) left on {date.strftime('%d.%m.%Y')}. "
            "Please reduce the number of guests or pick another date."
        )


# ── Write operations ──────────────────────────────────────────────────────────

async def create_reservation(
    session: AsyncSession,
    phone: str,
    guest_name: str,
    date: datetime.date,
    start_time: datetime.time,
    end_time: datetime.time,
    guests: int,
) -> Reservation:
    validate_date(date)
    await validate_capacity(session, date, guests)

    reservation = Reservation(
        phone=phone,
        guest_name=guest_name,
        reservation_date=date,
        start_time=start_time,
        end_time=end_time,
        guests=guests,
        status=ReservationStatus.CONFIRMED,
    )
    session.add(reservation)
    await session.commit()
    await session.refresh(reservation)
    return reservation


async def cancel_reservation(session: AsyncSession, reservation: Reservation) -> None:
    reservation.status = ReservationStatus.CANCELLED
    await session.commit()