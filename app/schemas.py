"""
Pydantic schemas for the admin REST API.
"""

import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import ReservationStatus



class TableCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=20, examples=["T1", "Bar-3"])
    capacity: int = Field(..., ge=1, le=30, examples=[4])
    is_active: bool = True
