from __future__ import annotations

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from schema_manifest import ROOTS


SCHEMA = "plm"
metadata = sa.MetaData(schema=SCHEMA)
UUID = postgresql.UUID(as_uuid=True)
UTC_TS = sa.TIMESTAMP(timezone=True)


def uuid_pk(name: str) -> sa.Column:
    return sa.Column(name, UUID, primary_key=True, server_default=sa.text("uuidv7()"))


def created_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", UTC_TS, nullable=False, server_default=sa.text("statement_timestamp()")),
    ]


def mutable_columns() -> list[sa.Column]:
    return [
        sa.Column("updated_at", UTC_TS, nullable=False, server_default=sa.text("statement_timestamp()")),
        sa.Column("lock_version", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
    ]


def project_fk() -> sa.Column:
    return sa.Column(
        "project_id",
        UUID,
        sa.ForeignKey(f"{SCHEMA}.prj_projects.project_id", ondelete="NO ACTION", onupdate="NO ACTION"),
        nullable=False,
    )


prj_projects = sa.Table(
    "prj_projects",
    metadata,
    uuid_pk("project_id"),
    sa.Column("project_code_normalized", sa.Text(), nullable=False),
    sa.Column("name", sa.Text(), nullable=False),
    sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'ACTIVE'")),
    *created_columns(),
    *mutable_columns(),
    sa.UniqueConstraint("project_code_normalized", name="uq_prj_projects__code_norm"),
    sa.CheckConstraint("state IN ('ACTIVE','ARCHIVED')", name="ck_prj_projects__state"),
    sa.CheckConstraint("lock_version >= 0", name="ck_prj_projects__lock_version"),
)

auth_users = sa.Table(
    "auth_users",
    metadata,
    uuid_pk("user_id"),
    sa.Column("username_normalized", sa.Text(), nullable=False),
    sa.Column("display_name", sa.Text(), nullable=False),
    sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'ACTIVE'")),
    *created_columns(),
    *mutable_columns(),
    sa.UniqueConstraint("username_normalized", name="uq_auth_users__username_norm"),
    sa.CheckConstraint("state IN ('ACTIVE','DISABLED','LOCKED')", name="ck_auth_users__state"),
)

prj_project_members = sa.Table(
    "prj_project_members",
    metadata,
    uuid_pk("project_member_id"),
    project_fk(),
    sa.Column("user_id", UUID, sa.ForeignKey(f"{SCHEMA}.auth_users.user_id", ondelete="NO ACTION"), nullable=False),
    sa.Column("project_role", sa.Text(), nullable=False),
    sa.Column("membership_state", sa.Text(), nullable=False, server_default=sa.text("'ACTIVE'")),
    *created_columns(),
    *mutable_columns(),
    sa.UniqueConstraint("project_member_id", "project_id", name="uq_prj_members__id_project"),
    sa.CheckConstraint(
        "membership_state IN ('ACTIVE','SUSPENDED','REMOVED')",
        name="ck_prj_members__state",
    ),
)


def scope_columns(table_name: str) -> tuple[list[sa.Column], list[sa.Constraint]]:
    return (
        [
            sa.Column("scope", sa.Text(), nullable=False),
            sa.Column(
                "project_id",
                UUID,
                sa.ForeignKey(f"{SCHEMA}.prj_projects.project_id", ondelete="NO ACTION"),
                nullable=True,
            ),
        ],
        [
            sa.CheckConstraint(
                "(scope='GLOBAL' AND project_id IS NULL) OR "
                "(scope='PROJECT' AND project_id IS NOT NULL)",
                name=f"ck_{table_name}__scope_project",
            )
        ],
    )


scope_cols, scope_checks = scope_columns("doc_documents")
doc_documents = sa.Table(
    "doc_documents",
    metadata,
    uuid_pk("document_id"),
    *scope_cols,
    sa.Column("title", sa.Text(), nullable=False),
    sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'ACTIVE'")),
    sa.Column("retention_due_at", UTC_TS, nullable=True),
    *created_columns(),
    *mutable_columns(),
    *scope_checks,
    sa.UniqueConstraint(
        "document_id", "scope", "project_id",
        name="uq_doc_documents__id_scope_project",
        postgresql_nulls_not_distinct=True,
    ),
)

scope_cols, scope_checks = scope_columns("doc_document_versions")
doc_document_versions = sa.Table(
    "doc_document_versions",
    metadata,
    uuid_pk("document_version_id"),
    sa.Column("document_id", UUID, nullable=False),
    *scope_cols,
    sa.Column("version_no", sa.Integer(), nullable=False),
    sa.Column("version_state", sa.Text(), nullable=False),
    sa.Column("content_fingerprint", postgresql.BYTEA(), nullable=False),
    *created_columns(),
    *scope_checks,
    sa.ForeignKeyConstraint(
        ["document_id", "scope", "project_id"],
        [
            f"{SCHEMA}.doc_documents.document_id",
            f"{SCHEMA}.doc_documents.scope",
            f"{SCHEMA}.doc_documents.project_id",
        ],
        name="fk_doc_versions__document_scope",
        ondelete="NO ACTION",
    ),
    sa.UniqueConstraint("document_id", "version_no", name="uq_doc_versions__document_no"),
    sa.CheckConstraint("version_no > 0", name="ck_doc_versions__version_no"),
    sa.CheckConstraint("octet_length(content_fingerprint)=32", name="ck_doc_versions__fingerprint"),
)

scope_cols, scope_checks = scope_columns("rvw_reviews")
rvw_reviews = sa.Table(
    "rvw_reviews",
    metadata,
    uuid_pk("review_id"),
    *scope_cols,
    sa.Column("subject_owner_module", sa.Text(), nullable=False),
    sa.Column("subject_object_type", sa.Text(), nullable=False),
    sa.Column("subject_object_id", UUID, nullable=False),
    sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'DRAFT'")),
    *created_columns(),
    *mutable_columns(),
    *scope_checks,
)

scope_cols, scope_checks = scope_columns("rvw_review_rounds")
rvw_review_rounds = sa.Table(
    "rvw_review_rounds",
    metadata,
    uuid_pk("review_round_id"),
    sa.Column("review_id", UUID, sa.ForeignKey(f"{SCHEMA}.rvw_reviews.review_id", ondelete="NO ACTION"), nullable=False),
    *scope_cols,
    sa.Column("subject_version_id", UUID, nullable=False),
    sa.Column("round_no", sa.Integer(), nullable=False),
    sa.Column("round_state", sa.Text(), nullable=False),
    *created_columns(),
    *scope_checks,
    sa.UniqueConstraint("review_id", "round_no", name="uq_rvw_rounds__review_no"),
)

scope_cols, scope_checks = scope_columns("job_jobs")
job_jobs = sa.Table(
    "job_jobs",
    metadata,
    uuid_pk("job_id"),
    *scope_cols,
    sa.Column("owner_module", sa.Text(), nullable=False),
    sa.Column("job_type", sa.Text(), nullable=False),
    sa.Column("idempotency_key", sa.Text(), nullable=False),
    sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'QUEUED'")),
    sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("available_at", UTC_TS, nullable=False, server_default=sa.text("statement_timestamp()")),
    sa.Column("lease_expires_at", UTC_TS, nullable=True),
    sa.Column("fencing_token", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
    sa.Column("retention_due_at", UTC_TS, nullable=True),
    *created_columns(),
    *mutable_columns(),
    *scope_checks,
    sa.UniqueConstraint(
        "owner_module", "scope", "project_id", "job_type", "idempotency_key",
        name="uq_job_jobs__idempotency",
        postgresql_nulls_not_distinct=True,
    ),
)

job_leases = sa.Table(
    "job_leases",
    metadata,
    uuid_pk("job_lease_id"),
    sa.Column("job_id", UUID, sa.ForeignKey(f"{SCHEMA}.job_jobs.job_id", ondelete="NO ACTION"), nullable=False),
    sa.Column("worker_id", sa.Text(), nullable=False),
    sa.Column("state", sa.Text(), nullable=False),
    sa.Column("fencing_token", sa.BigInteger(), nullable=False),
    sa.Column("lease_expires_at", UTC_TS, nullable=False),
    sa.Column("heartbeat_at", UTC_TS, nullable=False),
    *created_columns(),
)

scope_cols, scope_checks = scope_columns("job_outbox_events")
job_outbox_events = sa.Table(
    "job_outbox_events",
    metadata,
    uuid_pk("outbox_event_id"),
    *scope_cols,
    sa.Column("owner_module", sa.Text(), nullable=False),
    sa.Column("event_type", sa.Text(), nullable=False),
    sa.Column("delivery_state", sa.Text(), nullable=False, server_default=sa.text("'PENDING'")),
    sa.Column("next_attempt_at", UTC_TS, nullable=False, server_default=sa.text("statement_timestamp()")),
    *created_columns(),
    *scope_checks,
)

job_event_consumptions = sa.Table(
    "job_event_consumptions",
    metadata,
    uuid_pk("event_consumption_id"),
    sa.Column("outbox_event_id", UUID, sa.ForeignKey(f"{SCHEMA}.job_outbox_events.outbox_event_id", ondelete="NO ACTION"), nullable=False),
    sa.Column("consumer_id", sa.Text(), nullable=False),
    *created_columns(),
    sa.UniqueConstraint("outbox_event_id", "consumer_id", name="uq_job_consumptions__event_consumer"),
)

aud_events = sa.Table(
    "aud_events",
    metadata,
    uuid_pk("audit_event_id"),
    sa.Column("target_project_id", UUID, sa.ForeignKey(f"{SCHEMA}.prj_projects.project_id", ondelete="NO ACTION"), nullable=True),
    sa.Column("actor_id", UUID, nullable=True),
    sa.Column("target_owner_module", sa.Text(), nullable=False),
    sa.Column("target_object_type", sa.Text(), nullable=False),
    sa.Column("target_object_id", UUID, nullable=False),
    sa.Column("target_version_id", UUID, nullable=True),
    sa.Column("action", sa.Text(), nullable=False),
    sa.Column("occurred_at", UTC_TS, nullable=False, server_default=sa.text("statement_timestamp()")),
)

scope_cols, scope_checks = scope_columns("rag_embedding_indexes")
rag_embedding_indexes = sa.Table(
    "rag_embedding_indexes",
    metadata,
    uuid_pk("embedding_index_id"),
    *scope_cols,
    sa.Column("index_purpose", sa.Text(), nullable=False),
    sa.Column("index_version", sa.Integer(), nullable=False),
    sa.Column("embedding_dimension", sa.Integer(), nullable=False),
    sa.Column("state", sa.Text(), nullable=False),
    *created_columns(),
    *mutable_columns(),
    *scope_checks,
    sa.UniqueConstraint("embedding_index_id", "embedding_dimension", name="uq_rag_indexes__id_dimension"),
    sa.UniqueConstraint(
        "scope", "project_id", "index_purpose", "index_version",
        name="uq_rag_indexes__scope_purpose_version",
        postgresql_nulls_not_distinct=True,
    ),
    sa.CheckConstraint("embedding_dimension BETWEEN 1 AND 2000", name="ck_rag_indexes__dimension"),
)

scope_cols, scope_checks = scope_columns("rag_document_chunks")
rag_document_chunks = sa.Table(
    "rag_document_chunks",
    metadata,
    uuid_pk("chunk_id"),
    *scope_cols,
    sa.Column("document_version_id", UUID, sa.ForeignKey(f"{SCHEMA}.doc_document_versions.document_version_id", ondelete="NO ACTION"), nullable=False),
    sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'AVAILABLE'")),
    sa.Column("search_body", sa.Text(), nullable=False),
    sa.Column(
        "search_vector",
        postgresql.TSVECTOR(),
        sa.Computed("to_tsvector('simple', search_body)", persisted=True),
        nullable=False,
    ),
    *created_columns(),
    *mutable_columns(),
    *scope_checks,
)

scope_cols, scope_checks = scope_columns("rag_embedding_records")
rag_embedding_records = sa.Table(
    "rag_embedding_records",
    metadata,
    uuid_pk("embedding_record_id"),
    *scope_cols,
    sa.Column("embedding_index_id", UUID, nullable=False),
    sa.Column("chunk_id", UUID, sa.ForeignKey(f"{SCHEMA}.rag_document_chunks.chunk_id", ondelete="NO ACTION"), nullable=False),
    sa.Column("embedding_dimension", sa.Integer(), nullable=False),
    sa.Column("embedding", Vector(), nullable=False),
    sa.Column("state", sa.Text(), nullable=False),
    *created_columns(),
    *mutable_columns(),
    *scope_checks,
    sa.ForeignKeyConstraint(
        ["embedding_index_id", "embedding_dimension"],
        [f"{SCHEMA}.rag_embedding_indexes.embedding_index_id", f"{SCHEMA}.rag_embedding_indexes.embedding_dimension"],
        name="fk_rag_embeddings__index_dimension",
        ondelete="NO ACTION",
    ),
    sa.CheckConstraint("vector_dims(embedding)=embedding_dimension", name="ck_rag_embeddings__dimension"),
)

scope_cols, scope_checks = scope_columns("trc_links")
trc_links = sa.Table(
    "trc_links",
    metadata,
    uuid_pk("trace_link_id"),
    *scope_cols,
    sa.Column("source_owner_module", sa.Text(), nullable=False),
    sa.Column("source_object_type", sa.Text(), nullable=False),
    sa.Column("source_version_id", UUID, nullable=False),
    sa.Column("target_owner_module", sa.Text(), nullable=False),
    sa.Column("target_object_type", sa.Text(), nullable=False),
    sa.Column("target_version_id", UUID, nullable=False),
    sa.Column("relation_type", sa.Text(), nullable=False),
    sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'ACTIVE'")),
    *created_columns(),
    *scope_checks,
)

scope_cols, scope_checks = scope_columns("doc_file_objects")
doc_file_objects = sa.Table(
    "doc_file_objects",
    metadata,
    uuid_pk("file_object_id"),
    *scope_cols,
    sa.Column("storage_locator", sa.Text(), nullable=False),
    sa.Column("sha256", postgresql.BYTEA(), nullable=False),
    sa.Column("size_bytes", sa.BigInteger(), nullable=False),
    sa.Column("state", sa.Text(), nullable=False),
    sa.Column("retention_due_at", UTC_TS, nullable=True),
    *created_columns(),
    *mutable_columns(),
    *scope_checks,
    sa.CheckConstraint("octet_length(sha256)=32", name="ck_doc_files__sha256"),
    sa.CheckConstraint("size_bytes >= 0", name="ck_doc_files__size"),
)

plt_retention_holds = sa.Table(
    "plt_retention_holds",
    metadata,
    uuid_pk("retention_hold_id"),
    sa.Column("scope", sa.Text(), nullable=False),
    sa.Column("project_id", UUID, sa.ForeignKey(f"{SCHEMA}.prj_projects.project_id", ondelete="NO ACTION"), nullable=True),
    sa.Column("object_owner", sa.Text(), nullable=False),
    sa.Column("object_type", sa.Text(), nullable=False),
    sa.Column("object_id", UUID, nullable=False),
    sa.Column("state", sa.Text(), nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    *created_columns(),
    sa.CheckConstraint(
        "(scope='GLOBAL' AND project_id IS NULL) OR (scope='PROJECT' AND project_id IS NOT NULL)",
        name="ck_plt_holds__scope_project",
    ),
)

pln_wbs_items = sa.Table(
    "pln_wbs_items",
    metadata,
    uuid_pk("wbs_item_id"),
    project_fk(),
    sa.Column("plan_version_id", UUID, nullable=False),
    sa.Column("parent_item_id", UUID, nullable=True),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("wbs_code_normalized", sa.Text(), nullable=False),
    sa.Column("level", sa.Integer(), nullable=False),
    sa.Column("state", sa.Text(), nullable=False),
    *created_columns(),
    sa.UniqueConstraint("plan_version_id", "wbs_code_normalized", name="uq_pln_wbs_items__version_code"),
    sa.UniqueConstraint("wbs_item_id", "plan_version_id", "project_id", name="uq_pln_wbs_items__identity_scope"),
    sa.CheckConstraint("level BETWEEN 1 AND 6", name="ck_pln_wbs_items__level"),
)

pln_wbs_dependencies = sa.Table(
    "pln_wbs_dependencies",
    metadata,
    uuid_pk("wbs_dependency_id"),
    project_fk(),
    sa.Column("plan_version_id", UUID, nullable=False),
    sa.Column("predecessor_item_id", UUID, nullable=False),
    sa.Column("successor_item_id", UUID, nullable=False),
    sa.Column("dependency_type", sa.Text(), nullable=False, server_default=sa.text("'FS'")),
    *created_columns(),
    sa.ForeignKeyConstraint(
        ["predecessor_item_id", "plan_version_id", "project_id"],
        [f"{SCHEMA}.pln_wbs_items.wbs_item_id", f"{SCHEMA}.pln_wbs_items.plan_version_id", f"{SCHEMA}.pln_wbs_items.project_id"],
        name="fk_pln_wbs_deps__predecessor",
        ondelete="NO ACTION",
    ),
    sa.ForeignKeyConstraint(
        ["successor_item_id", "plan_version_id", "project_id"],
        [f"{SCHEMA}.pln_wbs_items.wbs_item_id", f"{SCHEMA}.pln_wbs_items.plan_version_id", f"{SCHEMA}.pln_wbs_items.project_id"],
        name="fk_pln_wbs_deps__successor",
        ondelete="NO ACTION",
    ),
    sa.CheckConstraint("dependency_type='FS'", name="ck_pln_wbs_deps__type"),
    sa.CheckConstraint("predecessor_item_id<>successor_item_id", name="ck_pln_wbs_deps__not_self"),
)


SPECIAL_TABLES = {table.name for table in metadata.tables.values()}


def create_generic_root(root) -> None:
    if root.table in SPECIAL_TABLES:
        return
    columns: list[sa.SchemaItem] = [uuid_pk(root.pk)]
    constraints: list[sa.SchemaItem] = []
    if root.profile.endswith("-PRJ"):
        columns.append(project_fk())
        constraints.append(sa.UniqueConstraint(root.pk, "project_id", name=f"uq_{root.table}__id_project"))
    elif root.profile.endswith("-SCP"):
        scoped, checks = scope_columns(root.table)
        columns.extend(scoped)
        constraints.extend(checks)
        constraints.append(
            sa.UniqueConstraint(
                root.pk, "scope", "project_id",
                name=f"uq_{root.table}__id_scope_project",
                postgresql_nulls_not_distinct=True,
            )
        )
    if root.profile.startswith("V-"):
        columns.extend(
            [
                sa.Column("series_id", UUID, nullable=False),
                sa.Column("version_no", sa.Integer(), nullable=False),
                sa.Column("state", sa.Text(), nullable=False),
                sa.Column("content_fingerprint", postgresql.BYTEA(), nullable=False),
            ]
        )
        constraints.extend(
            [
                sa.UniqueConstraint("series_id", "version_no", name=f"uq_{root.table}__series_no"),
                sa.CheckConstraint("version_no > 0", name=f"ck_{root.table}__version_no"),
                sa.CheckConstraint("octet_length(content_fingerprint)=32", name=f"ck_{root.table}__fingerprint"),
            ]
        )
    else:
        columns.append(sa.Column("state", sa.Text(), nullable=False, server_default=sa.text("'ACTIVE'")))
    columns.extend(created_columns())
    if root.profile.startswith(("M-", "R-")):
        columns.extend(mutable_columns())
        constraints.append(sa.CheckConstraint("lock_version >= 0", name=f"ck_{root.table}__lock_version"))
    sa.Table(root.table, metadata, *columns, *constraints)


for root_spec in ROOTS:
    create_generic_root(root_spec)


ROOT_TABLE_NAMES = frozenset(root.table for root in ROOTS)
