"""Run owned Win11 Edge/PG SOL-06 detail acceptance on disposable data."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_create_browser_for_detail",
    ROOT / "validation/sol-06-a09-p06-p03-structured-spec-browser/serve.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


if __name__ == "__main__":
    prior.prior.prior.prior.main(on_created=lambda **kwargs: prior.prior.prior.on_created(
        **kwargs, on_http=lambda **browser: prior.prior.on_browser(
            **browser, spec_mode=True, detail_mode=True)))
