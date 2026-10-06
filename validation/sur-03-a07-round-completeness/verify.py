"""Windows 11/PostgreSQL 18 proof for Round completeness owner."""

from __future__ import annotations

import runpy, uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.document.application.prove_fixed_source import VerifiedFixedSource
from plm_assistant.modules.document.application.read_documents import DocumentEvidenceSourceFacts
from plm_assistant.modules.evidence.application.fixed_project_source import EvidenceFixedProjectSourceService
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.survey.application.round_completeness import SurveyRoundCompletenessError, SurveyRoundCompletenessOwner, SurveyRoundCompletenessQuery
from plm_assistant.modules.survey.infrastructure.round_completeness_repository import SqlAlchemySurveyRoundCompletenessRepository
from plm_assistant.modules.survey.infrastructure.submission_repository import SqlAlchemySurveyAssignmentSubmissionRepository

ROOT=Path(__file__).resolve().parents[2]
schema=runpy.run_path(str(ROOT/"validation"/"sur-02-a02-round-schema"/"verify.py"))
auth=runpy.run_path(str(ROOT/"validation"/"ai-02-a02-model-create"/"verify.py"))
connect,definition=schema["connect"],schema["load_definition_fixture"]()
approve_definition,insert_evidence=schema["approve_definition"],schema["insert_evidence"]
seed_user=auth["seed_user"]

class FixedDocument:
    def __init__(self,facts): self.facts=facts
    def prove(self,*args,**kwargs): return VerifiedFixedSource(self.facts)

def reject(action,code="SURVEY_ROUND_INCOMPLETE"):
    try: action()
    except SurveyRoundCompletenessError as error:
        assert error.code==code,(error.code,code); return
    raise AssertionError("expected "+code)

