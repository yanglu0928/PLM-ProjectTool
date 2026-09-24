"""LIC-01 signed installation history; never stores private signing keys."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, LargeBinary, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


class LicenseInstallationRow(Base):
    __tablename__ = "lic_installations"
    __table_args__ = (
        CheckConstraint("installation_state IN ('IMPORTED','ACTIVE','SUPERSEDED','REJECTED')", name="ck_lic_installations__state"),
        CheckConstraint("installation_state = 'IMPORTED' OR validation_result_ref IS NOT NULL", name="ck_lic_installations__validated_state"),
        CheckConstraint("char_length(public_key_ref) BETWEEN 1 AND 128 AND public_key_ref ~ '^[A-Za-z0-9][A-Za-z0-9._:/-]*$'", name="ck_lic_installations__public_key_ref"),
        CheckConstraint("lock_version >= 0", name="ck_lic_installations__lock_version"),
        Index("uq_lic_installations__one_active", "installation_state", unique=True, postgresql_where=text("installation_state = 'ACTIVE'")),
        Index("ix_lic_installations__imported", "imported_at", "license_installation_id"),
    )

    license_installation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    public_key_ref: Mapped[str] = mapped_column(Text, nullable=False)
    imported_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.auth_users.user_id", ondelete="NO ACTION", name="fk_lic_installations__importer"), nullable=False, index=True)
    imported_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
    installation_state: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'IMPORTED'"))
    validation_result_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    import_trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    lock_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))


class LicenseInstallationDocumentRow(Base):
    __tablename__ = "lic_installation_documents"
    __table_args__ = (
        UniqueConstraint("license_installation_id", name="uq_lic_installation_documents__installation"),
        CheckConstraint("octet_length(signed_document) BETWEEN 1 AND 65536", name="ck_lic_installation_documents__size"),
        CheckConstraint("octet_length(document_sha256) = 32", name="ck_lic_installation_documents__sha256"),
    )

    license_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuidv7()"))
    license_installation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plm.lic_installations.license_installation_id", ondelete="NO ACTION", name="fk_lic_installation_documents__installation"), nullable=False)
    signed_document: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    document_sha256: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6), nullable=False, server_default=text("statement_timestamp()"))
