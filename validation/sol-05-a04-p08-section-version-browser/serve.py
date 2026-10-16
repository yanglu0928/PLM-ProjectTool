"""Disposable Win11 Edge/PG proof of the real VALIDATE detail page."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_browser_fixture",
    ROOT / "validation/sol-05-a03-p06-p03-section-version-browser/serve.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


if __name__ == "__main__":
    prior.prior.prior.main(on_created=lambda **kwargs: prior.prior.on_created(
        **kwargs, on_http=lambda **source: prior.on_browser(
            **source, validation_mode=True)))
