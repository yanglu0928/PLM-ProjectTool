"""Exercise GLOBAL Evidence create denials in the fixed non-release package.

All users, License state and documents are disposable synthetic fixtures.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation" / "evd-05-a02-packaged-edge" / "verify.py"
spec = spec_from_file_location("_evd05_packaged_positive", SOURCE)
assert spec and spec.loader
positive = module_from_spec(spec)
spec.loader.exec_module(positive)


def _counts(db) -> tuple[int, int, int]:
    return (
        db.execute("SELECT count(*) FROM plm.evd_evidence_records").fetchone()[0],
        db.execute("SELECT count(*) FROM plm.aud_events WHERE action='EVIDENCE_CREATED'").fetchone()[0],
        db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                   "WHERE operation='V1_EVIDENCE_CREATE'").fetchone()[0],
    )


def _denied(response: httpx.Response, status: int, code: str) -> None:
    assert response.status_code == status, (response.status_code, response.text)
    assert response.json()["error"]["code"] == code, response.text


def browser_probe(**kwargs) -> None:
    positive.browser_probe(**kwargs)
    with kwargs["connect_db"]() as db:
        source = db.execute(
            "SELECT d.document_id,v.document_version_id FROM plm.doc_documents d "
            "JOIN plm.doc_document_versions v ON v.document_id=d.document_id "
            "WHERE d.scope='GLOBAL' AND d.document_category='STANDARD_CAPABILITY' "
            "AND d.title='Synthetic Capability Source' AND v.availability_state='AVAILABLE'"
        ).fetchall()
        assert len(source) == 1, source
        document_id, version_id = source[0]
        before = _counts(db)
        assert before == (1, 1, 1), before

    body = {
        "document_id": str(document_id), "document_version_id": str(version_id),
        "locator": {"locator_type": "DOCUMENT"},
        "display_label": "Synthetic denied Evidence",
    }
    path = "/api/v1/global/evidence"
    origin = kwargs["origin"]
    admin_headers = {
        "origin": origin,
        "x-csrf-token": kwargs["login"].json()["data"]["csrf_token"],
        "idempotency-key": "evd05-packaged-negative-admin-001",
    }
    with httpx.Client(base_url=origin, verify=False, trust_env=False, timeout=15) as anonymous:
        _denied(anonymous.post(path, headers=admin_headers, json=body),
                401, "AUTH_SESSION_EXPIRED")

    username = "Synthetic Ordinary Evidence User"
    with kwargs["connect_db"]() as db, db.transaction():
        ordinary_id = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id", (username, username.lower()),
        ).fetchone()[0]
        credential_id = db.execute(
            "INSERT INTO plm.auth_password_credentials"
            "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
            "SELECT %s,1,password_hash,algorithm_id,parameter_set FROM "
            "plm.auth_password_credentials WHERE user_id=%s AND credential_version=1 "
            "RETURNING password_credential_id", (ordinary_id, kwargs["user_id"]),
        ).fetchone()[0]
        assert db.execute(
            "UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,"
            "state='ENABLED' WHERE user_id=%s", (credential_id, ordinary_id),
        ).rowcount == 1
    with httpx.Client(base_url=origin, verify=False, trust_env=False, timeout=15) as ordinary:
        login = ordinary.post(
            "/api/v1/auth/login", headers={"origin": origin},
            json={"username": username, "password": "synthetic-packaged-login-password"},
        )
        assert login.status_code == 200, (login.status_code, login.text)
        ordinary_headers = {
            "origin": origin, "x-csrf-token": login.json()["data"]["csrf_token"],
            "idempotency-key": "evd05-packaged-negative-ordinary-001",
        }
        _denied(ordinary.post(path, headers=ordinary_headers, json=body),
                404, "RESOURCE_NOT_FOUND")

    wrong_source = body | {"document_version_id": str(uuid.uuid4())}
    _denied(kwargs["client"].post(path, headers=admin_headers, json=wrong_source),
            404, "RESOURCE_NOT_FOUND")
    with kwargs["connect_db"]() as db:
        assert _counts(db) == before, (_counts(db), before)

    # Append an invalid validation event and advance the guarded singleton projection.
    # This is a synthetic EXPIRED-state simulation, not a wall-clock expiry claim.
    with kwargs["connect_db"]() as db, db.transaction():
        active_id, old_version = db.execute(
            "SELECT active_license_ref,state_version FROM plm.lic_validation_states "
            "WHERE singleton_key=1 AND validation_code='VALID' FOR UPDATE"
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
    expired_headers = admin_headers | {"idempotency-key": "evd05-packaged-negative-expired-001"}
    _denied(kwargs["client"].post(path, headers=expired_headers, json=body),
            403, "LICENSE_OPERATION_DENIED")
    with kwargs["connect_db"]() as db:
        after = _counts(db)
        assert after == before, (after, before)
        assert db.execute(
            "SELECT validation_code FROM plm.lic_validation_states WHERE singleton_key=1"
        ).fetchone() == ("EXPIRED",)
    print("Packaged GLOBAL Evidence denials: anonymous/member/wrong source/"
          "synthetic EXPIRED validation state; zero new Evidence/Audit/receipt PASS", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage", "pristine", "target"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    result = positive.smoke(
        args.candidate, args.stage, args.pristine, args.target, args.expected_sha256,
        synthetic_license_document_factory=positive.workflow.synthetic_document,
        licensed_https_probe=browser_probe,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
