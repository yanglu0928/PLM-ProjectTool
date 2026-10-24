"""Run owned Win11 Edge/PG SOL-06 CREATE page acceptance on disposable data."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol05_browser_for_sol06",
    ROOT / "validation/sol-05-a03-p06-p03-section-version-browser/serve.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


if __name__ == "__main__":
    prior.prior.prior.main(on_created=lambda **kwargs: prior.prior.on_created(
        **kwargs, on_http=lambda **browser: prior.on_browser(
            **browser, spec_mode=True)))
