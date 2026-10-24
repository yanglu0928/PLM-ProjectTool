"""Windows explicit GLOBAL Reference revise factory over disposable PG18."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_reference import (
    create_windows_global_reference_revise_router,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_reference_revise_http_pg",
    ROOT / "validation/sol-01-a08-reference-revise-http-pg/verify_global.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def on_qualified(**facts) -> None:
    fixture.on_qualified(
        **facts, router_factory=create_windows_global_reference_revise_router)


if __name__ == "__main__":
    fixture.fixture.main(on_qualified=on_qualified)
    print("SOL_01_A09_REFERENCE_REVISE_GLOBAL_WINDOWS_PG_PASS")
