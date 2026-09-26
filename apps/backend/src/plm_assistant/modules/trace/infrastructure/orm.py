"""Protected TraceLink history; target facts require owner ports."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plm_assistant.modules.platform.infrastructure.orm import Base


_PAIR = (
    "({role}_owner_module='document' AND {role}_object_type='DOC-02') OR "
    "({role}_owner_module='capability' AND {role}_object_type='CAP-02') OR "
    "({role}_owner_module='handover' AND {role}_object_type='HND-02') OR "
    "({role}_owner_module='survey' AND {role}_object_type IN ('SRV-02','SRV-05')) OR "
    "({role}_owner_module='requirement' AND {role}_object_type='REQ-03') OR "
    "({role}_owner_module='prototype' AND {role}_object_type IN ('PRT-03','PRT-04')) OR "
    "({role}_owner_module='solution' AND {role}_object_type IN ('SOL-01','SOL-03','SOL-05','SOL-06')) OR "
    "({role}_owner_module='plan' AND {role}_object_type IN ('PLN-02','PLN-03')) OR "
    "({role}_owner_module='output' AND {role}_object_type='OUT-02')"
)
_EDGE_SCOPE = (
    "(scope='GLOBAL' AND project_id IS NULL AND source_project_id IS NULL "
    "AND target_project_id IS NULL AND relation_type<>'REFERENCES_CAPABILITY') OR "
    "(scope='PROJECT' AND project_id IS NOT NULL AND target_project_id IS NOT NULL "
    "AND target_project_id=project_id AND "
    "((source_project_id IS NOT NULL AND source_project_id=project_id "
    "AND relation_type<>'REFERENCES_CAPABILITY') OR "
    "(source_project_id IS NULL AND relation_type IN ('DERIVED_FROM','REFERENCES_CAPABILITY') "
    "AND ((source_owner_module='capability' AND source_object_type='CAP-02') "
    "OR (source_owner_module='document' AND source_object_type='DOC-02' "
    "AND relation_type='DERIVED_FROM') "
    "OR (source_owner_module='prototype' AND source_object_type='PRT-04' "
    "AND relation_type='DERIVED_FROM') "
    "OR (source_owner_module='solution' AND source_object_type='SOL-01' "
    "AND relation_type='DERIVED_FROM') "
    "OR (source_owner_module='plan' AND source_object_type='PLN-03' "
    "AND relation_type='DERIVED_FROM')))))"
)


class TraceLinkRow(Base):
    __tablename__ = "trc_links"
    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                             name="fk_trc_links__project", ondelete="NO ACTION"),
        ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                             name="fk_trc_links__creator", ondelete="NO ACTION"),
        ForeignKeyConstraint(["superseded_by_ref"], ["plm.trc_links.trace_link_id"],
                             name="fk_trc_links__replacement", ondelete="NO ACTION"),
        CheckConstraint(f"({_PAIR.format(role='source')})",
                        name="ck_trc_links__source_type"),
        CheckConstraint(f"({_PAIR.format(role='target')})",
                        name="ck_trc_links__target_type"),
        CheckConstraint(_EDGE_SCOPE, name="ck_trc_links__scope"),
        CheckConstraint("NOT (source_owner_module=target_owner_module AND "
                        "source_object_type=target_object_type AND "
                        "source_object_id=target_object_id AND "
                        "source_version_id=target_version_id)",
                        name="ck_trc_links__not_self"),
        CheckConstraint("source_object_id<>'00000000-0000-0000-0000-000000000000'::uuid "
                        "AND source_version_id<>'00000000-0000-0000-0000-000000000000'::uuid "
                        "AND target_object_id<>'00000000-0000-0000-0000-000000000000'::uuid "
                        "AND target_version_id<>'00000000-0000-0000-0000-000000000000'::uuid "
                        "AND trace_id<>'00000000-0000-0000-0000-000000000000'::uuid",
                        name="ck_trc_links__identities"),
        CheckConstraint("relation_type IN ('DERIVED_FROM','REFINES','IMPLEMENTS',"
                        "'VALIDATES','GENERATED_FROM','REFERENCES_CAPABILITY','SUPERSEDES')",
                        name="ck_trc_links__relation"),
        CheckConstraint("(link_state='SUPERSEDED' AND superseded_by_ref IS NOT NULL "
                        "AND superseded_by_ref<>trace_link_id) OR "
                        "(link_state IN ('ACTIVE','REVOKED') AND superseded_by_ref IS NULL)",
                        name="ck_trc_links__state"),
        Index("uq_trc_links__active_edge", "source_owner_module", "source_object_type",
              "source_object_id", "source_version_id", "target_owner_module",
              "target_object_type", "target_object_id", "target_version_id", "relation_type",
              unique=True, postgresql_where=text("link_state='ACTIVE'")),
        Index("ix_trc_links__source_active", "source_owner_module", "source_object_type",
              "source_version_id", "source_project_id", "relation_type", "target_version_id",
              postgresql_where=text("link_state='ACTIVE'")),
        Index("ix_trc_links__target_active", "target_owner_module", "target_object_type",
              "target_version_id", "target_project_id", "relation_type", "source_version_id",
              postgresql_where=text("link_state='ACTIVE'")),
    )

    trace_link_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                                     server_default=text("uuidv7()"))
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_owner_module: Mapped[str] = mapped_column(Text, nullable=False)
    source_object_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    target_owner_module: Mapped[str] = mapped_column(Text, nullable=False)
    target_object_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    relation_type: Mapped[str] = mapped_column(Text, nullable=False)
    link_state: Mapped[str] = mapped_column(Text, nullable=False,
                                            server_default=text("'ACTIVE'"))
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True, precision=6),
                                                 nullable=False,
                                                 server_default=text("statement_timestamp()"))
    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    superseded_by_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
