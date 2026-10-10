"""DOC-03 FileObject metadata and append-only state history.

Revision ID: 20260925_0020
Revises: 20260925_0019
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql


revision = "20260925_0020"
down_revision = "20260925_0019"
branch_labels = None
depends_on = None


_STATES = "'STAGED','AVAILABLE','FAILED','CLEANUP_PENDING','REMOVED','RESTRICTED'"


def upgrade() -> None:
    op.create_table(
        "doc_file_objects",
        sa.Column("file_object_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("storage_class", sa.Text(), nullable=False),
        sa.Column("storage_locator", sa.Text(), nullable=False),
        sa.Column("original_name_metadata", sa.Text(), nullable=False),
        sa.Column("sha256", sa.LargeBinary()),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("detected_mime", sa.Text()),
        sa.Column("file_state", sa.Text(), nullable=False, server_default=sa.text("'STAGED'")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True)),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.Column("available_at", postgresql.TIMESTAMP(timezone=True, precision=6)),
        sa.Column("failure_code", sa.Text()),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("retention_due_at", postgresql.TIMESTAMP(timezone=True, precision=6)),
        sa.UniqueConstraint("file_object_id", "scope", "project_id",
                            name="uq_doc_file_objects__id_scope_project",
                            postgresql_nulls_not_distinct=True),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_doc_file_objects__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["created_by"], ["plm.auth_users.user_id"],
                                name="fk_doc_file_objects__creator", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["updated_by"], ["plm.auth_users.user_id"],
                                name="fk_doc_file_objects__updater", ondelete="NO ACTION"),
        sa.CheckConstraint("(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)",
                           name="ck_doc_file_objects__scope_project"),
        sa.CheckConstraint("storage_class IN ('TEMPORARY','PERSISTENT')",
                           name="ck_doc_file_objects__storage_class"),
        sa.CheckConstraint(f"file_state IN ({_STATES})", name="ck_doc_file_objects__state"),
        sa.CheckConstraint("char_length(storage_locator) BETWEEN 1 AND 1024 AND left(storage_locator,1) <> '/' AND position('..' in storage_locator)=0 AND position(':' in storage_locator)=0 AND position(chr(92) in storage_locator)=0",
                           name="ck_doc_file_objects__locator"),
        sa.CheckConstraint("char_length(original_name_metadata) BETWEEN 1 AND 255",
                           name="ck_doc_file_objects__name"),
        sa.CheckConstraint("sha256 IS NULL OR octet_length(sha256)=32", name="ck_doc_file_objects__sha256"),
        sa.CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="ck_doc_file_objects__size"),
        sa.CheckConstraint("detected_mime IS NULL OR char_length(detected_mime) BETWEEN 1 AND 255",
                           name="ck_doc_file_objects__mime"),
        sa.CheckConstraint("failure_code IS NULL OR char_length(failure_code) BETWEEN 1 AND 64",
                           name="ck_doc_file_objects__failure"),
        sa.CheckConstraint("lock_version >= 0", name="ck_doc_file_objects__version"),
        sa.CheckConstraint("file_state NOT IN ('AVAILABLE','RESTRICTED') OR (sha256 IS NOT NULL AND size_bytes IS NOT NULL AND detected_mime IS NOT NULL AND available_at IS NOT NULL)",
                           name="ck_doc_file_objects__available_shape"),
        sa.CheckConstraint("available_at IS NULL OR available_at >= created_at",
                           name="ck_doc_file_objects__available_time"),
        schema="plm",
    )
    op.create_index("ix_doc_file_objects__scope_project_state", "doc_file_objects",
                    ["scope", "project_id", "file_state"], schema="plm")
    op.create_table(
        "doc_file_state_events",
        sa.Column("file_state_event_id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuidv7()")),
        sa.Column("file_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_state", sa.Text()),
        sa.Column("to_state", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text()),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False,
                  server_default=sa.text("statement_timestamp()")),
        sa.ForeignKeyConstraint(["file_object_id"], ["plm.doc_file_objects.file_object_id"],
                                name="fk_doc_file_state_events__file", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["plm.auth_users.user_id"],
                                name="fk_doc_file_state_events__actor", ondelete="NO ACTION"),
        sa.CheckConstraint(f"from_state IS NULL OR from_state IN ({_STATES})",
                           name="ck_doc_file_state_events__from"),
        sa.CheckConstraint(f"to_state IN ({_STATES})", name="ck_doc_file_state_events__to"),
        sa.CheckConstraint("reason_code IS NULL OR char_length(reason_code) BETWEEN 1 AND 64",
                           name="ck_doc_file_state_events__reason"),
        schema="plm",
    )
    op.create_index("ix_doc_file_state_events__file_created", "doc_file_state_events",
                    ["file_object_id", "created_at"], schema="plm")
    op.execute("""
        CREATE FUNCTION plm.reject_file_state_event_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'file state event is immutable';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_doc_file_state_events_immutable
        BEFORE UPDATE OR DELETE ON plm.doc_file_state_events
        FOR EACH ROW EXECUTE FUNCTION plm.reject_file_state_event_mutation()
    """)


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline downgrade is disabled for FileObject metadata")
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM plm.doc_file_objects)")) or bind.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM plm.doc_file_state_events)")
    ):
        raise RuntimeError("FileObject metadata exists; downgrade refused")
    op.execute("DROP TRIGGER trg_doc_file_state_events_immutable ON plm.doc_file_state_events")
    op.execute("DROP FUNCTION plm.reject_file_state_event_mutation()")
    op.drop_index("ix_doc_file_state_events__file_created", table_name="doc_file_state_events", schema="plm")
    op.drop_table("doc_file_state_events", schema="plm")
    op.drop_index("ix_doc_file_objects__scope_project_state", table_name="doc_file_objects", schema="plm")
    op.drop_table("doc_file_objects", schema="plm")
