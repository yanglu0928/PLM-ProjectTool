"""Windows explicit GLOBAL Reference eligibility factory over disposable PG18."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_reference import (
    ProductionSolutionReferenceStartupError,
    create_windows_global_reference_eligibility_router,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_reference_eligibility_http_pg",
    ROOT / "validation/sol-01-a16-p04-reference-eligibility-http/verify_global.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def on_qualified(**facts) -> None:
    try:
        create_windows_global_reference_eligibility_router(
            runtime=facts["runtime"], sessions=None, origins=None,
            license_guard=facts["license_guard"], audit=facts["audit"],
            documents=facts["documents"], downloads=facts["downloads"],
            parse_results=facts["parse_results"])
    except ProductionSolutionReferenceStartupError:
        pass
    else:
        raise AssertionError("GLOBAL eligibility accepted missing security ports")
    fixture.on_qualified(
        **facts, router_factory=create_windows_global_reference_eligibility_router)


if __name__ == "__main__":
    fixture.fixture.main(on_qualified=on_qualified)
    print("SOL_01_A16_P05_REFERENCE_ELIGIBILITY_GLOBAL_WINDOWS_PG_PASS")
