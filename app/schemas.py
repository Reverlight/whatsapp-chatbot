"""
Pydantic schemas for the admin REST API.
"""

import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import ReservationStatus


# ── RestaurantTable ───────────────────────────────────────────────────────────

class TableCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=20, examples=["T1", "Bar-3"])
    capacity: int = Field(..., ge=1, le=30, examples=[4])
    is_active: bool = True


class TableUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=20)
    capacity: int | None = Field(None, ge=1, le=30)
    is_active: bool | None = None


class TableRead(BaseModel):
    id: int
    name: str
    capacity: int
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


# ── Reservation ───────────────────────────────────────────────────────────────

class ReservationCreate(BaseModel):
    guest_name: str = Field(..., min_length=1, max_length=100, examples=["John Doe"])
    phone: str = Field(..., min_length=7, max_length=32, examples=["+380671234567"])
    reservation_date: datetime.date = Field(..., examples=["2025-07-15"])
    start_time: datetime.time = Field(..., examples=["18:00"])
    end_time: datetime.time = Field(..., examples=["20:00"])
    guests: int = Field(..., ge=1, le=30, examples=[4])
    table_id: int | None = Field(None, description="Optionally assign a specific table")


class ReservationUpdate(BaseModel):
    guest_name: str | None = Field(None, min_length=1, max_length=100)
    phone: str | None = Field(None, min_length=7, max_length=32)
    reservation_date: datetime.date | None = None
    start_time: datetime.time | None = None
    end_time: datetime.time | None = None
    guests: int | None = Field(None, ge=1, le=30)
    table_id: int | None = None
    status: ReservationStatus | None = None


class TableNested(BaseModel):
    id: int
    name: str
    capacity: int

    model_config = {"from_attributes": True}


class ReservationRead(BaseModel):
    id: int
    guest_name: str
    phone: str
    table_id: int | None
    table: TableNested | None = None
    reservation_date: datetime.date
    start_time: datetime.time
    end_time: datetime.time
    guests: int
    status: ReservationStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}