"""Real Win11 composition of OutlineVersion POST with explicit storage roots."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_outline_version_create_router,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_version_http_pg_fixture",
    ROOT / "validation/sol-03-a04-p03-p03-p05-a02-outline-version-http-pg/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)

_roots: tuple[Path, Path] | None = None
_expiry_context: tuple[int, object] | None = None
_global_client_calls = 0


def _set_fixture_expiry(port: int, confirmation_id: object,
                        *, restore_to=None) -> None:
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        with db.transaction():
            # Synthetic-only fixture mutation: production Owner never bypasses
            # the confirmation append-only guard.
            db.execute("SET LOCAL session_replication_role='replica'")
            if restore_to is None:
                db.execute(
                    "UPDATE plm.sol_reference_deidentification_confirmations "
                    "SET expires_at=confirmed_at+interval '1 microsecond' "
                    "WHERE confirmation_id=%s", (confirmation_id,))
            else:
                db.execute(
                    "UPDATE plm.sol_reference_deidentification_confirmations "
                    "SET expires_at=%s WHERE confirmation_id=%s",
                    (restore_to, confirmation_id))


def windows_client(*, runtime, audit, license_guard, references):
    global _global_client_calls
    del references  # The factory must reconstruct every current source port.
    if _roots is None:
        raise AssertionError("verified source roots not installed")
    if _expiry_context is not None:
        _global_client_calls += 1
        if _global_client_calls == 2:
            _set_fixture_expiry(*_expiry_context)
    sessions = prior.SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=prior.SqlAlchemySessionRepository(),
        issue_access=object(), audit=audit)
    router = create_windows_outline_version_create_router(
        runtime=runtime, sessions=sessions,
        origins=prior.LoginOriginPolicy(["https://plm.example.test"]),
        license_guard=license_guard, audit=audit,
        document_storage_root=_roots[0],
        parse_result_storage_root=_roots[1])
    return TestClient(
        create_app(solution_outline_version_create_router=router),
        base_url="https://plm.example.test")


def project_created(**kwargs):
    global _roots
    scratch = kwargs["scratch"]
    _roots = (scratch / "private-documents", scratch / "private-results")
    return prior.project_created(**kwargs)


def global_qualified(**kwargs):
    global _roots, _expiry_context, _global_client_calls
    # These are synthetic fixture storages. Product composition only receives
    # explicit validated roots; it never introspects another service's fields.
    _roots = (kwargs["downloads"]._storage._root,
              kwargs["parse_results"]._storage._root)
    confirmed = kwargs["confirmed"]
    _expiry_context = (kwargs["port"], confirmed.confirmation_id)
    _global_client_calls = 0
    try:
        return prior.global_qualified(**kwargs)
    finally:
        _set_fixture_expiry(kwargs["port"], confirmed.confirmation_id,
                            restore_to=confirmed.expires_at)
        _expiry_context = None


if __name__ == "__main__":
    prior.client = windows_client
    prior.fixture.main(on_created=project_created)
    prior.composition.global_fixture.main(on_qualified=global_qualified)
    print("SOL_03_A04_P03_P03_P05_A03_OUTLINE_VERSION_WINDOWS_PASS: "
          "factory-rebuilt PROJECT/GLOBAL source ports, real ASGI/PG, "
          "failure-closed trust roots and default 404")
