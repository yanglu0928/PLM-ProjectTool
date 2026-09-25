from __future__ import annotations

import io
import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.document.application.prepare_download import (
    DownloadError, DownloadStorageError, PrepareDownloadService,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentDownloadSource, DocumentReadError, DocumentReadQuery,
)


class Tx:
    def __init__(self):
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def commit(self):
        self.committed = True


class Reader:
    def __init__(self, source):
        self.source = source
        self.calls = 0
        self.second = source

    def get_download_source(self, query, document_id, document_version_id):
        self.calls += 1
        assert document_id == self.source.document_id
        assert document_version_id == self.source.document_version_id
        if self.calls > 1 and isinstance(self.second, Exception):
            raise self.second
        return self.source if self.calls == 1 else self.second


class Storage:
    def __init__(self, content=b"verified"):
        self.content = content
        self.stream = None
        self.fail = False

    def open_verified_snapshot(self, locator, *, expected_sha256, expected_size,
                               max_bytes):
        assert locator == "global/objects/ab/" + "a" * 32
        assert expected_sha256 == b"h" * 32
        assert expected_size == len(self.content)
        assert max_bytes == 100_000_000
        if self.fail:
            raise DownloadStorageError("synthetic bad file")
        self.stream = io.BytesIO(self.content)
        return self.stream


class Audit:
    def __init__(self):
        self.events = []
        self.fail = False

    def append(self, tx, event):
        if self.fail:
            raise RuntimeError("synthetic audit failure")
        self.events.append((tx, event))
        return uuid.uuid4()


class PrepareDownloadTests(unittest.TestCase):
    def setUp(self):
        self.document = uuid.uuid4()
        self.version = uuid.uuid4()
        self.source = DocumentDownloadSource(
            uuid.uuid4(), self.document, self.version, uuid.uuid4(),
            "GLOBAL", None, "global/objects/ab/" + "a" * 32,
            b"h" * 32, len(b"verified"), "application/pdf",
        )
        self.query = DocumentReadQuery(b"s" * 32, uuid.uuid4(), "GLOBAL", None)
        self.reader = Reader(self.source)
        self.storage = Storage()
        self.audit = Audit()
        self.txs = []

    def service(self):
        def uow():
            tx = Tx()
            self.txs.append(tx)
            return tx
        return PrepareDownloadService(
            reader=self.reader, storage=self.storage,
            unit_of_work=uow, audit=self.audit,
        )

    def test_success_returns_only_verified_snapshot_and_closes(self):
        with self.service().prepare(self.query, self.document, self.version) as ready:
            self.assertEqual(ready.stream.read(), b"verified")
            self.assertEqual(ready.detected_mime, "application/pdf")
            self.assertNotIn("global/objects", repr(ready))
            self.assertEqual(self.reader.calls, 2)
        self.assertTrue(self.storage.stream.closed)
        self.assertEqual(self.audit.events, [])

    def test_recheck_revocation_or_changed_source_closes_snapshot(self):
        for second in (DocumentReadError("RESOURCE_NOT_FOUND"),
                       replace(self.source, file_object_id=uuid.uuid4())):
            with self.subTest(second=second):
                self.reader.calls = 0
                self.reader.second = second
                with self.assertRaises(DownloadError):
                    self.service().prepare(self.query, self.document, self.version)
                self.assertTrue(self.storage.stream.closed)

    def test_integrity_failure_records_pathless_audit_and_never_returns_bytes(self):
        self.storage.fail = True
        with self.assertRaises(DownloadError) as caught:
            self.service().prepare(self.query, self.document, self.version)
        self.assertEqual(caught.exception.code, "FILE_INTEGRITY_MISMATCH")
        self.assertEqual(self.reader.calls, 1)
        self.assertIsNone(self.storage.stream)
        self.assertEqual(len(self.audit.events), 1)
        tx, event = self.audit.events[0]
        self.assertTrue(tx.committed)
        self.assertEqual(event.action, "DOCUMENT_DOWNLOAD_INTEGRITY_FAILED")
        self.assertEqual(event.actor_id, self.source.actor_user_id)
        self.assertEqual(event.target_version_id, self.version)
        self.assertNotIn("global/objects", repr(event))

    def test_audit_failure_still_denies_download(self):
        self.storage.fail = True
        self.audit.fail = True
        with self.assertRaises(DownloadError) as caught:
            self.service().prepare(self.query, self.document, self.version)
        self.assertEqual(caught.exception.code, "DOCUMENT_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
