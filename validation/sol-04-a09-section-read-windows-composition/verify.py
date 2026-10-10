"""Win11 explicit Section GET composition over real ASGI/PG fixture."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_outline import (
    ProductionSolutionOutlineStartupError, create_windows_section_read_router,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_read_http_fixture",
    ROOT / "validation/sol-04-a08-section-read-http-pg/verify.py")
assert SPEC and SPEC.loader
http_fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(http_fixture)


def on_created(**kwargs) -> int:
    try:
        create_windows_section_read_router(
            runtime=None, sessions=None, origins=None, license_guard=None)
    except ProductionSolutionOutlineStartupError:
        pass
    else:
        raise AssertionError("missing read trust dependencies accepted")
    return http_fixture.on_created(
        **kwargs, create_router_factory=create_windows_section_read_router)


if __name__ == "__main__":
    http_fixture.prior.fixture.main(on_created=on_created)
    print("SOL_04_A09_SECTION_READ_WINDOWS_COMPOSITION_PASS: explicit Windows "
          "read Owner/router, real Session/ASGI/PG, denied trust and closed POST")
