"""Win11 Windows-factory OutlineVersion history over real dual-scope ASGI/PG."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    ProductionSolutionOutlineStartupError,
    create_windows_outline_version_read_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.solution.api.outline_version_list_cursor import OutlineVersionListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_history_http_for_windows",
    ROOT / "validation/sol-03-a05-a03-p03-outline-version-read-http-pg/verify.py")
assert SPEC and SPEC.loader
previous = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(previous)


def windows_client(*, runtime, audit, license_guard):
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(), issue_access=object(), audit=audit)
    router = create_windows_outline_version_read_router(
        runtime=runtime, sessions=sessions,
        origins=LoginOriginPolicy(["https://plm.example.test"]),
        license_guard=license_guard,
        cursors=OutlineVersionListCursorCodec(b"h" * 32))
    return TestClient(create_app(solution_outline_version_read_router=router),
                      base_url="https://plm.example.test")


def project_created(**kwargs):
    for cursors in (None, object()):
        try:
            create_windows_outline_version_read_router(
                runtime=kwargs["runtime"], sessions=object(), origins=object(),
                license_guard=kwargs["license_guard"], cursors=cursors)
        except ProductionSolutionOutlineStartupError:
            pass
        else:
            raise AssertionError("missing or wrong cursor family accepted")
    return previous.project_created(**kwargs)


if __name__ == "__main__":
    previous._client = windows_client
    previous.previous.previous.previous.fixture.main(on_created=project_created)
    previous.previous.previous.previous.composition.global_fixture.main(
        on_qualified=previous.global_qualified)
    print("SOL_03_A05_A03_P04_OUTLINE_VERSION_READ_WINDOWS_PG_PASS: "
          "Windows factory, real dual-scope ASGI/PG, dedicated cursor, refusals")
