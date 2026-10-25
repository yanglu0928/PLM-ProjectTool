"""Synthetic packaged Edge/HTTPS/PG proof for HND-02 Review and fixed version."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
import sys
import uuid
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))
base = runpy.run_path(str(ROOT / "validation/hnd-05-a04-p03-validate-submit-packaged/verify.py"))


def seed_observer(context: dict, project: uuid.UUID) -> uuid.UUID:
    """Disposable same-project non-reviewer; not a customer/business fact."""
    with context["connect_db"]() as db, db.transaction():
        department = db.execute(
            "SELECT department_id FROM plm.prj_project_members "
            "WHERE project_id=%s AND user_id=%s", (project, context["user_id"]),
        ).fetchone()
        assert department is not None
        username = "Synthetic Handover Observer"
        observer = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (username, username.lower()),
        ).fetchone()[0]
        credential = db.execute(
            "INSERT INTO plm.auth_password_credentials"
            "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
            "SELECT %s,1,password_hash,algorithm_id,parameter_set FROM "
            "plm.auth_password_credentials WHERE user_id=%s AND credential_version=1 "
            "RETURNING password_credential_id", (observer, context["user_id"]),
        ).fetchone()[0]
        db.execute(
            "UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,"
            "state='ENABLED' WHERE user_id=%s", (credential, observer),
        )
        member = db.execute(
            "INSERT INTO plm.prj_project_members(project_id,user_id,department_id,project_role) "
            "VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER') RETURNING project_member_id",
            (project, observer, department[0]),
        ).fetchone()
        assert member is not None
    return observer


def browser_probe(**context) -> None:
    base["browser_probe"](**context)
    origin = context["origin"]
    with context["connect_db"]() as db:
        row = db.execute(
            "SELECT a.project_id,a.handover_analysis_id,"
            "v.handover_analysis_version_id,v.review_ref,v.review_round_ref "
            "FROM plm.hnd_analyses a JOIN plm.hnd_analysis_versions v "
            "ON v.handover_analysis_id=a.handover_analysis_id "
            "WHERE a.analysis_purpose='Synthetic Handover Analysis'",
        ).fetchone()
        assert row is not None and row[3] and row[4], row
        project, analysis, version, review, round_id = row
        customer = db.execute(
            "SELECT user_id FROM plm.auth_users WHERE username_display="
            "'Synthetic Handover Customer'",
        ).fetchone()[0]
        assert db.execute(
            "SELECT count(*) FROM plm.rvw_review_decisions WHERE review_id=%s",
            (review,),
        ).fetchone()[0] == 0
    review_path = f"/api/v1/projects/{project}/reviews/{review}"
    decision_path = (f"/api/v1/projects/{project}/reviews/{review}/rounds/"
                     f"{round_id}:decide")
    # The upstream PROJECT fixture leaves its shared client signed in as an
    # outsider, while repeated admin logins hit production rate limits. Use a
    # one-time synthetic current member who is not assigned to this Review.
    observer_id = seed_observer(context, project)
    observer_client = httpx.Client(base_url=origin, verify=False, trust_env=False, timeout=20)
    observer_login = observer_client.post("/api/v1/auth/login", headers={"origin": origin}, json={
        "username": "Synthetic Handover Observer",
        "password": "synthetic-packaged-login-password",
    })
    assert observer_login.status_code == 200, (observer_login.status_code, observer_login.text)
    read = observer_client.get(review_path)
    assert read.status_code == 200, (read.status_code, read.text)
    assert read.json()["data"]["active_round"]["assignments"][0]["reviewer_id"] != str(observer_id)
    assert read.json()["data"]["subject_ref"] == {
        "resource_type": "HND-02", "resource_id": str(analysis),
    }
    assert read.json()["data"]["active_round"]["subject_version_ref"] == str(version)
    outsider = context["client"].get(review_path)
    assert outsider.status_code == 404, (outsider.status_code, outsider.text)
    with httpx.Client(base_url=origin, verify=False, trust_env=False, timeout=20) as anonymous:
        denied = anonymous.get(review_path)
        assert denied.status_code == 401, (denied.status_code, denied.text)
    denied = observer_client.get(f"/api/v1/projects/{uuid.uuid4()}/reviews/{review}")
    assert denied.status_code == 404, (denied.status_code, denied.text)
    csrf = observer_login.json()["data"]["csrf_token"]
    denied = observer_client.post(decision_path, headers={
        "origin": origin, "x-csrf-token": csrf,
        "idempotency-key": str(uuid.uuid4()),
    }, json={"decision": "APPROVE", "comment": None})
    assert denied.status_code == 404, (denied.status_code, denied.text)
    edge = subprocess.run([
        "node", str(Path(__file__).with_name("run-review-edge.mjs")), origin,
        *(str(value) for value in (project, analysis, version, review, round_id, customer)),
    ], capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=240, check=False)
    if edge.returncode or "HND_05_A05_P06_PACKAGED_EDGE_PASS" not in edge.stdout:
        raise AssertionError("packaged Handover review Edge failed: "
                             + edge.stdout[-9000:] + edge.stderr[-9000:])
    print(edge.stdout.strip(), flush=True)
    with context["connect_db"]() as db:
        state = db.execute(
            "SELECT review_state,active_round_id FROM plm.rvw_reviews WHERE review_id=%s",
            (review,),
        ).fetchone()
        assert state == ("APPROVED", None), state
        version_state = db.execute(
            "SELECT version_state FROM plm.hnd_analysis_versions "
            "WHERE handover_analysis_version_id=%s", (version,),
        ).fetchone()
        assert version_state == ("APPROVED",), version_state
        assert db.execute(
            "SELECT current_approved_version_ref FROM plm.hnd_analyses "
            "WHERE handover_analysis_id=%s", (analysis,),
        ).fetchone() == (version,)
        assert db.execute(
            "SELECT count(*) FROM plm.rvw_review_decisions WHERE review_id=%s "
            "AND reviewer_id=%s AND decision='APPROVE'", (review, customer),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "project_id=%s AND actor_id=%s AND operation='V1_REVIEW_DECIDE' "
            "AND state='COMPLETED'", (project, customer),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s "
            "AND target_object_id=%s AND action='HND_VERSION_APPROVED'",
            (project, version),
        ).fetchone()[0] == 1
        before = db.execute(
            "SELECT count(*) FROM plm.rvw_review_decisions WHERE review_id=%s",
            (review,),
        ).fetchone()[0]
    # Synthetic EXPIRED projection only; this does not prove natural time expiry.
    with context["connect_db"]() as db, db.transaction():
        active_id, old_version = db.execute(
            "SELECT active_license_ref,state_version FROM plm.lic_validation_states "
            "WHERE singleton_key=1 AND validation_code='VALID' FOR UPDATE",
        ).fetchone()
        event_id, validated_at = db.execute(
            "INSERT INTO plm.lic_validation_events"
            "(installation_id,validation_code,trace_id) "
            "VALUES (%s,'EXPIRED',%s) RETURNING validation_event_id,validated_at",
            (active_id, uuid.uuid4()),
        ).fetchone()
        assert db.execute(
            "UPDATE plm.lic_validation_states SET validation_code='EXPIRED',"
            "machine_fingerprint_hash=NULL,entitlement_snapshot=NULL,validated_at=%s,"
            "current_event_ref=%s,updated_at=statement_timestamp(),"
            "state_version=state_version+1 WHERE singleton_key=1 AND state_version=%s",
            (validated_at, event_id, old_version),
        ).rowcount == 1
    denied = observer_client.get(review_path)
    assert denied.status_code == 403, (denied.status_code, denied.text)
    with context["connect_db"]() as db:
        assert db.execute(
            "SELECT count(*) FROM plm.rvw_review_decisions WHERE review_id=%s",
            (review,),
        ).fetchone()[0] == before
    observer_client.close()
    print("HND_05_A05_P06_PACKAGED_PG_PASS: fixed version, one decision, "
          "approved Handover, Audit/receipt and denials", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage", "pristine", "target"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    result = base["base"]["project"]["base"].base.base.smoke(
        args.candidate, args.stage, args.pristine, args.target, args.expected_sha256,
        synthetic_license_document_factory=base["base"]["project"]["base"].base.base.synthetic_document,
        licensed_https_probe=browser_probe,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
