"""Packaged synthetic Handover DRAFT version Edge/HTTPS/PG proof."""

from __future__ import annotations

import argparse
import httpx
import json
import runpy
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))
project = runpy.run_path(str(ROOT / "validation/evd-05-a03-p03-project-packaged/verify.py"))
capability = runpy.run_path(str(ROOT / "validation/cap-02-a05-p03-p02-a03-packaged-multi-item/verify.py"))


def _negative_body(document_id: uuid.UUID, version_id: uuid.UUID,
                   baseline_id: uuid.UUID, baseline_version_id: uuid.UUID,
                   evidence_id: uuid.UUID) -> dict:
    return {"source_documents": [{"document_id": str(document_id),
                                   "document_version_id": str(version_id)}],
            "capability_baseline_id": str(baseline_id),
            "capability_baseline_version_id": str(baseline_version_id),
            "items": [{"analysis_item_id": str(uuid.uuid4()), "item_type": "GAP",
                       "title": "Synthetic forbidden duplicate", "statement": "Negative test only",
                       "impact": "No business impact", "severity": "LOW", "priority": "LOW",
                       "recommendation": None, "confirmation_question": None,
                       "required_input_spec": {}, "source_missing": False,
                       "evidence_refs": [str(evidence_id)], "capability_refs": [], "options": []}],
            "ai_task_refs": []}


