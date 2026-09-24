from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


APPLICATION_SCHEMA = "plm"

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(table_name)s__%(column_0_N_name)s",
    "uq": "uq_%(table_name)s__%(column_0_N_name)s",
    "ck": "ck_%(table_name)s__%(column_0_name)s",
    "fk": "fk_%(table_name)s__%(column_0_N_name)s__%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared production ORM base; business models are added by module WBS tasks."""

    metadata = MetaData(
        schema=APPLICATION_SCHEMA,
        naming_convention=NAMING_CONVENTION,
    )
