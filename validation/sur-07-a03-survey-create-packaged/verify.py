"""Synthetic packaged Edge/HTTPS/PG proof for PROJECT Survey Create."""

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
prior = runpy.run_path(str(ROOT / "validation/hnd-05-a05-p06-review-packaged/verify.py"))


def after_approval(state: dict, **context) -> None:
    project = context["project"]
    version = context["version"]
    origin = context["origin"]
    observer_id = context["observer_id"]
    observer = context["observer_client"]
    csrf = context["observer_csrf"]
    path = f"/api/v1/projects/{project}/surveys"
    with context["connect_db"]() as db:
        item_states = dict(db.execute(
            "SELECT item_state,count(*) FROM plm.hnd_analysis_items "
            "WHERE handover_analysis_version_id=%s GROUP BY item_state", (version,),
        ).fetchall())
        assert item_states == {"CONFIRMED": 2}, item_states
        assert db.execute(
            "SELECT count(*) FROM plm.srv_surveys WHERE project_id=%s "
            "AND name='Synthetic Face-to-Face Survey Definition'", (project,),
        ).fetchone()[0] == 0
    with httpx.Client(base_url=origin, verify=False, trust_env=False, timeout=20) as anonymous:
        denied = anonymous.post(path, headers={"origin": origin,
            "idempotency-key": str(uuid.uuid4())},
            json={"name": "Synthetic Anonymous Survey"})
        assert denied.status_code in (401, 403), (denied.status_code, denied.text)
    denied = observer.post(f"/api/v1/projects/{uuid.uuid4()}/surveys", headers={
        "origin": origin, "x-csrf-token": csrf,
        "idempotency-key": str(uuid.uuid4()),
    }, json={"name": "Synthetic Wrong Project Survey"})
    assert denied.status_code == 404, (denied.status_code, denied.text)
    with httpx.Client(base_url=origin, verify=False, trust_env=False, timeout=20) as customer:
        login = customer.post("/api/v1/auth/login", headers={"origin": origin}, json={
            "username": "Synthetic Handover Customer",
            "password": "synthetic-packaged-login-password",
        })
        assert login.status_code == 200, (login.status_code, login.text)
        denied = customer.post(path, headers={
            "origin": origin, "x-csrf-token": login.json()["data"]["csrf_token"],
            "idempotency-key": str(uuid.uuid4()),
        }, json={"name": "Synthetic Read-only Customer Survey"})
        assert denied.status_code == 404, (denied.status_code, denied.text)
    edge = subprocess.run([
        "node", str(Path(__file__).with_name("run-survey-create-edge.mjs")),
        origin, str(project), str(observer_id),
    ], capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=240, check=False)
    if edge.returncode:
        raise AssertionError("packaged Survey Create Edge failed: "
                             + edge.stdout[-9000:] + edge.stderr[-9000:])
    line = edge.stdout.strip().splitlines()[-1]
    result = json.loads(line)
    assert result["status"] == "SUR_07_A03_PACKAGED_EDGE_PASS", result
    assert result["project_id"] == str(project)
    assert result["actor_id"] == str(observer_id)
    survey = uuid.UUID(result["survey_id"])
    state["survey"] = survey
    state["project"] = project
    print(line, flush=True)
    with context["connect_db"]() as db:
        found = db.execute(
            "SELECT survey_state,current_approved_version_ref,created_by "
            "FROM plm.srv_surveys WHERE survey_id=%s AND project_id=%s "
            "AND name='Synthetic Face-to-Face Survey Definition'",
            (survey, project),
        ).fetchone()
        assert found == ("ACTIVE", None, observer_id), found
        assert db.execute(
            "SELECT count(*) FROM plm.srv_survey_versions WHERE survey_id=%s",
            (survey,),
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s "
            "AND target_object_id=%s AND action='SURVEY_CREATED' AND outcome='SUCCESS'",
            (project, survey),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "actor_id=%s AND project_id=%s AND operation='V1_SURVEY_CREATE' "
            "AND state='COMPLETED' AND result_ref_id=%s",
            (observer_id, project, survey),
        ).fetchone()[0] == 1
        state["count_before_expiry"] = db.execute(
            "SELECT count(*) FROM plm.srv_surveys WHERE project_id=%s", (project,),
        ).fetchone()[0]
    read = observer.get(f"{path}/{survey}")
    assert read.status_code == 200, (read.status_code, read.text)
    assert read.json()["data"]["survey_id"] == str(survey)
    print("SUR_07_A03_PACKAGED_PG_PASS: one definition, zero versions, "
          "one Audit/receipt, current HND source and denials", flush=True)


def after_expiry(state: dict, **context) -> None:
    project = context["project"]
    assert project == state["project"]
    denied = context["observer_client"].post(
        f"/api/v1/projects/{project}/surveys", headers={
            "origin": context["origin"],
            "x-csrf-token": context["observer_csrf"],
            "idempotency-key": str(uuid.uuid4()),
        }, json={"name": "Synthetic Expired-license Survey"})
    assert denied.status_code == 403, (denied.status_code, denied.text)
    with context["connect_db"]() as db:
        assert db.execute(
            "SELECT count(*) FROM plm.srv_surveys WHERE project_id=%s", (project,),
        ).fetchone()[0] == state["count_before_expiry"]
    print("SUR_07_A03_PACKAGED_LICENSE_DENIAL_PASS: synthetic EXPIRED projection", flush=True)


def browser_probe(**context) -> None:
    state: dict = {}
    prior["browser_probe"](**context,
        after_approval_probe=lambda **values: after_approval(state, **values),
        after_expiry_probe=lambda **values: after_expiry(state, **values))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage", "pristine", "target"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    runner = prior["base"]["base"]["project"]["base"].base.base
    result = runner.smoke(
        args.candidate, args.stage, args.pristine, args.target, args.expected_sha256,
        synthetic_license_document_factory=runner.synthetic_document,
        licensed_https_probe=browser_probe,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
