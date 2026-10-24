"""Exercise a fixed non-release Workflow package through real Caddy HTTPS.

Only ephemeral synthetic signing material and disposable Windows 11 resources are used.
No customer License, private key, or production trust root is written to the package.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from smoke_current_app_packaged_https import smoke  # noqa: E402

from plm_assistant.modules.license.application.license_validation import (  # noqa: E402
    PRODUCT_CODE, machine_fingerprint_hash,
)
from plm_assistant.modules.license.infrastructure.packaged_product_key import (  # noqa: E402
    PRODUCT_KEY_REF,
)


SOURCE = (Path(__file__).resolve().parents[1] /
          "wfl-02-a01-p03-history-schema" / "verify.py")
spec = spec_from_file_location("_workflow_packaged_https_fixture", SOURCE)
fixture = module_from_spec(spec)
spec.loader.exec_module(fixture)


def synthetic_document(private, selected_mac: str) -> bytes:
    now = datetime.now(timezone.utc)
    payload = {
        "license_id": "synthetic-workflow-https", "customer": "synthetic-only",
        "machine_fingerprint": machine_fingerprint_hash(selected_mac).hex(),
        "valid_from": (now - timedelta(days=1)).isoformat(),
        "valid_to": (now + timedelta(days=1)).isoformat(),
        "issue_time": (now - timedelta(days=2)).isoformat(),
        "schema_version": "plm.license.v1",
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":")).encode("utf-8")
    return json.dumps({
        "algorithm": "Ed25519", "payload": payload,
        "signature": base64.b64encode(private.sign(canonical)).decode("ascii"),
    }, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def licensed_probe(*, client, connect_db, user_id, signed_document: bytes,
                   selected_mac: str, login, origin: str) -> None:
    payload = json.loads(signed_document)["payload"]
    fingerprint = machine_fingerprint_hash(selected_mac)
    entitlement = {
        "product_code": PRODUCT_CODE, "grant_scope": "FULL_BUNDLE",
        "valid_from": payload["valid_from"], "valid_to": payload["valid_to"],
    }
    with connect_db() as db, db.transaction():
        db.execute("INSERT INTO plm.lic_trusted_time_states DEFAULT VALUES")
        installation_id = db.execute(
            "INSERT INTO plm.lic_installations(public_key_ref,imported_by,import_trace_id) "
            "VALUES (%s,%s,%s) RETURNING license_installation_id",
            (PRODUCT_KEY_REF, user_id, uuid.uuid4()),
        ).fetchone()[0]
        digest = hashlib.sha256(signed_document).digest()
        db.execute(
            "INSERT INTO plm.lic_installation_documents"
            "(license_installation_id,signed_document,document_sha256) VALUES (%s,%s,%s)",
            (installation_id, signed_document, digest),
        )
        now = datetime.now(timezone.utc)
        event_id, validated_at = db.execute(
            "INSERT INTO plm.lic_validation_events"
            "(installation_id,validation_code,machine_fingerprint_hash,document_sha256,"
            "entitlement_snapshot,trace_id,validated_at) "
            "VALUES (%s,'VALID',%s,%s,%s::jsonb,%s,%s) "
            "RETURNING validation_event_id,validated_at",
            (installation_id, fingerprint, digest, json.dumps(entitlement), uuid.uuid4(), now),
        ).fetchone()
        db.execute(
            "UPDATE plm.lic_installations SET installation_state='ACTIVE',"
            "validation_result_ref=%s,lock_version=1 WHERE license_installation_id=%s",
            (event_id, installation_id),
        )
        db.execute(
            "INSERT INTO plm.lic_validation_states"
            "(active_license_ref,machine_fingerprint_hash,validation_code,"
            "entitlement_snapshot,validated_at,current_event_ref,updated_at) "
            "VALUES (%s,%s,'VALID',%s::jsonb,%s,%s,%s)",
            (installation_id, fingerprint, json.dumps(entitlement), validated_at, event_id, now),
        )
        project_id = fixture.insert(db, "prj_projects", dict(
            project_code="WHTTPS", project_code_normalized="whttps",
            name="Synthetic packaged Workflow HTTPS", created_by=user_id), "project_id")
        department_id = fixture.insert(db, "prj_departments", dict(
            project_id=project_id, department_code="D", department_code_normalized="d",
            name="Synthetic department"), "department_id")
        fixture.insert(db, "prj_project_members", dict(
            project_id=project_id, user_id=user_id, department_id=department_id,
            project_role="PROJECT_MANAGER"), "project_member_id")
        workflow_id = fixture.initialize(db, project_id, user_id)

    path = f"/api/v1/projects/{project_id}/workflow"
    initial = client.get(path)
    assert initial.status_code == 200, (initial.status_code, initial.text)
    assert initial.headers["etag"] == '"v0"'
    assert initial.json()["data"]["workflow_id"] == str(workflow_id)
    assert initial.json()["data"]["state"] == "NOT_STARTED"
    assert len(initial.json()["data"]["stages"]) == 6

    start_path = path + ":start"
    headers = {"origin": origin, "x-csrf-token": login.json()["data"]["csrf_token"],
               "idempotency-key": "workflow-packaged-https-key-123", "if-match": '"v0"'}
    missing_csrf = client.post(start_path, headers={key: value for key, value in headers.items()
                                                   if key != "x-csrf-token"})
    assert missing_csrf.status_code == 403, (missing_csrf.status_code, missing_csrf.text)
    first = client.post(start_path, headers=headers)
    assert first.status_code == 200, (first.status_code, first.text)
    assert first.headers["etag"] == '"v1"'
    assert first.json()["data"]["workflow_id"] == str(workflow_id)
    assert first.json()["data"]["current_stage"] == "HANDOVER"
    assert first.json()["data"]["state"] == "ACTIVE"
    replay = client.post(start_path, headers=headers)
    assert replay.status_code == 200, (replay.status_code, replay.text)
    assert replay.json()["data"] == first.json()["data"]
    conflict = client.post(start_path, headers=headers | {
        "idempotency-key": "workflow-packaged-https-key-456"})
    assert conflict.status_code == 409, (conflict.status_code, conflict.text)
    current = client.get(path)
    assert current.status_code == 200 and current.headers["etag"] == '"v1"'
    assert current.json()["data"]["state"] == "ACTIVE"
    with connect_db() as db:
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events "
            "WHERE action='WORKFLOW_STARTED' AND target_project_id=%s",
            (project_id,),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE operation='V1_WORKFLOW_START' AND project_id=%s",
            (project_id,),
        ).fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM plm.wfl_stage_transitions").fetchone()[0] == 0
    print("Packaged Workflow external HTTPS GET/START/replay/CSRF/conflict/Audit PASS",
          flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage", "pristine", "target"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(
        args.candidate, args.stage, args.pristine, args.target, args.expected_sha256,
        synthetic_license_document_factory=synthetic_document,
        licensed_https_probe=licensed_probe,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
