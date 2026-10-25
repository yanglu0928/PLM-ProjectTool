"""Real PG18 admission over one-shot Provider Job and loopback TLS."""

from __future__ import annotations

import runpy
from pathlib import Path


source = Path(__file__).parents[1] / "ai-01-a05-p04-a05-one-shot-worker" / "verify.py"
runpy.run_path(str(source))["main"](persistent_secret_audit=True, maintenance_loop=True)
