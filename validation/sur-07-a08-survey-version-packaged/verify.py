"""Disposable packaged Edge/HTTPS/PG proof for Survey DRAFT version creation."""

from __future__ import annotations

import argparse
import json
import runpy
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))
survey_create = runpy.run_path(str(ROOT / "validation/sur-07-a03-survey-create-packaged/verify.py"))
handover_review = survey_create["prior"]
_seed_observer = handover_review["seed_observer"]


def seed_project_manager(context: dict, project: uuid.UUID) -> uuid.UUID:
    user_id = _seed_observer(context, project)
    with context["connect_db"]() as db:
        assert db.execute(
            "UPDATE plm.prj_project_members SET project_role='PROJECT_MANAGER' "
            "WHERE project_id=%s AND user_id=%s AND project_role='IMPLEMENTATION_MEMBER'",
            (project, user_id),
        ).rowcount == 1
    return user_id


# The Session is created after this fixture. The ProjectManager role therefore
# appears in its real authorization projection before Edge opens the Survey UI.
handover_review["seed_observer"] = seed_project_manager
handover_review["browser_probe"].__globals__["seed_observer"] = seed_project_manager


def after_approval(state: dict, **context) -> None:
    survey_create["after_approval"](state, **context)
    project, survey = state["project"], state["survey"]
    origin = context["origin"]
    observer = context["observer_client"]
    path = f"/api/v1/projects/{project}/surveys/{survey}/versions"
    candidates = observer.get(f"/api/v1/projects/{project}/survey-handover-sources")
    assert candidates.status_code == 200, (candidates.status_code, candidates.text)
    available = candidates.json()["data"]["items"]
    assert len(available) == 2 and all(item["state"] == "CONFIRMED" for item in available)
    with httpx.Client(base_url=origin, verify=False, trust_env=False, timeout=20) as anonymous:
        denied = anonymous.get(f"/api/v1/projects/{project}/survey-handover-sources")
        assert denied.status_code == 401, (denied.status_code, denied.text)
        denied = anonymous.post(path, headers={"origin": origin,
            "if-match": '"v0"', "idempotency-key": str(uuid.uuid4())},
            json={"questions": [], "target_department_ids": []})
        assert denied.status_code in (401, 403), (denied.status_code, denied.text)
    with context["connect_db"]() as db:
        expected_reviewer = db.execute(
            "SELECT user_id FROM plm.auth_users "
            "WHERE username_normalized='synthetic handover customer'"
        ).fetchone()
        assert expected_reviewer is not None, "synthetic customer reviewer fixture missing"
        expected_reviewer_id = expected_reviewer[0]
        membership = db.execute(
            "SELECT project_role FROM plm.prj_project_members "
            "WHERE project_id=%s AND user_id=%s",
            (project, expected_reviewer_id),
        ).fetchone()
        assert membership is not None and membership[0] in {
            "CUSTOMER_MANAGER", "CUSTOMER_MEMBER"
        }, membership
    edge = subprocess.run([
        "node", str(Path(__file__).with_name("run-survey-version-edge.mjs")),
        origin, str(project), str(survey), str(context["observer_id"]),
        str(expected_reviewer_id),
    ], capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=240, check=False)
    if edge.returncode:
        raise AssertionError("packaged SurveyVersion Edge failed: "
                             + edge.stdout[-9000:] + edge.stderr[-9000:])
    result = json.loads(edge.stdout.strip().splitlines()[-1])
    assert result["status"] == "SUR_07_A12_P05_PACKAGED_EDGE_PASS", result
    assert result["review_ui_subject_label"] is True
    assert result["review_ui_fixed_version_link"].endswith(
        f"?fixedVersionId={result['survey_version_id']}")
    assert result["assigned_reviewer_decision_controls_visible"] is True
    assert result["project_member_read_allowed"] is True
    assert result["non_assignee_decision_controls_hidden"] is True
    assert result["review_list_subject_label"] == "调研问题版本"
    assert result["project_id"] == str(project) and result["survey_id"] == str(survey)
    assert result["reviewer_id"] == str(expected_reviewer_id)
    non_reviewer_read = observer.get(
        f"/api/v1/projects/{project}/reviews/{result['review_id']}"
    )
    assert non_reviewer_read.status_code == 200, (
        non_reviewer_read.status_code, non_reviewer_read.text
    )
    assert non_reviewer_read.json()["data"]["review_id"] == result["review_id"]
    fixed_row = result["handover_item_row_id"]
    assert fixed_row in {item["handover_item_row_id"] for item in available}
    assert result["handover_analysis_version_id"] == str(context["version"])
    version = uuid.UUID(result["survey_version_id"])
    body = result["request_body"]
    state["body"] = body
    assert result["original_etag"] == '"v0"'
    state["version"] = version
    print(json.dumps({key: value for key, value in result.items() if key != "request_body"},
                     ensure_ascii=True, sort_keys=True), flush=True)
    with context["connect_db"]() as db:
        row = db.execute(
            "SELECT version_state,version_no,created_by FROM plm.srv_survey_versions "
            "WHERE survey_version_id=%s AND survey_id=%s AND project_id=%s",
            (version, survey, project),
        ).fetchone()
        assert row == ("IN_REVIEW", 1, context["observer_id"]), row
        assert db.execute("SELECT count(*) FROM plm.srv_questions WHERE survey_version_id=%s",
                          (version,)).fetchone()[0] == 1
        sources = db.execute(
            "SELECT source_kind,handover_item_row_id,manual_source_note "
            "FROM plm.srv_question_source_refs WHERE survey_version_id=%s ORDER BY ordinal",
            (version,),
        ).fetchall()
        assert len(sources) == 2 and sources[0][0] == "HANDOVER_ITEM"
        assert str(sources[0][1]) == fixed_row and sources[0][2] is None
        assert sources[1][0] == "MANUAL" and sources[1][1] is None
        assert "合成面对面访谈" in sources[1][2]
        target = db.execute("SELECT department_id FROM plm.srv_target_departments "
                            "WHERE survey_version_id=%s", (version,)).fetchall()
        assert len(target) == 1 and str(target[0][0]) == result["target_department_id"]
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s "
            "AND target_object_id=%s AND action='SURVEY_VERSION_CREATED' AND outcome='SUCCESS'",
            (project, version),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "actor_id=%s AND project_id=%s AND operation='V1_SURVEY_VERSION_CREATE' "
            "AND state='COMPLETED' AND result_ref_id=%s",
            (context["observer_id"], project, version),
        ).fetchone()[0] == 1
        final_version = db.execute(
            "SELECT version_state,review_ref,review_round_ref FROM plm.srv_survey_versions "
            "WHERE survey_version_id=%s", (version,),
        ).fetchone()
        review_id = uuid.UUID(result["review_id"])
        round_id = uuid.UUID(result["review_round_id"])
        reviewer_id = uuid.UUID(result["reviewer_id"])
        assert final_version == ("IN_REVIEW", review_id, round_id), final_version
        assert db.execute(
            "SELECT review_state,active_round_id,subject_type,subject_id FROM plm.rvw_reviews "
            "WHERE review_id=%s", (review_id,),
        ).fetchone() == ("IN_REVIEW", round_id, "SRV-02", survey)
        assert db.execute(
            "SELECT round_state,subject_version_id,started_by FROM plm.rvw_review_rounds "
            "WHERE review_round_id=%s", (round_id,),
        ).fetchone() == ("IN_REVIEW", version, context["observer_id"])
        assert db.execute(
            "SELECT reviewer_id,assignment_state FROM plm.rvw_review_assignments "
            "WHERE review_round_id=%s", (round_id,),
        ).fetchall() == [(reviewer_id, "PENDING")]
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s "
            "AND target_object_id=%s AND action='SURVEY_VERSION_VALIDATED' "
            "AND outcome='SUCCESS'", (project, version),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s "
            "AND target_object_id=%s AND action='REVIEW_CREATED' AND outcome='SUCCESS'",
            (project, review_id),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE target_project_id=%s "
            "AND target_object_id=%s AND action='REVIEW_STARTED' AND outcome='SUCCESS'",
            (project, round_id),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE actor_id=%s "
            "AND project_id=%s AND operation='V1_SURVEY_VERSION_SUBMIT_REVIEW' "
            "AND state='COMPLETED' AND result_ref_id=%s",
            (context["observer_id"], project, round_id),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.rvw_review_decisions WHERE review_id=%s",
            (review_id,),
        ).fetchone()[0] == 0
        assert db.execute(
            "SELECT current_approved_version_ref FROM plm.srv_surveys "
            "WHERE survey_id=%s", (survey,),
        ).fetchone() == (None,)
        state["version_count"] = db.execute(
            "SELECT count(*) FROM plm.srv_survey_versions WHERE survey_id=%s", (survey,),
        ).fetchone()[0]
    assert state["version_count"] == 1
    headers = {"origin": origin, "x-csrf-token": context["observer_csrf"],
               "if-match": '"v1"', "idempotency-key": str(uuid.uuid4())}
    invalid = json.loads(json.dumps(body))
    invalid["questions"][0]["sources"][0]["handover_item_row_id"] = str(uuid.uuid4())
    denied = observer.post(path, headers=headers, json=invalid)
    # Submit-review advances the Survey write boundary; the pre-submit ETag
    # must be rejected before a second version can be created.
    assert denied.status_code == 409 and denied.json()["error"]["code"] == "CONFLICT_VERSION", (
        denied.status_code, denied.text)
    denied = observer.post(f"/api/v1/projects/{uuid.uuid4()}/surveys/{survey}/versions",
                           headers=headers, json=body)
    assert denied.status_code == 404, (denied.status_code, denied.text)
    with httpx.Client(base_url=origin, verify=False, trust_env=False, timeout=20) as customer:
        login = customer.post("/api/v1/auth/login", headers={"origin": origin}, json={
            "username": "Synthetic Handover Customer",
            "password": "synthetic-packaged-login-password",
        })
        assert login.status_code == 200, (login.status_code, login.text)
        denied = customer.get(f"/api/v1/projects/{project}/survey-handover-sources")
        assert denied.status_code == 404, (denied.status_code, denied.text)
        denied = customer.post(path, headers={"origin": origin,
            "x-csrf-token": login.json()["data"]["csrf_token"],
            "if-match": '"v0"', "idempotency-key": str(uuid.uuid4())}, json=body)
        assert denied.status_code == 404, (denied.status_code, denied.text)
    with context["connect_db"]() as db:
        assert db.execute("SELECT count(*) FROM plm.srv_survey_versions WHERE survey_id=%s",
                          (survey,)).fetchone()[0] == 1
    print("SUR_07_A08_PACKAGED_PG_PASS: DRAFT fixed+MANUAL, target, one Audit/receipt, "
          "same-key replay and denied writers", flush=True)
    print("SUR_07_A12_P05_PACKAGED_PG_PASS: DRAFT Validate, ProjectManager atomic "
          "submit-review, exact ACTIVE reviewer snapshot, member read and non-assignee decision denial, "
          "Audit and receipt", flush=True)


