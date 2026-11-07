"""Disposable packaged Edge/HTTPS/PG proof for Survey DRAFT version creation."""

from __future__ import annotations

import argparse
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import traceback
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
_CURRENT_STAGE = "none"


def mark_stage(stage: str) -> None:
    global _CURRENT_STAGE
    if not re.fullmatch(r"[A-Z0-9_]{1,64}", stage):
        raise ValueError("invalid diagnostic stage")
    _CURRENT_STAGE = "SUR_07_A08_STAGE_" + stage
    print(_CURRENT_STAGE, flush=True)


sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))
extract_verified = runpy.run_path(str(ROOT / "tools/run_a17_packaged_cloud_validation.py"))["extract_verified"]
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
    mark_stage("APPROVAL_FIXTURE_START")
    survey_create["after_approval"](state, **context)
    mark_stage("APPROVAL_FIXTURE_READY")
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
    mark_stage("EDGE_START")
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
    mark_stage("EDGE_PASS")
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
    mark_stage("LICENSE_EXPIRY_FIXTURE_START")
    survey_create["after_expiry"](state, **context)
    mark_stage("LICENSE_EXPIRY_FIXTURE_READY")
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
    mark_stage("BROWSER_CALLBACK_START")
    handover_review["browser_probe"](**context,
        after_approval_probe=lambda **values: after_approval(state, **values),
        after_expiry_probe=lambda **values: after_expiry(state, **values))
    mark_stage("BROWSER_CALLBACK_PASS")


