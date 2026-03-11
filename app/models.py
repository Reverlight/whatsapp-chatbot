import datetime
import enum

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


# ── Mixins ────────────────────────────────────────────────────────────────────

class AuditMixin:
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


# ── Enums ─────────────────────────────────────────────────────────────────────

class ReservationStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW   = "no_show"


# ── Models ────────────────────────────────────────────────────────────────────

class RestaurantTable(Base, AuditMixin):
    """A physical table in the restaurant, managed by admins."""

    __tablename__ = "restaurant_tables"

    # Human-readable label shown to staff and confirmation messages: "T1", "Bar-3"
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    # Maximum guests this table can seat
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    # False when the table is temporarily out of service
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    reservations: Mapped[list["Reservation"]] = relationship(
        "Reservation", back_populates="table", foreign_keys="[Reservation.table_id]"
    )

    def __repr__(self) -> str:
        return f"<RestaurantTable {self.name} ({self.capacity} seats)>"


class Reservation(Base, AuditMixin):
    """A customer table reservation. Table is auto-assigned on booking."""

    __tablename__ = "reservations"

    guest_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Assigned automatically — best fitting free table for the requested guest count
    table_id: Mapped[int | None] = mapped_column(
        ForeignKey("restaurant_tables.id"), nullable=True, index=True
    )
    reservation_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    guests: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus),
        nullable=False,
        default=ReservationStatus.CONFIRMED,
        index=True,
    )

    table: Mapped["RestaurantTable | None"] = relationship(
        "RestaurantTable", back_populates="reservations", foreign_keys=[table_id]
    )

    def __repr__(self) -> str:
        return (
            f"<Reservation {self.guest_name} "
            f"{self.reservation_date} {self.start_time}–{self.end_time} "
            f"[{self.status}]>"
        )


class MenuDocument(Base, AuditMixin):
    """An uploaded menu PDF. Text is extracted at upload time for AI context."""

    __tablename__ = "menu_documents"

    filename: Mapped[str] = mapped_column(String(255), unique=False, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)