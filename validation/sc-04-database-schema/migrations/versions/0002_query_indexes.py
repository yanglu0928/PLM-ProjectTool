"""Add SC-03 representative indexes and append-only guards."""

from alembic import op


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


INDEX_DDL: tuple[str, ...] = (
    "CREATE UNIQUE INDEX uq_prj_members__user_active "
    "ON plm.prj_project_members (user_id) WHERE membership_state='ACTIVE'",
    "CREATE UNIQUE INDEX uq_prj_members__project_user_live "
    "ON plm.prj_project_members (project_id,user_id) "
    "WHERE membership_state IN ('ACTIVE','SUSPENDED')",
    "CREATE UNIQUE INDEX uq_rvw_rounds__review_in_review "
    "ON plm.rvw_review_rounds (review_id) WHERE round_state='IN_REVIEW'",
    "CREATE UNIQUE INDEX uq_job_leases__job_active "
    "ON plm.job_leases (job_id) WHERE state='ACTIVE'",
    "CREATE UNIQUE INDEX uq_rag_indexes__scope_purpose_active "
    "ON plm.rag_embedding_indexes (scope,project_id,index_purpose) "
    "NULLS NOT DISTINCT WHERE state='ACTIVE'",
    "CREATE UNIQUE INDEX uq_rag_embeddings__index_chunk_available "
    "ON plm.rag_embedding_records (embedding_index_id,chunk_id) WHERE state='AVAILABLE'",
    "CREATE INDEX ix_doc_documents__project_state_time "
    "ON plm.doc_documents (project_id,state,updated_at DESC,document_id DESC) "
    "WHERE scope='PROJECT'",
    "CREATE INDEX ix_job_jobs__claim "
    "ON plm.job_jobs (priority DESC,available_at,job_id) "
    "WHERE state IN ('QUEUED','RETRY_WAIT')",
    "CREATE INDEX ix_job_jobs__lease_expiry "
    "ON plm.job_jobs (lease_expires_at,job_id) WHERE state='RUNNING'",
    "CREATE INDEX ix_job_outbox__claim "
    "ON plm.job_outbox_events (next_attempt_at,outbox_event_id) "
    "WHERE delivery_state IN ('PENDING','RETRY_WAIT')",
    "CREATE INDEX ix_aud_events__project_time "
    "ON plm.aud_events (target_project_id,occurred_at DESC,audit_event_id DESC)",
    "CREATE INDEX ix_aud_events__target_time "
    "ON plm.aud_events "
    "(target_owner_module,target_object_type,target_object_id,target_version_id,occurred_at DESC)",
    "CREATE INDEX ix_trc_links__source_active "
    "ON plm.trc_links "
    "(source_owner_module,source_object_type,source_version_id,project_id,relation_type,target_version_id) "
    "WHERE state='ACTIVE'",
    "CREATE INDEX ix_trc_links__target_active "
    "ON plm.trc_links "
    "(target_owner_module,target_object_type,target_version_id,project_id,relation_type,source_version_id) "
    "WHERE state='ACTIVE'",
    "CREATE INDEX ix_plt_holds__selector_active "
    "ON plm.plt_retention_holds (scope,project_id,object_owner,object_type,object_id) "
    "WHERE state='ACTIVE'",
    "CREATE INDEX ix_doc_files__retention_due "
    "ON plm.doc_file_objects (retention_due_at,file_object_id) "
    "WHERE retention_due_at IS NOT NULL AND state IN ('STAGED','FAILED','CLEANUP_PENDING')",
    "CREATE INDEX ix_pln_wbs_items__parent_order "
    "ON plm.pln_wbs_items (plan_version_id,parent_item_id,ordinal,wbs_item_id)",
    "CREATE INDEX ix_pln_wbs_deps__out "
    "ON plm.pln_wbs_dependencies (plan_version_id,predecessor_item_id,successor_item_id)",
    "CREATE INDEX ix_pln_wbs_deps__in "
    "ON plm.pln_wbs_dependencies (plan_version_id,successor_item_id,predecessor_item_id)",
    "CREATE INDEX ix_rag_chunks__search_gin "
    "ON plm.rag_document_chunks USING gin (search_vector)",
    "CREATE INDEX ix_rag_chunks__project_state "
    "ON plm.rag_document_chunks (project_id,state,chunk_id) WHERE scope='PROJECT'",
    "CREATE INDEX ix_rag_embed__v32_hnsw "
    "ON plm.rag_embedding_records "
    "USING hnsw ((embedding::vector(32)) vector_cosine_ops) "
    "WITH (m=32,ef_construction=200) "
    "WHERE state='AVAILABLE' AND embedding_dimension=32",
)


INDEX_NAMES: tuple[str, ...] = tuple(ddl.split()[2] for ddl in INDEX_DDL)


def upgrade() -> None:
    for ddl in INDEX_DDL:
        op.execute(ddl)
    op.execute(
        """
        CREATE FUNCTION plm.deny_append_only_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'append-only table % cannot be changed', TG_TABLE_NAME
            USING ERRCODE='55000';
        END;
        $$
        """
    )
    for table_name in ("aud_events", "trc_links"):
        op.execute(
            f"CREATE TRIGGER trg_{table_name}__append_only "
            f"BEFORE UPDATE OR DELETE ON plm.{table_name} "
            "FOR EACH ROW EXECUTE FUNCTION plm.deny_append_only_change()"
        )


def downgrade() -> None:
    for table_name in ("aud_events", "trc_links"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}__append_only ON plm.{table_name}")
    op.execute("DROP FUNCTION IF EXISTS plm.deny_append_only_change()")
    for index_name in reversed(INDEX_NAMES):
        op.execute(f"DROP INDEX IF EXISTS plm.{index_name}")
