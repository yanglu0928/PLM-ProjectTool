"""Prove whole-document GLOBAL Evidence creation from a fixed non-release package.

Everything written is disposable synthetic data; no formal trust or release claim.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from smoke_current_app_packaged_https import smoke  # noqa: E402


def load(name: str, path: Path):
    spec = spec_from_file_location(name, path)
    assert spec and spec.loader
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


capability = load("_evd05_capability_fixture", ROOT / "validation" /
                  "cap-02-a03-a04-p02-packaged-edge" / "verify.py")
workflow = capability.workflow


def browser_probe(**kwargs) -> None:
    capability.browser_probe(**kwargs)
    script = Path(__file__).with_name("run-global-evidence-edge.mjs")
    result = subprocess.run(
        ["node", str(script), kwargs["origin"]], capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=150, check=False,
    )
    if result.returncode:
        raise AssertionError(
            f"packaged Edge GLOBAL Evidence flow failed: {result.stdout}\n{result.stderr}"
        )
    assert "EVD_05_A02_PACKAGED_EDGE_POSITIVE_PASS" in result.stdout, result.stdout
    print(result.stdout, flush=True)
    with kwargs["connect_db"]() as db:
        rows = db.execute(
            "SELECT e.evidence_id,e.document_id,e.document_version_id,e.locator_payload,"
            "e.content_fingerprint,e.eligibility_state,e.eligibility_reason,"
            "v.content_sha256 "
            "FROM plm.evd_evidence_records e JOIN plm.doc_document_versions v "
            "ON v.document_version_id=e.document_version_id "
            "WHERE e.scope='GLOBAL' AND e.project_id IS NULL "
            "AND e.display_label='Synthetic Whole Document Evidence'"
        ).fetchall()
        assert len(rows) == 1, rows
        evidence_id, document_id, version_id, locator, fingerprint, state, reason, source_hash = rows[0]
        assert locator == {"locator_type": "DOCUMENT"} and fingerprint == source_hash
        assert state == "CANDIDATE" and reason is None
        document = db.execute(
            "SELECT d.document_id,v.document_version_id FROM plm.doc_documents d "
            "JOIN plm.doc_document_versions v ON v.document_id=d.document_id "
            "WHERE d.scope='GLOBAL' AND d.document_category='STANDARD_CAPABILITY' "
            "AND d.title='Synthetic Capability Source'"
        ).fetchall()
        assert document == [(document_id, version_id)], document
        audit = db.execute(
            "SELECT count(*) FROM plm.aud_events "
            "WHERE action='EVIDENCE_CREATED' AND actor_id=%s AND target_object_id=%s",
            (kwargs["user_id"], evidence_id),
        ).fetchone()[0]
        receipt = db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_EVIDENCE_CREATE' AND project_id IS NULL",
        ).fetchone()[0]
        assert audit == 1 and receipt == 1, (audit, receipt)
    print("Synthetic GLOBAL Evidence CANDIDATE / fixed source / Audit / receipt PASS", flush=True)


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
