"""Win11 explicit SolutionSection write composition using real ASGI/PG fixture."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_outline import (
    ProductionSolutionOutlineStartupError, create_windows_section_create_router,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_create_http_fixture",
    ROOT / "validation/sol-04-a04-section-create-http-pg/verify.py")
assert SPEC and SPEC.loader
http_fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(http_fixture)


def on_created(**kwargs) -> int:
    try:
        create_windows_section_create_router(
            runtime=None, sessions=None, origins=None,
            license_guard=None, audit=None)
    except ProductionSolutionOutlineStartupError:
        pass
    else:
        raise AssertionError("missing trust dependencies accepted")
    return http_fixture.on_created(
        **kwargs, create_router_factory=create_windows_section_create_router)


if __name__ == "__main__":
    http_fixture.fixture.main(on_created=on_created)
    print("SOL_04_A05_SECTION_WINDOWS_COMPOSITION_PASS: explicit Windows "
          "write Owner/router, real Session/ASGI/PG, denied trust and closed default")
