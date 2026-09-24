from __future__ import annotations

from sqlalchemy import BigInteger, Float, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class PocVector(Base):
    __tablename__ = "poc02_migration_vectors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(32), nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
