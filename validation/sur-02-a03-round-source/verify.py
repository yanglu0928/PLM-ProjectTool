"""Windows 11/PostgreSQL 18 proof for Round PROJECT_RECORD append."""

from __future__ import annotations

import runpy
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

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
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.application.authorization import ProjectActorFacts
from plm_assistant.modules.survey.application.round_source import (
    SurveyRoundProjectRecordProofService,
    SurveyRoundSourceAppend,
    SurveyRoundSourceError,
    SurveyRoundSourceQuery,
)
from plm_assistant.modules.survey.infrastructure.round_source_repository import (
    SqlAlchemySurveyRoundSourceRepository,
)


ROOT = Path(__file__).resolve().parents[2]
schema = runpy.run_path(str(
    ROOT / "validation" / "sur-02-a02-round-schema" / "verify.py"
))
connect = schema["connect"]
seed_dependencies = schema["load_definition_fixture"]().seed_dependencies
insert_valid = schema["load_definition_fixture"]().insert_valid
approve_definition = schema["approve_definition"]
insert_evidence = schema["insert_evidence"]


class SessionAccess:
    def __init__(self, actor: uuid.UUID) -> None:
        self.actor = actor

    def authenticated_user(self, transaction, *, session_token, now):
        return self.actor


class ProjectAccess:
    def __init__(self, role: str = "IMPLEMENTATION_MEMBER") -> None:
        self.role = role

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


def reject(operation, code: str) -> None:
    try:
        operation()
    except SurveyRoundSourceError as error:
        assert error.code == code, error.code
        return
    raise AssertionError("operation unexpectedly succeeded: " + code)


def main() -> None:
    database = "sur02a03_" + uuid.uuid4().hex[:8]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime = None
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        command.upgrade(create_migration_config(url), "head")
        with connect(database) as db:
            ids = seed_dependencies(db)
            survey, version = insert_valid(db, ids, name="Round source survey")
            approve_definition(db, ids, survey, version)
            question_id = db.execute(
                "SELECT question_id FROM plm.srv_questions "
                "WHERE survey_version_id=%s ORDER BY sequence_no LIMIT 1",
                (version,),
            ).fetchone()[0]
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
            evidence, document, document_version, fingerprint = insert_evidence(db, ids)

        facts = DocumentEvidenceSourceFacts(
            document, document_version, "PROJECT", ids["project"],
            "PROJECT_RECORD", "ACTIVE", fingerprint.hex(),
        )
        projects = ProjectAccess()
        owner = EvidenceFixedProjectSourceService(
            sessions=SessionAccess(ids["actor"]),
            projects=projects,
            evidence=SqlAlchemyEvidenceFixedSourceRepository(),
            documents=FixedDocument(facts),
            allowed_project_roles=frozenset({
                "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
            }),
            required_document_category="PROJECT_RECORD",
        )
        proofs = SurveyRoundProjectRecordProofService(evidence=owner)
        repository = SqlAlchemySurveyRoundSourceRepository()
        query = SurveyRoundSourceQuery(
            b"s" * 32, uuid.uuid4(), ids["project"], evidence,
        )
        runtime = create_database_runtime(url)

        with runtime.unit_of_work() as tx:
            verified = proofs.prove(tx, query)
            first = repository.append(tx, SurveyRoundSourceAppend(
                round_id, ids["project"], question_id, verified,
                datetime.now(timezone.utc),
            ))
            assert first.ordinal == 0 and first.question_id == question_id
            with connect(database) as rival:
                for table, identity, value in (
                    ("evd_evidence_records", "evidence_id", evidence),
                    ("srv_rounds", "survey_round_id", round_id),
                ):
                    try:
                        rival.execute(sql.SQL(
                            "SELECT 1 FROM plm.{} WHERE {}=%s FOR UPDATE NOWAIT"
                        ).format(sql.Identifier(table), sql.Identifier(identity)), (value,))
                    except psycopg.Error as error:
                        assert error.sqlstate == "55P03", (table, error.sqlstate)
                    else:
                        raise AssertionError(table + " was not locked in caller transaction")
            tx.commit()

        with runtime.unit_of_work() as tx:
            verified = proofs.prove(tx, query)
            second = repository.append(tx, SurveyRoundSourceAppend(
                round_id, ids["project"], None, verified,
                datetime.now(timezone.utc),
            ))
            assert second.ordinal == 1 and second.question_id is None
            tx.commit()

        with runtime.unit_of_work() as tx:
            verified = proofs.prove(tx, query)
            reject(
                lambda: repository.append(tx, SurveyRoundSourceAppend(
                    round_id, ids["project"], uuid.uuid4(), verified,
                    datetime.now(timezone.utc),
                )),
                "RESOURCE_NOT_FOUND",
            )
        with connect(database) as db:
            assert db.execute(
                "SELECT count(*),min(ordinal),max(ordinal) "
                "FROM plm.srv_round_source_records WHERE survey_round_id=%s",
                (round_id,),
            ).fetchone() == (2, 0, 1)

        projects.role = "CUSTOMER_MANAGER"
        with runtime.unit_of_work() as tx:
            reject(lambda: proofs.prove(tx, query), "ROUND_SOURCE_UNAVAILABLE")
        projects.role = "IMPLEMENTATION_MEMBER"

        with connect(database) as db:
            db.execute(
                "UPDATE plm.srv_rounds SET round_state='CLOSED',closed_by=%s,"
                "closed_at=statement_timestamp(),close_report_fingerprint=%s,"
                "updated_by=%s,updated_at=statement_timestamp(),lock_version=2 "
                "WHERE survey_round_id=%s",
                (ids["actor"], b"c" * 32, ids["actor"], round_id),
            )
        with runtime.unit_of_work() as tx:
            verified = proofs.prove(tx, query)
            reject(
                lambda: repository.append(tx, SurveyRoundSourceAppend(
                    round_id, ids["project"], None, verified,
                    datetime.now(timezone.utc),
                )),
                "RESOURCE_NOT_FOUND",
            )
        with connect(database) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.srv_round_source_records "
                "WHERE survey_round_id=%s", (round_id,)
            ).fetchone()[0] == 2
        command.check(create_migration_config(url))
    finally:
        if runtime is not None:
            runtime.dispose()
        with connect("postgres") as admin:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database))
            )
    print(
        "SUR_02_A03_ROUND_SOURCE_PASS: exact PROJECT_RECORD Evidence proof, "
        "PM/Implementation role boundary, caller-transaction Evidence/Round locks, "
        "fixed-version Question, sequential append, rollback and CLOSED refusal "
        "verified on Windows 11/PostgreSQL 18"
    )


if __name__ == "__main__":
    main()
