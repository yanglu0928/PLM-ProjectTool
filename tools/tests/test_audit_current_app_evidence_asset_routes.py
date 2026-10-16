from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_current_app_evidence_asset_routes import (  # noqa: E402
    BACKEND, FRONTEND_MARKERS, PREFIX, ROUTES, audit,
)


class CandidateEvidenceAssetContractTests(unittest.TestCase):
    def test_exact_bundle_and_backend_bytes_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dist = root / "dist"
            (dist / "assets").mkdir(parents=True)
            files = {"index.html": b"<script src='/assets/index-test.js'></script>",
                     "assets/index-test.js": "|".join(FRONTEND_MARKERS).encode(),
                     "assets/index-test.css": b"body{}"}
            for relative, data in files.items():
                local = dist / relative
                local.parent.mkdir(parents=True, exist_ok=True)
                local.write_bytes(data)
            candidate = root / "candidate.zip"
            with zipfile.ZipFile(candidate, "w") as archive:
                for relative, data in files.items():
                    archive.writestr(PREFIX + relative, data)
                for relative, markers in ROUTES.items():
                    data = "\n".join(markers).encode()
                    source = root / "apps/backend/src/plm_assistant" / relative
                    source.parent.mkdir(parents=True, exist_ok=True)
                    source.write_bytes(data)
                    archive.writestr(BACKEND + relative, data)
                archive.writestr("manifest.json", json.dumps({
                    "kind": "WINDOWS11_CURRENT_APP_NON_RELEASE_CANDIDATE",
                    "release_eligible": False,
                    "frontend_sha256": {PREFIX + relative: hashlib.sha256(data).hexdigest()
                                        for relative, data in files.items()},
                }))
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            result = audit(candidate, dist, root, expected_sha256=digest)
            self.assertEqual(result["status"], "CURRENT_APP_EVIDENCE_ASSET_ROUTE_CONTRACT_PASS")
            (dist / "assets/index-test.js").write_bytes(b"stale")
            with self.assertRaisesRegex(ValueError, "rebuilt frontend differs"):
                audit(candidate, dist, root, expected_sha256=digest)


if __name__ == "__main__":
    unittest.main()
