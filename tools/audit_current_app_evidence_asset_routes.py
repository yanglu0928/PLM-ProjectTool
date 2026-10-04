"""Bind the fixed candidate's Evidence UI bytes to backend route source bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from package_windows_unified_candidate import digest_path, zip_members


CURRENT_SHA256 = "eb2494be5de85b64a7ac64ce02112ed52454d0423d2a7e8406f120a126e14ed7"
PREFIX = "payload/frontend/dist/"
BACKEND = "payload/runtime/packages/plm_assistant/"
FRONTEND_MARKERS = (
    "/admin/evidence", "/projects/:projectId/evidence",
    ":set-eligibility", ":lookup-eligibility-operation",
    "plm.evidence.global.eligibility.pending", "plm.evidence.eligibility.pending",
)
ROUTES = {
    "modules/evidence/api/set_eligibility.py": (
        '/api/v1/global/evidence/{evidence_id}:set-eligibility',
        '/api/v1/projects/{project_id}/evidence/{evidence_id}:set-eligibility',
    ),
    "modules/evidence/api/lookup_eligibility_operation.py": (
        '/api/v1/global/evidence/{evidence_id}:lookup-eligibility-operation',
        '/api/v1/projects/{project_id}/evidence/{evidence_id}:lookup-eligibility-operation',
    ),
    "entrypoints/production_login.py": (
        'create_evidence_eligibility_router(',
        'create_evidence_eligibility_operation_lookup_router(',
        'evidence_eligibility_router=evidence_eligibility_router',
        'evidence_eligibility_operation_lookup_router=evidence_eligibility_operation_lookup_router',
    ),
    "entrypoints/api.py": (
        'app.include_router(evidence_eligibility_router)',
        'app.include_router(evidence_eligibility_operation_lookup_router)',
    ),
}


def audit(candidate: Path, frontend_dist: Path, repo_root: Path,
          expected_sha256: str = CURRENT_SHA256) -> dict[str, object]:
    if digest_path(candidate) != expected_sha256:
        raise ValueError("current candidate SHA-256 differs")
    if not frontend_dist.is_dir() or frontend_dist.is_symlink():
        raise ValueError("fresh frontend dist required")
    with zipfile.ZipFile(candidate) as archive:
        names = set(zip_members(archive))
        manifest = json.loads(archive.read("manifest.json"))
        assets = manifest.get("frontend_sha256")
        if (manifest.get("kind") != "WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE" or
                manifest.get("release_eligible") is not False or
                not isinstance(assets, dict) or len(assets) != 3 or
                set(assets) != {name for name in names if name.startswith(PREFIX)}):
            raise ValueError("current frontend manifest differs")
        for name, expected in assets.items():
            local = frontend_dist / name.removeprefix(PREFIX)
            if (not name.startswith(PREFIX) or not local.is_file() or local.is_symlink() or
                    hashlib.sha256(local.read_bytes()).hexdigest() != expected or
                    hashlib.sha256(archive.read(name)).hexdigest() != expected):
                raise ValueError("rebuilt frontend differs from candidate")
        js = [name for name in assets if name.endswith(".js")]
        if len(js) != 1 or any(marker.encode() not in archive.read(js[0])
                               for marker in FRONTEND_MARKERS):
            raise ValueError("compiled Evidence UI marker missing")
        for relative, markers in ROUTES.items():
            name = BACKEND + relative
            local = repo_root / "apps/backend/src/plm_assistant" / relative
            if name not in names or not local.is_file() or local.read_bytes() != archive.read(name):
                raise ValueError("backend route source differs from candidate: " + relative)
            content = archive.read(name).decode("utf-8")
            if any(marker not in content for marker in markers):
                raise ValueError("backend Evidence route marker missing: " + relative)
    return {"status": "CURRENT_APP_EVIDENCE_ASSET_ROUTE_CONTRACT_PASS",
            "candidate_sha256": expected_sha256,
            "frontend_asset_count": len(assets),
            "compiled_evidence_marker_count": len(FRONTEND_MARKERS),
            "backend_route_source_count": len(ROUTES),
            "real_browser_verified": False, "release_eligible": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--frontend-dist", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.candidate, args.frontend_dist, args.repo_root),
                     ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
