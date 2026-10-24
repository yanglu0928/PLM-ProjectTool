"""Owned Win11 Edge/Uvicorn/PG proof for SectionVersion create."""

from __future__ import annotations

import importlib.util
import socket
import subprocess
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import psycopg
import uvicorn

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_section_version_create_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_owner_fixture_for_edge",
    ROOT / "validation/sol-05-a02-p11-section-version-create-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_edge(*, port, runtime, audit, license_guard, project, other_project,
            token, csrf, evidence, document_version, documents, downloads,
            parse_results, section, requirement, requirement_version, **_unused):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        reservation.listen(128)
        http_port = reservation.getsockname()[1]
        origin = f"http://127.0.0.1:{http_port}"
        sessions = SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemySessionRepository(),
            issue_access=object(), audit=audit)
        router = create_windows_section_version_create_router(
            runtime=runtime, sessions=sessions, origins=LoginOriginPolicy([origin]),
            license_guard=license_guard, audit=audit, documents=documents,
            downloads=downloads, parse_results=parse_results)
        app = create_app(solution_section_version_create_router=router)
        server = uvicorn.Server(uvicorn.Config(
            app, log_level="critical", access_log=False,
            proxy_headers=False, lifespan="on", timeout_graceful_shutdown=5))
        worker = Thread(target=lambda: server.run(sockets=[reservation]), daemon=False)
        worker.start()
        try:
            deadline = monotonic() + 15
            while not server.started:
                if not worker.is_alive() or monotonic() > deadline:
                    raise RuntimeError("Owned SectionVersion Uvicorn did not start")
                sleep(.05)
            result = subprocess.run(
                ["node", str(Path(__file__).with_name("run-edge-browser.mjs")),
                 origin, str(project), str(other_project), str(section),
                 str(document_version), str(requirement),
                 str(requirement_version), str(evidence), token.hex(), csrf.hex()],
                check=False, timeout=120, capture_output=True, text=True,
                encoding="utf-8")
            if result.returncode:
                raise RuntimeError("SectionVersion Edge proof failed: "
                                   f"{result.stdout[-3000:]} {result.stderr[-3000:]}")
            print(result.stdout.strip(), flush=True)
        finally:
            server.should_exit = True
            worker.join(timeout=15)
            if worker.is_alive():
                raise RuntimeError("Owned SectionVersion Uvicorn did not stop")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        for table, predicate in (
            ("sol_section_versions", "solution_section_id=%s"),
            ("sol_section_version_create_results", "solution_section_id=%s"),
            ("plt_idempotency_receipts", "operation='V1_SOL_SECTION_VERSION_CREATE'"),
            ("aud_events", "action='SOL_SECTION_VERSION_CREATED'"),
        ):
            args = (section,) if "%s" in predicate else ()
            assert db.execute(
                f"SELECT count(*) FROM plm.{table} WHERE {predicate}", args
            ).fetchone()[0] == 6, table
    print("SOL_05_A02_P12_P02_EDGE_NETWORK_PG_PASS: owned Edge/Uvicorn/PG, "
          "one committed version, first response, receipt and audit")


if __name__ == "__main__":
    prior.prior.main(on_created=lambda **kwargs: prior.on_created(
        **kwargs, on_http=on_edge))
