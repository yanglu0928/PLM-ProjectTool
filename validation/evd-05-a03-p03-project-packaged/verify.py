"""Packaged synthetic PROJECT fixed-document Evidence Edge/HTTPS/PG proof."""

from __future__ import annotations

import argparse
import httpx
import json
import subprocess
import sys
import uuid
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation/pkg-pilot-01-a04-p06-handover-create/verify.py"
spec = spec_from_file_location("_evd_a03_handover_fixture", SOURCE)
assert spec is not None and spec.loader is not None
base = module_from_spec(spec)
spec.loader.exec_module(base)


def browser_probe(**context) -> None:
    # Existing packaged path creates a synthetic PROJECT fixed DocumentVersion by UI.
    base.browser_probe(**context)
    with context["connect_db"]() as db:
        project = db.execute(
            "SELECT project_id FROM plm.prj_projects WHERE project_code='WHTTPS'"
        ).fetchone()
        assert project is not None
        project_id = project[0]
    checked = subprocess.run(
        ["node", str(Path(__file__).with_name("run-project-evidence-edge.mjs")),
         context["origin"], str(project_id)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, check=False,
    )
    if checked.returncode or "EVD_05_A03_P03_PACKAGED_EDGE_PASS" not in checked.stdout:
        raise AssertionError("packaged PROJECT Evidence Edge failed: "
                             + checked.stdout[-6000:] + checked.stderr[-6000:])
    print(checked.stdout.strip(), flush=True)
    with context["connect_db"]() as db:
        rows = db.execute(
            "SELECT e.evidence_id,e.document_id,e.document_version_id,e.locator_payload,"
            "e.content_fingerprint,e.eligibility_state,e.eligibility_reason,"
            "v.content_sha256 FROM plm.evd_evidence_records e "
            "JOIN plm.doc_document_versions v ON v.document_version_id=e.document_version_id "
            "WHERE e.scope='PROJECT' AND e.project_id=%s "
            "AND e.display_label='Synthetic Project Handover Evidence'",
            (project_id,),
        ).fetchall()
        assert len(rows) == 1, rows
        evidence_id, document_id, version_id, locator, fingerprint, state, reason, source_hash = rows[0]
        assert locator == {"locator_type": "DOCUMENT"} and fingerprint == source_hash
        assert state == "ELIGIBLE" and reason == "Synthetic isolated source checked against fixed document only"
        doc = db.execute(
            "SELECT d.document_id,v.document_version_id FROM plm.doc_documents d "
            "JOIN plm.doc_document_versions v ON v.document_id=d.document_id "
            "WHERE d.project_id=%s AND d.title='Synthetic Handover Source'",
            (project_id,),
        ).fetchall()
        assert doc == [(document_id, version_id)], doc
        audit = db.execute(
            "SELECT action,count(*) FROM plm.aud_events WHERE target_project_id=%s "
            "AND target_object_id=%s GROUP BY action", (project_id, evidence_id),
        ).fetchall()
        assert dict(audit).get("EVIDENCE_CREATED") == 1, audit
        assert dict(audit).get("EVIDENCE_ELIGIBILITY_SET") == 1, audit
        receipts = db.execute(
            "SELECT operation,count(*) FROM plm.plt_idempotency_receipts "
            "WHERE project_id=%s AND result_ref_id=%s AND state='COMPLETED' "
            "GROUP BY operation", (project_id, evidence_id),
        ).fetchall()
        assert dict(receipts).get("V1_EVIDENCE_CREATE") == 1, receipts
        assert dict(receipts).get("V1_EVIDENCE_SET_ELIGIBILITY") == 1, receipts
        foreign = db.execute(
            "SELECT project_id FROM plm.prj_projects WHERE project_code='HNDNEG'"
        ).fetchone()
        assert foreign is not None
        foreign_project = foreign[0]
    body = {"document_id": str(document_id), "document_version_id": str(version_id),
            "locator": {"locator_type": "DOCUMENT"},
            "display_label": "Synthetic forbidden cross-project source"}
    with httpx.Client(base_url=context["origin"], verify=False,
                      trust_env=False, timeout=15) as anonymous:
        refused = anonymous.post(f"/api/v1/projects/{project_id}/evidence",
                                 headers={"origin": context["origin"],
                                          "idempotency-key": str(uuid.uuid4())}, json=body)
        assert refused.status_code in (401, 403), (refused.status_code, refused.text)
    with httpx.Client(base_url=context["origin"], verify=False,
                      trust_env=False, timeout=15) as outsider:
        login = outsider.post("/api/v1/auth/login", headers={"origin": context["origin"]},
                             json={"username": "Synthetic Foreign Source Manager",
                                   "password": "synthetic-packaged-login-password"})
        assert login.status_code == 200, (login.status_code, login.text)
        headers = {"origin": context["origin"],
                   "x-csrf-token": login.json()["data"]["csrf_token"],
                   "idempotency-key": str(uuid.uuid4())}
        refused = outsider.post(f"/api/v1/projects/{project_id}/evidence",
                                headers=headers, json=body)
        assert refused.status_code == 404, (refused.status_code, refused.text)
        headers["idempotency-key"] = str(uuid.uuid4())
        refused = outsider.post(f"/api/v1/projects/{foreign_project}/evidence",
                                headers=headers, json=body)
        assert refused.status_code in (404, 422), (refused.status_code, refused.text)
    with context["connect_db"]() as db:
        count = db.execute(
            "SELECT count(*) FROM plm.evd_evidence_records WHERE scope='PROJECT' "
            "AND project_id IN (%s,%s)", (project_id, foreign_project),
        ).fetchone()[0]
        assert count == 1, count
    print("EVD_05_A03_P03_PACKAGED_PG_PASS: fixed PROJECT source, ELIGIBLE, Audit, receipts", flush=True)
    print("EVD_05_A03_P03_PACKAGED_NEGATIVE_PASS: anonymous, unassigned, foreign source", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage", "pristine", "target"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    result = base.base.base.smoke(
        args.candidate, args.stage, args.pristine, args.target, args.expected_sha256,
        synthetic_license_document_factory=base.base.base.synthetic_document,
        licensed_https_probe=browser_probe,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
