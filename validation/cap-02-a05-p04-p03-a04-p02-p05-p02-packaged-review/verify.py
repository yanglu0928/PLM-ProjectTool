"""Fixed non-release candidate: synthetic GLOBAL Capability Review over packaged HTTPS/Edge/PG."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher  # noqa: E402
from smoke_current_app_packaged_https import smoke  # noqa: E402


def load(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evidence = load("_cap_review_package_evidence", ROOT / "validation" /
                "evd-05-a02-packaged-edge" / "verify.py")
workflow = evidence.workflow
EXTENDED_NEGATIVE = os.environ.get("PLM_CAP_PACKAGED_REVIEW_NEGATIVE") == "1"


def expect(response: httpx.Response, status: int) -> dict:
    if response.status_code != status:
        raise AssertionError((response.request.method, response.request.url.path,
                              response.status_code, response.text[:400]))
    body = response.json()
    assert set(body) == {"data", "trace_id"}, body
    return body["data"]


def headers(origin: str, csrf: str, *, key: str | None = None,
            etag: str | None = None) -> dict[str, str]:
    result = {"origin": origin, "x-csrf-token": csrf}
    if key is not None:
        result["idempotency-key"] = key
    if etag is not None:
        result["if-match"] = etag
    return result


def seed_user(connect_db, display: str) -> uuid.UUID:
    clear = bytearray(b"synthetic-packaged-review-only")
    view = memoryview(clear)
    try:
        hashed = ScryptPasswordHasher().hash_password(view)
    finally:
        view.release()
        clear[:] = b"\x00" * len(clear)
    with connect_db() as db:
        user = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (display, display.lower()),
        ).fetchone()[0]
        credential = db.execute(
            "INSERT INTO plm.auth_password_credentials(user_id,credential_version,"
            "password_hash,algorithm_id,parameter_set) "
            "VALUES (%s,1,%s,%s,%s::jsonb) RETURNING password_credential_id",
            (user, hashed.password_hash, hashed.algorithm_id,
             '{"n":131072,"r":8,"p":1,"dklen":32}'),
        ).fetchone()[0]
        db.execute(
            "UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,"
            "state='ENABLED' WHERE user_id=%s", (credential, user),
        )
    return user


def login_user(origin: str, display: str) -> tuple[httpx.Client, str]:
    client = httpx.Client(base_url=origin, verify=False, timeout=8,
                          follow_redirects=False, trust_env=False)
    try:
        login = expect(client.post("/api/v1/auth/login", json={
            "username": display, "password": "synthetic-packaged-review-only",
        }, headers={"origin": origin}), 200)
        assert login["deployment_role"] == "NONE"
        return client, login["csrf_token"]
    except Exception:
        client.close()
        raise


def probe(**context) -> None:
    evidence.browser_probe(**context)
    client, connect_db, origin = (context["client"], context["connect_db"],
                                  context["origin"])
    admin_csrf = context["login"].json()["data"]["csrf_token"]
    with connect_db() as db:
        document_id, document_version_id = db.execute(
            "SELECT d.document_id,v.document_version_id FROM plm.doc_documents d "
            "JOIN plm.doc_document_versions v ON v.document_id=d.document_id "
            "WHERE d.scope='GLOBAL' AND d.document_category='STANDARD_CAPABILITY' "
            "AND d.title='Synthetic Capability Source'",
        ).fetchone()
        evidence_id, state = db.execute(
            "SELECT evidence_id,eligibility_state FROM plm.evd_evidence_records "
            "WHERE scope='GLOBAL' AND display_label='Synthetic Whole Document Evidence'",
        ).fetchone()
        assert state == "CANDIDATE"
        baseline_id, = db.execute(
            "SELECT baseline_id FROM plm.cap_baselines "
            "WHERE baseline_code='CAP.SYNTHETIC.PKG'",
        ).fetchone()
    reviewer_one = seed_user(connect_db, "Synthetic Capability Reviewer One")
    reviewer_two = seed_user(connect_db, "Synthetic Capability Reviewer Two")
    seed_user(connect_db, "Synthetic Capability Outsider")
    evidence_path = f"/api/v1/global/evidence/{evidence_id}"
    candidate = expect(client.get(evidence_path), 200)
    assert candidate["eligibility_state"] == "CANDIDATE"
    eligible = expect(client.post(
        evidence_path + ":set-eligibility",
        headers=headers(origin, admin_csrf, key=str(uuid.uuid4()), etag=candidate["etag"]),
        json={"eligibility_state": "ELIGIBLE", "reason": "Synthetic fixed source reviewed"},
    ), 200)
    assert eligible["eligibility_state"] == "ELIGIBLE"
    baseline_path = f"/api/v1/global/capability-baselines/{baseline_id}"
    baseline = expect(client.get(baseline_path), 200)
    source = [{"document_id": str(document_id),
               "document_version_id": str(document_version_id)}]
    drafts = [{
        "stable_item_id": str(uuid.uuid4()), "capability_code": f"CAP.PKG.REVIEW.{ordinal}",
        "domain_name": "PLM", "module_name": "Capability", "feature_name": "Review",
        "name": f"Synthetic Packaged Review Item {ordinal}",
        "description": "Synthetic fixed capability content", "boundary": "GLOBAL only",
        "prerequisites": [], "interface_refs": [], "document_refs": source,
        "evidence_refs": [str(evidence_id)], "item_state": "AVAILABLE",
    } for ordinal in range(2)]
    version = expect(client.post(
        baseline_path + "/versions",
        headers=headers(origin, admin_csrf, key=str(uuid.uuid4()), etag=baseline["etag"]),
        json={"items": drafts},
    ), 201)
    version_id = version["baseline_version_id"]
    version_path = baseline_path + f"/versions/{version_id}"
    validation = expect(client.post(version_path + ":validate",
                                    headers=headers(origin, admin_csrf, key=str(uuid.uuid4()))), 200)
    assert validation["valid"] is True and validation["item_count"] == 2, validation
    submitted = expect(client.post(
        version_path + ":submit-review",
        headers=headers(origin, admin_csrf, key=str(uuid.uuid4())),
        json={"reviewer_ids": [str(reviewer_one), str(reviewer_two)],
              "policy_ref": "DEPLOYMENT_ALL_V1", "due_at": None,
              "submission_note": None},
    ), 201)
    review_id, round_id = submitted["review_id"], submitted["review_round_id"]
    review_path = f"/api/v1/global/reviews/{review_id}"
    with httpx.Client(base_url=origin, verify=False, timeout=8, trust_env=False) as anon:
        assert anon.get(review_path + "/fixed-version").status_code == 401
    outsider, outsider_csrf = login_user(origin, "Synthetic Capability Outsider")
    try:
        assert outsider.get(review_path).status_code == 404
        assert outsider.get(review_path + "/fixed-version").status_code == 404
        if EXTENDED_NEGATIVE:
            denied = outsider.post(
                review_path + f"/rounds/{round_id}:decide",
                headers=headers(origin, outsider_csrf, key=str(uuid.uuid4())),
                json={"decision": "APPROVE", "comment": None},
            )
            assert denied.status_code == 404, denied.text[:300]
    finally:
        outsider.close()
    reviewer, reviewer_csrf = login_user(origin, "Synthetic Capability Reviewer Two")
    try:
        first = expect(reviewer.get(review_path + "/fixed-items?page_size=1"), 200)
        assert first["has_more"] is True and len(first["items"]) == 1
        cursor = first["next_cursor"]
        changed = cursor[:-1] + ("A" if cursor[-1] != "A" else "B")
        assert reviewer.get(review_path + "/fixed-items?page_size=1&cursor=" + changed).status_code == 400
        if EXTENDED_NEGATIVE:
            other_session, _ = login_user(origin, "Synthetic Capability Reviewer One")
            try:
                assert other_session.get(
                    review_path + "/fixed-items?page_size=1&cursor=" + cursor,
                ).status_code == 400
                with connect_db() as db:
                    db.execute("UPDATE plm.auth_users SET state='DISABLED' WHERE user_id=%s",
                               (reviewer_one,))
                rejected = other_session.get(review_path + "/fixed-version")
                assert rejected.status_code in (401, 404), rejected.text[:300]
            finally:
                with connect_db() as db:
                    db.execute("UPDATE plm.auth_users SET state='ENABLED' WHERE user_id=%s",
                               (reviewer_one,))
                other_session.close()
        browser = subprocess.run(
            ["node", str(Path(__file__).with_name("run-review-edge.mjs")), origin,
             str(baseline_id), version_id, review_id], capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=150, check=False,
        )
        if browser.returncode:
            raise AssertionError("packaged Review Edge failed: "
                                 + browser.stdout[-3500:] + browser.stderr[-3500:])
        assert "CAP_02_P05_P02_PACKAGED_REVIEW_EDGE_PASS" in browser.stdout
        print(browser.stdout.strip(), flush=True)
        second_key = str(uuid.uuid4())
        second_body = {"decision": "APPROVE", "comment": None}
        second = expect(reviewer.post(
            review_path + f"/rounds/{round_id}:decide",
            headers=headers(origin, reviewer_csrf, key=second_key),
            json=second_body,
        ), 200)
        assert second["state"] == "APPROVED"
        if EXTENDED_NEGATIVE:
            replay = expect(reviewer.post(
                review_path + f"/rounds/{round_id}:decide",
                headers=headers(origin, reviewer_csrf, key=second_key),
                json=second_body,
            ), 200)
            assert replay == second
            different = reviewer.post(
                review_path + f"/rounds/{round_id}:decide",
                headers=headers(origin, reviewer_csrf, key=str(uuid.uuid4())),
                json=second_body,
            )
            assert different.status_code in (409, 422), different.text[:300]
    finally:
        reviewer.close()
    current = expect(client.get(baseline_path), 200)
    assert current["current_approved_version_ref"] == version_id
    with connect_db() as db:
        decisions = db.execute(
            "SELECT reviewer_id,decision FROM plm.rvw_review_decisions WHERE review_id=%s",
            (review_id,),
        ).fetchall()
        audit = db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='REVIEW_DECISION_RECORDED' "
            "AND actor_id IN (%s,%s)", (reviewer_one, reviewer_two),
        ).fetchone()[0]
        assert set(decisions) == {(reviewer_one, "APPROVE"), (reviewer_two, "APPROVE")}
        assert audit == 2
    print("CAP_02_P05_P02_PACKAGED_REVIEW_PG_PASS: 2 fixed items, 2 reviewers, pointer, Audit, denials", flush=True)
    if EXTENDED_NEGATIVE:
        print("CAP_02_P05_P03_PACKAGED_NEGATIVE_PASS: disabled, cross-session, outsider write, replay", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage", "pristine", "target"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(
        args.candidate, args.stage, args.pristine, args.target, args.expected_sha256,
        synthetic_license_document_factory=workflow.synthetic_document,
        licensed_https_probe=probe,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