def main() -> int:
    mark_stage("VERIFIER_START")
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
    mark_stage("TEMP_ROOT_READY")
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    stage_parent = args.stage.parent.resolve(strict=True)
    if (stage_parent != temp or not str(args.stage).isascii()
            or not args.stage.name.startswith("plm-current-app-stage-")
            or args.stage.exists() or args.stage.is_symlink()):
        raise ValueError("current-app stage root rejected")
    mark_stage("CANDIDATE_STAGE_EXTRACT_START")
    extract_verified(args.candidate, args.expected_sha256, args.stage)
    mark_stage("CANDIDATE_STAGE_EXTRACT_PASS")
    stage_initdb = args.stage / "payload" / "pgsql" / "bin" / "initdb.exe"
    if not stage_initdb.is_file() or stage_initdb.is_symlink():
        raise ValueError("verified candidate initdb path rejected")
    mark_stage("STAGE_INITDB_PROBE_START")
    initdb_probe = subprocess.run(
        [str(stage_initdb), "--version"], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=30, check=False,
    )
    if initdb_probe.returncode:
        mark_stage("STAGE_INITDB_PROBE_FAIL")
        raise RuntimeError(
            "synthetic packaged migration command failed: initdb.exe, exit="
            + str(initdb_probe.returncode) + ", output="
        )
    mark_stage("STAGE_INITDB_PROBE_PASS")
    target_root = args.target
    if (target_root.parent.resolve(strict=True) != temp or not str(target_root).isascii()
            or not target_root.name.startswith("plm-install-rehearsal-target-")
            or target_root.exists() or target_root.is_symlink()):
        raise ValueError("target rehearsal root rejected")
    original_path = os.environ.get("PATH", "")
    os.environ["PATH"] = os.pathsep.join((
        str(target_root / "runtime" / "pgsql" / "bin"),
        str(target_root / "runtime" / "pgsql" / "lib"),
        original_path,
    ))
    mark_stage("BUNDLED_PG_DLL_PATH_READY")
    runner = handover_review["base"]["base"]["project"]["base"].base.base
    platform_write_globals = runner.smoke.__globals__["original_smoke"].__globals__
    original_pg_run = platform_write_globals["_run"]
    target_pg_bin = target_root / "runtime" / "pgsql" / "bin"
    target_pg_probes = {
        "initdb": "not_run", "postgres": "not_run", "temp_env": "not_run",
        "temp_env_applied": "no",
    }

    def a08_pg_run(arguments, *, env=None, timeout=120):
        actual_env = dict(env if env is not None else os.environ)
        if (arguments and Path(arguments[0]).name.casefold() == "initdb.exe"
                and target_pg_probes["initdb"] == "not_run"):
            for name in ("initdb", "postgres"):
                try:
                    probe = subprocess.run(
                        [str(target_pg_bin / (name + ".exe")), "--version"],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, timeout=30, check=False, env=actual_env,
                    )
                    target_pg_probes[name] = str(probe.returncode)
                except subprocess.TimeoutExpired:
                    target_pg_probes[name] = "timeout"
                except OSError:
                    target_pg_probes[name] = "launch_error"

            pg_temp_value = actual_env.get("TEMP", "")
            pg_temp = Path(pg_temp_value)
            owned_temp = Path(tempfile.gettempdir()).resolve(strict=True)
            probe_root = None
            try:
                if (not pg_temp_value or pg_temp.is_symlink()
                        or pg_temp.resolve(strict=True).parent != owned_temp
                        or not pg_temp.name.startswith("plm-pg18-platform-write-")
                        or owned_temp.drive.upper() != "D:"
                        or not str(pg_temp).isascii()):
                    target_pg_probes["temp_env"] = "unsafe_boundary"
                else:
                    pg_temp = pg_temp.resolve(strict=True)
                    probe_root = pg_temp / "a08-initdb-base-temp-probe"
                    if probe_root.exists() or probe_root.is_symlink():
                        target_pg_probes["temp_env"] = "unsafe_boundary"
                    else:
                        probe_root.mkdir()
                        probe_args = list(arguments)
                        pgdata_indexes = [
                            index for index, value in enumerate(probe_args)
                            if value.startswith("--pgdata=")
                        ]
                        if len(pgdata_indexes) != 1:
                            target_pg_probes["temp_env"] = "invalid_args"
                        else:
                            probe_args[pgdata_indexes[0]] = "--pgdata=" + str(probe_root / "data")
                            alternate_env = dict(actual_env)
                            alternate_env["TEMP"] = str(owned_temp)
                            alternate_env["TMP"] = str(owned_temp)
                            try:
                                probe = subprocess.run(
                                    probe_args, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=60, check=False, env=alternate_env,
                                )
                                target_pg_probes["temp_env"] = str(probe.returncode)
                                if probe.returncode == 0:
                                    actual_env["TEMP"] = str(owned_temp)
                                    actual_env["TMP"] = str(owned_temp)
                                    target_pg_probes["temp_env_applied"] = "yes"
                            except subprocess.TimeoutExpired:
                                target_pg_probes["temp_env"] = "timeout"
                            except OSError:
                                target_pg_probes["temp_env"] = "launch_error"
            finally:
                if probe_root is not None and probe_root.exists() and not probe_root.is_symlink():
                    resolved_probe = probe_root.resolve(strict=True)
                    if (resolved_probe.parent == pg_temp.resolve(strict=True)
                            and resolved_probe.name == "a08-initdb-base-temp-probe"
                            and resolved_probe.drive.upper() == "D:"
                            and str(resolved_probe).isascii()):
                        shutil.rmtree(resolved_probe)
            mark_stage("TARGET_PG_TEMP_ENV_PROBE_DONE")
        return original_pg_run(arguments, env=actual_env, timeout=timeout)

    platform_write_globals["_run"] = a08_pg_run
    mark_stage("PACKAGED_SMOKE_START")
    try:
        result = runner.smoke(
            args.candidate, args.stage, args.pristine, args.target, args.expected_sha256,
            synthetic_license_document_factory=runner.synthetic_document,
            licensed_https_probe=browser_probe,
        )
    except Exception as exc:
        frames = []
        for frame in traceback.extract_tb(exc.__traceback__)[-8:]:
            filename = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(frame.filename).name)[:80]
            frames.append(filename + ":" + str(frame.lineno))
        exception_name = re.sub(r"[^A-Za-z0-9_.-]", "_", type(exc).__name__)[:80]
        winerror = getattr(exc, "winerror", None)
        if not isinstance(winerror, int):
            winerror = "none"
        child = "none"
        child_exit = "none"
        error_message = exc.args[0] if len(exc.args) == 1 and isinstance(exc.args[0], str) else ""
        child_match = re.match(
            r"synthetic packaged migration command failed: ([A-Za-z0-9_.-]{1,80}), "
            r"exit=(-?\d{1,10}), output=",
            error_message,
        )
        if child_match and child_match.group(1).casefold() in {
            "initdb.exe", "pg_ctl.exe", "psql.exe", "postgres.exe", "python.exe",
        }:
            child, child_exit = child_match.groups()
        print("SUR_07_A08_SAFE_DIAG: exception=" + exception_name
              + "; winerror=" + str(winerror)
              + "; child=" + child
              + "; child_exit=" + child_exit
              + "; target_initdb_probe=" + target_pg_probes["initdb"]
              + "; target_postgres_probe=" + target_pg_probes["postgres"]
              + "; target_initdb_temp_env_probe=" + target_pg_probes["temp_env"]
              + "; target_initdb_temp_env_applied=" + target_pg_probes["temp_env_applied"]
              + "; stage=" + _CURRENT_STAGE
              + "; frames=" + (">".join(frames) if frames else "none"), flush=True)
        raise
    finally:
        platform_write_globals["_run"] = original_pg_run
    mark_stage("PACKAGED_SMOKE_PASS")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
