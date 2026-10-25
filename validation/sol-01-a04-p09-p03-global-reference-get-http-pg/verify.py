"""Windows GET composition against isolated PG GLOBAL Create fixture."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_reference import create_windows_global_reference_read_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_create_pg",
    ROOT / "validation/sol-01-a04-p08-p06-p03-global-reference-create-http-pg/verify.py")
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def check(*, runtime, license_guard, result, document, version, evidence,
          node_evidence, **_unused):
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(),
        audit=object())
    origins = LoginOriginPolicy(["https://plm.example.test"])
    router = create_windows_global_reference_read_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard)
    path = "/api/v1/global/reference-solutions/" + result["reference_solution_id"]
    headers = {"cookie": "plm_session=" + base.fixture.TOKEN.hex(),
               "origin": "https://plm.example.test"}
    with TestClient(create_app(global_reference_read_router=router),
                    base_url="https://plm.example.test") as client:
        response = client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["scope"] == "GLOBAL" and data["project_id"] is None
        assert data["reference_solution_id"] == result["reference_solution_id"]
        assert data["reference_version_id"] == result["reference_version_id"]
        assert data["document_version_ids"] == [str(version)]
        assert data["document_refs"] == [{"document_id": str(document),
                                         "document_version_id": str(version)}]
        assert data["evidence_ids"] == [str(evidence), str(node_evidence)]
        assert response.headers["etag"] == result["etag"]
        assert "deidentification_confirmation_id" not in data
        assert client.get(path, headers={"origin": headers["origin"]}).status_code == 401
        assert client.get(path, headers={**headers, "origin": "https://evil.test"}).status_code == 403
        assert client.get(path + "?project_id=" + str(uuid.uuid4()), headers=headers).status_code == 400
        assert client.get(path.rsplit("/", 1)[0] + "/" + str(uuid.uuid4()),
                          headers=headers).status_code == 404
    denied = create_windows_global_reference_read_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=DeniedLicense())
    with TestClient(create_app(global_reference_read_router=denied),
                    base_url="https://plm.example.test") as client:
        assert client.get(path, headers=headers).status_code == 403


def on_preview(**kwargs):
    base.on_preview(**kwargs, on_created=check, on_revoked=check)


def main():
    base.fixture.main(on_preview=on_preview)
    print("SOL_01_A04_P09_P03_GLOBAL_REFERENCE_GET_HTTP_PG_PASS")


if __name__ == "__main__":
    main()