def browser_probe(**context) -> None:
    # One disposable PROJECT fixture creates a fixed DocumentVersion, Analysis and ELIGIBLE Evidence.
    project["browser_probe"](**context)
    origin = context["origin"]
    # The project fixture leaves its original HTTP client signed in as the synthetic outsider.
    # Reuse the same disposable database/project but create the approved GLOBAL baseline through
    # its real browser/review chain, skipping only the already executed GLOBAL
    # Document/Capability seed; the GLOBAL Evidence and approvals still run.
    global_evidence = capability["evidence"]
    global_evidence["capability"].browser_probe = lambda **_kwargs: None
    with context["connect_db"]() as db:
        promoted = db.execute(
            "UPDATE plm.auth_users SET deployment_role='DEPLOYMENT_ADMIN' "
            "WHERE user_id=%s AND state='ENABLED' RETURNING user_id",
            (context["user_id"],),
        ).fetchone()
        assert promoted == (context["user_id"],), promoted
    first_global = subprocess.run(
        ["node", str(Path(global_evidence["capability"].__file__).with_name("run-capability-edge.mjs")),
         origin], capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, check=False,
    )
    if first_global.returncode or "CAP_02_A03_A04_P02_PACKAGED_EDGE_PASS" not in first_global.stdout:
        raise AssertionError("packaged first GLOBAL fixed source failed: "
                             + first_global.stdout[-5000:] + first_global.stderr[-5000:])
    print(first_global.stdout.strip(), flush=True)
    with httpx.Client(base_url=origin, verify=False, trust_env=False, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"origin": origin},
                           json={"username": "Synthetic Packaged User",
                                 "password": "synthetic-packaged-login-password"})
        assert login.status_code == 200, (login.status_code, login.text)
        capability["probe"](**(context | {"client": admin, "login": login}))
    with context["connect_db"]() as db:
        row = db.execute(
            "SELECT p.project_id,a.handover_analysis_id,a.source_set_ref,a.lock_version "
            "FROM plm.hnd_analyses a JOIN plm.prj_projects p ON p.project_id=a.project_id "
            "WHERE p.project_code='WHTTPS' AND a.analysis_purpose='Synthetic Handover Analysis'"
        ).fetchone()
        assert row is not None and row[3] == 0, row
        project_id, analysis_id, source_ref, _ = row
        source = db.execute(
            "SELECT e.evidence_id,e.document_id,e.document_version_id "
            "FROM plm.evd_evidence_records e WHERE e.project_id=%s "
            "AND e.display_label='Synthetic Project Handover Evidence' "
            "AND e.eligibility_state='ELIGIBLE'", (project_id,),
        ).fetchone()
        assert source is not None
        evidence_id, document_id, document_version_id = source
        approved = db.execute(
            "SELECT b.baseline_id,b.current_approved_version_ref "
            "FROM plm.cap_baselines b WHERE b.baseline_code='CAP.SYNTHETIC.MULTI.PKG'"
        ).fetchone()
        assert approved is not None and approved[1] is not None
        baseline_id, baseline_version_id = approved
    edge = subprocess.run(
        ["node", str(Path(__file__).with_name("run-handover-version-edge.mjs")),
         origin, str(project_id), str(analysis_id)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=240, check=False,
    )
    if edge.returncode or "HND_05_A02_P04_PACKAGED_EDGE_PASS" not in edge.stdout:
        raise AssertionError("packaged Handover Version Edge failed: "
                             + edge.stdout[-6500:] + edge.stderr[-6500:])
    print(edge.stdout.strip(), flush=True)
    with context["connect_db"]() as db:
        versions = db.execute(
            "SELECT handover_analysis_version_id,version_no,version_state,source_set_ref,"
            "capability_baseline_id,capability_baseline_version_ref,declared_item_count "
            "FROM plm.hnd_analysis_versions WHERE handover_analysis_id=%s",
            (analysis_id,),
        ).fetchall()
        assert len(versions) == 1, versions
        version_id, version_no, state, fixed_source, cap_id, cap_version, count = versions[0]
        assert (version_no, state, fixed_source, cap_id, cap_version, count) == (
            1, "DRAFT", source_ref, baseline_id, baseline_version_id, 2)
        items = db.execute(
            "SELECT analysis_item_row_id,ordinal,item_type,title,source_missing,"
            "confirmation_question,required_input_spec,item_state "
            "FROM plm.hnd_analysis_items WHERE handover_analysis_version_id=%s ORDER BY ordinal",
            (version_id,),
        ).fetchall()
        assert len(items) == 2 and [(item[1], item[2], item[4], item[7]) for item in items] == [
            (0, "GAP", False, "CANDIDATE"), (1, "NEED_CONFIRM", False, "CANDIDATE")], items
        assert items[0][3] == "Synthetic grounded interface gap"
        assert items[1][3] == "Synthetic mapping decision needed"
        assert items[1][5] == "Which mapping approach should be used?"
        assert items[1][6] == {"fields": [{"name": "Old and new code mapping",
                                           "format": "Two-column code table",
                                           "example": "OLD-001 -> NEW-001", "required": True}]}
        refs = db.execute(
            "SELECT i.ordinal,r.evidence_id FROM plm.hnd_analysis_items i "
            "JOIN plm.hnd_item_evidence_refs r ON r.analysis_item_row_id=i.analysis_item_row_id "
            "WHERE i.handover_analysis_version_id=%s ORDER BY i.ordinal", (version_id,),
        ).fetchall()
        assert refs == [(0, evidence_id), (1, evidence_id)], refs
        fixed_refs = db.execute(
            "SELECT document_id,document_version_id FROM plm.hnd_analysis_source_document_refs "
            "WHERE handover_analysis_version_id=%s", (version_id,),
        ).fetchall()
        assert fixed_refs == [(document_id, document_version_id)], fixed_refs
        options = db.execute(
            "SELECT option_code,label FROM plm.hnd_item_options WHERE analysis_item_row_id=%s "
            "ORDER BY ordinal", (items[1][0],),
        ).fetchall()
        assert options == [("A", "Retain old code with mapping"),
                           ("B", "Switch to new code")], options
        audit = db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='HND_VERSION_CREATED' "
            "AND target_object_id=%s", (version_id,),
        ).fetchone()[0]
        receipt = db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_HND_VERSION_CREATE' AND result_ref_id=%s "
            "AND project_id=%s AND state='COMPLETED'", (version_id, project_id),
        ).fetchone()[0]
        root = db.execute(
            "SELECT lock_version,current_approved_version_ref FROM plm.hnd_analyses "
            "WHERE handover_analysis_id=%s", (analysis_id,),
        ).fetchone()
        assert audit == receipt == 1 and root == (1, None), (audit, receipt, root)
    body = _negative_body(document_id, document_version_id, baseline_id,
                          baseline_version_id, evidence_id)
    path = f"/api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions"
    with httpx.Client(base_url=origin, verify=False, trust_env=False, timeout=20) as anonymous:
        refused = anonymous.post(path, headers={"origin": origin,
                                                 "if-match": '"v1"',
                                                 "idempotency-key": str(uuid.uuid4())}, json=body)
        assert refused.status_code in (401, 403), (refused.status_code, refused.text)
    with httpx.Client(base_url=origin, verify=False, trust_env=False, timeout=20) as outsider:
        login = outsider.post("/api/v1/auth/login", headers={"origin": origin},
                             json={"username": "Synthetic Foreign Source Manager",
                                   "password": "synthetic-packaged-login-password"})
        assert login.status_code == 200, (login.status_code, login.text)
        refused = outsider.post(path, headers={"origin": origin,
                                               "x-csrf-token": login.json()["data"]["csrf_token"],
                                               "if-match": '"v1"',
                                               "idempotency-key": str(uuid.uuid4())}, json=body)
        assert refused.status_code == 404, (refused.status_code, refused.text)
    with httpx.Client(base_url=origin, verify=False, trust_env=False, timeout=20) as admin:
        login = admin.post("/api/v1/auth/login", headers={"origin": origin},
                           json={"username": "Synthetic Packaged User",
                                 "password": "synthetic-packaged-login-password"})
        assert login.status_code == 200, (login.status_code, login.text)
        wrong = body | {"source_documents": [{"document_id": str(document_id),
                                              "document_version_id": str(uuid.uuid4())}]}
        refused = admin.post(path, headers={"origin": origin,
                                            "x-csrf-token": login.json()["data"]["csrf_token"],
                                            "if-match": '"v1"',
                                            "idempotency-key": str(uuid.uuid4())}, json=wrong)
        assert refused.status_code == 422, (refused.status_code, refused.text)
    with context["connect_db"]() as db:
        count = db.execute(
            "SELECT count(*) FROM plm.hnd_analysis_versions WHERE handover_analysis_id=%s",
            (analysis_id,),
        ).fetchone()[0]
        assert count == 1, count
    print("HND_05_A02_P04_PACKAGED_PG_PASS: DRAFT two cards, fixed source, Audit, one receipt", flush=True)
    print("HND_05_A02_P04_PACKAGED_NEGATIVE_PASS: anonymous, unassigned, wrong fixed source", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage", "pristine", "target"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    result = project["base"].base.base.smoke(
        args.candidate, args.stage, args.pristine, args.target, args.expected_sha256,
        synthetic_license_document_factory=project["base"].base.base.synthetic_document,
        licensed_https_probe=browser_probe,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
