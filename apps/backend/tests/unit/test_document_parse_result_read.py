from __future__ import annotations

import hashlib
import io
import json
import sys
import unittest
import uuid
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from plm_assistant.modules.document.application.read_documents import (  # noqa: E402
    DocumentDownloadSource, DocumentReadQuery,
)
from plm_assistant.modules.document.application.prepare_download import (  # noqa: E402
    DownloadError, VerifiedDownload,
)
from plm_assistant.modules.document.application.read_parse_result import (  # noqa: E402
    DocumentParseResultReadService, FixedParseResultSource, ParseResultReadError,
)


class _UnitOfWork:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _Documents:
    def __init__(self, source):
        self.source = source
        self.calls = 0
        self.denied_on = None
        self.changed_on = None

    def prepare(self, *_):
        self.calls += 1
        if self.denied_on == self.calls:
            raise DownloadError("AUTH_ACCESS_DENIED")
        if self.changed_on == self.calls:
            source = self.source
            return VerifiedDownload(source.document_version_id, source.size_bytes,
                                    source.detected_mime, b"x" * 32, io.BytesIO())
        source = self.source
        return VerifiedDownload(source.document_version_id, source.size_bytes,
                                source.detected_mime, source.content_sha256, io.BytesIO())


class _Metadata:
    def __init__(self, source):
        self.source = source
        self.calls = 0
        self.changed_on = None

    def get(self, *_args, **_kwargs):
        self.calls += 1
        if self.changed_on == self.calls:
            return None
        return self.source


class _Storage:
    def __init__(self, content):
        self.content = content
        self.calls = 0

    def read_verified(self, **_kwargs):
        self.calls += 1
        return self.content


class DocumentParseResultReadTests(unittest.TestCase):
    def setUp(self):
        self.document_id = uuid.uuid4()
        self.version_id = uuid.uuid4()
        self.record_id = uuid.uuid4()
        self.result_id = uuid.uuid4()
        self.project_id = uuid.uuid4()
        self.query = DocumentReadQuery(b"s" * 32, uuid.uuid4(), "PROJECT", self.project_id)
        self.original_hash = b"a" * 32
        self.content = json.dumps({
            "schema_version": "1", "document_version_id": str(self.version_id),
            "source_sha256": self.original_hash.hex(), "parser_profile": "PLAIN_TEXT",
            "parser_version": "1", "nodes": [],
        }, separators=(",", ":")).encode()
        self.source = DocumentDownloadSource(
            uuid.uuid4(), self.document_id, self.version_id, uuid.uuid4(),
            "PROJECT", self.project_id, "documents/fixed", self.original_hash,
            12, "text/plain",
        )
        self.result = FixedParseResultSource(
            self.record_id, self.version_id, "PROJECT", self.project_id,
            "PLAIN_TEXT", "1", self.result_id,
            f"results/projects/{self.project_id.hex}/{self.result_id.hex[:2]}/{self.result_id.hex}.json",
            hashlib.sha256(self.content).digest(), len(self.content), 1,
        )
        self.documents = _Documents(self.source)
        self.metadata = _Metadata(self.result)
        self.storage = _Storage(self.content)
        self.service = DocumentParseResultReadService(
            documents=self.documents, metadata=self.metadata,
            storage=self.storage, unit_of_work=_UnitOfWork,
        )

    def read(self):
        return self.service.read(
            self.query, document_id=self.document_id,
            document_version_id=self.version_id, parse_record_id=self.record_id,
        )

    def test_fixed_result_verified_and_reauthorized(self):
        read = self.read()
        self.assertEqual(read.content, self.content)
        self.assertEqual((self.documents.calls, self.metadata.calls, self.storage.calls), (2, 2, 1))
        self.assertNotIn("content", repr(read))

    def test_revoked_after_storage_read_fails_closed(self):
        self.documents.denied_on = 2
        with self.assertRaisesRegex(ParseResultReadError, "AUTH_ACCESS_DENIED"):
            self.read()

    def test_version_source_drift_fails_closed(self):
        self.documents.changed_on = 2
        with self.assertRaisesRegex(ParseResultReadError, "RESOURCE_NOT_FOUND"):
            self.read()

    def test_result_metadata_drift_fails_closed(self):
        self.metadata.changed_on = 2
        with self.assertRaisesRegex(ParseResultReadError, "RESOURCE_NOT_FOUND"):
            self.read()

    def test_storage_tamper_fails_closed(self):
        self.storage.content = self.content[:-1] + b"!"
        with self.assertRaisesRegex(ParseResultReadError, "FILE_INTEGRITY_MISMATCH"):
            self.read()

    def test_wrong_project_and_failed_record_never_read_bytes(self):
        self.metadata.source = None
        with self.assertRaisesRegex(ParseResultReadError, "RESOURCE_NOT_FOUND"):
            self.read()
        self.assertEqual(self.storage.calls, 0)

    def test_payload_source_hash_mismatch_fails_closed(self):
        payload = json.loads(self.content)
        payload["source_sha256"] = "f" * 64
        self.storage.content = json.dumps(payload, separators=(",", ":")).encode()
        self.metadata.source = FixedParseResultSource(
            self.record_id, self.version_id, "PROJECT", self.project_id,
            "PLAIN_TEXT", "1", self.result_id, self.result.storage_locator,
            hashlib.sha256(self.storage.content).digest(), len(self.storage.content), 1,
        )
        with self.assertRaisesRegex(ParseResultReadError, "PARSER_RESULT_INVALID"):
            self.read()


if __name__ == "__main__":
    unittest.main()
