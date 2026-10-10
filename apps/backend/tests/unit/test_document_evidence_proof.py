from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
import uuid
from pathlib import Path

from plm_assistant.modules.document.application.prepare_download import (
    DownloadError, PrepareDownloadService, VerifiedDownload,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentDownloadSource, DocumentReadQuery,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.evidence.application.document_source_proof import (
    DocumentEvidenceProofService, EvidenceSourceError,
)


class _Snapshots:
    def __init__(self, result) -> None:
        self.result = result
        self.calls = 0

    def prepare(self, query, document_id, document_version_id):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class _Reader:
    def __init__(self, source: DocumentDownloadSource) -> None:
        self.source = source

    def get_download_source(self, query, document_id, document_version_id):
        return self.source


class _Tx:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def commit(self):
        pass


class _Audit:
    def __init__(self) -> None:
        self.actions: list[str] = []

    def append(self, tx, event):
        self.actions.append(event.action)
        return uuid.uuid4()


class DocumentEvidenceProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document_id, self.version_id = uuid.uuid4(), uuid.uuid4()
        self.query = DocumentReadQuery(
            session_token=b"s" * 32, trace_id=uuid.uuid4(),
            scope="PROJECT", project_id=uuid.uuid4(),
        )

    def test_verified_whole_document_uses_server_digest_and_closes_stream(self) -> None:
        stream = io.BytesIO(b"verified")
        digest = hashlib.sha256(b"verified").digest()
        snapshots = _Snapshots(VerifiedDownload(self.version_id, 8, "application/pdf", digest, stream))
        proof = DocumentEvidenceProofService(document_snapshots=snapshots).prove(
            self.query, document_id=self.document_id,
            document_version_id=self.version_id,
            locator={"locator_type": "DOCUMENT"},
        )
        self.assertEqual(proof.content_fingerprint, digest)
        self.assertEqual(proof.locator, {"locator_type": "DOCUMENT"})
        self.assertEqual(proof.precision, "DOCUMENT")
        self.assertTrue(stream.closed)
        self.assertNotIn(digest.hex(), repr(proof))

    def test_precise_or_invalid_locator_never_opens_document(self) -> None:
        snapshots = _Snapshots(None)
        service = DocumentEvidenceProofService(document_snapshots=snapshots)
        for locator, code in (
            ({"locator_type": "PAGE", "page_no": 1}, "EVIDENCE_RESOLUTION_UNAVAILABLE"),
            ({"locator_type": "DOCUMENT", "file_path": "C:/private"}, "EVIDENCE_LOCATOR_INVALID"),
        ):
            with self.subTest(locator=locator):
                with self.assertRaises(EvidenceSourceError) as caught:
                    service.prove(self.query, document_id=self.document_id,
                                  document_version_id=self.version_id, locator=locator)
                self.assertEqual(caught.exception.code, code)
        self.assertEqual(snapshots.calls, 0)
        invalid_query = DocumentReadQuery(
            session_token=b"short", trace_id=self.query.trace_id,
            scope="PROJECT", project_id=self.query.project_id,
        )
        with self.assertRaises(EvidenceSourceError) as caught:
            service.prove(invalid_query, document_id=self.document_id,
                          document_version_id=self.version_id,
                          locator={"locator_type": "DOCUMENT"})
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(snapshots.calls, 0)

    def test_unavailable_and_mismatched_source_fail_closed(self) -> None:
        for issue, code in (
            (DownloadError("RESOURCE_NOT_FOUND"), "RESOURCE_NOT_FOUND"),
            (RuntimeError("private path"), "DOCUMENT_UNAVAILABLE"),
        ):
            with self.subTest(code=code):
                with self.assertRaises(EvidenceSourceError) as caught:
                    DocumentEvidenceProofService(document_snapshots=_Snapshots(issue)).prove(
                        self.query, document_id=self.document_id,
                        document_version_id=self.version_id,
                        locator={"locator_type": "DOCUMENT"},
                    )
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn("private path", str(caught.exception))
        stream = io.BytesIO(b"x")
        with self.assertRaises(EvidenceSourceError):
            DocumentEvidenceProofService(document_snapshots=_Snapshots(
                VerifiedDownload(uuid.uuid4(), 1, "text/plain", b"h" * 32, stream),
            )).prove(self.query, document_id=self.document_id,
                     document_version_id=self.version_id,
                     locator={"locator_type": "DOCUMENT"})
        self.assertTrue(stream.closed)

    def test_real_storage_snapshot_detects_corruption_without_path_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="plm-evidence-proof-") as temp:
            root = Path(temp) / "data"
            root.mkdir()
            storage = LocalFileStorage(root)
            file_id = uuid.uuid4()
            _, final = storage.locators(scope="PROJECT", project_id=self.query.project_id,
                                        file_object_id=file_id)
            target = root / final
            target.parent.mkdir(parents=True)
            original = b"%PDF-1.7\nsynthetic evidence\n%%EOF\n"
            target.write_bytes(original)
            digest = hashlib.sha256(original).digest()
            source = DocumentDownloadSource(
                actor_user_id=uuid.uuid4(), document_id=self.document_id,
                document_version_id=self.version_id, file_object_id=file_id,
                scope="PROJECT", project_id=self.query.project_id,
                storage_locator=final, content_sha256=digest,
                size_bytes=len(original), detected_mime="application/pdf",
            )
            audit = _Audit()
            prepare = PrepareDownloadService(
                reader=_Reader(source), storage=storage,
                unit_of_work=lambda: _Tx(), audit=audit,
            )
            service = DocumentEvidenceProofService(document_snapshots=prepare)
            proof = service.prove(self.query, document_id=self.document_id,
                                  document_version_id=self.version_id,
                                  locator={"locator_type": "DOCUMENT"})
            self.assertEqual(proof.content_fingerprint, digest)
            target.write_bytes(b"changed")
            with self.assertRaises(EvidenceSourceError) as caught:
                service.prove(self.query, document_id=self.document_id,
                              document_version_id=self.version_id,
                              locator={"locator_type": "DOCUMENT"})
            self.assertEqual(caught.exception.code, "FILE_INTEGRITY_MISMATCH")
            self.assertEqual(audit.actions, ["DOCUMENT_DOWNLOAD_INTEGRITY_FAILED"])


if __name__ == "__main__":
    unittest.main()
