"""Add OUT-01 OutputRequest and immutable OutputContext tables.

Revision ID: 20261026_0220
Revises: 20261026_0210
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261026_0220"
down_revision = "20261026_0210"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "out_requests",
        sa.Column("output_request_id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("output_type", sa.Text(), nullable=False),
        sa.Column("template_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("plugin_operation", sa.Text(), nullable=False),
        sa.Column("input_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("context_snapshot_ref", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("generation_no", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("request_state", sa.Text(), server_default=sa.text("'REQUESTED'"), nullable=False),
        sa.Column("job_ref", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("current_execution_ref", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("retryable", sa.Boolean(), nullable=True),
        sa.Column("requested_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  server_default=sa.text("statement_timestamp()"), nullable=False),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=True),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("lock_version", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("retention_due_at", postgresql.TIMESTAMP(timezone=True, precision=6), nullable=False),
        sa.PrimaryKeyConstraint("output_request_id", name="pk_out_requests"),
        sa.UniqueConstraint("output_request_id", "project_id", name="uq_out_requests__id_project"),
        sa.UniqueConstraint("project_id", "requested_by", "idempotency_key",
                            name="uq_out_requests__idempotency"),
        sa.ForeignKeyConstraint(["project_id"], ["plm.prj_projects.project_id"],
                                name="fk_out_requests__project", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["requested_by"], ["plm.auth_users.user_id"],
                                name="fk_out_requests__requester", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(
            ["template_version_id"],
            ["plm.prt_template_versions.prototype_template_version_id"],
            name="fk_out_requests__template_version", ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["job_ref"], ["plm.job_jobs.job_id"],
                                name="fk_out_requests__job", ondelete="NO ACTION"),
        sa.CheckConstraint(
            "output_request_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND project_id <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND requested_by <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND context_snapshot_ref <> '00000000-0000-0000-0000-000000000000'::uuid "
            "AND (job_ref IS NULL OR job_ref <> '00000000-0000-0000-0000-000000000000'::uuid) "
            "AND (current_execution_ref IS NULL OR current_execution_ref <> "
            "'00000000-0000-0000-0000-000000000000'::uuid)", name="ck_out_requests__ids"),
        sa.CheckConstraint(
            "request_state IN ('REQUESTED','QUEUED','GENERATING','VALIDATING','SUCCEEDED',"
            "'FAILED','CANCEL_REQUESTED','CANCELLED')", name="ck_out_requests__state"),
        sa.CheckConstraint(
            "output_type ~ '^[A-Z][A-Z0-9_]{0,63}$' AND "
            "char_length(policy_version) BETWEEN 1 AND 128 AND policy_version=btrim(policy_version) AND "
            "char_length(plugin_operation) BETWEEN 1 AND 128 AND plugin_operation=btrim(plugin_operation) AND "
            "char_length(idempotency_key) BETWEEN 1 AND 255 AND idempotency_key=btrim(idempotency_key) AND "
            "char_length(trace_id) BETWEEN 1 AND 128 AND trace_id=btrim(trace_id) AND "
            "octet_length(input_fingerprint)=32", name="ck_out_requests__request_shape"),
        sa.CheckConstraint("generation_no > 0 AND attempt_count >= 0 AND lock_version >= 0",
                           name="ck_out_requests__counters"),
        sa.CheckConstraint(
            "(request_state IN ('REQUESTED','QUEUED','GENERATING','VALIDATING') AND "
            "completed_at IS NULL AND error_code IS NULL) OR "
            "(request_state='SUCCEEDED' AND completed_at IS NOT NULL AND error_code IS NULL) OR "
            "(request_state='FAILED' AND completed_at IS NOT NULL AND error_code IS NOT NULL) OR "
            "(request_state IN ('CANCEL_REQUESTED','CANCELLED') AND "
            "(completed_at IS NULL OR completed_at>=requested_at))",
            name="ck_out_requests__completion"),
        sa.CheckConstraint(
            "(error_code IS NULL OR error_code ~ '^OUTPUT_[A-Z0-9_]{1,57}$') AND "
            "(started_at IS NULL OR (isfinite(started_at) AND started_at>=requested_at)) AND "
            "(completed_at IS NULL OR (isfinite(completed_at) AND completed_at>=requested_at AND "
            "(started_at IS NULL OR completed_at>=started_at))) AND "
            "isfinite(requested_at) AND isfinite(retention_due_at)",
            name="ck_out_requests__time_error"),
        schema="plm",
    )
    op.create_index(
        "uq_out_requests__generation_live", "out_requests",
        ["project_id", "output_type", "input_fingerprint", "template_version_id",
         "policy_version", "generation_no"], unique=True,
        postgresql_where=sa.text(
            "request_state IN ('REQUESTED','QUEUED','GENERATING','VALIDATING','SUCCEEDED')"
        ), schema="plm",
    )
    op.create_index(
        "ix_out_requests__project_state_requested", "out_requests",
        ["project_id", "request_state", sa.text("requested_at DESC"),
         sa.text("output_request_id DESC")], schema="plm",
    )

    op.create_table(
        "out_context_snapshots",
        sa.Column("context_snapshot_id", postgresql.UUID(as_uuid=True),
                  server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("output_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_schema_version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("context_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("context_fingerprint", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                  server_default=sa.text("statement_timestamp()"), nullable=False),
        sa.PrimaryKeyConstraint("context_snapshot_id", name="pk_out_context_snapshots"),
        sa.UniqueConstraint("context_snapshot_id", "output_request_id", "project_id",
                            name="uq_out_context_snapshots__identity"),
        sa.UniqueConstraint("output_request_id", name="uq_out_context_snapshots__request"),
        sa.ForeignKeyConstraint(
            ["output_request_id", "project_id"],
            ["plm.out_requests.output_request_id", "plm.out_requests.project_id"],
            name="fk_out_context_snapshots__request", ondelete="NO ACTION",
            deferrable=True, initially="DEFERRED"),
        sa.CheckConstraint(
            "context_snapshot_id <> '00000000-0000-0000-0000-000000000000'::uuid AND "
            "output_request_id <> '00000000-0000-0000-0000-000000000000'::uuid AND "
            "project_id <> '00000000-0000-0000-0000-000000000000'::uuid AND "
            "context_schema_version=1 AND octet_length(context_fingerprint)=32 AND "
            "jsonb_typeof(context_payload)='object' AND pg_column_size(context_payload)<=262144 AND "
            "isfinite(created_at)", name="ck_out_context_snapshots__shape"),
        schema="plm",
    )
    op.create_foreign_key(
        "fk_out_requests__context_snapshot", "out_requests", "out_context_snapshots",
        ["context_snapshot_ref", "output_request_id", "project_id"],
        ["context_snapshot_id", "output_request_id", "project_id"],
        source_schema="plm", referent_schema="plm", ondelete="NO ACTION",
        deferrable=True, initially="DEFERRED",
    )

    for table, pk, label in (
        ("out_context_source_refs", "source_ref_id", "source"),
        ("out_context_evidence_refs", "evidence_ref_id", "evidence"),
    ):
        fp = label == "evidence"
        cols = [
            sa.Column(pk, postgresql.UUID(as_uuid=True), server_default=sa.text("uuidv7()"), nullable=False),
            sa.Column("context_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("output_request_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("ref_ordinal", sa.Integer(), nullable=False),
            sa.Column("scope", sa.Text(), nullable=False),
            sa.Column("source_project_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("owner_module", sa.Text(), nullable=False),
            sa.Column("object_type", sa.Text(), nullable=False),
            sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("version_id", postgresql.UUID(as_uuid=True), nullable=False),
        ]
        if fp:
            cols.append(sa.Column("content_fingerprint", sa.LargeBinary(), nullable=False))
        cols.append(sa.Column("added_at", postgresql.TIMESTAMP(timezone=True, precision=6),
                              server_default=sa.text("statement_timestamp()"), nullable=False))
        label_prefix = "out_context_evidence_refs" if fp else "out_context_source_refs"
        op.create_table(
            table, *cols,
            sa.PrimaryKeyConstraint(pk, name=f"pk_{table}"),
            sa.ForeignKeyConstraint(
                ["context_snapshot_id", "output_request_id", "project_id"],
                ["plm.out_context_snapshots.context_snapshot_id",
                 "plm.out_context_snapshots.output_request_id",
                 "plm.out_context_snapshots.project_id"],
                name=f"fk_{table}__snapshot", ondelete="NO ACTION"),
            sa.UniqueConstraint("context_snapshot_id", "ref_ordinal",
                                name=f"uq_{table}__ordinal"),
            sa.UniqueConstraint("context_snapshot_id", "owner_module", "object_type",
                                "object_id", "version_id", name=f"uq_{table}__identity"),
            sa.CheckConstraint(
                f"{pk} <> '00000000-0000-0000-0000-000000000000'::uuid AND "
                "object_id <> '00000000-0000-0000-0000-000000000000'::uuid AND "
                "version_id <> '00000000-0000-0000-0000-000000000000'::uuid AND "
                "ref_ordinal BETWEEN 1 AND 10000",
                name=f"ck_{table}__ids"),
            sa.CheckConstraint(
                "owner_module ~ '^[a-z][a-z0-9_]{0,63}$' AND "
                "object_type ~ '^[A-Z][A-Z0-9_]{0,63}$' AND scope IN ('PROJECT','GLOBAL') AND "
                "((scope='PROJECT' AND source_project_id=project_id) OR "
                "(scope='GLOBAL' AND source_project_id IS NULL)) AND "
                + ("octet_length(content_fingerprint)=32 AND " if fp else "")
                + "isfinite(added_at)",
                name=f"ck_{table}__shape" if fp else f"ck_{table}__scope"),
            schema="plm",
        )
        op.create_index(
            f"ix_{table}__fixed_version", table,
            ["owner_module", "object_type", "object_id", "version_id"],
            schema="plm",
        )

    op.execute(sa.text(r"""
        CREATE OR REPLACE FUNCTION plm.guard_output_context_immutable()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'OutputContext snapshot references are immutable';
        END; $$;
    """))
    for table in (
        "out_context_snapshots", "out_context_source_refs",
        "out_context_evidence_refs",
    ):
        op.execute(sa.text(
            "CREATE TRIGGER trg_" + table + "__immutable "
            "BEFORE UPDATE OR DELETE ON plm." + table + " "
            "FOR EACH ROW EXECUTE FUNCTION plm.guard_output_context_immutable()"
        ))


def downgrade() -> None:
    if context.is_offline_mode():
        raise RuntimeError("offline OutputRequest downgrade is disabled")
    for table in (
        "out_context_evidence_refs", "out_context_source_refs",
        "out_context_snapshots", "out_requests",
    ):
        exists = op.get_bind().execute(sa.text(
            "SELECT EXISTS (SELECT 1 FROM plm." + table + ")"
        )).scalar_one()
        if exists:
            raise RuntimeError("OutputRequest data prevents safe downgrade")
    for table in (
        "out_context_evidence_refs", "out_context_source_refs",
        "out_context_snapshots",
    ):
        op.execute(sa.text(
            "DROP TRIGGER trg_" + table + "__immutable ON plm." + table
        ))
    op.execute(sa.text("DROP FUNCTION plm.guard_output_context_immutable()"))
    op.drop_table("out_context_evidence_refs", schema="plm")
    op.drop_table("out_context_source_refs", schema="plm")
    op.drop_constraint("fk_out_requests__context_snapshot", "out_requests",
                       schema="plm", type_="foreignkey")
    op.drop_table("out_context_snapshots", schema="plm")
    op.drop_table("out_requests", schema="plm")
