"""Prove packaged browser Project creation with isolated synthetic authority."""

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
spec = spec_from_file_location("_pkg_pilot_a04_p04_base", SOURCE)
assert spec is not None and spec.loader is not None
base = module_from_spec(spec)
spec.loader.exec_module(base)

CODE = "PKGEDGE1"
NAME = "Synthetic Browser Project"
MANAGER = "Synthetic Packaged Project Manager"


def browser_probe(**kwargs) -> None:
    base.base.licensed_probe(**kwargs)
    user_id = kwargs["user_id"]
    with kwargs["connect_db"]() as db, db.transaction():
        assert db.execute(
            "UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN' "
            "WHERE user_id=%s AND state='ENABLED'", (user_id,),
        ).rowcount == 1
        manager_id = db.execute(
            "INSERT INTO plm.auth_users"
            "(username_display,username_normalized) VALUES (%s,%s) RETURNING user_id",
            (MANAGER, MANAGER.lower()),
        ).fetchone()[0]
        credential_id = db.execute(
            "INSERT INTO plm.auth_password_credentials"
            "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
            "SELECT %s,1,password_hash,algorithm_id,parameter_set FROM "
            "plm.auth_password_credentials WHERE user_id=%s AND credential_version=1 "
            "RETURNING password_credential_id",
            (manager_id, user_id),
        ).fetchone()[0]
        assert db.execute(
            "UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,"
            "state='ENABLED' WHERE user_id=%s", (credential_id, manager_id),
        ).rowcount == 1

    command = ["node", str(Path(__file__).with_name("run-project-create-edge.mjs")),
               kwargs["origin"], CODE, NAME, MANAGER]
    checked = subprocess.run(command, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=120,
                             check=False)
    if checked.returncode or "PKG_PILOT_01_A04_P04_PROJECT_CREATE_EDGE_PASS" not in checked.stdout:
        raise RuntimeError("packaged Project create Edge proof failed: " +
                           (checked.stdout + checked.stderr)[-12000:])
    with kwargs["connect_db"]() as db:
        project = db.execute(
            "SELECT project_id,created_by FROM plm.prj_projects "
            "WHERE project_code=%s AND name=%s", (CODE, NAME),
        ).fetchall()
        assert len(project) == 1 and project[0][1] == user_id, project
        project_id = project[0][0]
        assert db.execute(
            "SELECT count(*) FROM plm.prj_departments WHERE project_id=%s "
            "AND department_code='DEFAULT'", (project_id,),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.prj_project_members WHERE project_id=%s "
            "AND user_id=%s AND project_role='PROJECT_MANAGER' AND state='ACTIVE'",
            (project_id, manager_id),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT workflow_state,current_stage_key FROM plm.wfl_project_workflows "
            "WHERE project_id=%s", (project_id,),
        ).fetchone() == ("NOT_STARTED", None)
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='PROJECT_CREATED' "
            "AND target_object_id=%s", (project_id,),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE actor_id=%s AND operation='V1_PROJECT_CREATE' "
            "AND result_ref_id=%s AND state='COMPLETED'", (user_id, project_id),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.prj_project_members WHERE project_id=%s AND user_id=%s",
            (project_id, user_id),
        ).fetchone()[0] == 0
    print(checked.stdout, flush=True)
    print("Packaged Project/Department/Manager/Workflow/Audit/receipt PG PASS", flush=True)


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
