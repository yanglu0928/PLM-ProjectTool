"""Packaged PlanVersion Edge/HTTPS/PG proof, layered on the P51-A05 runner."""

from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))

a05 = runpy.run_path(str(ROOT / "validation/plt-pkg-01-a09-p51-a05-prototype-packaged/verify.py"))
plan_edge = runpy.run_path(str(ROOT / "validation/plan-version-edge-postgres/verify.py"))


def skip_unrelated_survey_followups(_state, **_context) -> None:
    # P51-A17 is the PlanVersion slice. The enclosing P51-A05 chain has already
    # exercised Survey creation/review; its post-approval and synthetic-expiry
    # Edge reruns are unrelated and can fail on Chromium profile cleanup after
    # the PlanVersion callback has completed.
    return None


a05["p51"]["after_approval"] = skip_unrelated_survey_followups
a05["p51"]["after_expiry"] = skip_unrelated_survey_followups


def packaged_planversion_probe(**context) -> None:
    # Reuse the P51 disposable project and account, but do not make PlanVersion
    # acceptance depend on the unrelated Prototype Package catalog UI.
    fixture_db = context["fixture_db"]
    project = context["project"]
    with fixture_db() as db:
        db.execute("DELETE FROM plm.auth_login_rate_buckets")
        actor_row = db.execute(
            "SELECT user_id FROM plm.auth_users "
            "WHERE username_normalized='synthetic packaged user'"
        ).fetchone()
        assert actor_row is not None, "synthetic package manager missing"
        actor = actor_row[0]
        membership = db.execute(
            "SELECT project_role,state FROM plm.prj_project_members "
            "WHERE project_id=%s AND user_id=%s", (project, actor),
        ).fetchone()
        assert membership is not None and membership[0] in {
            "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
        }, membership
        with db.transaction():
            db.execute("SET LOCAL session_replication_role='replica'")
            db.execute("UPDATE plm.prj_projects SET state='ACTIVE' WHERE project_id=%s", (project,))
            db.execute(
                "UPDATE plm.prj_project_members SET state='ACTIVE',effective_at="
                "statement_timestamp(),ended_at=NULL WHERE project_id=%s AND user_id=%s",
                (project, actor),
            )
            db.execute(
                "UPDATE plm.prj_departments d SET state='ACTIVE' FROM plm.prj_project_members m "
                "WHERE m.project_id=%s AND m.user_id=%s AND d.department_id=m.department_id",
                (project, actor),
            )
    context["user_id"] = actor
    a05["seed_current_requirement"](context, project)
    with fixture_db() as db:
        approved = db.execute(
            "SELECT 1 FROM plm.sol_outlines WHERE project_id=%s "
            "AND current_approved_version_ref IS NOT NULL LIMIT 1", (project,),
        ).fetchone()
    if approved is None:
        # Reuse the already-reviewed source fixture builder; it writes only to
        # this disposable package-smoke PostgreSQL instance.
        from sqlalchemy.engine import URL

        from plm_assistant.entrypoints.windows_license_runtime import (
            _assemble as assemble_license_services,
        )
        from plm_assistant.entrypoints.windows_trusted_time import (
            create_windows_trusted_time_integrity,
        )
        from plm_assistant.modules.audit.application.public import AuditService
        from plm_assistant.modules.audit.infrastructure.audit_repository import (
            SqlAlchemyAuditRepository,
        )
        from plm_assistant.modules.auth.infrastructure.deployment_read_access import (
            SqlAlchemyDeploymentReadAccess,
        )
        from plm_assistant.modules.auth.infrastructure.project_read_access import (
            SqlAlchemyProjectReadAccess,
        )
        from plm_assistant.modules.document.application.prepare_download import (
            PrepareDownloadService,
        )
        from plm_assistant.modules.document.application.read_documents import (
            DocumentReadService,
        )
        from plm_assistant.modules.document.application.read_parse_result import (
            DocumentParseResultReadService,
        )
        from plm_assistant.modules.document.infrastructure.local_storage import (
            LocalFileStorage,
        )
        from plm_assistant.modules.document.infrastructure.parse_result_read_repository import (
            SqlAlchemyParseResultReadRepository,
        )
        from plm_assistant.modules.document.infrastructure.parse_result_storage import (
            LocalParseResultStorage,
        )
        from plm_assistant.modules.document.infrastructure.read_repository import (
            SqlAlchemyDocumentReadRepository,
        )
        from plm_assistant.modules.platform.infrastructure.bootstrap_config import (
            BootstrapSettings,
        )
        from plm_assistant.modules.platform.infrastructure.database import (
            create_database_runtime,
        )
        from plm_assistant.modules.license.infrastructure.packaged_product_key import (
            PackagedProductKey,
        )
        from plm_assistant.modules.license.infrastructure.windows_selected_machine import (
            WindowsSelectedMachine,
        )
        from plm_assistant.modules.project.infrastructure.authorization_repository import (
            SqlAlchemyProjectAuthorizationRepository,
        )

        runtime = create_database_runtime(URL.create(
            "postgresql+psycopg", username="poc_admin", host="127.0.0.1",
            port=fixture_db.pg_port, database=fixture_db.database,
        ))
        settings = BootstrapSettings(
            data_root=Path(fixture_db.data_root),
            selected_mac=context["selected_mac"],
            trusted_origins=(context["origin"],),
        )
        licenses = assemble_license_services(
            runtime, product=PackagedProductKey(
                read_manifest=lambda: Path(
                    fixture_db.product_public_key_file,
                ).read_bytes(),
            ),
            machine=WindowsSelectedMachine(settings.selected_mac),
            integrity=create_windows_trusted_time_integrity(),
        )
        audit = AuditService(SqlAlchemyAuditRepository())
        documents = DocumentReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(),
            admin_access=SqlAlchemyDeploymentReadAccess(),
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
            license_guard=licenses.guard,
            repository=SqlAlchemyDocumentReadRepository(),
        )
        downloads = PrepareDownloadService(
            reader=documents, storage=LocalFileStorage(settings.data_root),
            unit_of_work=runtime.unit_of_work, audit=audit,
        )
        parse_results = DocumentParseResultReadService(
            documents=downloads,
            metadata=SqlAlchemyParseResultReadRepository(),
            storage=LocalParseResultStorage(settings.data_root),
            unit_of_work=runtime.unit_of_work,
        )
        token = bytes.fromhex(context["client"].cookies["plm_session"])
        csrf = bytes.fromhex(context["login"].json()["data"]["csrf_token"])
        try:
            outline_fixture = plan_edge["owner"].full
            # The source fixture historically targets a database named
            # "postgres"; the packaged smoke creates a unique disposable DB.
            # Bind only this in-memory fixture module to that owned DB.
            outline_fixture._connection = lambda port: {
                "host": "127.0.0.1", "port": port, "user": "poc_admin",
                "dbname": fixture_db.database,
            }
            outline_fixture._outline_full(**(context | {
                "port": fixture_db.pg_port,
                "runtime": runtime, "manager": actor, "token": token,
                "csrf": csrf, "license_guard": licenses.guard,
                "audit": audit, "documents": documents,
                "downloads": downloads, "parse_results": parse_results,
            }))
        finally:
            runtime.dispose()
    with fixture_db() as db:
        assert db.execute(
            "SELECT 1 FROM plm.sol_outlines WHERE project_id=%s "
            "AND current_approved_version_ref IS NOT NULL LIMIT 1", (project,),
        ).fetchone(), "synthetic Approved Outline source fixture unavailable"

    env = os.environ.copy()
    env.update({
        "PLM_P51_A17_MANAGER": "Synthetic Packaged User",
        "PLM_P51_A17_REVIEWER": "Synthetic Handover Customer",
        "PLM_P51_A17_PASSWORD": "synthetic-packaged-login-password",
        "PLM_P51_A17_TEMP": r"D:\PLMToolTemp",
    })
    edge = subprocess.run(
        ["node", str(ROOT / "validation/plt-pkg-01-a09-p51-a17-planversion-packaged/run-edge-browser.mjs"),
         context["origin"], str(project)],
        cwd=ROOT, env=env, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=360, check=False,
    )
    if edge.returncode or "P51_A17_PACKAGED_PLANVERSION_EDGE_PASS" not in edge.stdout:
        raise AssertionError("packaged PlanVersion Edge flow failed: " + edge.stdout[-12000:])
    print(edge.stdout.strip(), flush=True)
    match = __import__("re").search(r"plan=([0-9a-f-]{36}); version=([0-9a-f-]{36})", edge.stdout)
    assert match, "PlanVersion browser result identities missing"
    plan_id, version_id = map(uuid.UUID, match.groups())
    with fixture_db() as db:
        plan = db.execute(
            "SELECT plan_state FROM plm.pln_plans WHERE plan_id=%s AND project_id=%s",
            (plan_id, project),
        ).fetchone()
        version = db.execute(
            "SELECT version_state,review_ref FROM plm.pln_plan_versions "
            "WHERE plan_version_id=%s AND project_id=%s", (version_id, project),
        ).fetchone()
        counts = db.execute(
            "SELECT (SELECT count(*) FROM plm.pln_wbs_items WHERE plan_version_id=%s),"
            "(SELECT count(*) FROM plm.pln_item_requirement_refs WHERE plan_version_id=%s),"
            "(SELECT count(*) FROM plm.pln_plan_version_validation_results WHERE plan_version_id=%s)",
            (version_id, version_id, version_id),
        ).fetchone()
        review = db.execute(
            "SELECT review_state,active_round_id FROM plm.rvw_reviews WHERE review_id=%s",
            (version[1],),
        ).fetchone() if version and version[1] else None
        round_state = db.execute(
            "SELECT round_state FROM plm.rvw_review_rounds WHERE review_round_id=%s",
            (review[1],),
        ).fetchone() if review else None
        decisions = db.execute(
            "SELECT count(*) FROM plm.rvw_review_decisions WHERE review_round_id=%s",
            (review[1],),
        ).fetchone()[0] if review else -1
    if (plan != ("ACTIVE",) or not version or version[0] != "IN_REVIEW"
            or counts != (2, 2, 1) or not review or review[0] != "IN_REVIEW"
            or not round_state or round_state[0] != "IN_REVIEW" or decisions != 0):
        raise AssertionError(
            f"packaged PlanVersion PG state mismatch: plan={plan}, version={version}, "
            f"children={counts}, review={review}, round={round_state}, decisions={decisions}"
        )
    print(f"P51_A17_PACKAGED_PLANVERSION_PG_PASS: state={version[0]}; "
          f"WBS/requirement/validation={counts}; Review/Round={review[0]}/{round_state[0]}; decisions=0",
          flush=True)


a05["prototype_probe"].__globals__["prototype_probe"] = packaged_planversion_probe


if __name__ == "__main__":
    test_temp = Path(os.environ.get("PLM_P51_TEMP_ROOT", r"D:\PLMToolTemp"))
    if (not test_temp.is_absolute() or test_temp.drive.upper() != "D:"
            or test_temp.name != "PLMToolTemp" or not str(test_temp).isascii()):
        raise ValueError("P51 temporary root must be an explicit ASCII D: PLMToolTemp directory")
    test_temp.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = str(test_temp)
    os.environ["TMP"] = str(test_temp)
    import tempfile
    tempfile.tempdir = None
    sys.exit(a05["main"]())
