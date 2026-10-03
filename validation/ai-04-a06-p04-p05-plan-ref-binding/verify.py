"""Run the shared Windows composition proof including downstream PlanRef binding."""

from __future__ import annotations

import importlib.util
from pathlib import Path


path = (
    Path(__file__).resolve().parents[1]
    / "ai-04-a06-p04-p04-a06-windows-composition"
    / "verify.py"
)
spec = importlib.util.spec_from_file_location("windows_plan_ref_binding", path)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


if __name__ == "__main__":
    module.main()
