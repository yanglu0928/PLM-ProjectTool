"""Durable singleton maintenance state; concurrency fence is a separate Port."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from .orm import Base


class MaintenanceStateRow(Base):
    __tablename__ = "plt_maintenance_state"
    __table_args__ = (
        CheckConstraint("state_id=1 AND state IN ('RUNNING','MAINTENANCE') "
                        "AND lock_version>=0", name="ck_plt_maintenance_state__shape"),
    )

    state_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
