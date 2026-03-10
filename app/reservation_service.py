"""
Reservation business logic.

Rules:
- A customer can only hold 1 active future reservation at a time.
- Table is auto-assigned: smallest table that fits the guest count and is free
  for the requested date/time slot. If none found, ReservationError is raised
  with a helpful message listing what IS available.
- Restaurant is only open on days listed in settings.RESERVATION_OPEN_DAYS.
- Reservations can only be made up to settings.RESERVATION_MAX_ADVANCE_DAYS ahead.
"""

import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import settings
from app.models import Reservation, ReservationStatus, RestaurantTable


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


async def find_free_table(
    session: AsyncSession,
    date: datetime.date,
    start_time: datetime.time,
    end_time: datetime.time,
    guests: int,
) -> RestaurantTable:
    """
    Find the smallest active table that fits `guests` and has no overlapping
    confirmed reservation on the given date/time slot.

    Raises ReservationError if none found, with a message showing what's available.
    """
    # All active tables that can seat the requested guests, smallest first
    tables_result = await session.execute(
        select(RestaurantTable)
        .where(
            RestaurantTable.is_active == True,
            RestaurantTable.capacity >= guests,
        )
        .order_by(RestaurantTable.capacity)
    )
    candidate_tables = tables_result.scalars().all()

    if not candidate_tables:
        # No tables exist at all that fit — show what the max capacity is
        max_result = await session.execute(
            select(RestaurantTable)
            .where(RestaurantTable.is_active == True)
            .order_by(RestaurantTable.capacity.desc())
            .limit(1)
        )
        biggest = max_result.scalar_one_or_none()
        if biggest:
            raise ReservationError(
                f"❌ No table available for {guests} guests. "
                f"Our largest available table seats {biggest.capacity}."
            )
        raise ReservationError("❌ No tables are currently available")

    # Find booked table IDs for overlapping time slots on this date
    booked_result = await session.execute(
        select(Reservation.table_id)
        .where(
            Reservation.reservation_date == date,
            Reservation.status == ReservationStatus.CONFIRMED,
            Reservation.table_id.isnot(None),
            # Overlap condition: existing starts before our end AND ends after our start
            Reservation.start_time < end_time,
            Reservation.end_time > start_time,
        )
    )
    booked_table_ids = {row[0] for row in booked_result.all()}

    # Pick the first (smallest fitting) table that isn't booked
    for table in candidate_tables:
        if table.id not in booked_table_ids:
            return table

    # All fitting tables are taken — tell the customer what's free
    free_result = await session.execute(
        select(RestaurantTable)
        .where(
            RestaurantTable.is_active == True,
            RestaurantTable.id.notin_(booked_table_ids),
        )
        .order_by(RestaurantTable.capacity.desc())
        .limit(1)
    )
    biggest_free = free_result.scalar_one_or_none()

    if biggest_free:
        raise ReservationError(
            f"❌ No free table for {guests} guests at that time. "
            f"The largest available table seats {biggest_free.capacity}."
        )
    raise ReservationError(
        f"❌ No free tables at that time. Please choose a different time slot."
    )


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

    table = await find_free_table(session, date, start_time, end_time, guests)

    reservation = Reservation(
        phone=phone,
        guest_name=guest_name,
        reservation_date=date,
        start_time=start_time,
        end_time=end_time,
        guests=guests,
        table_id=table.id,
        status=ReservationStatus.CONFIRMED,
    )
    session.add(reservation)
    await session.commit()
    await session.refresh(reservation)
    return reservation, table


async def cancel_reservation(session: AsyncSession, reservation: Reservation) -> None:
    reservation.status = ReservationStatus.CANCELLED
    await session.commit()