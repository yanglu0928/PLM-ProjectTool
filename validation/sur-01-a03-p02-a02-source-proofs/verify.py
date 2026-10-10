"""Windows 11/PostgreSQL 18 proof for Survey source Owner adapters."""

from __future__ import annotations

import runpy
import uuid
from pathlib import Path

from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.capability.infrastructure.survey_source_proof import (
    SqlAlchemyCapabilitySurveySourceProof,
)
from plm_assistant.modules.handover.infrastructure.survey_source_proof import (
    SqlAlchemyHandoverSurveySourceProof,
)
from plm_assistant.modules.document.infrastructure.survey_template_proof import (
    SqlAlchemySurveyTemplateProof,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.project.infrastructure.survey_source_proof import (
    SqlAlchemySurveyTargetDepartmentProof,
)


ROOT = Path(__file__).resolve().parents[2]
schema = runpy.run_path(str(
    ROOT / "validation" / "sur-01-a02-definition-schema" / "verify.py"
))
connect, seed_dependencies = schema["connect"], schema["seed_dependencies"]


def main() -> None:
    database = "sur01a03p02a02_" + uuid.uuid4().hex[:6]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        url = URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=55434, database=database,
        )
        command.upgrade(create_migration_config(url), "head")
        with connect(database) as db:
            ids = seed_dependencies(db)
        runtime = create_database_runtime(url)
        try:
            handover = SqlAlchemyHandoverSurveySourceProof()
            capability = SqlAlchemyCapabilitySurveySourceProof()
            department = SqlAlchemySurveyTargetDepartmentProof()
            template = SqlAlchemySurveyTemplateProof()
            with runtime.unit_of_work() as tx:
                h = handover.prove(
                    tx, project_id=ids["project"],
                    analysis_item_row_id=ids["handover_item_row"],
                    handover_analysis_version_id=ids["analysis_version"],
                    handover_analysis_id=ids["analysis"],
                )
                c = capability.prove(
                    tx, capability_item_row_id=ids["capability_item_row"],
                    baseline_version_id=ids["baseline_version"],
                    baseline_id=ids["baseline"],
                )
                d = department.prove(
                    tx, project_id=ids["project"], department_id=ids["department"],
                )
                t = template.prove(
                    tx, path_project_id=ids["project"],
                    document_id=ids["template_document"],
                    document_version_id=ids["template_version"],
                )
                assert h is not None and h.item_state == "CONFIRMED"
                assert c is not None and c.item_state == "AVAILABLE"
                assert d is not None and d.state == "ACTIVE"
                assert t is not None and t.scope == "GLOBAL"
                assert template.prove(
                    tx, path_project_id=ids["project"],
                    document_id=ids["record_document"],
                    document_version_id=ids["record_version"],
                ) is None
                assert handover.prove(
                    tx, project_id=uuid.uuid4(),
                    analysis_item_row_id=ids["handover_item_row"],
                    handover_analysis_version_id=ids["analysis_version"],
                    handover_analysis_id=ids["analysis"],
                ) is None
                assert capability.prove(
                    tx, capability_item_row_id=uuid.uuid4(),
                    baseline_version_id=ids["baseline_version"],
                    baseline_id=ids["baseline"],
                ) is None
                assert department.prove(
                    tx, project_id=ids["project"], department_id=uuid.uuid4(),
                ) is None
            with connect(database) as db, db.transaction():
                db.execute("SET LOCAL session_replication_role='replica'")
                db.execute("UPDATE plm.hnd_analyses SET analysis_state='RESTRICTED' "
                           "WHERE handover_analysis_id=%s", (ids["analysis"],))
                db.execute("UPDATE plm.cap_baselines SET baseline_state='RESTRICTED' "
                           "WHERE baseline_id=%s", (ids["baseline"],))
                db.execute("UPDATE plm.prj_departments SET state='INACTIVE' "
                           "WHERE department_id=%s", (ids["department"],))
            with runtime.unit_of_work() as tx:
                assert handover.prove(
                    tx, project_id=ids["project"],
                    analysis_item_row_id=ids["handover_item_row"],
                    handover_analysis_version_id=ids["analysis_version"],
                    handover_analysis_id=ids["analysis"],
                ) is None
                assert capability.prove(
                    tx, capability_item_row_id=ids["capability_item_row"],
                    baseline_version_id=ids["baseline_version"],
                    baseline_id=ids["baseline"],
                ) is None
                assert department.prove(
                    tx, project_id=ids["project"], department_id=ids["department"],
                ) is None
            print(
                "SUR_01_A03_P02_A02_SOURCE_PROOFS_PASS: current approved Handover/"
                "Capability, TEMPLATE Document and active Project Department proofs plus cross-scope, missing "
                "and stale-state rejection verified on PostgreSQL 18"
            )
        finally:
            runtime.dispose()
    finally:
        with connect("postgres") as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database)))


if __name__ == "__main__":
    main()
