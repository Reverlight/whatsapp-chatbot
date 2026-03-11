import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Reservation, ReservationStatus, RestaurantTable

# ── Helpers ───────────────────────────────────────────────────────────────────

FUTURE_DATE = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()


async def _seed_table(
    db: AsyncSession, name: str = "T1", capacity: int = 4
) -> RestaurantTable:
    t = RestaurantTable(name=name, capacity=capacity, is_active=True)
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


async def _seed_reservation(
    db: AsyncSession, table: RestaurantTable, phone: str = "380991234567"
) -> Reservation:
    r = Reservation(
        guest_name="John Doe",
        phone=phone,
        table_id=table.id,
        reservation_date=datetime.date.today() + datetime.timedelta(days=7),
        start_time=datetime.time(18, 0),
        end_time=datetime.time(20, 0),
        guests=2,
        status=ReservationStatus.CONFIRMED,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


# ── CREATE ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_reservation_auto_table(
    async_client: AsyncClient, async_db: AsyncSession
):
    await _seed_table(async_db, "T1", 4)

    response = await async_client.post(
        "/api/reservations",
        json={
            "guest_name": "Alice",
            "phone": "+380991234567",
            "reservation_date": FUTURE_DATE,
            "start_time": "18:00",
            "end_time": "20:00",
            "guests": 2,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["guest_name"] == "Alice"
    assert data["status"] == "confirmed"
    assert data["table"] is not None


@pytest.mark.asyncio
async def test_create_reservation_specific_table(
    async_client: AsyncClient, async_db: AsyncSession
):
    t = await _seed_table(async_db, "VIP", 6)

    response = await async_client.post(
        "/api/reservations",
        json={
            "guest_name": "Bob",
            "phone": "380991234567",
            "reservation_date": FUTURE_DATE,
            "start_time": "19:00",
            "end_time": "21:00",
            "guests": 4,
            "table_id": t.id,
        },
    )
    assert response.status_code == 201
    assert response.json()["table_id"] == t.id


@pytest.mark.asyncio
async def test_create_reservation_invalid_phone(
    async_client: AsyncClient, async_db: AsyncSession
):
    await _seed_table(async_db)

    response = await async_client.post(
        "/api/reservations",
        json={
            "guest_name": "Alice",
            "phone": "bad",
            "reservation_date": FUTURE_DATE,
            "start_time": "18:00",
            "end_time": "20:00",
            "guests": 2,
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_reservation_past_date(
    async_client: AsyncClient, async_db: AsyncSession
):
    await _seed_table(async_db)
    past = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    response = await async_client.post(
        "/api/reservations",
        json={
            "guest_name": "Alice",
            "phone": "380991234567",
            "reservation_date": past,
            "start_time": "18:00",
            "end_time": "20:00",
            "guests": 2,
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_reservation_table_too_small(
    async_client: AsyncClient, async_db: AsyncSession
):
    t = await _seed_table(async_db, "Small", 2)

    response = await async_client.post(
        "/api/reservations",
        json={
            "guest_name": "Alice",
            "phone": "380991234567",
            "reservation_date": FUTURE_DATE,
            "start_time": "18:00",
            "end_time": "20:00",
            "guests": 6,
            "table_id": t.id,
        },
    )
    assert response.status_code == 422


# ── LIST ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_reservations(async_client: AsyncClient, async_db: AsyncSession):
    t = await _seed_table(async_db)
    await _seed_reservation(async_db, t)

    response = await async_client.get("/api/reservations")
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_list_reservations_filter_status(
    async_client: AsyncClient, async_db: AsyncSession
):
    t = await _seed_table(async_db)
    await _seed_reservation(async_db, t)

    response = await async_client.get("/api/reservations?status=cancelled")
    assert response.status_code == 200
    assert len(response.json()) == 0

    response = await async_client.get("/api/reservations?status=confirmed")
    assert response.status_code == 200
    assert len(response.json()) == 1


# ── GET ONE ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_reservation(async_client: AsyncClient, async_db: AsyncSession):
    t = await _seed_table(async_db)
    r = await _seed_reservation(async_db, t)

    response = await async_client.get(f"/api/reservations/{r.id}")
    assert response.status_code == 200
    assert response.json()["guest_name"] == "John Doe"


@pytest.mark.asyncio
async def test_get_reservation_not_found(async_client: AsyncClient):
    response = await async_client.get("/api/reservations/999")
    assert response.status_code == 404


# ── UPDATE ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_reservation(async_client: AsyncClient, async_db: AsyncSession):
    t = await _seed_table(async_db)
    r = await _seed_reservation(async_db, t)

    response = await async_client.patch(
        f"/api/reservations/{r.id}",
        json={"guest_name": "Jane Doe", "guests": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["guest_name"] == "Jane Doe"
    assert data["guests"] == 3


@pytest.mark.asyncio
async def test_update_reservation_not_found(async_client: AsyncClient):
    response = await async_client.patch(
        "/api/reservations/999", json={"guest_name": "Nobody"}
    )
    assert response.status_code == 404


# ── CANCEL ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_reservation(async_client: AsyncClient, async_db: AsyncSession):
    t = await _seed_table(async_db)
    r = await _seed_reservation(async_db, t)

    response = await async_client.post(f"/api/reservations/{r.id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_already_cancelled(
    async_client: AsyncClient, async_db: AsyncSession
):
    t = await _seed_table(async_db)
    r = await _seed_reservation(async_db, t)
    r.status = ReservationStatus.CANCELLED
    await async_db.commit()

    response = await async_client.post(f"/api/reservations/{r.id}/cancel")
    assert response.status_code == 405


@pytest.mark.asyncio
async def test_cancel_not_found(async_client: AsyncClient):
    response = await async_client.post("/api/reservations/999/cancel")
    assert response.status_code == 404


# ── DELETE ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_reservation(async_client: AsyncClient, async_db: AsyncSession):
    t = await _seed_table(async_db)
    r = await _seed_reservation(async_db, t)

    response = await async_client.delete(f"/api/reservations/{r.id}")
    assert response.status_code == 204

    result = await async_db.execute(select(Reservation))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_reservation_not_found(async_client: AsyncClient):
    response = await async_client.delete("/api/reservations/999")
    assert response.status_code == 404
