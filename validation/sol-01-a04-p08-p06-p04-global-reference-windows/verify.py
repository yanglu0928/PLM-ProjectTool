"""Windows composition over the isolated GLOBAL Reference Create PG fixture."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_reference import (
    create_windows_global_reference_create_router,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_reference_create_pg",
    ROOT / "validation/sol-01-a04-p08-p06-p03-global-reference-create-http-pg/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def on_preview(**kwargs) -> None:
    fixture.on_preview(
        **kwargs, create_router_factory=create_windows_global_reference_create_router)


def main() -> None:
    fixture.fixture.main(on_preview=on_preview)
    print("SOL_01_A04_P08_P06_P04_GLOBAL_REFERENCE_WINDOWS_PASS: explicit "
          "Windows composition with isolated PG18, real Session and private files")


if __name__ == "__main__":
    main()
