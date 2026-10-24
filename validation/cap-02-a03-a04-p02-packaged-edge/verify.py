"""Verify GLOBAL capability upload and baseline identity in the fixed Windows package.

All accounts, files, License material and database state are disposable synthetic data.
The result is an internal-Pilot proof, never formal trust or release clearance.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from plm_assistant.modules.capability.domain.source_collection import (
    canonical_source_collection_ref,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from smoke_current_app_packaged_https import smoke  # noqa: E402

SOURCE = ROOT / "validation" / "wfl-01-a08-p07-packaged-https" / "verify.py"
spec = spec_from_file_location("_workflow_packaged_capability_fixture", SOURCE)
assert spec and spec.loader
workflow = module_from_spec(spec)
spec.loader.exec_module(workflow)


def browser_probe(**kwargs) -> None:
    workflow.licensed_probe(**kwargs)
    with kwargs["connect_db"]() as db:
        changed = db.execute(
            "UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN' "
            "WHERE user_id=%s AND state='ENABLED' RETURNING user_id",
            (kwargs["user_id"],),
        ).fetchone()
        assert changed and changed[0] == kwargs["user_id"]
    script = Path(__file__).with_name("run-capability-edge.mjs")
    result = subprocess.run(
        ["node", str(script), kwargs["origin"]],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=150, check=False,
    )
    if result.returncode:
        raise AssertionError(
            f"packaged Edge capability flow failed: {result.stdout}\n{result.stderr}"
        )
    assert "CAP_02_A03_A04_P02_PACKAGED_EDGE_PASS" in result.stdout, result.stdout
    print(result.stdout, flush=True)
    with kwargs["connect_db"]() as db:
        source = db.execute(
            "SELECT d.document_id,v.document_version_id,v.availability_state "
            "FROM plm.doc_documents d JOIN plm.doc_document_versions v "
            "ON v.document_id=d.document_id "
            "WHERE d.scope='GLOBAL' AND d.document_category='STANDARD_CAPABILITY' "
            "AND d.title='Synthetic Capability Source'"
        ).fetchall()
        assert len(source) == 1 and source[0][2] == "AVAILABLE", source
        baseline = db.execute(
            "SELECT baseline_id,baseline_state,source_collection_ref "
            "FROM plm.cap_baselines WHERE baseline_code='CAP.SYNTHETIC.PKG'"
        ).fetchall()
        assert len(baseline) == 1 and baseline[0][1] == "ACTIVE", baseline
        assert baseline[0][2] == canonical_source_collection_ref((source[0][1],))
        for action in ("DOCUMENT_UPLOAD_CREATE", "DOCUMENT_UPLOAD_CONTENT_STAGED",
                       "DOCUMENT_UPLOAD_COMMIT", "CAP_BASELINE_CREATED"):
            count = db.execute(
                "SELECT count(*) FROM plm.aud_events WHERE action=%s AND actor_id=%s",
                (action, kwargs["user_id"]),
            ).fetchone()[0]
            assert count == 1, (action, count)
    print("Synthetic GLOBAL fixed Document and baseline identity / Audit PASS", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage", "pristine", "target"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(
        args.candidate, args.stage, args.pristine, args.target, args.expected_sha256,
        synthetic_license_document_factory=workflow.synthetic_document,
        licensed_https_probe=browser_probe,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
