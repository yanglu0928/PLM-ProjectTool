from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from augment_windows_unified_ocr_notices import augment  # noqa: E402


class UnifiedNoticeAugmentTests(unittest.TestCase):
    def test_equal_content_files_keep_distinct_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-notice-augment-unit-") as temp:
            parent = Path(temp).resolve(strict=True)
            source = parent / "source.zip"
            sidecar = parent / "sidecar.zip"
            digest = hashlib.sha256(b"same").hexdigest()
            with zipfile.ZipFile(source, "w") as output:
                output.writestr("payload/a", b"same")
                output.writestr("payload/b", b"same")
                output.writestr("payload-sha256sums.txt", f"{digest}  payload/a\n{digest}  payload/b\n")
                output.writestr("manifest.json", json.dumps({"release_eligible": False, "payload_file_count": 2}))
                output.writestr("third-party-inventory.json", "{}")
            with zipfile.ZipFile(sidecar, "w") as output:
                output.writestr("notices/new.dist-info/LICENSE", b"notice")
            notice = {"source": "notices/new.dist-info/LICENSE",
                      "target": "payload/third-party-licenses/ocr-python-notices/new.dist-info/LICENSE",
                      "sha256": hashlib.sha256(b"notice").hexdigest()}
            with (patch("augment_windows_unified_ocr_notices.inspect_candidate",
                        return_value={"payload_file_count": 2}),
                  patch("augment_windows_unified_ocr_notices.inspect_sidecar", return_value=[notice])):
                result = augment(source, sidecar, parent)
            self.assertTrue(Path(result["archive"]).resolve().is_relative_to(parent))
            self.assertEqual(result["payload_file_count"], 3)
            with zipfile.ZipFile(result["archive"]) as bundle:
                self.assertEqual(bundle.read("payload/a"), bundle.read("payload/b"))
                self.assertEqual(len(bundle.read("payload-sha256sums.txt").splitlines()), 3)


if __name__ == "__main__":
    unittest.main()
