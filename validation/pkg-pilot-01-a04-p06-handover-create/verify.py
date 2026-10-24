"""Prove packaged Handover create through real Edge and isolated synthetic PG."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation/pkg-pilot-01-a04-p03-packaged-edge/verify.py"
spec = spec_from_file_location("_pkg_pilot_a04_p06_base", SOURCE)
assert spec is not None and spec.loader is not None
base = module_from_spec(spec)
spec.loader.exec_module(base)

TITLE = "Synthetic Handover Source"
PURPOSE = "Synthetic Handover Analysis"


def browser_probe(**kwargs) -> None:
    base.base.licensed_probe(**kwargs)
    command = ["node", str(Path(__file__).with_name("run-handover-create-edge.mjs")),
               kwargs["origin"]]
    checked = subprocess.run(command, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=150,
                             check=False)
    if checked.returncode or "PKG_PILOT_01_A04_P06_HANDOVER_EDGE_PASS" not in checked.stdout:
        raise RuntimeError("packaged Handover create Edge proof failed: " +
                           (checked.stdout + checked.stderr)[-12000:])
    with kwargs["connect_db"]() as db:
        project = db.execute("SELECT project_id FROM plm.prj_projects "
                             "WHERE project_code='WHTTPS'").fetchone()
        assert project is not None
        project_id = project[0]
        document = db.execute(
            "SELECT document_id,latest_version_ref FROM plm.doc_documents "
            "WHERE project_id=%s AND title=%s AND document_state='ACTIVE'",
            (project_id, TITLE),
        ).fetchall()
        assert len(document) == 1 and document[0][1] is not None, document
        doc_id, version_id = document[0]
        assert db.execute(
            "SELECT availability_state FROM plm.doc_document_versions "
            "WHERE document_id=%s AND document_version_id=%s",
            (doc_id, version_id),
        ).fetchone() == ("AVAILABLE",)
        analyses = db.execute(
            "SELECT handover_analysis_id,source_set_ref,created_by,analysis_state "
            "FROM plm.hnd_analyses WHERE project_id=%s AND analysis_purpose=%s",
            (project_id, PURPOSE),
        ).fetchall()
        assert len(analyses) == 1 and analyses[0][2] == kwargs["user_id"] \
            and analyses[0][3] == "ACTIVE", analyses
        analysis_id = analyses[0][0]
        assert analyses[0][1].startswith("sha256:") and len(analyses[0][1]) == 71
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='HND_ANALYSIS_CREATED' "
            "AND target_project_id=%s AND target_object_id=%s",
            (project_id, analysis_id),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE actor_id=%s AND project_id=%s AND operation='V1_HND_ANALYSIS_CREATE' "
            "AND result_ref_id=%s AND state='COMPLETED'",
            (kwargs["user_id"], project_id, analysis_id),
        ).fetchone()[0] == 1
    headers = {"origin": kwargs["origin"],
               "x-csrf-token": kwargs["login"].json()["data"]["csrf_token"],
               "idempotency-key": "handover-packaged-negative-key-001"}
    original_path = f"/api/v1/projects/{project_id}/handover-analyses"
    empty = kwargs["client"].post(original_path, headers=headers,
        json={"analysis_purpose": "Synthetic missing source", "source_documents": []})
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "VALIDATION_FAILED", \
        (empty.status_code, empty.text)
    other_username = "Synthetic Foreign Source Manager"
    with kwargs["connect_db"]() as db, db.transaction():
        other_project = base.base.fixture.insert(db, "prj_projects", dict(
            project_code="HNDNEG", project_code_normalized="hndneg",
            name="Synthetic Foreign Source Project", created_by=kwargs["user_id"]), "project_id")
        other_department = base.base.fixture.insert(db, "prj_departments", dict(
            project_id=other_project, department_code="D", department_code_normalized="d",
            name="Synthetic department"), "department_id")
        other_user = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (other_username, other_username.lower()),
        ).fetchone()[0]
        credential_id = db.execute(
            "INSERT INTO plm.auth_password_credentials"
            "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
            "SELECT %s,1,password_hash,algorithm_id,parameter_set FROM "
            "plm.auth_password_credentials WHERE user_id=%s AND credential_version=1 "
            "RETURNING password_credential_id", (other_user, kwargs["user_id"]),
        ).fetchone()[0]
        assert db.execute(
            "UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,"
            "state='ENABLED' WHERE user_id=%s", (credential_id, other_user),
        ).rowcount == 1
        base.base.fixture.insert(db, "prj_project_members", dict(
            project_id=other_project, user_id=other_user, department_id=other_department,
            project_role="PROJECT_MANAGER"), "project_member_id")
    logout = kwargs["client"].post("/api/v1/auth/logout", headers=headers | {
        "idempotency-key": "handover-packaged-negative-logout-001"})
    assert logout.status_code == 200 and logout.json()["data"]["revoked"] is True, \
        (logout.status_code, logout.text)
    second_login = kwargs["client"].post("/api/v1/auth/login", headers={"origin": kwargs["origin"]},
        json={"username": other_username, "password": "synthetic-packaged-login-password"})
    assert second_login.status_code == 200, (second_login.status_code, second_login.text)
    second_headers = {"origin": kwargs["origin"],
                      "x-csrf-token": second_login.json()["data"]["csrf_token"],
                      "idempotency-key": "handover-packaged-negative-key-002"}
    foreign = kwargs["client"].post(
        f"/api/v1/projects/{other_project}/handover-analyses",
        headers=second_headers,
        json={"analysis_purpose": "Synthetic foreign source",
              "source_documents": [{"document_id": str(doc_id),
                                    "document_version_id": str(version_id)}]})
    assert foreign.status_code == 422 and foreign.json()["error"]["code"] == "HANDOVER_SOURCE_REQUIRED", \
        (foreign.status_code, foreign.text)
    unassigned = kwargs["client"].post(
        original_path,
        headers=second_headers | {"idempotency-key": "handover-packaged-negative-key-003"},
        json={"analysis_purpose": "Synthetic unassigned project",
              "source_documents": [{"document_id": str(doc_id),
                                    "document_version_id": str(version_id)}]})
    assert unassigned.status_code == 404 and unassigned.json()["error"]["code"] == "RESOURCE_NOT_FOUND", \
        (unassigned.status_code, unassigned.text)
    with kwargs["connect_db"]() as db:
        assert db.execute(
            "SELECT count(*) FROM plm.hnd_analyses WHERE project_id IN (%s,%s)",
            (project_id, other_project),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='HND_ANALYSIS_CREATED' "
            "AND target_project_id IN (%s,%s)",
            (project_id, other_project),
        ).fetchone()[0] == 1
    print(checked.stdout, flush=True)
    print("Packaged document fixed version/Handover Analysis/Audit/receipt and source/permission denials PG PASS", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    temp = Path(__import__("tempfile").gettempdir())
    pristine = temp / ("plm-install-rehearsal-" + uuid.uuid4().hex[:12])
    target = temp / ("plm-install-rehearsal-" + uuid.uuid4().hex[:12])
    result = base.base.smoke(args.candidate, args.stage, pristine, target,
                             args.expected_sha256,
                             synthetic_license_document_factory=base.base.synthetic_document,
                             licensed_https_probe=browser_probe)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
