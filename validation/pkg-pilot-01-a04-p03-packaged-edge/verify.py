"""Run a real Edge read-only UI precheck against the fixed synthetic package."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation/wfl-01-a08-p07-packaged-https/verify.py"
spec = spec_from_file_location("_pkg_pilot_a04_p03_base", SOURCE)
assert spec is not None and spec.loader is not None
base = module_from_spec(spec)
spec.loader.exec_module(base)


def browser_probe(**kwargs) -> None:
    base.licensed_probe(**kwargs)
    command = ["node", str(Path(__file__).with_name("run-edge-browser.mjs")),
               kwargs["origin"]]
    checked = subprocess.run(command, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=120,
                             check=False)
    if checked.returncode or "PKG_PILOT_01_A04_P03_EDGE_PASS" not in checked.stdout:
        raise RuntimeError("packaged Edge UI precheck failed: " +
                           (checked.stdout + checked.stderr)[-12000:])
    print(checked.stdout, flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    temp = Path(__import__("tempfile").gettempdir())
    pristine = temp / ("plm-install-rehearsal-" + uuid.uuid4().hex[:12])
    target = temp / ("plm-install-rehearsal-" + uuid.uuid4().hex[:12])
    result = base.smoke(args.candidate, args.stage, pristine, target,
                        args.expected_sha256,
                        synthetic_license_document_factory=base.synthetic_document,
                        licensed_https_probe=browser_probe)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
