"""Synthetic packaged Edge/HTTPS/PG proof for a two-source Capability editor."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path

from plm_assistant.modules.capability.domain.source_collection import canonical_source_collection_ref

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "apps" / "backend" / "src"))
from smoke_current_app_packaged_https import smoke  # noqa: E402

import runpy  # noqa: E402

evidence = runpy.run_path(str(ROOT / "validation" / "evd-05-a02-packaged-edge" / "verify.py"))
review = runpy.run_path(str(ROOT / "validation" /
    "cap-02-a05-p04-p03-a04-p02-p05-p02-packaged-review" / "verify.py"))


def probe(**context) -> None:
    evidence["browser_probe"](**context)
    client, connect_db, origin = context["client"], context["connect_db"], context["origin"]
    csrf = context["login"].json()["data"]["csrf_token"]
    with connect_db() as db:
        first = db.execute(
            "SELECT d.document_id,v.document_version_id FROM plm.doc_documents d "
            "JOIN plm.doc_document_versions v ON v.document_id=d.document_id "
            "WHERE d.scope='GLOBAL' AND d.title='Synthetic Capability Source'",
        ).fetchone()
        assert first is not None
        first_evidence = db.execute(
            "SELECT evidence_id FROM plm.evd_evidence_records "
            "WHERE display_label='Synthetic Whole Document Evidence'",
        ).fetchone()[0]
    path = f"/api/v1/global/evidence/{first_evidence}"
    candidate = review["expect"](client.get(path), 200)
    review["expect"](client.post(
        path + ":set-eligibility",
        headers=review["headers"](origin, csrf, key=str(uuid.uuid4()), etag=candidate["etag"]),
        json={"eligibility_state": "ELIGIBLE", "reason": "Synthetic packaged proof only"},
    ), 200)
    content = b"Synthetic independent GLOBAL standard capability source two.\n"
    base = "/api/v1/global/document-uploads"
    intent = review["expect"](client.post(
        base, headers=review["headers"](origin, csrf, key=str(uuid.uuid4())),
        json={"purpose": "CAPABILITY_SOURCE", "category": "STANDARD_CAPABILITY",
              "title": "Synthetic Multi Source Two", "display_name": "synthetic-multi-two.txt",
              "size_hint_bytes": len(content), "mime_hint": "text/plain"},
    ), 201)
    upload_id = intent["upload_id"]
    received = review["expect"](client.put(
        f"{base}/{upload_id}/content", content=content,
        headers={"origin": origin, "x-csrf-token": csrf,
                 "x-upload-token": intent["upload_token"],
                 "x-content-sha256": hashlib.sha256(content).hexdigest(),
                 "content-type": "application/octet-stream"},
    ), 200)
    assert received["sha256"] == hashlib.sha256(content).hexdigest()
    committed = review["expect"](client.post(
        f"{base}/{upload_id}:commit",
        headers=review["headers"](origin, csrf, key=str(uuid.uuid4())),
    ), 201)
    second_doc = uuid.UUID(committed["document_id"])
    second_version = uuid.UUID(committed["document_version_id"])
    fixed_second = review["expect"](client.get(
        f"/api/v1/global/documents/{second_doc}/versions/{second_version}"), 200)
    assert fixed_second["availability_state"] == "AVAILABLE"
    second_candidate = review["expect"](client.post(
        "/api/v1/global/evidence",
        headers=review["headers"](origin, csrf, key=str(uuid.uuid4())),
        json={"document_id": str(second_doc), "document_version_id": str(second_version),
              "locator": {"locator_type": "DOCUMENT"},
              "display_label": "Synthetic Multi Evidence Two"},
    ), 201)
    second_evidence = uuid.UUID(second_candidate["evidence_id"])
    current_second = review["expect"](client.get(f"/api/v1/global/evidence/{second_evidence}"), 200)
    review["expect"](client.post(
        f"/api/v1/global/evidence/{second_evidence}:set-eligibility",
        headers=review["headers"](origin, csrf, key=str(uuid.uuid4()), etag=current_second["etag"]),
        json={"eligibility_state": "ELIGIBLE", "reason": "Synthetic packaged proof only"},
    ), 200)
    source = [{"document_id": str(doc), "document_version_id": str(version)}
              for doc, version in (first, (second_doc, second_version))]
    baseline = review["expect"](client.post(
        "/api/v1/global/capability-baselines",
        headers=review["headers"](origin, csrf, key=str(uuid.uuid4())),
        json={"baseline_code": "CAP.SYNTHETIC.MULTI.PKG", "name": "Synthetic Multi Baseline",
              "description": "Disposable two-source browser proof", "source_documents": source},
    ), 201)
    baseline_id = baseline["baseline_id"]
    assert baseline["source_collection_ref"] == canonical_source_collection_ref(
        (first[1], second_version))
    browser = subprocess.run(
        ["node", str(Path(__file__).with_name("run-multi-item-edge.mjs")),
         origin, baseline_id, str(first[0]), str(second_doc)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180, check=False,
    )
    if browser.returncode:
        raise AssertionError("packaged multi-item Edge failed: "
                             + browser.stdout[-4500:] + browser.stderr[-4500:])
    assert "CAP_02_P03_A03_PACKAGED_MULTI_ITEM_EDGE_PASS" in browser.stdout
    print(browser.stdout.strip(), flush=True)
    with connect_db() as db:
        rows = db.execute(
            "SELECT v.baseline_version_id,v.version_state,i.capability_code,i.item_state,"
            "r.document_id,r.document_version_id,e.evidence_id "
            "FROM plm.cap_baseline_versions v JOIN plm.cap_items i "
            "ON i.baseline_version_id=v.baseline_version_id "
            "JOIN plm.cap_item_document_refs r ON r.capability_item_row_id=i.capability_item_row_id "
            "JOIN plm.cap_item_evidence_refs e ON e.capability_item_row_id=i.capability_item_row_id "
            "WHERE v.baseline_id=%s ORDER BY i.ordinal", (baseline_id,),
        ).fetchall()
        assert len(rows) == 2, rows
        version_id = rows[0][0]
        assert all(row[0] == version_id and row[1] == "DRAFT" for row in rows), rows
        assert [(row[2], row[3], row[4], row[5], row[6]) for row in rows] == [
            ("CAP.MULTI.ONE", "AVAILABLE", first[0], first[1], first_evidence),
            ("CAP.MULTI.TWO", "DEPRECATED", second_doc, second_version, second_evidence),
        ], rows
        audit = db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='CAP_VERSION_CREATED' "
            "AND target_object_id=%s", (version_id,),
        ).fetchone()[0]
        assert audit == 1, audit
    path = f"/api/v1/global/capability-baselines/{baseline_id}/versions/{version_id}"
    items = review["expect"](client.get(path + "/items"), 200)
    assert [item["state"] for item in items["items"]] == ["AVAILABLE", "DEPRECATED"]
    report = review["expect"](client.post(
        path + ":validate", headers=review["headers"](origin, csrf, key=str(uuid.uuid4()))), 200)
    assert report["valid"] is True and report["item_count"] == 2, report
    reviewer_one = review["seed_user"](connect_db, "Synthetic Multi Reviewer One")
    reviewer_two = review["seed_user"](connect_db, "Synthetic Multi Reviewer Two")
    submitted = review["expect"](client.post(
        path + ":submit-review", headers=review["headers"](origin, csrf, key=str(uuid.uuid4())),
        json={"reviewer_ids": [str(reviewer_one), str(reviewer_two)],
              "policy_ref": "DEPLOYMENT_ALL_V1", "due_at": None, "submission_note": None},
    ), 201)
    review_path = f"/api/v1/global/reviews/{submitted['review_id']}"
    for display in ("Synthetic Multi Reviewer One", "Synthetic Multi Reviewer Two"):
        reviewer, reviewer_csrf = review["login_user"](origin, display)
        try:
            fixed = review["expect"](reviewer.get(review_path + "/fixed-items"), 200)
            assert [item["state"] for item in fixed["items"]] == ["AVAILABLE", "DEPRECATED"]
            decision = review["expect"](reviewer.post(
                review_path + f"/rounds/{submitted['review_round_id']}:decide",
                headers=review["headers"](origin, reviewer_csrf, key=str(uuid.uuid4())),
                json={"decision": "APPROVE", "comment": None},
            ), 200)
        finally:
            reviewer.close()
    assert decision["state"] == "APPROVED"
    current = review["expect"](client.get(f"/api/v1/global/capability-baselines/{baseline_id}"), 200)
    assert current["current_approved_version_ref"] == str(version_id)
    with connect_db() as db:
        decisions = db.execute(
            "SELECT reviewer_id,decision FROM plm.rvw_review_decisions WHERE review_id=%s",
            (submitted["review_id"],),
        ).fetchall()
        audit_count = db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='REVIEW_DECISION_RECORDED' "
            "AND actor_id IN (%s,%s)", (reviewer_one, reviewer_two),
        ).fetchone()[0]
        receipt_count = db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_CAP_VERSION_CREATE' AND result_ref_id=%s "
            "AND project_id IS NULL AND state='COMPLETED'",
            (version_id,),
        ).fetchone()[0]
        assert set(decisions) == {(reviewer_one, "APPROVE"), (reviewer_two, "APPROVE")}
        assert audit_count == 2 and receipt_count == 1, (audit_count, receipt_count)
    print("CAP_02_P03_A03_PACKAGED_MULTI_ITEM_PG_PASS: two sources, DRAFT, DEPRECATED, Review", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage", "pristine", "target"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(
        args.candidate, args.stage, args.pristine, args.target, args.expected_sha256,
        synthetic_license_document_factory=evidence["workflow"].synthetic_document,
        licensed_https_probe=probe,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
