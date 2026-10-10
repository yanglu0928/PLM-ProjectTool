"""Isolated PG18/ASGI GLOBAL attestation transport proof over synthetic sources."""

from __future__ import annotations

import importlib.util
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.solution.api.reference_deidentification import create_reference_deidentification_router


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_reference_fixture",
    ROOT / "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def on_preview(*, runtime, audit, license_guard, preview, confirm, revoke, request,
               document, version, evidence, node_evidence, fingerprint, port,
               router_factory=None, documents=None, downloads=None,
               parse_results=None,
               **_unused) -> None:
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    if router_factory is None:
        router = create_reference_deidentification_router(
            sessions=sessions, origins=origins,
            previews=preview, confirmations=confirm, revocations=revoke)
    else:
        router = router_factory(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=license_guard, audit=audit,
            documents=documents, downloads=downloads,
            parse_results=parse_results)
    base = "/api/v1/global/reference-deidentification-confirmations"
    headers = {
        "cookie": "plm_session=" + fixture.TOKEN.hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": fixture.CSRF.hex(),
        "idempotency-key": "http-" + "r" * 16,
    }
    body = {
        "document_version_ids": [str(version)],
        "evidence_ids": [str(evidence), str(node_evidence)],
        "source_project_class": "PLM",
        "deidentification_class": "DEIDENTIFIED",
        "applicability": {"industry": "synthetic"},
    }
    with TestClient(create_app(reference_deidentification_router=router),
                    base_url="https://plm.example.test") as client:
        lookup_path = base + ":lookup-operation"
        if router_factory is not None:
            missing = client.post(lookup_path, headers=headers,
                json={"operation_kind": "CONFIRM", "operation_key": headers["idempotency-key"]})
            assert missing.status_code == 200 and missing.json()["data"] == {"status": "UNCONFIRMED"}
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            before = db.execute(
                "SELECT count(*) FROM plm.sol_reference_deidentification_confirmations").fetchone()[0]
        shown = client.post(base + ":preview", headers=headers, json=body)
        assert shown.status_code == 200, shown.text
        data = shown.json()["data"]
        assert data["source_fingerprint"] == fingerprint.hex()
        assert data["document_refs"] == [{
            "document_id": str(document), "document_version_id": str(version)}]
        assert data["evidence_ids"] == [str(evidence), str(node_evidence)]
        assert "synthetic.txt" not in shown.text
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.sol_reference_deidentification_confirmations").fetchone()[0] == before
        confirm_body = {
            **body, "expected_source_fingerprint": data["source_fingerprint"],
            "attestation_statement": "I_VERIFIED_DEIDENTIFICATION",
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            .replace("+00:00", "Z"),
        }
        assert client.post(base, headers=headers, json={
            **confirm_body, "expected_source_fingerprint": "0" * 64,
        }).json()["error"]["code"] == "SOURCE_SNAPSHOT_CHANGED"
        assert client.post(base + ":preview", headers={**headers,
            "x-csrf-token": (b"x" * 32).hex()}, json=body).status_code == 403
        assert client.post(base, headers={**headers,
            "origin": "https://evil.test"}, json=confirm_body).status_code == 403
        created = client.post(base, headers=headers, json=confirm_body)
        assert created.status_code == 201, created.text
        confirmation_id = created.json()["data"]["confirmation_id"]
        if router_factory is not None:
            looked_up = client.post(lookup_path, headers=headers,
                json={"operation_kind": "CONFIRM", "operation_key": headers["idempotency-key"]})
            assert looked_up.status_code == 200, looked_up.text
            assert looked_up.json()["data"] == {
                "status": "COMPLETED", "confirmation_id": confirmation_id,
                "first_status_code": 201, "current_state": "CONFIRMED"}
            wrong_kind = client.post(lookup_path, headers=headers,
                json={"operation_kind": "REVOKE", "operation_key": headers["idempotency-key"]})
            assert wrong_kind.status_code == 200 and wrong_kind.json()["data"] == {"status": "UNCONFIRMED"}
            other_token, other_csrf = b"o" * 32, b"p" * 32
            with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                                 dbname="postgres", autocommit=True) as db:
                other = db.execute(
                    "INSERT INTO plm.auth_users(username_display,username_normalized) "
                    "VALUES ('Reference Other Admin','reference other admin') RETURNING user_id"
                ).fetchone()[0]
                credential = db.execute(
                    "INSERT INTO plm.auth_password_credentials(user_id,credential_version,"
                    "password_hash,algorithm_id,parameter_set) VALUES "
                    "(%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
                    "RETURNING password_credential_id", (other,),
                ).fetchone()[0]
                db.execute("UPDATE plm.auth_users SET credential_version=1,"
                           "active_password_credential_id=%s,state='ENABLED',"
                           "deployment_role='DEPLOYMENT_ADMIN' WHERE user_id=%s",
                           (credential, other))
                db.execute(
                    "INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,"
                    "credential_version,idle_expires_at,absolute_expires_at) "
                    "VALUES (%s,%s,%s,1,statement_timestamp()+interval '30 minutes',"
                    "statement_timestamp()+interval '2 hours')",
                    (hashlib.sha256(other_token).digest(),
                     hashlib.sha256(other_csrf).digest(), other))
            other_headers = {**headers, "cookie": "plm_session=" + other_token.hex(),
                             "x-csrf-token": other_csrf.hex()}
            cross_actor = client.post(lookup_path, headers=other_headers,
                json={"operation_kind": "CONFIRM", "operation_key": headers["idempotency-key"]})
            assert cross_actor.status_code == 200 and cross_actor.json()["data"] == {"status": "UNCONFIRMED"}
        replay = client.post(base, headers=headers, json=confirm_body)
        assert replay.status_code == 201, replay.text
        assert replay.json()["data"]["confirmation_id"] == confirmation_id
        assert client.post(base, headers=headers, json={
            **confirm_body, "expires_at": (datetime.now(timezone.utc) + timedelta(days=2))
            .isoformat().replace("+00:00", "Z"),
        }).status_code == 409
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.sol_reference_deidentification_confirmations").fetchone()[0] == before + 1
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action='SOL_REFERENCE_DEIDENTIFICATION_CONFIRMED'").fetchone()[0] == 1
        revocation_headers = {**headers, "idempotency-key": "http-" + "v" * 16}
        path = base + "/" + confirmation_id + ":revoke"
        revoked = client.post(path, headers=revocation_headers,
                              json={"reason_code": "ADMIN_REVIEW"})
        assert revoked.status_code == 200, revoked.text
        assert client.post(path, headers=revocation_headers,
                           json={"reason_code": "ADMIN_REVIEW"}).status_code == 200
        if router_factory is not None:
            looked_up = client.post(lookup_path, headers=headers,
                json={"operation_kind": "CONFIRM", "operation_key": headers["idempotency-key"]})
            assert looked_up.status_code == 200, looked_up.text
            assert looked_up.json()["data"]["current_state"] == "REVOKED"
            revoke_lookup = client.post(lookup_path, headers=headers,
                json={"operation_kind": "REVOKE", "operation_key": revocation_headers["idempotency-key"]})
            assert revoke_lookup.status_code == 200, revoke_lookup.text
            assert revoke_lookup.json()["data"] == {
                "status": "COMPLETED", "confirmation_id": confirmation_id,
                "first_status_code": 200, "current_state": "REVOKED"}
        assert client.post(path, headers={**revocation_headers,
            "idempotency-key": "http-" + "z" * 16},
            json={"reason_code": "ADMIN_REVIEW"}).status_code == 409
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            assert db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action='SOL_REFERENCE_DEIDENTIFICATION_REVOKED'").fetchone()[0] == 1
    print("SOL_01_A04_P08_P03_P04_GLOBAL_ATTESTATION_HTTP_PG_PASS: "
          "real Session, fixed Document/Evidence proof, snapshot fence, "
          "idempotent confirm/revoke and audit")


def main() -> None:
    fixture.main(on_preview=on_preview)


if __name__ == "__main__":
    main()
