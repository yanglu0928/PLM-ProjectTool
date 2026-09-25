"""Bounded single-request upload staging; no authorization or DB mutation."""

from __future__ import annotations

import codecs
import hashlib
import hmac
import os
import re
import stat
import uuid
import zipfile
import zlib
from dataclasses import dataclass, field
from typing import Iterable
from xml.etree import ElementTree

from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage, LocalStorageError


_MIME = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".png": "image/png",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".tif": "image/tiff", ".tiff": "image/tiff",
    ".txt": "text/plain", ".csv": "text/csv",
}
_OOXML_MAIN = {
    ".docx": ("word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"),
    ".xlsx": ("xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
    ".pptx": ("ppt/presentation.xml", "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"),
}
_RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?\Z", re.I | re.ASCII)
_CHUNK_BYTES = 1_048_576


class ContentSpoolError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class StagedContentProof:
    staging_locator: str
    sha256: bytes = field(repr=False)
    size_bytes: int
    detected_mime: str


class ValidatedContentSpool:
    """Caller must authorize Intent before invoking; result is not a FileObject."""

    def __init__(self, *, storage: LocalFileStorage, max_bytes: int,
                 allowed_extensions: frozenset[str]) -> None:
        if (not isinstance(storage, LocalFileStorage)
                or type(max_bytes) is not int or not 0 < max_bytes <= 9_223_372_036_854_775_807
                or type(allowed_extensions) is not frozenset
                or not allowed_extensions or not allowed_extensions <= _MIME.keys()):
            raise ValueError("Invalid content spool policy")
        self._storage = storage
        self._max_bytes = max_bytes
        self._allowed = allowed_extensions

    def receive(self, *, chunks: Iterable[bytes], scope: str,
                project_id: uuid.UUID | None, file_object_id: uuid.UUID,
                original_display_name: str, declared_length: int,
                declared_sha256: bytes, mime_hint: str | None = None,
                expected_size_bytes: int | None = None) -> StagedContentProof:
        extension = self._extension(original_display_name)
        if (type(declared_length) is not int or declared_length <= 0
                or type(declared_sha256) is not bytes or len(declared_sha256) != 32):
            raise ContentSpoolError("VALIDATION_FAILED")
        if declared_length > self._max_bytes:
            raise ContentSpoolError("FILE_TOO_LARGE")
        if expected_size_bytes is not None:
            if type(expected_size_bytes) is not int or expected_size_bytes < 0:
                raise ContentSpoolError("VALIDATION_FAILED")
            if expected_size_bytes != declared_length:
                raise ContentSpoolError("FILE_INTEGRITY_MISMATCH")
        if extension not in self._allowed or mime_hint is not None and mime_hint != _MIME[extension]:
            raise ContentSpoolError("FILE_TYPE_UNSUPPORTED")
        try:
            locator, _ = self._storage.locators(
                scope=scope, project_id=project_id, file_object_id=file_object_id,
            )
        except LocalStorageError:
            raise ContentSpoolError("FILE_CONTENT_UNAVAILABLE") from None
        identity = None
        try:
            with self._storage.reserve_staging(locator) as stream:
                info = os.fstat(stream.fileno())
                identity = (info.st_dev, info.st_ino)
                digest = hashlib.sha256()
                total = 0
                for chunk in chunks:
                    if type(chunk) is not bytes or len(chunk) > _CHUNK_BYTES:
                        raise ContentSpoolError("VALIDATION_FAILED")
                    total += len(chunk)
                    if total > declared_length or total > self._max_bytes:
                        raise ContentSpoolError("FILE_TOO_LARGE")
                    stream.write(chunk)
                    digest.update(chunk)
                if (total != declared_length
                        or not hmac.compare_digest(digest.digest(), declared_sha256)):
                    raise ContentSpoolError("FILE_INTEGRITY_MISMATCH")
                stream.flush()
                os.fsync(stream.fileno())
                self._check_type(stream, extension, total)
                after = os.fstat(stream.fileno())
                if (not stat.S_ISREG(after.st_mode) or after.st_nlink != 1
                        or (after.st_dev, after.st_ino) != identity
                        or after.st_size != total):
                    raise ContentSpoolError("FILE_CONTENT_UNAVAILABLE")
            self._storage.verify_content(
                locator, expected_sha256=digest.digest(),
                expected_size=total, max_bytes=self._max_bytes,
            )
            return StagedContentProof(locator, digest.digest(), total, _MIME[extension])
        except Exception as exc:
            if identity is not None:
                try:
                    self._storage.discard_new_staging(
                        locator, device=identity[0], inode=identity[1],
                    )
                except LocalStorageError:
                    pass  # Orphan must be handled by the controlled TTL recovery job.
            if isinstance(exc, ContentSpoolError):
                raise
            raise ContentSpoolError("FILE_CONTENT_UNAVAILABLE") from None

    @staticmethod
    def _extension(name: object) -> str:
        if (type(name) is not str or not 1 <= len(name) <= 255
                or name != name.strip() or name.endswith(".")
                or "/" in name or "\\" in name or ":" in name
                or any(ord(char) < 32 or ord(char) == 127 for char in name)
                or _RESERVED.fullmatch(name)):
            raise ContentSpoolError("FILE_TYPE_UNSUPPORTED")
        suffix = "." + name.rsplit(".", 1)[-1].lower()
        if suffix not in _MIME:
            raise ContentSpoolError("FILE_TYPE_UNSUPPORTED")
        return suffix

    @staticmethod
    def _check_type(stream, extension: str, total: int) -> None:
        stream.seek(0)
        head = stream.read(16)
        if extension == ".pdf" and total >= 12 and head.startswith(b"%PDF-"):
            stream.seek(max(total - 1024, 0))
            if b"%%EOF" in stream.read(1024):
                return
        if extension == ".png" and total >= 20 and head.startswith(b"\x89PNG\r\n\x1a\n"):
            stream.seek(-12, os.SEEK_END)
            if stream.read(12).endswith(b"IEND\xaeB`\x82"):
                return
        if extension in (".jpg", ".jpeg") and total >= 5 and head.startswith(b"\xff\xd8\xff"):
            stream.seek(-2, os.SEEK_END)
            if stream.read(2) == b"\xff\xd9":
                return
        if extension in (".tif", ".tiff") and head[:4] in (b"II*\x00", b"MM\x00*"):
            return
        if extension in (".txt", ".csv"):
            stream.seek(0)
            decoder = codecs.getincrementaldecoder("utf-8-sig")("strict")
            try:
                while part := stream.read(_CHUNK_BYTES):
                    value = decoder.decode(part)
                    if any(ord(char) < 32 and char not in "\t\r\n" for char in value):
                        break
                else:
                    decoder.decode(b"", final=True)
                    return
            except UnicodeError:
                pass
        if extension in _OOXML_MAIN and head.startswith(b"PK\x03\x04"):
            stream.seek(0)
            ValidatedContentSpool._check_ooxml(stream, extension, total)
            return
        raise ContentSpoolError("FILE_TYPE_UNSUPPORTED")

    @staticmethod
    def _check_ooxml(stream, extension: str, total: int) -> None:
        main_part, main_mime = _OOXML_MAIN[extension]
        try:
            with zipfile.ZipFile(stream) as archive:
                infos = archive.infolist()
                if not 2 <= len(infos) <= 4096:
                    raise ContentSpoolError("FILE_TYPE_UNSUPPORTED")
                names = set()
                expanded = 0
                for info in infos:
                    name = info.filename
                    folded = name.casefold()
                    if (not name or name.startswith("/") or "\\" in name or ":" in name
                            or any(part in ("", ".", "..") for part in name.rstrip("/").split("/"))
                            or info.flag_bits & 1
                            or stat.S_ISLNK(info.external_attr >> 16)
                            or folded in names
                            or folded.endswith("/vbaproject.bin")
                            or "/activex/" in "/" + folded):
                        raise ContentSpoolError("FILE_TYPE_UNSUPPORTED")
                    names.add(folded)
                    expanded += info.file_size
                    if expanded > min(total * 8, 536_870_912):
                        raise ContentSpoolError("FILE_TYPE_UNSUPPORTED")
                if (main_part.casefold() not in names
                        or "[content_types].xml" not in names
                        or "_rels/.rels" not in names):
                    raise ContentSpoolError("FILE_TYPE_UNSUPPORTED")
                ct = archive.getinfo("[Content_Types].xml")
                if ct.file_size > 1_048_576:
                    raise ContentSpoolError("FILE_TYPE_UNSUPPORTED")
                root = ElementTree.fromstring(archive.read(ct))
                expected = "{http://schemas.openxmlformats.org/package/2006/content-types}"
                if root.tag != expected + "Types" or not any(
                    node.tag == expected + "Override"
                    and node.get("PartName") == "/" + main_part
                    and node.get("ContentType") == main_mime
                    for node in root
                ):
                    raise ContentSpoolError("FILE_TYPE_UNSUPPORTED")
                if archive.testzip() is not None:
                    raise ContentSpoolError("FILE_TYPE_UNSUPPORTED")
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError,
                RuntimeError, OSError, EOFError, zlib.error):
            raise ContentSpoolError("FILE_TYPE_UNSUPPORTED") from None
