import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Reservation, ReservationStatus, RestaurantTable

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _seed_table(
    db: AsyncSession, name: str = "T1", capacity: int = 4
) -> RestaurantTable:
    t = RestaurantTable(name=name, capacity=capacity, is_active=True)
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


# ── CREATE ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_table(async_client: AsyncClient, async_db: AsyncSession):
    response = await async_client.post(
        "/api/tables",
        json={"name": "T1", "capacity": 4},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "T1"
    assert data["capacity"] == 4
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_duplicate_name(async_client: AsyncClient, async_db: AsyncSession):
    await _seed_table(async_db, "T1")

    response = await async_client.post(
        "/api/tables",
        json={"name": "t1", "capacity": 2},  # case-insensitive duplicate
    )
    assert response.status_code == 409


# ── LIST ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_tables(async_client: AsyncClient, async_db: AsyncSession):
    await _seed_table(async_db, "A1", 2)
    await _seed_table(async_db, "A2", 6)

    response = await async_client.get("/api/tables")
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_list_tables_active_only(
    async_client: AsyncClient, async_db: AsyncSession
):
    await _seed_table(async_db, "Active")
    inactive = RestaurantTable(name="Inactive", capacity=2, is_active=False)
    async_db.add(inactive)
    await async_db.commit()

    response = await async_client.get("/api/tables?active_only=true")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Active"


# ── GET ONE ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_table(async_client: AsyncClient, async_db: AsyncSession):
    t = await _seed_table(async_db)

    response = await async_client.get(f"/api/tables/{t.id}")
    assert response.status_code == 200
    assert response.json()["name"] == "T1"


@pytest.mark.asyncio
async def test_get_table_not_found(async_client: AsyncClient):
    response = await async_client.get("/api/tables/999")
    assert response.status_code == 404


# ── UPDATE ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_table(async_client: AsyncClient, async_db: AsyncSession):
    t = await _seed_table(async_db)

    response = await async_client.patch(
        f"/api/tables/{t.id}",
        json={"capacity": 8},
    )
    assert response.status_code == 200
    assert response.json()["capacity"] == 8


@pytest.mark.asyncio
async def test_update_rename_duplicate(
    async_client: AsyncClient, async_db: AsyncSession
):
    await _seed_table(async_db, "T1")
    t2 = await _seed_table(async_db, "T2")

    response = await async_client.patch(
        f"/api/tables/{t2.id}",
        json={"name": "T1"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_update_not_found(async_client: AsyncClient):
    response = await async_client.patch("/api/tables/999", json={"capacity": 2})
    assert response.status_code == 404


# ── DELETE ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_table(async_client: AsyncClient, async_db: AsyncSession):
    t = await _seed_table(async_db)

    response = await async_client.delete(f"/api/tables/{t.id}")
    assert response.status_code == 204

    result = await async_db.execute(select(RestaurantTable))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_table_with_confirmed_reservation(
    async_client: AsyncClient, async_db: AsyncSession
):
    import datetime

    t = await _seed_table(async_db)
    res = Reservation(
        guest_name="John",
        phone="380991234567",
        table_id=t.id,
        reservation_date=datetime.date.today() + datetime.timedelta(days=5),
        start_time=datetime.time(18, 0),
        end_time=datetime.time(20, 0),
        guests=2,
        status=ReservationStatus.CONFIRMED,
    )
    async_db.add(res)
    await async_db.commit()

    response = await async_client.delete(f"/api/tables/{t.id}")
    assert response.status_code == 409
    assert "confirmed reservations" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_not_found(async_client: AsyncClient):
    response = await async_client.delete("/api/tables/999")
    assert response.status_code == 404
