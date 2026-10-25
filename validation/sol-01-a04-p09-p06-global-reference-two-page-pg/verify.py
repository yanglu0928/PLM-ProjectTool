"""Two real GLOBAL References and signed HTTP keyset pages in isolated PG18."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_reference import create_windows_global_reference_list_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.global_reference_list_cursor import GlobalReferenceListCursorCodec
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec
from plm_assistant.modules.solution.application.create_reference_solution import CreateReferenceSolution, ReferenceCreateService
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_sources_fixture",
    ROOT / "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


class DeniedLicense:
    def require_valid(self, *, trace_id):
        raise RuntimeLicenseError("LICENSE_OPERATION_DENIED")


def check(*, runtime, request, sources, audit, license_guard, qualified,
          confirmed, port, **_unused) -> None:
    creates = ReferenceCreateService(
        unit_of_work=runtime.unit_of_work,
        global_access=SqlAlchemyLicenseImportAccess(),
        project_access=SqlAlchemyProjectWriteAccess(),
        project_authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        license_guard=license_guard, sources=sources,
        repository=SqlAlchemyReferenceCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
    )
    first = creates.create(CreateReferenceSolution(
        request, fixture.CSRF, "Synthetic GLOBAL Reference Alpha", "global-page-alpha-01"))
    second = creates.create(CreateReferenceSolution(
        request, fixture.CSRF, "Synthetic GLOBAL Reference Beta", "global-page-beta-01"))
    identities = sorted((first.reference_solution_id, second.reference_solution_id))
    assert first.deidentification_confirmation_id == confirmed.confirmation_id
    assert second.deidentification_confirmation_id == confirmed.confirmation_id
    assert first.reference_solution_id != second.reference_solution_id
    assert qualified.deidentification_confirmation_id == confirmed.confirmation_id
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        rows = db.execute("SELECT reference_solution_id FROM plm.sol_reference_solutions "
                          "WHERE scope='GLOBAL' AND project_id IS NULL "
                          "ORDER BY reference_solution_id").fetchall()
        assert [item[0] for item in rows] == identities
        assert db.execute("SELECT count(*) FROM plm.aud_events "
                          "WHERE action='SOL_REFERENCE_CREATED'").fetchone()[0] == 2
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    origins = LoginOriginPolicy(["https://plm.example.test"])
    codec = GlobalReferenceListCursorCodec(b"g" * 32)
    router = create_windows_global_reference_list_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, cursors=codec)
    headers = {"cookie": "plm_session=" + fixture.TOKEN.hex(),
               "origin": "https://plm.example.test"}
    path = "/api/v1/global/reference-solutions"
    with TestClient(create_app(global_reference_list_router=router),
                    base_url="https://plm.example.test") as client:
        first_page = client.get(path, params={"page_size": "1"}, headers=headers)
        assert first_page.status_code == 200, first_page.text
        one = first_page.json()["data"]
        assert [item["reference_solution_id"] for item in one["items"]] == [str(identities[0])]
        assert one["has_more"] and one["next_cursor"]
        assert one["items"][0]["scope"] == "GLOBAL" and one["items"][0]["project_id"] is None
        assert "deidentification_confirmation_id" not in one["items"][0]
        second_page = client.get(path, params={"page_size": "1", "cursor": one["next_cursor"]},
                                 headers=headers)
        assert second_page.status_code == 200, second_page.text
        two = second_page.json()["data"]
        assert [item["reference_solution_id"] for item in two["items"]] == [str(identities[1])]
        assert not two["has_more"] and two["next_cursor"] is None
        project_cursor = ReferenceListCursorCodec(b"g" * 32).encode(
            session_token=fixture.TOKEN, project_id=uuid.uuid4(), page_size=1,
            reference_solution_id=identities[0])
        for params in (
                {"page_size": "1", "cursor": project_cursor},
                {"page_size": "2", "cursor": one["next_cursor"]},
                {"page_size": "1", "cursor": "A" + one["next_cursor"][1:]},
        ):
            assert client.get(path, params=params, headers=headers).status_code == 400
        assert client.get(path, headers={"origin": headers["origin"]}).status_code == 401
        assert client.get(path, headers={**headers, "origin": "https://evil.test"}).status_code == 403
    denied = create_windows_global_reference_list_router(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=DeniedLicense(), cursors=codec)
    with TestClient(create_app(global_reference_list_router=denied),
                    base_url="https://plm.example.test") as client:
        assert client.get(path, headers=headers).status_code == 403


def main() -> None:
    fixture.main(on_qualified=check)
    print("SOL_01_A04_P09_P06_GLOBAL_REFERENCE_TWO_PAGE_PG_PASS")


if __name__ == "__main__":
    main()
