"""Windows 11/PostgreSQL 18 proof for SurveyConclusion source boundaries."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.infrastructure.survey_conclusion_task import (
    SqlAlchemySurveyConclusionAITaskProof,
)
from plm_assistant.modules.document.application.prove_fixed_source import (
    VerifiedFixedSource,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentEvidenceSourceFacts,
)
from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectSourceService,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.handover.infrastructure.survey_conclusion_issue import (
    SqlAlchemySurveyConclusionIssueProof,
)
from plm_assistant.modules.platform.infrastructure.database import (
    create_database_runtime,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)
from plm_assistant.modules.project.application.authorization import ProjectActorFacts
from plm_assistant.modules.survey.application.conclusion_sources import (
    ConclusionProjectRecordQuery,
    SurveyConclusionProjectRecordProofService,
    SurveyConclusionSourceError,
)
from plm_assistant.modules.survey.infrastructure.conclusion_response_source import (
    SqlAlchemyConclusionResponseProof,
)


ROOT = Path(__file__).resolve().parents[2]
HOST, PORT, USER = "127.0.0.1", 55434, "poc_admin"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


schema = load(
    ROOT / "validation" / "sur-04-a02-conclusion-schema" / "verify.py",
    "sur04a03_schema_fixture",
)
definition = load(
    ROOT / "validation" / "sur-01-a02-definition-schema" / "verify.py",
    "sur04a03_definition_fixture",
)
round_fixture = load(
    ROOT / "validation" / "sur-02-a02-round-schema" / "verify.py",
    "sur04a03_round_fixture",
)


class SessionAccess:
    def __init__(self, actor: uuid.UUID) -> None:
        self.actor = actor

    def authenticated_user(self, transaction, *, session_token, now):
        return self.actor


class ProjectAccess:
    def __init__(self) -> None:
        self.role = "IMPLEMENTATION_MEMBER"

    def actor_facts(self, transaction, *, user_id, project_id, lock=False):
        return ProjectActorFacts("ACTIVE", self.role)


class FixedDocument:
    def __init__(self, facts: DocumentEvidenceSourceFacts) -> None:
        self.facts = facts

    def prove(
        self, transaction, query, *, document_id, document_version_id,
        parse_record_id=None,
    ):
        return VerifiedFixedSource(self.facts)


def count_sources(database: str) -> tuple[int, int, int, int, int]:
    with schema.connect(database) as db:
        return db.execute(
            "SELECT (SELECT count(*) FROM plm.srv_responses),"
            "(SELECT count(*) FROM plm.evd_evidence_records),"
            "(SELECT count(*) FROM plm.hnd_action_items),"
            "(SELECT count(*) FROM plm.ai_tasks),"
            "(SELECT count(*) FROM plm.srv_conclusions)"
        ).fetchone()


def main() -> None:
    database = "sur04a03_" + uuid.uuid4().hex[:8]
    with schema.connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create(
            "postgresql+psycopg", username=USER, host=HOST, port=PORT,
            database=database,
        )
        cfg = create_migration_config(url)
        command.upgrade(cfg, "head")
        command.check(cfg)
        with schema.connect(database) as db:
            ids = definition.seed_dependencies(db)
            db.execute(
                "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,"
                "project_role) VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER')",
                (ids["project"], ids["actor"], ids["department"]),
            )
            survey, version = definition.insert_valid(
                db, ids, name="Conclusion source proof survey",
            )
            round_fixture.approve_definition(db, ids, survey, version)
            round_id = db.execute(
                "INSERT INTO plm.srv_rounds(survey_id,survey_version_id,project_id,"
                "round_no,created_by) VALUES (%s,%s,%s,1,%s) "
                "RETURNING survey_round_id",
                (survey, version, ids["project"], ids["actor"]),
            ).fetchone()[0]
            db.execute(
                "UPDATE plm.srv_rounds SET round_state='OPEN',opened_by=%s,"
                "opened_at=statement_timestamp(),updated_by=%s,"
                "updated_at=statement_timestamp(),lock_version=1 "
                "WHERE survey_round_id=%s",
                (ids["actor"], ids["actor"], round_id),
            )
            assignment = db.execute(
                "INSERT INTO plm.srv_assignments(survey_round_id,survey_id,"
                "survey_version_id,project_id,department_id,created_by) "
                "VALUES (%s,%s,%s,%s,%s,%s) RETURNING survey_assignment_id",
                (round_id, survey, version, ids["project"], ids["department"],
                 ids["actor"]),
            ).fetchone()[0]
            question = db.execute(
                "SELECT question_row_id FROM plm.srv_questions "
                "WHERE survey_version_id=%s ORDER BY sequence_no LIMIT 1",
                (version,),
            ).fetchone()[0]
            with db.transaction():
                response = db.execute(
                    "INSERT INTO plm.srv_responses(survey_assignment_id,"
                    "survey_round_id,survey_id,survey_version_id,project_id,"
                    "question_row_id,response_source,recorded_by,recorded_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,'SELF_SERVICE',%s,"
                    "statement_timestamp()) RETURNING survey_response_id",
                    (assignment, round_id, survey, version, ids["project"],
                     question, ids["actor"]),
                ).fetchone()[0]
                answer = db.execute(
                    "INSERT INTO plm.srv_answers(survey_response_id,"
                    "survey_assignment_id,question_row_id,project_id,raw_answer) "
                    "VALUES (%s,%s,%s,%s,'Validated conclusion input') "
                    "RETURNING survey_answer_id",
                    (response, assignment, question, ids["project"]),
                ).fetchone()[0]
            evidence, document, document_version, fingerprint = (
                round_fixture.insert_evidence(db, ids)
            )
            db.execute(
                "INSERT INTO plm.srv_answer_evidence_refs(survey_answer_id,"
                "survey_response_id,survey_assignment_id,question_row_id,project_id,"
                "evidence_id,document_id,document_version_id,"
                "observed_evidence_lock_version,content_fingerprint,recorded_by,"
                "recorded_at,ordinal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,"
                "statement_timestamp(),0)",
                (answer, response, assignment, question, ids["project"], evidence,
                 document, document_version, fingerprint, ids["actor"]),
            )
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "UPDATE plm.srv_assignments SET submission_state='VALIDATED',"
                    "validated_by=%s,validated_at=statement_timestamp(),updated_by=%s,"
                    "updated_at=statement_timestamp(),lock_version=1 "
                    "WHERE survey_assignment_id=%s",
                    (ids["actor"], ids["actor"], assignment),
                )
                db.execute(
                    "UPDATE plm.srv_rounds SET round_state='CLOSED',closed_by=%s,"
                    "closed_at=statement_timestamp(),close_report_fingerprint=%s,"
                    "updated_by=%s,updated_at=statement_timestamp(),lock_version=2 "
                    "WHERE survey_round_id=%s",
                    (ids["actor"], b"c" * 32, ids["actor"], round_id),
                )

            action = uuid.uuid4()
            with db.transaction():
                created = db.execute("SELECT statement_timestamp()").fetchone()[0]
                db.execute(
                    "INSERT INTO plm.hnd_action_items(action_item_id,project_id,"
                    "source_kind,source_analysis_version_ref,source_item_id,action_type,"
                    "title,requested_input_spec,owner_ref,due_at,priority,created_by,"
                    "created_reason,created_at,updated_at) VALUES (%s,%s,'ANALYSIS_ITEM',"
                    "%s,%s,'PROVIDE_INFO','Conclusion open issue','{}'::jsonb,%s,"
                    "%s+interval '1 day','HIGH',%s,'A03 proof fixture',%s,%s)",
                    (action, ids["project"], ids["analysis_version"],
                     ids["handover_item"], ids["actor"], created, ids["actor"],
                     created, created),
                )
                db.execute(
                    "INSERT INTO plm.hnd_action_state_events(action_item_id,project_id,"
                    "sequence_no,from_state,to_state,actor_id,reason,occurred_at,trace_id) "
                    "VALUES (%s,%s,0,NULL,'OPEN',%s,'A03 proof fixture',%s,%s)",
                    (action, ids["project"], ids["actor"], created, uuid.uuid4()),
                )

            ai_task, invocation, suggestion = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute(
                    "INSERT INTO plm.ai_tasks(ai_task_id,scope,project_id,task_type,"
                    "requested_by,input_fingerprint,prompt_policy_ref,output_schema_ref,"
                    "context_policy_ref,task_state,suggestion_state,current_invocation_ref,"
                    "trace_id,started_at,completed_at) VALUES (%s,'PROJECT',%s,"
                    "'SURVEY_ANALYZE',%s,%s,'survey-analyze.v1','survey-conclusion.v1',"
                    "'project.v1','SUCCEEDED','AVAILABLE',%s,%s,statement_timestamp(),"
                    "statement_timestamp())",
                    (ai_task, ids["project"], ids["actor"], b"i" * 32,
                     invocation, uuid.uuid4()),
                )
                db.execute(
                    "INSERT INTO plm.ai_suggestion_payloads(suggestion_payload_id,"
                    "ai_invocation_id,ai_task_id,scope,project_id,output_schema_ref,"
                    "schema_version,canonical_payload,payload_fingerprint,quality_flags) "
                    "VALUES (%s,%s,%s,'PROJECT',%s,'survey-conclusion.v1',1,%s,%s,%s)",
                    (suggestion, invocation, ai_task, ids["project"],
                     Jsonb({"summary": "AI suggestion, not a formal fact"}),
                     b"a" * 32, Jsonb(["REVIEW_REQUIRED"])),
                )

        facts = DocumentEvidenceSourceFacts(
            document, document_version, "PROJECT", ids["project"],
            "PROJECT_RECORD", "ACTIVE", fingerprint.hex(),
        )
        projects = ProjectAccess()
        project_record = SurveyConclusionProjectRecordProofService(
            evidence=EvidenceFixedProjectSourceService(
                sessions=SessionAccess(ids["actor"]),
                projects=projects,
                evidence=SqlAlchemyEvidenceFixedSourceRepository(),
                documents=FixedDocument(facts),
                allowed_project_roles=frozenset({
                    "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                }),
                required_document_category="PROJECT_RECORD",
            ),
        )
        response_owner = SqlAlchemyConclusionResponseProof()
        issue_owner = SqlAlchemySurveyConclusionIssueProof()
        ai_owner = SqlAlchemySurveyConclusionAITaskProof()
        evidence_query = ConclusionProjectRecordQuery(
            b"s" * 32, uuid.uuid4(), ids["project"], evidence,
        )
        before = count_sources(database)
        runtime = create_database_runtime(url)
        with runtime.unit_of_work() as tx:
            response_proof = response_owner.prove(
                tx, project_id=ids["project"], survey_id=survey,
                round_refs=(round_id,), response_id=response,
            )
            assert response_proof is not None
            assert response_proof.answer_id == answer
            assert response_proof.evidence_ids == (evidence,)
            assert len(response_proof.answer_fingerprint) == 32

            evidence_proof = project_record.prove(tx, evidence_query)
            assert evidence_proof.evidence_id == evidence
            assert evidence_proof.observed_evidence_lock_version == 0
            assert evidence_proof.content_fingerprint == fingerprint

            issue_proof = issue_owner.prove(
                tx, project_id=ids["project"], action_item_id=action,
            )
            assert issue_proof is not None
            assert issue_proof.action_state == "OPEN" and issue_proof.lock_version == 0

            ai_proof = ai_owner.prove(
                tx, project_id=ids["project"], ai_task_id=ai_task,
            )
            assert ai_proof is not None
            assert ai_proof.invocation_id == invocation
            assert ai_proof.suggestion_payload_id == suggestion
            assert ai_proof.payload_fingerprint == b"a" * 32
            assert ai_proof.fact_status == "NOT_FORMAL_FACT"

            other_project = uuid.uuid4()
            assert response_owner.prove(
                tx, project_id=other_project, survey_id=survey,
                round_refs=(round_id,), response_id=response,
            ) is None
            assert response_owner.prove(
                tx, project_id=ids["project"], survey_id=survey,
                round_refs=(uuid.uuid4(),), response_id=response,
            ) is None
            assert issue_owner.prove(
                tx, project_id=other_project, action_item_id=action,
            ) is None
            assert ai_owner.prove(
                tx, project_id=other_project, ai_task_id=ai_task,
            ) is None
            assert ai_owner.prove(
                tx, project_id=ids["project"], ai_task_id=uuid.uuid4(),
            ) is None
            tx.commit()

        projects.role = "CUSTOMER_MANAGER"
        with runtime.unit_of_work() as tx:
            try:
                project_record.prove(tx, evidence_query)
            except SurveyConclusionSourceError as error:
                assert error.code == "SURVEY_CONCLUSION_SOURCE_INVALID"
            else:
                raise AssertionError("unauthorized project role accepted")

        assert count_sources(database) == before
        command.check(cfg)
    finally:
        if runtime is not None:
            runtime.dispose()
        with schema.connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database),
            ))
    print(
        "SUR_04_A03_CONCLUSION_SOURCE_PROOFS_PASS: caller-transaction, read-only, "
        "same-project CLOSED/VALIDATED Response, PROJECT_RECORD Evidence, current "
        "HND-03 state and SUCCEEDED SURVEY_ANALYZE non-formal suggestion proofs; "
        "cross-project, wrong-round, missing-reference and role refusals verified "
        "on Windows 11/PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
