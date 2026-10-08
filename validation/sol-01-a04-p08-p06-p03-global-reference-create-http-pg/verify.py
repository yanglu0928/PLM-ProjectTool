"""Isolated PG18/ASGI GLOBAL Reference Create with synthetic proof only."""

from __future__ import annotations

import importlib.util
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_reference import _source_service
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.reference_create import create_global_reference_create_router
from plm_assistant.modules.solution.api.reference_deidentification import create_reference_deidentification_router
from plm_assistant.modules.solution.application.create_reference_solution import ReferenceCreateService
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_reference_fixture",
    ROOT / "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def on_preview(*, runtime, audit, license_guard, preview, confirm, revoke,
               document, version, evidence, node_evidence, port, scratch,
               documents, downloads, parse_results,
               create_router_factory=None, **_unused) -> None:
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    project_repository = SqlAlchemyProjectAuthorizationRepository()
    sources = _source_service(
        documents=documents, downloads=downloads, parse_results=parse_results,
        project_repository=project_repository)

    def create_service(guard):
        return ReferenceCreateService(
            unit_of_work=runtime.unit_of_work,
            global_access=SqlAlchemyLicenseImportAccess(),
            project_access=SqlAlchemyProjectWriteAccess(),
            project_authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work, repository=project_repository),
            license_guard=guard, sources=sources,
            repository=SqlAlchemyReferenceCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)

    if create_router_factory is None:
        create_router = create_global_reference_create_router(
            sessions=sessions, origins=origins, creates=create_service(license_guard))
    else:
        create_router = create_router_factory(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=license_guard, audit=audit,
            documents=documents, downloads=downloads, parse_results=parse_results)
    attestation_router = create_reference_deidentification_router(
        sessions=sessions, origins=origins, previews=preview,
        confirmations=confirm, revocations=revoke)
    path = "/api/v1/global/reference-solutions"
    attestation = "/api/v1/global/reference-deidentification-confirmations"
    body = {
        "name": "Synthetic Global Reference",
        "document_version_ids": [str(version)],
        "evidence_ids": [str(evidence), str(node_evidence)],
        "source_project_class": "PLM",
        "deidentification_class": "DEIDENTIFIED",
        "applicability": {"industry": "synthetic"},
    }
    headers = {
        "cookie": "plm_session=" + fixture.TOKEN.hex(),
        "origin": "https://plm.example.test",
        "x-csrf-token": fixture.CSRF.hex(),
        "idempotency-key": "global-create-" + "a" * 16,
    }

    def counts():
        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            return tuple(db.execute(f"SELECT count(*) FROM plm.{table}").fetchone()[0]
                         for table in ("sol_reference_solutions", "sol_reference_versions",
                                       "sol_reference_document_refs", "sol_reference_evidence_refs"))

    def posted(client, key, value=body):
        return client.post(path, headers={**headers, "idempotency-key": key}, json=value)

    with TestClient(create_app(
            global_reference_create_router=create_router,
            reference_deidentification_router=attestation_router),
            base_url="https://plm.example.test") as client:
        assert counts() == (0, 0, 0, 0)
        absent = posted(client, "global-create-absent-01")
        assert absent.status_code == 404, absent.text
        assert counts() == (0, 0, 0, 0)

        shown = client.post(attestation + ":preview", headers=headers,
                            json={key: value for key, value in body.items() if key != "name"})
        assert shown.status_code == 200, shown.text
        confirmation_body = {
            **{key: value for key, value in body.items() if key != "name"},
            "expected_source_fingerprint": shown.json()["data"]["source_fingerprint"],
            "attestation_statement": "I_VERIFIED_DEIDENTIFICATION",
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=3))
            .isoformat().replace("+00:00", "Z"),
        }
        confirmed = client.post(attestation, headers={**headers,
            "idempotency-key": "global-confirm-" + "c" * 16}, json=confirmation_body)
        assert confirmed.status_code == 201, confirmed.text
        confirmation_id = confirmed.json()["data"]["confirmation_id"]

        created = posted(client, headers["idempotency-key"])
        assert created.status_code == 201, created.text
        result = created.json()["data"]
        assert result["scope"] == "GLOBAL" and result["project_id"] is None
        assert result["eligibility_state"] == "REFERENCE_ONLY"
        assert result["version_state"] == "DRAFT"
        assert created.headers["etag"] == '"v0"'
        assert created.headers["location"].endswith(result["reference_solution_id"])
        assert created.headers["x-trace-id"] == created.json()["trace_id"]
        assert "confirmation_id" not in created.text and "synthetic.txt" not in created.text
        assert counts() == (1, 1, 1, 2)
        replay = posted(client, headers["idempotency-key"])
        assert replay.status_code == 201 and replay.json()["data"] == result
        assert posted(client, headers["idempotency-key"],
                      {**body, "name": "Different"}).status_code == 409
        assert client.post(path, headers={**headers,
            "x-csrf-token": (b"x" * 32).hex()}, json=body).status_code == 403
        assert client.post(path, headers={**headers,
            "origin": "https://evil.test"}, json=body).status_code == 403
        assert posted(client, "global-create-wrong-class", {
            **body, "source_project_class": "OTHER"}).status_code == 404
        assert counts() == (1, 1, 1, 2)

        with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                             dbname="postgres", autocommit=True) as db:
            row = db.execute(
                "SELECT v.deidentification_confirmation_id,v.source_fingerprint,"
                "v.declared_document_count,v.declared_evidence_count "
                "FROM plm.sol_reference_versions v WHERE v.reference_version_id=%s",
                (result["reference_version_id"],)).fetchone()
            assert str(row[0]) == confirmation_id
            assert row[1] == bytes.fromhex(confirmation_body["expected_source_fingerprint"])
            assert row[2:] == (1, 2)
            assert db.execute("SELECT count(*) FROM plm.aud_events "
                              "WHERE action='SOL_REFERENCE_CREATED'").fetchone()[0] == 1
            locator = db.execute("SELECT storage_locator FROM plm.doc_file_objects "
                                 "WHERE scope='GLOBAL'").fetchone()[0]
        source = scratch / "private-documents" / locator
        original = source.read_bytes()
        try:
            source.write_bytes(b"X" * len(original))
            assert posted(client, "global-create-tamper-01").status_code == 503
        finally:
            source.write_bytes(original)
        assert counts() == (1, 1, 1, 2)

        time.sleep(max(0, (datetime.fromisoformat(confirmation_body["expires_at"]
            .replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds()) + .2)
        assert posted(client, "global-create-expired-01").status_code == 404
        assert counts() == (1, 1, 1, 2)
        later = client.post(attestation, headers={**headers,
            "idempotency-key": "global-confirm-" + "d" * 16},
            json={**confirmation_body, "expires_at": (
                datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
                .replace("+00:00", "Z")})
        assert later.status_code == 201, later.text
        later_id = later.json()["data"]["confirmation_id"]
        revoked = client.post(attestation + "/" + later_id + ":revoke",
            headers={**headers, "idempotency-key": "global-revoke-" + "r" * 16},
            json={"reason_code": "ADMIN_REVIEW"})
        assert revoked.status_code == 200, revoked.text
        assert posted(client, "global-create-revoked-01").status_code == 404
        assert counts() == (1, 1, 1, 2)

    denied = create_global_reference_create_router(
        sessions=sessions, origins=origins, creates=create_service(DeniedLicense()))
    with TestClient(create_app(global_reference_create_router=denied),
                    base_url="https://plm.example.test") as client:
        response = posted(client, "global-create-license-01")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "LICENSE_OPERATION_DENIED"
    assert counts() == (1, 1, 1, 2)
    print("SOL_01_A04_P08_P06_P03_GLOBAL_CREATE_HTTP_PG_PASS: synthetic "
          "confirmation, fixed private file, Session, replay, expiry/revocation, "
          "tamper, CSRF/Origin, License and atomic rows")


def main() -> None:
    fixture.main(on_preview=on_preview)


if __name__ == "__main__":
    main()
