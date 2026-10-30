"""Packaged synthetic Prototype Edge/HTTPS/PG verification for P51-A05."""

from __future__ import annotations

import argparse
import hashlib
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
p51 = runpy.run_path(str(ROOT / "validation/sur-07-a08-survey-version-packaged/verify.py"))


def seed_current_requirement(context: dict, project: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed only the approved Requirement and fixed Project Document fixtures."""
    requirement, version = uuid.uuid4(), uuid.uuid4()
    review_id, review_round_id = uuid.uuid4(), uuid.uuid4()
    source = uuid.uuid4()
    criteria = (uuid.uuid4(), uuid.uuid4())
    document, file_object, document_version = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    content = b"Synthetic Prototype fixed document; not customer information.\n"
    content_sha = hashlib.sha256(content).digest()
    actor = context["user_id"]
    with context["fixture_db"]() as db, db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        db.execute(
            "INSERT INTO plm.doc_documents(document_id,scope,project_id,document_category,"
            "title,original_display_name,created_by) VALUES (%s,'PROJECT',%s,'PROJECT_RECORD',"
            "'Synthetic Prototype Fixed Document','prototype-input.txt',%s)",
            (document, project, actor),
        )
        db.execute(
            "INSERT INTO plm.doc_file_objects(file_object_id,scope,project_id,storage_class,"
            "storage_locator,original_name_metadata,created_by,file_state,sha256,size_bytes,"
            "detected_mime,available_at) VALUES (%s,'PROJECT',%s,'PERSISTENT',%s,"
            "'prototype-input.txt',%s,'AVAILABLE',%s,%s,'text/plain',statement_timestamp())",
            (file_object, project, f"projects/{project.hex}/objects/{file_object.hex[:2]}/{file_object.hex}", actor,
             content_sha, len(content)),
        )
        db.execute(
            "INSERT INTO plm.doc_document_versions(document_version_id,document_id,scope,"
            "project_id,version_no,file_object_id,content_sha256,size_bytes,detected_mime,"
            "source_metadata,created_by) VALUES (%s,%s,'PROJECT',%s,1,%s,%s,%s,'text/plain',"
            "'{}'::jsonb,%s)",
            (document_version, document, project, file_object, content_sha, len(content), actor),
        )
        db.execute(
            "UPDATE plm.doc_documents SET latest_version_ref=%s,effective_version_ref=%s "
            "WHERE document_id=%s", (document_version, document_version, document),
        )
        db.execute(
            "INSERT INTO plm.req_requirements(requirement_id,project_id,requirement_code,"
            "requirement_code_normalized,created_by) VALUES (%s,%s,%s,%s,%s)",
            (requirement, project, "REQ-P51-PROTOTYPE-001", "REQ-P51-PROTOTYPE-001", actor),
        )
        # A05 uses a synthetic pre-approved Requirement as Prototype input. Keep its
        # Review pointers internally coherent instead of inventing orphan UUIDs.
        db.execute(
            """INSERT INTO plm.rvw_reviews(review_id,scope,project_id,subject_type,
              subject_id,policy_code,review_state,active_round_id,created_by)
              VALUES (%s,'PROJECT',%s,'REQ-03',%s,'REQUIREMENT_ALL_V1','APPROVED',NULL,%s)""",
            (review_id, project, requirement, actor),
        )
        db.execute(
            """INSERT INTO plm.rvw_review_rounds(review_round_id,review_id,scope,
              project_id,round_no,subject_version_id,round_state,started_by,started_at)
              VALUES (%s,%s,'PROJECT',%s,1,%s,'APPROVED',%s,statement_timestamp())""",
            (review_round_id, review_id, project, version, actor),
        )
        db.execute(
            """INSERT INTO plm.req_requirement_versions(
              requirement_version_id,requirement_id,project_id,version_no,version_state,
              statement,rationale,domain_name,priority,risk,requirement_classification,
              content_fingerprint,declared_source_count,declared_acceptance_count,
              declared_capability_count,declared_assumption_count,declared_exclusion_count,
              declared_dependency_count,declared_ai_task_count,review_ref,review_round_ref,created_by)
              VALUES (%s,%s,%s,1,'APPROVED',%s,%s,'PLM','HIGH','LOW','STANDARD_FUNCTION',
              %s,1,2,0,0,0,0,0,%s,%s,%s)""",
            (version, requirement, project,
             "项目应形成可追溯的受控原型评审记录",
             "仅作为P51隔离浏览器验收的合成输入，不代表客户确认",
             b"p" * 32, review_id, review_round_id, actor),
        )
        db.execute(
            """INSERT INTO plm.req_sources(requirement_version_id,requirement_id,project_id,
              ordinal,source_type,source_object_id) VALUES (%s,%s,%s,0,'HUMAN_DECISION',%s)""",
            (version, requirement, project, source),
        )
        for ordinal, criterion in enumerate(criteria):
            db.execute(
                """INSERT INTO plm.req_acceptance_criteria(acceptance_criterion_id,
                  requirement_version_id,requirement_id,project_id,ordinal,observable_result,
                  verification_method,required_data,required_environment,evidence_requirement)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (criterion, version, requirement, project, ordinal,
                 "原型版本可固定输入并进入正式评审" if ordinal == 0
                 else "送审回执不得显示为客户批准",
                 "真实Edge和包内HTTPS API", "隔离合成项目数据", "Windows 11 + PG18",
                 "固定版本、状态与审核记录"),
            )
        db.execute(
            "UPDATE plm.req_requirements SET current_approved_version_ref=%s "
            "WHERE requirement_id=%s", (version, requirement),
        )
    locator = f"projects/{project.hex}/objects/{file_object.hex[:2]}/{file_object.hex}"
    source_path = Path(context["fixture_db"].data_root) / locator
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(content)
    return requirement, version, document, document_version


