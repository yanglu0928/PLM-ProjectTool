"""Win11 Edge/PG SOL-06 structured-spec validation page acceptance."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_detail_browser_for_validation",
    ROOT / "validation/sol-06-a10-p05-structured-spec-detail-browser/serve.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


if __name__ == "__main__":
    prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs: prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **browser: prior.prior.prior.on_browser(
                **browser, spec_mode=True, detail_mode=True,
                spec_validation_mode=True)))
