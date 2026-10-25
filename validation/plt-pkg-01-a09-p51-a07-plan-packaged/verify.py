"""Packaged synthetic Plan identity Edge/HTTPS/PG verification for P51-A07."""

from __future__ import annotations

import json
import os
import re
import runpy
import subprocess
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))
base = runpy.run_path(str(ROOT / "validation/plt-pkg-01-a09-p51-a05-prototype-packaged/verify.py"))


def plan_probe(**context) -> None:
    env = os.environ.copy()
    env["PLM_PLAN_TEST_MANAGER"] = "Synthetic Packaged User"
    env["PLM_PLAN_TEST_PASSWORD"] = "synthetic-packaged-login-password"
    edge = subprocess.run(
        ["node", str(ROOT / "validation/plt-pkg-01-a09-p51-a07-plan-packaged/run-edge-browser.mjs"),
         context["origin"], str(context["project"])],
        cwd=ROOT, env=env, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300, check=False,
    )
    if edge.returncode or "P51_A07_PACKAGED_PLAN_EDGE_PASS" not in edge.stdout:
        raise AssertionError("packaged Plan Edge failed: " + edge.stdout[-12000:])
    print(edge.stdout.strip(), flush=True)
    match = re.search(r"P51_A07_RESULT (\{[^\r\n]+\})", edge.stdout)
    assert match, "packaged Plan Edge result identity missing"
    plan_id = uuid.UUID(json.loads(match.group(1))["plan"])
    with context["connect_db"]() as db:
        row = db.execute(
            "SELECT plan_state,name,current_approved_version_ref,created_by FROM plm.pln_plans "
            "WHERE plan_id=%s AND project_id=%s", (plan_id, context["project"]),
        ).fetchone()
        assert row == ("ACTIVE", "P51-A07 Synthetic Implementation Plan", None, context["user_id"]), row
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts WHERE project_id=%s "
            "AND operation='V1_PLAN_CREATE' AND state='COMPLETED' AND result_ref_id=%s",
            (context["project"], plan_id),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='PLAN_CREATED' "
            "AND target_project_id=%s AND target_object_id=%s AND outcome='SUCCESS'",
            (context["project"], plan_id),
        ).fetchone()[0] == 1
    print("P51_A07_PACKAGED_PLAN_PG_PASS: ACTIVE identity; one Audit/receipt; no approved version",
          flush=True)


def main() -> int:
    base_main = base["main"]
    namespace = base_main.__globals__
    original = namespace["prototype_probe"]
    ran = False

    def prototype_then_plan(**context):
        nonlocal ran
        original(**context)
        plan_probe(**context)
        ran = True

    namespace["prototype_probe"] = prototype_then_plan
    result = base_main()
    if not ran:
        raise RuntimeError("P51-A07 Plan probe callback did not execute")
    return result


if __name__ == "__main__":
    sys.exit(main())
