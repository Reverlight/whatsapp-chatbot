from datetime import datetime
from typing import Optional, Self

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AuditMixin:
    # The Shared columns class
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )


import datetime

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SessionChat(Base, AuditMixin):
    session_id 


class Message(Base, AuditMixin):
    session_id foreign key
    message
