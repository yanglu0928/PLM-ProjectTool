"""Real PostgreSQL/HTTP proof for the Windows Capability composition."""

from __future__ import annotations

import runpy
import os
import uuid
from pathlib import Path

from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_capability import (
    CAPABILITY_BASELINE_CURSOR_KEY_REF, CAPABILITY_CHILD_CURSOR_KEY_REF,
    create_windows_capability_routers,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import (
    SqlAlchemyAuditRepository,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


ROOT = Path(__file__).resolve().parents[2]
_create = runpy.run_path(str(
    ROOT / "validation" / "ai-02-a02-model-create" / "verify.py"
))
_schema = runpy.run_path(str(
    ROOT / "validation" / "cap-01-a02-capability-schema" / "verify.py"
))
connect, seed_user = _create["connect"], _create["seed_user"]
Guard, CSRF = _create["Guard"], _create["CSRF"]
seed_global_source = _schema["seed_global_source"]
ADMIN_TOKEN = b"a" * 32
REVIEWER_ONE_TOKEN = b"b" * 32
REVIEWER_TWO_TOKEN = b"c" * 32
OUTSIDER_TOKEN = b"d" * 32
GLOBAL_REVIEW_HTTP = os.environ.get("PLM_CAP_GLOBAL_REVIEW_HTTP_VALIDATION") == "1"


class Keys:
    def resolve_key(self, key_ref: str) -> bytes | None:
        return {
            CAPABILITY_BASELINE_CURSOR_KEY_REF: b"b" * 32,
            CAPABILITY_CHILD_CURSOR_KEY_REF: b"c" * 32,
        }.get(key_ref)


class Sessions:
    def validate(self, token: bytes, *, csrf_token: bytes | None = None,
                 require_csrf: bool = False):
        if (token not in (
                ADMIN_TOKEN, REVIEWER_ONE_TOKEN, REVIEWER_TWO_TOKEN,
                OUTSIDER_TOKEN)
                or require_csrf and csrf_token != CSRF):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def _headers(*, key: str | None = None, etag: str | None = None,
             json: bool = False, token: bytes = ADMIN_TOKEN) -> dict[str, str]:
    result = {
        "origin": "https://plm.example.test",
        "cookie": "plm_session=" + token.hex(),
        "x-csrf-token": CSRF.hex(),
    }
    if key is not None:
        result["idempotency-key"] = key
    if etag is not None:
        result["if-match"] = etag
    if json:
        result["content-type"] = "application/json"
    return result


def _expect(response, status: int):
    if response.status_code != status:
        raise AssertionError((response.status_code, response.text))
    return response.json()["data"]


def main() -> None:
    name = "cap01a05a07_" + uuid.uuid4().hex[:10]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create(
                "postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=55434, database=name,
            )
            cfg = create_migration_config(url)
            command.upgrade(cfg, "head")
            command.check(cfg)
            runtime = create_database_runtime(url)
            try:
                with connect(name) as db:
                    seed_user(db, "Synthetic HTTP Admin", "DEPLOYMENT_ADMIN", ADMIN_TOKEN)
                    reviewer_one = seed_user(
                        db, "Synthetic HTTP Reviewer One", "NONE", REVIEWER_ONE_TOKEN,
                    )
                    reviewer_two = seed_user(
                        db, "Synthetic HTTP Reviewer Two", "NONE", REVIEWER_TWO_TOKEN,
                    )
                    if GLOBAL_REVIEW_HTTP:
                        seed_user(db, "Synthetic HTTP Outsider", "NONE", OUTSIDER_TOKEN)
                    _, document_id, document_version_id, evidence_id = (
                        seed_global_source(db)
                    )
                    with db.transaction():
                        db.execute("SET LOCAL session_replication_role='replica'")
                        db.execute("""
                            UPDATE plm.doc_file_objects f
                               SET sha256=v.content_sha256
                              FROM plm.doc_document_versions v
                             WHERE v.document_version_id=%s
                               AND f.file_object_id=v.file_object_id
                        """, (document_version_id,))

                guard = Guard()
                routers = create_windows_capability_routers(
                    runtime, sessions=Sessions(),
                    origins=LoginOriginPolicy(["https://plm.example.test"]),
                    license_guard=guard,
                    audit=AuditService(SqlAlchemyAuditRepository()),
                    include_write=True, resolver=Keys(),
                )
                app = create_app(
                    capability_read_router=routers.reads,
                    capability_command_router=routers.commands,
                    capability_review_router=routers.review_submission,
                    global_capability_review_router=routers.global_review,
                )
                source = [{
                    "document_id": str(document_id),
                    "document_version_id": str(document_version_id),
                }]

                def baseline(client: TestClient, code: str) -> dict:
                    return _expect(client.post(
                        "/api/v1/global/capability-baselines",
                        headers=_headers(key=str(uuid.uuid4()), json=True),
                        json={"baseline_code": code, "name": code,
                              "description": "HTTP proof",
                              "source_documents": source},
                    ), 201)

                def version(client: TestClient, baseline_id: str,
                            etag: str, code: str) -> dict:
                    return _expect(client.post(
                        f"/api/v1/global/capability-baselines/{baseline_id}/versions",
                        headers=_headers(
                            key=str(uuid.uuid4()), etag=etag, json=True,
                        ),
                        json={"items": [{
                            "stable_item_id": str(uuid.uuid4()),
                            "capability_code": code + ".ITEM",
                            "domain_name": "PLM", "module_name": "Capability",
                            "feature_name": "HTTP", "name": "HTTP Item",
                            "description": "Real PostgreSQL HTTP proof",
                            "boundary": "GLOBAL only", "prerequisites": [],
                            "interface_refs": [], "document_refs": source,
                            "evidence_refs": [str(evidence_id)],
                            "item_state": "AVAILABLE",
                        }]},
                    ), 201)

                with TestClient(app, base_url="https://plm.example.test") as client:
                    first = baseline(client, "PLM.HTTP.A")
                    baseline_id = first["baseline_id"]
                    patched = _expect(client.patch(
                        f"/api/v1/global/capability-baselines/{baseline_id}",
                        headers=_headers(etag=first["etag"], json=True),
                        json={"name": "PLM HTTP A2"},
                    ), 200)
                    created = version(
                        client, baseline_id, patched["etag"], "PLM.HTTP.A",
                    )
                    version_id = created["baseline_version_id"]
                    _expect(client.get(
                        "/api/v1/global/capability-baselines?page_size=1",
                        headers=_headers(),
                    ), 200)
                    _expect(client.get(
                        f"/api/v1/global/capability-baselines/{baseline_id}",
                        headers=_headers(),
                    ), 200)
                    _expect(client.get(
                        f"/api/v1/global/capability-baselines/{baseline_id}/versions",
                        headers=_headers(),
                    ), 200)
                    _expect(client.get(
                        f"/api/v1/global/capability-baselines/{baseline_id}/versions/"
                        f"{version_id}", headers=_headers(),
                    ), 200)
                    items = _expect(client.get(
                        f"/api/v1/global/capability-baselines/{baseline_id}/versions/"
                        f"{version_id}/items", headers=_headers(),
                    ), 200)
                    assert len(items["items"]) == 1
                    _expect(client.post(
                        f"/api/v1/global/capability-baselines/{baseline_id}/versions/"
                        f"{version_id}:validate",
                        headers=_headers(key=str(uuid.uuid4())),
                    ), 200)
                    review_key = str(uuid.uuid4())
                    review_body = {
                        "reviewer_ids": [str(reviewer_two), str(reviewer_one)],
                        "policy_ref": "DEPLOYMENT_ALL_V1",
                        "due_at": None, "submission_note": None,
                    }
                    submitted = _expect(client.post(
                        f"/api/v1/global/capability-baselines/{baseline_id}/versions/"
                        f"{version_id}:submit-review",
                        headers=_headers(key=review_key, json=True), json=review_body,
                    ), 201)
                    replayed = _expect(client.post(
                        f"/api/v1/global/capability-baselines/{baseline_id}/versions/"
                        f"{version_id}:submit-review",
                        headers=_headers(key=review_key, json=True), json=review_body,
                    ), 201)
                    assert replayed["review_round_id"] == submitted["review_round_id"]
                    if GLOBAL_REVIEW_HTTP:
                        review_id = submitted["review_id"]
                        round_id = submitted["review_round_id"]
                        path = f"/api/v1/global/reviews/{review_id}"
                        decide_path = f"{path}/rounds/{round_id}:decide"
                        assert TestClient(create_app()).get(path).status_code == 404
                        read_only = create_windows_capability_routers(
                            runtime, sessions=Sessions(),
                            origins=LoginOriginPolicy(["https://plm.example.test"]),
                            license_guard=guard,
                            audit=AuditService(SqlAlchemyAuditRepository()),
                            include_write=False, resolver=Keys(),
                        )
                        assert read_only.global_review is None
                        detail = _expect(client.get(path, headers=_headers()), 200)
                        assert detail["review_round_id"] == round_id
                        assert detail["baseline_version_id"] == version_id
                        assert _expect(client.get(
                            path, headers=_headers(token=REVIEWER_ONE_TOKEN),
                        ), 200)["review_id"] == review_id
                        assert client.get(path, headers=_headers(
                            token=OUTSIDER_TOKEN)).status_code == 404
                        guard.enabled = False
                        assert client.get(path, headers=_headers()).status_code == 403
                        guard.enabled = True
                        body = {"decision": "APPROVE", "comment": None}
                        first_key = str(uuid.uuid4())
                        assert client.post(decide_path, headers=_headers(
                            key=str(uuid.uuid4()), json=True,
                            token=OUTSIDER_TOKEN,
                        ), json=body).status_code == 404
                        assert client.post(decide_path, headers={
                            **_headers(key=str(uuid.uuid4()), json=True,
                                       token=REVIEWER_ONE_TOKEN),
                            "x-csrf-token": "0" * 64,
                        }, json=body).status_code in (401, 403)
                        first = _expect(client.post(
                            decide_path, headers=_headers(
                                key=first_key, json=True,
                                token=REVIEWER_ONE_TOKEN,
                            ), json=body,
                        ), 200)
                        replay = _expect(client.post(
                            decide_path, headers=_headers(
                                key=first_key, json=True,
                                token=REVIEWER_ONE_TOKEN,
                            ), json=body,
                        ), 200)
                        assert replay == first
                        assert first["state"] == "IN_REVIEW"
                        second = _expect(client.post(
                            decide_path, headers=_headers(
                                key=str(uuid.uuid4()), json=True,
                                token=REVIEWER_TWO_TOKEN,
                            ), json=body,
                        ), 200)
                        assert second["state"] == "APPROVED"
                        assert _expect(client.get(path, headers=_headers()), 200)[
                            "state"] == "APPROVED"

                    second = baseline(client, "PLM.HTTP.B")
                    second_id = second["baseline_id"]
                    second_version = version(
                        client, second_id, second["etag"], "PLM.HTTP.B",
                    )
                    _expect(client.post(
                        f"/api/v1/global/capability-baselines/{second_id}/versions/"
                        f"{second_version['baseline_version_id']}:restrict",
                        headers=_headers(key=str(uuid.uuid4()), json=True),
                        json={"reason_code": "SECURITY_RESTRICTION"},
                    ), 200)
                    restricted_baseline = _expect(client.get(
                        f"/api/v1/global/capability-baselines/{second_id}",
                        headers=_headers(),
                    ), 200)
                    _expect(client.post(
                        f"/api/v1/global/capability-baselines/{second_id}:archive",
                        headers=_headers(
                            key=str(uuid.uuid4()),
                            etag=restricted_baseline["etag"],
                        ),
                    ), 200)

                with connect(name) as db:
                    states = db.execute("""
                        SELECT baseline_state, count(*)
                          FROM plm.cap_baselines GROUP BY baseline_state
                    """).fetchall()
                    versions = db.execute("""
                        SELECT version_state, count(*)
                          FROM plm.cap_baseline_versions GROUP BY version_state
                    """).fetchall()
                    assert dict(states) == {"ACTIVE": 1, "ARCHIVED": 1}
                    assert dict(versions) == ({"APPROVED": 1, "RESTRICTED": 1}
                                              if GLOBAL_REVIEW_HTTP else
                                              {"IN_REVIEW": 1, "RESTRICTED": 1})
                    assert db.execute(
                        "SELECT count(*) FROM plm.rvw_reviews WHERE scope='GLOBAL'"
                    ).fetchone()[0] == 1
                command.check(cfg)
                print(
                    ("CAP_02_A05_P04_P03_A03_P02_WINDOWS_HTTP_PG_PASS: "
                     "explicit write-mode GLOBAL Review, assigned reviewers, "
                     "replay and approved pointer verified with synthetic trust"
                     if GLOBAL_REVIEW_HTTP else
                     "CAP_01_A05_A07_WINDOWS_COMPOSITION_PASS: twelve frozen "
                     "operations, real PostgreSQL, HTTP, replay and state rollback "
                     "boundaries verified with isolated synthetic cursor keys")
                )
            finally:
                runtime.dispose()
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(name)
            ))


if __name__ == "__main__":
    main()