def after_expiry(state: dict, **context) -> None:
    survey_create["after_expiry"](state, **context)
    project, survey = state["project"], state["survey"]
    denied = context["observer_client"].post(
        f"/api/v1/projects/{project}/surveys/{survey}/versions", headers={
            "origin": context["origin"], "x-csrf-token": context["observer_csrf"],
            "if-match": '"v1"', "idempotency-key": str(uuid.uuid4()),
        }, json=state["body"])
    assert denied.status_code == 403, (denied.status_code, denied.text)
    with context["connect_db"]() as db:
        assert db.execute("SELECT count(*) FROM plm.srv_survey_versions WHERE survey_id=%s",
                          (survey,)).fetchone()[0] == state["version_count"]
    print("SUR_07_A08_PACKAGED_LICENSE_DENIAL_PASS: synthetic EXPIRED projection", flush=True)


def browser_probe(**context) -> None:
    state: dict = {}
    handover_review["browser_probe"](**context,
        after_approval_probe=lambda **values: after_approval(state, **values),
        after_expiry_probe=lambda **values: after_expiry(state, **values))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage", "pristine", "target"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--temp-root", type=Path,
                        help="Explicit existing ASCII disposable temp parent for this proof")
    args = parser.parse_args()
    if args.temp_root is not None:
        root = args.temp_root.resolve(strict=True)
        if (not root.is_dir() or not str(root).isascii()
                or root.name != "PLMToolTemp" or root.drive.upper() != "D:"):
            raise ValueError("alternate temp root rejected")
        tempfile.tempdir = str(root)
    runner = handover_review["base"]["base"]["project"]["base"].base.base
    result = runner.smoke(
        args.candidate, args.stage, args.pristine, args.target, args.expected_sha256,
        synthetic_license_document_factory=runner.synthetic_document,
        licensed_https_probe=browser_probe,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
