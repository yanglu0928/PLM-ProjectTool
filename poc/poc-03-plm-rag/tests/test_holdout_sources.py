from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.holdout_sources import ingest_holdout_sources  # noqa: E402


def parsed_payload(name: str, source_hash: str, text: str) -> dict:
    return {
        "source": {"name": name, "sha256": source_hash},
        "blocks": [{"text": text}],
    }


class HoldoutSourceTests(unittest.TestCase):
    def test_new_source_is_parsed_and_written_under_hash_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "input"
            history = root / "history"
            output = root / "output"
            input_dir.mkdir()
            history.mkdir()
            source = input_dir / "new.docx"
            source.write_bytes(b"new-source")
            source_hash = hashlib.sha256(b"new-source").hexdigest()
            accepted, report = ingest_holdout_sources(
                input_dir,
                output,
                historical_roots=[history],
                schema={"type": "object", "required": ["source", "blocks"]},
                parse=lambda path: parsed_payload(path.name, source_hash, "新的调研内容"),
            )
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(len(accepted), 1)
            parsed_path = output / "SURVEY" / f"SURVEY-HO-{source_hash[:12].upper()}.parsed.json"
            self.assertTrue(parsed_path.is_file())
            written = json.loads(parsed_path.read_text(encoding="utf-8"))
            self.assertEqual(written["metadata"]["evidence_role"], "ACTUAL_CUSTOMER_DISCOVERY_RECORD")
            self.assertEqual(report["source_governance"]["survey_form_templates"], "REFERENCE_ONLY_NOT_ELIGIBLE_FOR_HOLDOUT_QUOTA")

    def test_historical_file_duplicate_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "input"
            history = root / "history"
            input_dir.mkdir()
            history.mkdir()
            source = input_dir / "duplicate.docx"
            source.write_bytes(b"same")
            source_hash = hashlib.sha256(b"same").hexdigest()
            (history / "old.parsed.json").write_text(
                json.dumps(parsed_payload("old.docx", source_hash, "历史内容")),
                encoding="utf-8",
            )
            accepted, report = ingest_holdout_sources(
                input_dir,
                root / "output",
                historical_roots=[history],
                schema={"type": "object"},
                parse=lambda path: parsed_payload(path.name, source_hash, "历史内容"),
            )
            self.assertEqual(accepted, [])
            self.assertEqual(report["summary"]["reason_counts"], {"HISTORICAL_FILE_DUPLICATE": 1})

    def test_historical_content_duplicate_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "input"
            history = root / "history"
            input_dir.mkdir()
            history.mkdir()
            source = input_dir / "renamed.docx"
            source.write_bytes(b"new-bytes")
            source_hash = hashlib.sha256(b"new-bytes").hexdigest()
            (history / "old.parsed.json").write_text(
                json.dumps(parsed_payload("old.docx", hashlib.sha256(b"old").hexdigest(), "相同内容")),
                encoding="utf-8",
            )
            accepted, report = ingest_holdout_sources(
                input_dir,
                root / "output",
                historical_roots=[history],
                schema={"type": "object"},
                parse=lambda path: parsed_payload(path.name, source_hash, "相同内容"),
            )
            self.assertEqual(accepted, [])
            self.assertEqual(report["summary"]["reason_counts"], {"HISTORICAL_CONTENT_DUPLICATE": 1})


if __name__ == "__main__":
    unittest.main()
