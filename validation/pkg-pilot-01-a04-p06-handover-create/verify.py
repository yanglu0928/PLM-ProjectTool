"""Prove packaged Handover create through real Edge and isolated synthetic PG."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "validation/pkg-pilot-01-a04-p03-packaged-edge/verify.py"
spec = spec_from_file_location("_pkg_pilot_a04_p06_base", SOURCE)
assert spec is not None and spec.loader is not None
base = module_from_spec(spec)
spec.loader.exec_module(base)

TITLE = "Synthetic Handover Source"
PURPOSE = "Synthetic Handover Analysis"


def browser_probe(**kwargs) -> None:
    base.base.licensed_probe(**kwargs)
    command = ["node", str(Path(__file__).with_name("run-handover-create-edge.mjs")),
               kwargs["origin"]]
    checked = subprocess.run(command, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=150,
                             check=False)
    if checked.returncode or "PKG_PILOT_01_A04_P06_HANDOVER_EDGE_PASS" not in checked.stdout:
        raise RuntimeError("packaged Handover create Edge proof failed: " +
                           (checked.stdout + checked.stderr)[-12000:])
    with kwargs["connect_db"]() as db:
        project = db.execute("SELECT project_id FROM plm.prj_projects "
                             "WHERE project_code='WHTTPS'").fetchone()
        assert project is not None
        project_id = project[0]
        document = db.execute(
            "SELECT document_id,latest_version_ref FROM plm.doc_documents "
            "WHERE project_id=%s AND title=%s AND document_state='ACTIVE'",
            (project_id, TITLE),
        ).fetchall()
        assert len(document) == 1 and document[0][1] is not None, document
        doc_id, version_id = document[0]
        assert db.execute(
            "SELECT availability_state FROM plm.doc_document_versions "
            "WHERE document_id=%s AND document_version_id=%s",
            (doc_id, version_id),
        ).fetchone() == ("AVAILABLE",)
        analyses = db.execute(
            "SELECT handover_analysis_id,source_set_ref,created_by,analysis_state "
            "FROM plm.hnd_analyses WHERE project_id=%s AND analysis_purpose=%s",
            (project_id, PURPOSE),
        ).fetchall()
        assert len(analyses) == 1 and analyses[0][2] == kwargs["user_id"] \
            and analyses[0][3] == "ACTIVE", analyses
        analysis_id = analyses[0][0]
        assert analyses[0][1].startswith("sha256:") and len(analyses[0][1]) == 71
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='HND_ANALYSIS_CREATED' "
            "AND target_project_id=%s AND target_object_id=%s",
            (project_id, analysis_id),
        ).fetchone()[0] == 1
        assert db.execute(
            "SELECT count(*) FROM plm.plt_idempotency_receipts "
            "WHERE actor_id=%s AND project_id=%s AND operation='V1_HND_ANALYSIS_CREATE' "
            "AND result_ref_id=%s AND state='COMPLETED'",
            (kwargs["user_id"], project_id, analysis_id),
        ).fetchone()[0] == 1
    print(checked.stdout, flush=True)
    print("Packaged document fixed version/Handover Analysis/Audit/receipt PG PASS", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "stage"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    temp = Path(__import__("tempfile").gettempdir())
    pristine = temp / ("plm-install-rehearsal-" + uuid.uuid4().hex[:12])
    target = temp / ("plm-install-rehearsal-" + uuid.uuid4().hex[:12])
    result = base.base.smoke(args.candidate, args.stage, pristine, target,
                             args.expected_sha256,
                             synthetic_license_document_factory=base.base.synthetic_document,
                             licensed_https_probe=browser_probe)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
