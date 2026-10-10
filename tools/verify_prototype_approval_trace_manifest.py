"""Verify Migration 0133 against an isolated PostgreSQL 18 database."""

from __future__ import annotations

import argparse
import hashlib
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from plm_assistant.modules.platform.infrastructure.migration import (
    downgrade_database,
    upgrade_database,
)


PREVIOUS = "20261008_0132"
HEAD = "20261008_0133"


def _expect_database_error(action, fragment: str) -> None:
    try:
        action()
    except DBAPIError as error:
        if fragment not in str(error.orig):
            raise AssertionError(f"expected {fragment!r}, got {error.orig!s}") from error
    else:
        raise AssertionError(f"expected database rejection containing {fragment!r}")


def verify(database_url: str) -> None:
    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM plm.alembic_version")) == HEAD

    downgrade_database(database_url, PREVIOUS)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM plm.alembic_version")) == PREVIOUS
        assert not connection.scalar(text(
            "SELECT to_regclass('plm.prt_version_approval_trace_manifests') "
            "IS NOT NULL"
        ))
    upgrade_database(database_url, HEAD)

    ids = {name: uuid.uuid4() for name in (
        "user", "project", "template", "template_version", "prototype",
        "prototype_version", "review", "round", "review_result", "document",
        "document_version", "file", "requirement", "requirement_version",
        "template_link", "document_link", "requirement_link", "manifest",
    )}
    fingerprint = hashlib.sha256(b"PRT-01-A07-A03-P02").digest()

    seed = """
    SET session_replication_role='replica';
    INSERT INTO plm.auth_users
      (user_id,username_display,username_normalized,state,deployment_role,
       credential_version,lock_version)
    VALUES (:user,'Trace Approver','trace_approver','DISABLED','NONE',0,0);
    INSERT INTO plm.prj_projects
      (project_id,project_code,project_code_normalized,name,state,created_by,lock_version)
    VALUES (:project,'PRT0133','PRT0133','PRT 0133','ACTIVE',:user,0);
    INSERT INTO plm.prt_templates
      (prototype_template_id,scope,project_id,name,template_state,
       current_template_version_ref,created_by,lock_version)
    VALUES (:template,'GLOBAL',NULL,'Global Template','ACTIVE',:template_version,:user,1);
    INSERT INTO plm.prt_template_versions
      (prototype_template_version_id,prototype_template_id,scope,project_id,
       version_no,version_state,content_fingerprint,layout_contract,
       component_contract,applicable_terminals,created_by,declared_artifact_count)
    VALUES (:template_version,:template,'GLOBAL',NULL,1,'PUBLISHED',:fingerprint,
            '{}'::jsonb,'{}'::jsonb,ARRAY['WEB'],:user,0);
    INSERT INTO plm.rvw_reviews
      (review_id,scope,project_id,subject_type,subject_id,policy_code,
       review_state,active_round_id,lock_version,created_by)
    VALUES (:review,'PROJECT',:project,'PRT-03',:prototype,'PROTOTYPE_ALL_V1',
            'APPROVED',NULL,2,:user);
    INSERT INTO plm.rvw_review_rounds
      (review_round_id,review_id,scope,project_id,round_no,subject_version_id,
       round_state,lock_version,started_by,started_at)
    VALUES (:round,:review,'PROJECT',:project,1,:prototype_version,
            'APPROVED',2,:user,statement_timestamp());
    INSERT INTO plm.prt_prototypes
      (prototype_id,project_id,name,prototype_state,current_approved_version_ref,
       created_by,updated_by,lock_version)
    VALUES (:prototype,:project,'Approved Prototype','ACTIVE',:prototype_version,
            :user,:user,2);
    INSERT INTO plm.prt_prototype_versions
      (prototype_version_id,prototype_id,project_id,version_no,version_state,
       template_ref,template_version_ref,coverage_summary,content_fingerprint,
       declared_artifact_count,declared_requirement_count,
       declared_interaction_count,review_ref,review_round_ref,created_by)
    VALUES (:prototype_version,:prototype,:project,1,'APPROVED',:template,
            :template_version,'{}'::jsonb,:fingerprint,1,1,1,:review,:round,:user);
    INSERT INTO plm.doc_document_versions
      (document_version_id,document_id,scope,project_id,version_no,file_object_id,
       content_sha256,size_bytes,detected_mime,source_metadata,created_by,
       availability_state)
    VALUES (:document_version,:document,'GLOBAL',NULL,1,:file,:fingerprint,1,
            'text/plain','{}'::jsonb,:user,'AVAILABLE');
    INSERT INTO plm.prt_version_artifact_refs
      (prototype_version_id,prototype_id,project_id,artifact_kind,target_id,ordinal)
    VALUES (:prototype_version,:prototype,:project,'DOCUMENT_VERSION',
            :document_version,1);
    INSERT INTO plm.prt_version_requirement_refs
      (prototype_version_id,prototype_id,project_id,requirement_id,
       requirement_version_id,ordinal)
    VALUES (:prototype_version,:prototype,:project,:requirement,
            :requirement_version,1);
    SET session_replication_role='origin';
    """
    with engine.begin() as connection:
        seed_parameters = {**ids, "fingerprint": fingerprint}
        for statement in seed.split(";"):
            if statement.strip():
                connection.execute(text(statement), seed_parameters)
        for kind, owner, object_type, object_id, version_id, source_project, relation in (
            ("template_link", "prototype", "PRT-04", ids["template"],
             ids["template_version"], None, "DERIVED_FROM"),
            ("document_link", "document", "DOC-02", ids["document"],
             ids["document_version"], None, "DERIVED_FROM"),
            ("requirement_link", "requirement", "REQ-03", ids["requirement"],
             ids["requirement_version"], ids["project"], "IMPLEMENTS"),
        ):
            connection.execute(text("""
                INSERT INTO plm.trc_links
                  (trace_link_id,scope,project_id,source_owner_module,
                   source_object_type,source_object_id,source_version_id,
                   source_project_id,target_owner_module,target_object_type,
                   target_object_id,target_version_id,target_project_id,
                   relation_type,link_state,created_by,trace_id,lock_version)
                VALUES (:link,'PROJECT',:project,:owner,:object_type,:object_id,
                        :version_id,:source_project,'prototype','PRT-03',:prototype,
                        :prototype_version,:project,:relation,'ACTIVE',:user,
                        :trace_id,0)
            """), {
                **ids, "link": ids[kind], "owner": owner,
                "object_type": object_type, "object_id": object_id,
                "version_id": version_id, "source_project": source_project,
                "relation": relation, "trace_id": uuid.uuid4(),
            })

    manifest_insert = text("""
        INSERT INTO plm.prt_version_approval_trace_manifests
          (approval_trace_manifest_id,prototype_version_id,prototype_id,project_id,
           review_state_result_id,review_id,review_round_id,template_id,
           template_version_id,content_fingerprint,declared_artifact_count,
           declared_requirement_count,declared_trace_link_count,approved_by)
        VALUES (:manifest,:prototype_version,:prototype,:project,:review_result,
                :review,:round,:template,:template_version,:fingerprint,1,1,3,:user)
    """)
    review_result_insert = text("""
        INSERT INTO plm.prt_version_review_state_results
          (review_state_result_id,prototype_version_id,prototype_id,project_id,
           review_id,review_round_id,event_type,previous_approved_version_ref,
           current_approved_version_ref,actor_id,expected_lock_version,lock_version)
        VALUES (:review_result,:prototype_version,:prototype,:project,:review,:round,
                'APPROVED',NULL,:prototype_version,:user,1,2)
    """)

    def insert_approval_without_manifest() -> None:
        with engine.begin() as connection:
            connection.execute(review_result_insert, ids)

    _expect_database_error(
        insert_approval_without_manifest, "Prototype approval has no Trace manifest"
    )

    def insert_incomplete() -> None:
        with engine.begin() as connection:
            connection.execute(review_result_insert, ids)
            connection.execute(manifest_insert, {**ids, "fingerprint": fingerprint})

    _expect_database_error(
        insert_incomplete, "Prototype approval Trace manifest source set is incomplete"
    )

    source_insert = text("""
        INSERT INTO plm.prt_version_approval_trace_sources
          (approval_trace_manifest_id,prototype_version_id,prototype_id,project_id,
           ordinal,source_kind,source_owner_module,source_object_type,
           source_object_id,source_version_id,source_project_id,relation_type,
           trace_link_id)
        VALUES (:manifest,:prototype_version,:prototype,:project,:ordinal,:source_kind,
                :owner,:object_type,:object_id,:version_id,:source_project,
                :relation,:link)
    """)
    with engine.begin() as connection:
        connection.execute(review_result_insert, ids)
        connection.execute(manifest_insert, {**ids, "fingerprint": fingerprint})
        rows = (
            (1, "TEMPLATE_VERSION", "prototype", "PRT-04", ids["template"],
             ids["template_version"], None, "DERIVED_FROM", ids["template_link"]),
            (2, "DOCUMENT_VERSION", "document", "DOC-02", ids["document"],
             ids["document_version"], None, "DERIVED_FROM", ids["document_link"]),
            (3, "REQUIREMENT_VERSION", "requirement", "REQ-03", ids["requirement"],
             ids["requirement_version"], ids["project"], "IMPLEMENTS",
             ids["requirement_link"]),
        )
        for ordinal, source_kind, owner, object_type, object_id, version_id, source_project, relation, link in rows:
            connection.execute(source_insert, {
                **ids, "ordinal": ordinal, "source_kind": source_kind,
                "owner": owner, "object_type": object_type,
                "object_id": object_id, "version_id": version_id,
                "source_project": source_project, "relation": relation,
                "link": link,
            })

    with engine.connect() as connection:
        assert connection.scalar(text(
            "SELECT count(*) FROM plm.prt_version_approval_trace_manifests"
        )) == 1
        assert connection.scalar(text(
            "SELECT count(*) FROM plm.prt_version_approval_trace_sources"
        )) == 3

    def mismatched_edge() -> None:
        with engine.begin() as connection:
            connection.execute(source_insert, {
                **ids, "ordinal": 4, "source_kind": "DOCUMENT_VERSION",
                "owner": "document", "object_type": "DOC-02",
                "object_id": uuid.uuid4(), "version_id": uuid.uuid4(),
                "source_project": None, "relation": "DERIVED_FROM",
                "link": ids["template_link"],
            })

    _expect_database_error(
        mismatched_edge, "does not match active TraceLink"
    )

    for statement, fragment in (
        ("UPDATE plm.prt_version_approval_trace_manifests SET approved_by=approved_by",
         "history is immutable"),
        ("DELETE FROM plm.prt_version_approval_trace_sources",
         "history is immutable"),
        ("TRUNCATE plm.prt_version_approval_trace_sources",
         "history cannot be truncated"),
    ):
        _expect_database_error(
            lambda sql=statement: _execute(engine, sql), fragment
        )

    try:
        downgrade_database(database_url, PREVIOUS)
    except RuntimeError as error:
        assert "history prevents downgrade" in str(error)
    else:
        raise AssertionError("history-bearing Migration 0133 downgrade was not refused")

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM plm.alembic_version")) == HEAD
    engine.dispose()


def _execute(engine, statement: str) -> None:
    with engine.begin() as connection:
        connection.execute(text(statement))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database_url")
    args = parser.parse_args()
    verify(args.database_url)
    print("PRT_01_A07_A03_P02_APPROVAL_TRACE_MANIFEST_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
