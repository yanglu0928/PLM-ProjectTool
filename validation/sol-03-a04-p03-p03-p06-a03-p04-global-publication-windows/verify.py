"""Windows explicit-write GLOBAL publication factory over disposable PG18."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_reference import (
    ProductionSolutionReferenceStartupError,
    create_windows_global_reference_publication_router,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_publication_http_pg_fixture",
    ROOT / "validation/sol-03-a04-p03-p03-p06-a03-p03-global-publication-http/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def on_qualified(**facts) -> None:
    try:
        create_windows_global_reference_publication_router(
            runtime=facts["runtime"], sessions=None, origins=None,
            license_guard=facts["license_guard"], audit=facts["audit"],
            documents=facts["documents"], downloads=facts["downloads"],
            parse_results=facts["parse_results"])
    except ProductionSolutionReferenceStartupError:
        pass
    else:
        raise AssertionError("GLOBAL publication accepted missing security ports")
    fixture.on_qualified(
        **facts, router_factory=create_windows_global_reference_publication_router)


if __name__ == "__main__":
    fixture.fixture.main(on_qualified=on_qualified)
    print("SOL_03_A04_P03_P03_P06_A03_P04_GLOBAL_PUBLICATION_WINDOWS_PG_PASS")
