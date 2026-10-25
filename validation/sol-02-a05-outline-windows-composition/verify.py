"""Win11 explicit SolutionOutline composition over the isolated HTTP/PG fixture."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_outline import create_windows_outline_create_router


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_create_http_fixture",
    ROOT / "validation/sol-02-a04-outline-create-http-pg/verify.py")
assert SPEC and SPEC.loader
http_fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(http_fixture)


def on_created(**kwargs) -> int:
    return http_fixture.on_created(
        **kwargs, create_router_factory=create_windows_outline_create_router)


if __name__ == "__main__":
    http_fixture.prior.main(on_created=on_created)
    print("SOL_02_A05_OUTLINE_WINDOWS_COMPOSITION_PASS: explicit Windows "
          "Owner/router, real Session/ASGI/PG, denied trust and closed default")