def main():
    database="sur03a07_"+uuid.uuid4().hex[:8]; token=b"p"*32
    with connect("postgres") as admin: admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    runtime=None
    try:
        url=URL.create("postgresql+psycopg",username="poc_admin",host="127.0.0.1",port=55434,database=database)
        command.upgrade(create_migration_config(url),"head")
        with connect(database) as db:
            ids=definition.seed_dependencies(db); actor=seed_user(db,"Completeness PM","NONE",token)
            db.execute("INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,'PROJECT_MANAGER')",(ids["project"],actor,ids["department"]))
            survey,version=definition.insert_valid(db,ids,name="Completeness survey"); approve_definition(db,ids,survey,version)
            qrow=db.execute("SELECT question_row_id FROM plm.srv_questions WHERE survey_version_id=%s ORDER BY sequence_no LIMIT 1",(version,)).fetchone()[0]
            evidence,document,document_version,fingerprint=insert_evidence(db,ids)
            round_id,empty_round,assignment,response,answer=(uuid.uuid4() for _ in range(5))
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("UPDATE plm.srv_questions SET required=false WHERE survey_version_id=%s AND question_row_id<>%s",(version,qrow))
                for rid,no in ((round_id,1),(empty_round,2)):
                    db.execute("INSERT INTO plm.srv_rounds(survey_round_id,survey_id,survey_version_id,project_id,round_no,round_state,opened_by,opened_at,created_by,updated_by,lock_version) VALUES (%s,%s,%s,%s,%s,'OPEN',%s,statement_timestamp(),%s,%s,1)",(rid,survey,version,ids["project"],no,actor,actor,actor))
                db.execute("INSERT INTO plm.srv_assignments(survey_assignment_id,survey_round_id,survey_id,survey_version_id,project_id,department_id,assignee_user_id,submission_state,submitted_by,submitted_at,validated_by,validated_at,created_by,updated_by,lock_version) VALUES (%s,%s,%s,%s,%s,%s,%s,'VALIDATED',%s,statement_timestamp(),%s,statement_timestamp(),%s,%s,3)",(assignment,round_id,survey,version,ids["project"],ids["department"],actor,actor,actor,actor,actor))
                db.execute("INSERT INTO plm.srv_responses(survey_response_id,survey_assignment_id,survey_round_id,survey_id,survey_version_id,project_id,question_row_id,response_source,recorded_by,recorded_at) VALUES (%s,%s,%s,%s,%s,%s,%s,'SELF_SERVICE',%s,statement_timestamp())",(response,assignment,round_id,survey,version,ids["project"],qrow,actor))
                db.execute("INSERT INTO plm.srv_answers(survey_answer_id,survey_response_id,survey_assignment_id,question_row_id,project_id,answer_value) VALUES (%s,%s,%s,%s,%s,to_jsonb('answer'::text))",(answer,response,assignment,qrow,ids["project"]))
                db.execute("INSERT INTO plm.srv_answer_evidence_refs(survey_answer_id,survey_response_id,survey_assignment_id,question_row_id,project_id,document_id,document_version_id,evidence_id,observed_evidence_lock_version,content_fingerprint,recorded_by,recorded_at,ordinal) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,statement_timestamp(),0)",(answer,response,assignment,qrow,ids["project"],document,document_version,evidence,fingerprint,actor))
        runtime=create_database_runtime(url)
        facts=DocumentEvidenceSourceFacts(document,document_version,"PROJECT",ids["project"],"PROJECT_RECORD","ACTIVE",fingerprint.hex(),"record.pdf")
        evidence_owner=EvidenceFixedProjectSourceService(sessions=SqlAlchemyProjectReadAccess(),projects=SqlAlchemyProjectAuthorizationRepository(),evidence=SqlAlchemyEvidenceFixedSourceRepository(),documents=FixedDocument(facts),allowed_project_roles=frozenset({"PROJECT_MANAGER","IMPLEMENTATION_MEMBER"}),clock=lambda:datetime.now(timezone.utc))
        owner=SurveyRoundCompletenessOwner(repository=SqlAlchemySurveyRoundCompletenessRepository(),submissions=SqlAlchemySurveyAssignmentSubmissionRepository(),evidence_owner=evidence_owner)
        query=SurveyRoundCompletenessQuery(token,uuid.uuid4(),ids["project"],round_id,actor,"PROJECT_MANAGER")
        with runtime.unit_of_work() as tx:
            first=owner.prove(tx,query); second=owner.prove(tx,query)
            assert first==second and first.assignment_count==1 and first.evidence_count==1
            with connect(database) as rival:
                for table,column,value in (("srv_rounds","survey_round_id",round_id),("srv_assignments","survey_assignment_id",assignment),("evd_evidence_records","evidence_id",evidence)):
                    try: rival.execute(sql.SQL("SELECT 1 FROM plm.{} WHERE {}=%s FOR UPDATE NOWAIT").format(sql.Identifier(table),sql.Identifier(column)),(value,))
                    except psycopg.Error as error: assert error.sqlstate=="55P03",(table,error.sqlstate)
                    else: raise AssertionError(table+" not locked")
        with runtime.unit_of_work() as tx:
            reject(lambda: owner.prove(tx,SurveyRoundCompletenessQuery(
                token,uuid.uuid4(),ids["project"],empty_round,actor,"PROJECT_MANAGER")))
        with connect(database) as db:
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("UPDATE plm.srv_assignments SET submission_state='SUBMITTED' WHERE survey_assignment_id=%s",(assignment,))
        with runtime.unit_of_work() as tx: reject(lambda: owner.prove(tx,query))
        with connect(database) as db:
            with db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("UPDATE plm.srv_assignments SET submission_state='VALIDATED' WHERE survey_assignment_id=%s",(assignment,))
            db.execute("UPDATE plm.evd_evidence_records SET eligibility_state='REVOKED',eligibility_reason='drift',updated_by=%s,updated_at=statement_timestamp(),lock_version=1 WHERE evidence_id=%s",(actor,evidence))
        with runtime.unit_of_work() as tx: reject(lambda: owner.prove(tx,query))
        command.check(create_migration_config(url))
    finally:
        if runtime is not None: runtime.dispose()
        with connect("postgres") as admin: admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
    print("SUR_03_A07_ROUND_COMPLETENESS_PASS: nonempty target coverage, VALIDATED/current-answer/Evidence proof, stable fingerprint, caller locks, empty/nonterminal/drift refusal verified on Windows 11/PostgreSQL 18")

if __name__=="__main__": main()
