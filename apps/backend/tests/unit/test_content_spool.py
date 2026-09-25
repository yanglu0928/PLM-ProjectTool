from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
import uuid
import zipfile
from pathlib import Path

from plm_assistant.modules.document.infrastructure.content_spool import (
    ContentSpoolError, ValidatedContentSpool,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage, LocalStorageError


_EXTENSIONS = frozenset((
    ".pdf", ".docx", ".xlsx", ".pptx", ".png", ".jpg",
    ".jpeg", ".tif", ".tiff", ".txt", ".csv",
))


def ooxml(extension: str, *, malicious: str | None = None) -> bytes:
    main = {
        ".docx": ("word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"),
        ".xlsx": ("xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
        ".pptx": ("ppt/presentation.xml", "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"),
    }[extension]
    body = io.BytesIO()
    with zipfile.ZipFile(body, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/{main[0]}" ContentType="{main[1]}"/></Types>')
        package.writestr("_rels/.rels", "<Relationships/>")
        package.writestr(main[0], "<document/>")
        if malicious:
            package.writestr(malicious, "bad")
    return body.getvalue()


class ContentSpoolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="plm-content-spool-")
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name) / "data"
        root.mkdir()
        self.root = root
        self.storage = LocalFileStorage(root)
        self.spool = ValidatedContentSpool(
            storage=self.storage, max_bytes=2_000_000,
            allowed_extensions=_EXTENSIONS,
        )
        self.project = uuid.uuid4()
        self.file_id = uuid.uuid4()

    def receive(self, content: bytes, name: str, **changes):
        options = dict(
            chunks=(content[i:i + 7] for i in range(0, len(content), 7)),
            scope="PROJECT", project_id=self.project,
            file_object_id=self.file_id, original_display_name=name,
            declared_length=len(content), declared_sha256=hashlib.sha256(content).digest(),
        )
        options.update(changes)
        return self.spool.receive(**options)

    def stage_path(self) -> Path:
        locator, _ = self.storage.locators(
            scope="PROJECT", project_id=self.project, file_object_id=self.file_id,
        )
        return self.root / locator

    def test_pdf_stream_and_exclusive_no_overwrite(self):
        data = b"%PDF-1.7\nsynthetic only\n%%EOF\n"
        proof = self.receive(data, "合同.pdf", mime_hint="application/pdf",
                             expected_size_bytes=len(data))
        self.assertEqual(proof.sha256, hashlib.sha256(data).digest())
        self.assertEqual(proof.size_bytes, len(data))
        self.assertEqual(proof.detected_mime, "application/pdf")
        self.assertEqual(self.stage_path().read_bytes(), data)
        self.assertNotIn(str(self.root), repr(proof))
        with self.assertRaises(ContentSpoolError):
            self.receive(data, "合同.pdf")
        self.assertEqual(self.stage_path().read_bytes(), data)

    def test_reject_size_hash_type_mime_and_name_without_staging(self):
        content = b"%PDF-1.7\nsynthetic\n"
        for name, changes, code in (
            ("bad.pdf", {"declared_length": len(content) - 1}, "FILE_TOO_LARGE"),
            ("bad.pdf", {"declared_length": len(content) + 1}, "FILE_INTEGRITY_MISMATCH"),
            ("bad.pdf", {"declared_sha256": b"x" * 32}, "FILE_INTEGRITY_MISMATCH"),
            ("bad.pdf", {"expected_size_bytes": len(content) + 1}, "FILE_INTEGRITY_MISMATCH"),
            ("bad.pdf", {"mime_hint": "image/png"}, "FILE_TYPE_UNSUPPORTED"),
            ("../bad.pdf", {}, "FILE_TYPE_UNSUPPORTED"),
            ("CON.pdf", {}, "FILE_TYPE_UNSUPPORTED"),
            ("bad.exe", {}, "FILE_TYPE_UNSUPPORTED"),
            ("bad.pdf", {"chunks": [b"not a PDF"]}, "FILE_INTEGRITY_MISMATCH"),
        ):
            with self.subTest(name=name, changes=changes), self.assertRaises(ContentSpoolError) as caught:
                self.receive(content, name, **changes)
            self.assertEqual(caught.exception.code, code)
            self.assertFalse(self.stage_path().exists())

    def test_ooxml_structure_and_traversal(self):
        for extension, mime in (
            (".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            (".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            (".pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ):
            self.file_id = uuid.uuid4()
            proof = self.receive(ooxml(extension), "sample" + extension)
            self.assertEqual(proof.detected_mime, mime)
        for bad in ("../escape", "word/../escape", "word/vbaProject.bin"):
            self.file_id = uuid.uuid4()
            with self.assertRaises(ContentSpoolError):
                self.receive(ooxml(".docx", malicious=bad), "bad.docx")
            self.assertFalse(self.stage_path().exists())
        self.file_id = uuid.uuid4()
        with self.assertRaises(ContentSpoolError):
            self.receive(ooxml(".docx"), "spoofed.pdf")

    def test_text_utf8_and_invalid_binary(self):
        proof = self.receive("中文,调研\n".encode("utf-8"), "survey.csv")
        self.assertEqual(proof.detected_mime, "text/csv")
        self.file_id = uuid.uuid4()
        with self.assertRaises(ContentSpoolError):
            self.receive(b"a\x00b", "binary.txt")
        self.assertFalse(self.stage_path().exists())
        self.file_id = uuid.uuid4()
        with self.assertRaises(ContentSpoolError):
            self.receive(b"\xff", "invalid.txt")
        self.assertFalse(self.stage_path().exists())

    def test_declared_limit_chunk_limit_and_file_signatures(self):
        body = b"%PDF-1.7\n" + b"x" * 65_000
        self.spool = ValidatedContentSpool(
            storage=self.storage, max_bytes=1024,
            allowed_extensions=frozenset((".pdf",)),
        )
        with self.assertRaises(ContentSpoolError) as caught:
            self.receive(body, "big.pdf")
        self.assertEqual(caught.exception.code, "FILE_TOO_LARGE")
        self.assertFalse(self.stage_path().exists())
        self.spool = ValidatedContentSpool(
            storage=self.storage, max_bytes=2_000_000,
            allowed_extensions=_EXTENSIONS,
        )
        with self.assertRaises(ContentSpoolError) as caught:
            self.receive(body, "big.pdf", chunks=[body + b"x" * 1_000_000])
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertFalse(self.stage_path().exists())
        with self.assertRaises(ContentSpoolError) as caught:
            self.receive(b"fake PDF bytes", "fake.pdf")
        self.assertEqual(caught.exception.code, "FILE_TYPE_UNSUPPORTED")
        self.assertFalse(self.stage_path().exists())
        with self.assertRaises(ContentSpoolError) as caught:
            self.receive(b"%PDF-1.7\nmissing trailer", "truncated.pdf")
        self.assertEqual(caught.exception.code, "FILE_TYPE_UNSUPPORTED")
        self.assertFalse(self.stage_path().exists())
        self.file_id = uuid.uuid4()
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 12 + b"\x00\x00\x00\x00IEND\xaeB`\x82"
        self.assertEqual(self.receive(png, "picture.png").detected_mime, "image/png")
        self.file_id = uuid.uuid4()
        self.assertEqual(self.receive(b"\xff\xd8\xff\xe0data\xff\xd9", "photo.jpeg").detected_mime, "image/jpeg")
        self.file_id = uuid.uuid4()
        self.assertEqual(self.receive(b"II*\x00data", "scan.tif").detected_mime, "image/tiff")

    def test_failed_stream_cleanup_does_not_remove_existing_file(self):
        content = b"%PDF-1.7\nknown\n%%EOF\n"
        self.receive(content, "first.pdf")
        path = self.stage_path()
        wrong_inode = path.stat().st_ino + 1
        with self.assertRaises(LocalStorageError):
            self.storage.discard_new_staging(
                self.storage.locators(scope="PROJECT", project_id=self.project,
                                      file_object_id=self.file_id)[0],
                device=path.stat().st_dev, inode=wrong_inode,
            )
        self.assertEqual(path.read_bytes(), content)
        with self.assertRaises(ContentSpoolError):
            self.receive(content, "second.pdf")
        self.assertEqual(path.read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
