"""Packaged synthetic Handover DRAFT validate and Review submission proof."""

from __future__ import annotations

import argparse
import httpx
import json
import runpy
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))
base = runpy.run_path(str(ROOT / "validation/hnd-05-a02-p04-version-packaged/verify.py"))


def _login(client: httpx.Client, origin: str, username: str) -> dict:
    response = client.post("/api/v1/auth/login", headers={"origin": origin}, json={
        "username": username, "password": "synthetic-packaged-login-password",
    })
    assert response.status_code == 200, (response.status_code, response.text)
    return {"origin": origin, "x-csrf-token": response.json()["data"]["csrf_token"]}


def _seed_customer(context: dict, project_id: uuid.UUID) -> uuid.UUID:
    """Synthetic identity fixture only; actual Action/Review writes use HTTPS APIs."""
    with context["connect_db"]() as db, db.transaction():
        department = db.execute(
            "SELECT department_id FROM plm.prj_project_members "
            "WHERE project_id=%s AND user_id=%s", (project_id, context["user_id"]),
        ).fetchone()
        assert department is not None
        username = "Synthetic Handover Customer"
        customer = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (username, username.lower()),
        ).fetchone()[0]
        credential = db.execute(
            "INSERT INTO plm.auth_password_credentials"
            "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
            "SELECT %s,1,password_hash,algorithm_id,parameter_set FROM "
            "plm.auth_password_credentials WHERE user_id=%s AND credential_version=1 "
            "RETURNING password_credential_id", (customer, context["user_id"]),
        ).fetchone()[0]
        db.execute(
            "UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,"
            "state='ENABLED' WHERE user_id=%s", (credential, customer),
        )
        member = db.execute(
            "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
            "VALUES (%s,%s,%s,'CUSTOMER_MANAGER') RETURNING project_member_id",
            (project_id, customer, department[0]),
        ).fetchone()
        assert member is not None
    return customer


def browser_probe(**context) -> None:
    base["browser_probe"](**context)
    origin = context["origin"]
    with context["connect_db"]() as db:
        row = db.execute(
            "SELECT a.project_id,a.handover_analysis_id,v.handover_analysis_version_id "
            "FROM plm.hnd_analyses a JOIN plm.hnd_analysis_versions v "
            "ON v.handover_analysis_id=a.handover_analysis_id "
            "WHERE a.analysis_purpose='Synthetic Handover Analysis'",
        ).fetchone()
        assert row is not None
        project_id, analysis_id, version_id = row
        need = db.execute(
            "SELECT analysis_item_id FROM plm.hnd_analysis_items "
            "WHERE handover_analysis_version_id=%s AND item_type='NEED_CONFIRM'",
            (version_id,),
        ).fetchone()
        assert need is not None
        item_id = need[0]
        outsider = db.execute(
            "SELECT user_id FROM plm.auth_users WHERE username_display="
            "'Synthetic Foreign Source Manager'",
        ).fetchone()[0]
    customer = _seed_customer(context, project_id)
    review_path = (f"/api/v1/projects/{project_id}/handover-analyses/{analysis_id}/"
                   f"versions/{version_id}:submit-review")
    body = {"reviewer_ids": [str(customer)], "policy_ref": "HANDOVER_ALL_V1",
            "due_at": None, "submission_note": None}
    with httpx.Client(base_url=origin, verify=False, trust_env=False, timeout=20) as anonymous:
        rejected = anonymous.post(review_path, headers={"origin": origin,
            "idempotency-key": str(uuid.uuid4())}, json=body)
        assert rejected.status_code in (401, 403), (rejected.status_code, rejected.text)
    with httpx.Client(base_url=origin, verify=False, trust_env=False, timeout=20) as outsider_client:
        outsider_headers = _login(outsider_client, origin, "Synthetic Foreign Source Manager")
        rejected = outsider_client.post(review_path, headers=outsider_headers | {
            "idempotency-key": str(uuid.uuid4())}, json=body)
        assert rejected.status_code == 404, (rejected.status_code, rejected.text)
    with context["connect_db"]() as db:
        assert db.execute("SELECT count(*) FROM plm.rvw_subject_snapshots WHERE project_id=%s "
                          "AND subject_version_id=%s", (project_id, version_id)).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM plm.hnd_action_items WHERE "
                          "source_item_id=%s", (item_id,)).fetchone()[0] == 0
    edge = subprocess.run(["node", str(Path(__file__).with_name("run-validate-submit-edge.mjs")),
                           origin, str(project_id), str(analysis_id), str(version_id),
                           str(customer), str(item_id), str(outsider)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=240, check=False)
    if edge.returncode or "HND_05_A04_P03_PACKAGED_EDGE_PASS" not in edge.stdout:
        raise AssertionError("packaged Handover validate/submit Edge failed: "
                             + edge.stdout[-9000:] + edge.stderr[-9000:])
    print(edge.stdout.strip(), flush=True)
    with context["connect_db"]() as db:
        actions = db.execute("SELECT action_item_id,action_state FROM plm.hnd_action_items "
            "WHERE project_id=%s AND source_analysis_version_ref=%s AND source_item_id=%s",
            (project_id, version_id, item_id)).fetchall()
        assert len(actions) == 1 and actions[0][1] == "OPEN", actions
        state = db.execute("SELECT version_state,review_ref,review_round_ref FROM "
            "plm.hnd_analysis_versions WHERE handover_analysis_version_id=%s",
            (version_id,)).fetchone()
        assert state is not None and state[0] == "IN_REVIEW" and state[1] and state[2], state
        audits = dict(db.execute("SELECT action,count(*) FROM plm.aud_events "
            "WHERE target_project_id=%s AND target_object_id=%s "
            "GROUP BY action", (project_id, version_id)).fetchall())
        assert audits.get("HND_VERSION_CREATED") == 1 and audits.get("HND_VERSION_VALIDATED") == 1, audits
        receipts = dict(db.execute("SELECT operation,count(*) FROM plm.plt_idempotency_receipts "
            "WHERE project_id=%s AND state='COMPLETED' AND operation IN "
            "('V1_HND_VERSION_VALIDATE','V1_HND_VERSION_SUBMIT_REVIEW') "
            "GROUP BY operation", (project_id,)).fetchall())
        assert receipts == {"V1_HND_VERSION_VALIDATE": 1,
                            "V1_HND_VERSION_SUBMIT_REVIEW": 1}, receipts
    print("HND_05_A04_P03_PACKAGED_PG_PASS: one validated report and one IN_REVIEW submission", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage", "pristine", "target"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    result = base["project"]["base"].base.base.smoke(
        args.candidate, args.stage, args.pristine, args.target, args.expected_sha256,
        synthetic_license_document_factory=base["project"]["base"].base.base.synthetic_document,
        licensed_https_probe=browser_probe,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
