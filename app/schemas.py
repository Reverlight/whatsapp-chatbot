"""
Pydantic schemas for the admin REST API.
"""

import datetime

from pydantic import BaseModel, Field


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