def prototype_probe(**context) -> None:
    # Run before the upstream synthetic License-expiry negative case, so this
    # independent feature probe still exercises a VALID product License.
    fixture_db = context.pop("fixture_db")
    with fixture_db() as db:
        db.execute("DELETE FROM plm.auth_login_rate_buckets")
    with fixture_db() as db:
        project = context["project"]
        actor_row = db.execute(
            "SELECT user_id FROM plm.auth_users "
            "WHERE username_normalized='synthetic packaged user'"
        ).fetchone()
        assert actor_row is not None, "packaged synthetic application user missing"
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
    context["fixture_db"] = fixture_db
    requirement, version, document, document_version = seed_current_requirement(context, project)
    with fixture_db() as db:
        assert db.execute(
            "SELECT current_approved_version_ref FROM plm.req_requirements "
            "WHERE requirement_id=%s AND project_id=%s", (requirement, project),
        ).fetchone() == (version,)
    document_probe = context["observer_client"].get(
        f"/api/v1/projects/{project}/documents?page_size=50",
    )
    if document_probe.status_code != 200:
        raise AssertionError(f"packaged Document candidate read: {document_probe.status_code} {document_probe.text[:1000]}")
    document_candidates = document_probe.json()["data"]["items"]
    assert any(item["document_id"] == str(document)
               and item["effective_version_ref"] == str(document_version)
               for item in document_candidates), "fixed synthetic project document is not selectable"
    env = os.environ.copy()
    env["PLM_PROTOTYPE_TEST_USERNAME"] = "Synthetic Packaged User"
    env["PLM_PROTOTYPE_TEST_PASSWORD"] = "synthetic-packaged-login-password"
    env["PLM_PROTOTYPE_TEST_REVIEWER_LABEL"] = "Synthetic Handover Customer"
    output = ROOT / "artifacts/plt-pkg-01-a09-p51-a05-prototype-packaged"
    edge = subprocess.run(
        ["node", str(ROOT / "validation/prt-01-a10-a07-windows-browser/run-edge-browser.mjs"),
         context["origin"], str(project), str(output)],
        cwd=ROOT, env=env, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300, check=False,
    )
    if edge.returncode or "PRT_01_A10_A07_WINDOWS_EDGE_BROWSER_PASS" not in edge.stdout:
        raise AssertionError("packaged Prototype Edge failed: " + edge.stdout[-12000:])
    print(edge.stdout.strip(), flush=True)
    with context["connect_db"]() as db:
        prototype = db.execute(
            "SELECT prototype_id FROM plm.prt_prototypes WHERE project_id=%s "
            "AND name='受控审批交互原型'", (project,),
        ).fetchone()
        assert prototype is not None, "browser did not create Prototype identity"
        row = db.execute(
            """SELECT v.prototype_version_id,v.version_state,v.review_ref,v.review_round_ref,
              p.current_approved_version_ref
              FROM plm.prt_prototype_versions v JOIN plm.prt_prototypes p
                ON p.prototype_id=v.prototype_id AND p.project_id=v.project_id
              WHERE v.prototype_id=%s AND v.project_id=%s""", (prototype[0], project),
        ).fetchone()
        assert row is not None and row[1] == "IN_REVIEW" and row[2] and row[3], row
        assert row[4] is None, row
        review_id = row[2]
        assert db.execute(
            "SELECT count(*) FROM plm.rvw_review_decisions WHERE review_id=%s", (review_id,),
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE project_id=%s "
            "AND operation='V1_PRT_VERSION_SUBMIT_REVIEW' AND state='COMPLETED' "
            "AND result_ref_id=%s", (project, row[3]),
        ).fetchone()[0] == 1
    print("P51_A05_PACKAGED_PROTOTYPE_PG_PASS: version IN_REVIEW; zero decisions; no approval pointer",
          flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage", "pristine", "target"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--temp-root", type=Path, required=True)
    args = parser.parse_args()
    temp = args.temp_root.resolve(strict=True)
    if not temp.is_dir() or not str(temp).isascii() or temp.name != "PLMToolTemp" or temp.drive.upper() != "D:":
        raise ValueError("P51 disposable temp root rejected")
    import tempfile
    tempfile.tempdir = str(temp)
    runner = p51["handover_review"]["base"]["base"]["project"]["base"].base.base
    handover_review = p51["browser_probe"].__globals__["handover_review"]
    original_handover_probe = handover_review["browser_probe"]
    fixture_db_ref = {}

    def prototype_before_expiry(**context):
        upstream_before_expiry = context.pop("before_expiry_probe", None)

        def run_prototype(**values):
            if upstream_before_expiry is not None:
                upstream_before_expiry(**values)
            values["fixture_db"] = fixture_db_ref["connect"]
            prototype_probe(**values)

        return original_handover_probe(
            **context, before_expiry_probe=run_prototype,
        )

    handover_review["browser_probe"] = prototype_before_expiry

    def packaged_chain_probe(**context):
        fixture_db_ref["connect"] = context.pop("fixture_db")
        p51["browser_probe"](**context)

    result = runner.smoke(
        args.candidate, args.stage, args.pristine, args.target, args.expected_sha256,
        synthetic_license_document_factory=runner.synthetic_document,
        licensed_https_probe=packaged_chain_probe,
        fast_reuse_verified_stage=True,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
