"""Windows explicit composition of GLOBAL attestation over isolated PG."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from plm_assistant.entrypoints.windows_solution_reference import (
    create_windows_reference_deidentification_router,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_attestation_http_pg",
    ROOT / "validation/sol-01-a04-p08-p03-p04-attestation-http-pg/verify.py")
assert SPEC and SPEC.loader
base = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(base)


def on_preview(**kwargs):
    base.on_preview(**kwargs,
                    router_factory=create_windows_reference_deidentification_router)


def main() -> None:
    base.fixture.main(on_preview=on_preview)
    print("SOL_01_A04_P08_P03_P05_GLOBAL_ATTESTATION_WINDOWS_PG_PASS: "
          "explicit Windows owner composition and HTTP/PG proof")


if __name__ == "__main__":
    main()
