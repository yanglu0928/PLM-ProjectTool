"""Win11 explicit SolutionOutline GET composition over isolated ASGI/PG."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_outline import create_windows_outline_read_router


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "outline_read_http_fixture",
    ROOT / "validation/sol-02-a06-p02-outline-read-http-pg/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def on_created(**kwargs) -> int:
    return prior.on_created(
        **kwargs, create_router_factory=create_windows_outline_read_router)


if __name__ == "__main__":
    prior.prior.prior.main(on_created=on_created)
    print("SOL_02_A06_P03_OUTLINE_WINDOWS_COMPOSITION_PASS: explicit Windows "
          "GET owner/router, real Session/ASGI/PG and closed default")
