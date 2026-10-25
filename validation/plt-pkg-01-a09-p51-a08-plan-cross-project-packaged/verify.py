"""Packaged cross-project Plan GET non-enumeration proof for P51-A08."""

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
plan = runpy.run_path(
    str(ROOT / "validation/plt-pkg-01-a09-p51-a07-plan-packaged/verify.py"))


def cross_project_probe(**context) -> None:
    env = os.environ.copy()
    env["PLM_PLAN_TEST_MANAGER"] = "Synthetic Packaged User"
    env["PLM_PLAN_TEST_PASSWORD"] = "synthetic-packaged-login-password"
    foreign_project = uuid.uuid4()
    edge = subprocess.run(
        ["node", str(ROOT / "validation/plt-pkg-01-a09-p51-a07-plan-packaged/run-edge-browser.mjs"),
         context["origin"], str(context["project"]), str(foreign_project)],
        cwd=ROOT, env=env, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300, check=False,
    )
    if edge.returncode or "P51_A08_CROSS_PROJECT_PLAN_READ_404_PASS" not in edge.stdout:
        raise AssertionError("packaged cross-project Plan read failed: " + edge.stdout[-12000:])
    print(edge.stdout.strip(), flush=True)
    match = re.search(r"P51_A07_RESULT (\{[^\r\n]+\})", edge.stdout)
    assert match, "P51-A08 Plan identity result missing"
    plan_id = uuid.UUID(json.loads(match.group(1))["plan"])
    with context["connect_db"]() as db:
        row = db.execute(
            "SELECT plan_state,name,current_approved_version_ref,created_by FROM plm.pln_plans "
            "WHERE plan_id=%s AND project_id=%s", (plan_id, context["project"]),
        ).fetchone()
        assert row == ("ACTIVE", "P51-A07 Synthetic Implementation Plan", None,
                       context["user_id"]), row
        assert db.execute(
            "SELECT count(*) FROM plm.pln_plans WHERE plan_id=%s", (plan_id,),
        ).fetchone()[0] == 1
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
    print("P51_A08_CROSS_PROJECT_PLAN_PG_PASS: one source identity; no foreign disclosure/write",
          flush=True)


def main() -> int:
    namespace = plan["main"].__globals__
    original = namespace["plan_probe"]
    ran = False

    def plan_then_cross_project(**context):
        nonlocal ran
        original(**context)
        cross_project_probe(**context)
        ran = True

    namespace["plan_probe"] = plan_then_cross_project
    result = plan["main"]()
    if not ran:
        raise RuntimeError("P51-A08 cross-project probe callback did not execute")
    return result


if __name__ == "__main__":
    sys.exit(main())
