from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from transfer_parent_candidate_chunks import (  # noqa: E402
    MANIFEST_NAME,
    SUMMARY_NAME,
    join_candidate,
    split_candidate,
)


class ParentCandidateChunkTransferTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.name != "nt":
            self.skipTest("parent artifact handoff is Windows-targeted")
        self.root = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
        self.source = self.root / ("a35-source-" + next(tempfile._get_candidate_names()))
        self.source.mkdir()
        self.output = self.root / ("a35-parts-" + next(tempfile._get_candidate_names()))
        self.archive_bytes = bytes(range(251)) * 5
        (self.source / "parent.zip").write_bytes(self.archive_bytes)
        (self.source / SUMMARY_NAME).write_text(
            json.dumps({
                "status": "WINDOWS_PARENT_PACKAGE_NON_RELEASE_CANDIDATE_INTEGRITY_PASS",
                "release_eligible": False,
                "legal_clearance": False,
                "archive_sha256": hashlib.sha256(self.archive_bytes).hexdigest(),
                "source_commit": "a" * 40,
                "workflow_run": "123456789",
            }),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        import shutil

        for path in (self.source, self.output):
            if path.exists():
                shutil.rmtree(path)

    def _bundles(self, manifest: dict[str, object], *, tamper: bool = False) -> list[Path]:
        summary = self.output / SUMMARY_NAME
        result = []
        chunks = manifest["chunks"]
        for meta in chunks:
            name = str(meta["name"])
            payload = (self.output / name).read_bytes()
            if tamper and int(meta["index"]) == 0:
                payload = payload + b"tamper"
            bundle = self.root / ("a35-bundle-" + name.replace(".bin", ".zip"))
            with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(MANIFEST_NAME, json.dumps(manifest))
                archive.writestr(SUMMARY_NAME, summary.read_bytes())
                archive.writestr(name, payload)
            result.append(bundle)
        return result

    def test_split_and_join_preserves_archive_and_summary_digests(self) -> None:
        manifest = split_candidate(self.source, self.output, "old", chunk_bytes=128)
        bundles = self._bundles(manifest)
        archive = self.root / "a35-joined-old.zip"
        summary = self.root / "a35-joined-old-summary.json"
        result = join_candidate(bundles, archive, summary, "old")
        self.assertEqual(archive.read_bytes(), self.archive_bytes)
        self.assertEqual(json.loads(summary.read_text(encoding="utf-8"))["release_eligible"], False)
        self.assertEqual(result["archive_sha256"], hashlib.sha256(self.archive_bytes).hexdigest())
        for path in (*bundles, archive, summary):
            path.unlink()

    def test_join_rejects_tampered_chunk_before_publishing_archive(self) -> None:
        manifest = split_candidate(self.source, self.output, "current", chunk_bytes=128)
        bundles = self._bundles(manifest, tamper=True)
        archive = self.root / "a35-joined-tampered.zip"
        summary = self.root / "a35-joined-tampered-summary.json"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            join_candidate(bundles, archive, summary, "current")
        self.assertFalse(archive.exists())
        self.assertFalse(summary.exists())
        for path in bundles:
            path.unlink()

    def test_join_rejects_missing_chunk(self) -> None:
        manifest = split_candidate(self.source, self.output, "old", chunk_bytes=128)
        bundles = self._bundles(manifest)[:-1]
        archive = self.root / "a35-joined-incomplete.zip"
        with self.assertRaisesRegex(ValueError, "sequence incomplete"):
            join_candidate(bundles, archive, self.root / "unused.json", "old")
        self.assertFalse(archive.exists())
        for path in self.root.glob("a35-bundle-old.part-*.zip"):
            path.unlink()

    def test_split_rejects_invalid_chunk_size_and_prefix(self) -> None:
        with self.assertRaisesRegex(ValueError, "chunk size"):
            split_candidate(self.source, self.output, "old", chunk_bytes=50_000_001)
        with self.assertRaisesRegex(ValueError, "prefix"):
            split_candidate(self.source, self.output, "unexpected", chunk_bytes=128)

    def test_paths_must_be_direct_children_of_non_c_runner_temp(self) -> None:
        with self.assertRaisesRegex(ValueError, "D-drive RUNNER_TEMP"):
            with patch.dict(os.environ, {"RUNNER_TEMP": str(self.source)}):
                split_candidate(self.source, self.output, "old", chunk_bytes=128)


if __name__ == "__main__":
    unittest.main()
