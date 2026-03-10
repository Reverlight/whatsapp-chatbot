import datetime
import enum

from sqlalchemy import (
    String, Date, Time, Integer, ForeignKey,
    Enum, Boolean, func, text,
)
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
    NO_SHOW = "no_show"


# ── Models ────────────────────────────────────────────────────────────────────
class Table(Base, AuditMixin):
    """A physical table in the restaurant."""

    __tablename__ = "tables"

    # Human-readable label shown to staff: "T1", "Bar-3", "Terrace A"
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    # Maximum guests this table can seat
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)

    # False when the table is temporarily removed or out of service
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="table")

    def __repr__(self) -> str:
        return f"<Table {self.number} ({self.capacity} seats, {self.zone})>"


class Reservation(Base, AuditMixin):
    __tablename__ = "reservations"

    guest_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    table_id: Mapped[int | None] = mapped_column(
        ForeignKey("tables.id"), nullable=True, index=True
    )

    reservation_date: Mapped[datetime.date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    guests: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus),
        nullable=False,
        default=ReservationStatus.PENDING,
        index=True,
    )


    def __repr__(self) -> str:
        return (
            f"<Reservation {self.confirmation_code} "
            f"{self.guest_name} {self.reservation_date} {self.start_time} "
            f"[{self.status}]>"
        )
