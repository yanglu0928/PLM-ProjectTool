"""Bounded, read-only inspection of signed Plugin ZIP archives."""
from __future__ import annotations

import io
import stat
import unicodedata
import zipfile
from dataclasses import dataclass
from typing import BinaryIO

from plm_assistant.modules.plugin.application.manifest_parser import (
    ParsedPluginManifest,
    PluginManifestError,
    PluginManifestParser,
)
from plm_assistant.modules.plugin.application.signature_verifier import (
    PluginPackageSignatureVerification,
    PluginPackageSignatureVerifier,
)


MAX_PACKAGE_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_ITEMS = 4096
MAX_MANIFEST_BYTES = 65_536
MAX_MEMBER_BYTES = 512 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
MAX_PATH_BYTES = 1024
MAX_COMPONENT_BYTES = 255
_MANIFEST_PATH = "manifest.json"
_SUPPORTED_COMPRESSION = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})
_WINDOWS_RESERVED_NAMES = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
})
_SPECIAL_FILE_MODES = frozenset({
    stat.S_IFLNK,
    stat.S_IFCHR,
    stat.S_IFBLK,
    stat.S_IFIFO,
    stat.S_IFSOCK,
})


class PluginPackageInspectionError(ValueError):
    """Stable, non-sensitive failure for an unsafe or malformed package archive."""

    def __init__(self, code: str = "PLUGIN_PACKAGE_INVALID") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class InspectedPluginPackage:
    """Read-only validation output; it does not imply import or execution approval."""

    manifest: ParsedPluginManifest
    signature_verification: PluginPackageSignatureVerification
    archive_item_count: int


def _canonical_archive_path(name: object, *, directory: bool) -> str:
    if type(name) is not str or not name:
        raise PluginPackageInspectionError()
    if directory:
        if not name.endswith("/") or name.endswith("//"):
            raise PluginPackageInspectionError()
        value = name[:-1]
    else:
        if name.endswith("/"):
            raise PluginPackageInspectionError()
        value = name
    if not value or value.startswith("/") or "\\" in value or ":" in value:
        raise PluginPackageInspectionError()
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError:
        raise PluginPackageInspectionError() from None
    if (
        len(encoded) > MAX_PATH_BYTES
        or unicodedata.normalize("NFC", value) != value
        or any(unicodedata.category(char) == "Cc" for char in value)
    ):
        raise PluginPackageInspectionError()
    parts = value.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise PluginPackageInspectionError()
    for part in parts:
        try:
            part_bytes = part.encode("utf-8", "strict")
        except UnicodeError:
            raise PluginPackageInspectionError() from None
        if len(part_bytes) > MAX_COMPONENT_BYTES or part.endswith((".", " ")):
            raise PluginPackageInspectionError()
        base = part.split(".", 1)[0].rstrip(" .").upper()
        if base in _WINDOWS_RESERVED_NAMES:
            raise PluginPackageInspectionError()
    return value


def _mode_type(info: zipfile.ZipInfo) -> int:
    return stat.S_IFMT(info.external_attr >> 16)


def _read_bounded_manifest(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
) -> bytes:
    if (
        info.file_size < 1
        or info.file_size > MAX_MANIFEST_BYTES
        or info.is_dir()
    ):
        raise PluginPackageInspectionError()
    try:
        with archive.open(info, "r") as stream:
            manifest = stream.read(MAX_MANIFEST_BYTES + 1)
            if len(manifest) > MAX_MANIFEST_BYTES:
                raise PluginPackageInspectionError()
            # Read one extra byte above the declared size to catch inconsistent metadata.
            extra = stream.read(1)
            if extra:
                raise PluginPackageInspectionError()
    except PluginPackageInspectionError:
        raise
    except Exception:
        raise PluginPackageInspectionError() from None
    return manifest


class PluginPackageArchiveInspector:
    """Inspect ZIP metadata, parse its root manifest, then verify exact archive bytes."""

    def __init__(
        self,
        manifest_parser: PluginManifestParser,
        signature_verifier: PluginPackageSignatureVerifier,
    ) -> None:
        if manifest_parser is None or signature_verifier is None:
            raise ValueError("manifest parser and signature verifier are required")
        self._manifest_parser = manifest_parser
        self._signature_verifier = signature_verifier

    def inspect_and_verify(
        self,
        archive_bytes: bytes,
        *,
        detached_signature: bytes,
        signer_key_ref: str,
    ) -> InspectedPluginPackage:
        if (
            type(archive_bytes) is not bytes
            or not 1 <= len(archive_bytes) <= MAX_PACKAGE_BYTES
        ):
            raise PluginPackageInspectionError()

        try:
            with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
                infos = archive.infolist()
                if not infos or len(infos) > MAX_ARCHIVE_ITEMS:
                    raise PluginPackageInspectionError()

                seen_casefolded: set[str] = set()
                regular_files: set[str] = set()
                manifest_info: zipfile.ZipInfo | None = None
                total_uncompressed = 0

                for info in infos:
                    is_dir = info.is_dir()
                    if info.orig_filename != info.filename:
                        raise PluginPackageInspectionError()
                    name = _canonical_archive_path(info.filename, directory=is_dir)
                    folded = name.casefold()
                    if folded in seen_casefolded:
                        raise PluginPackageInspectionError()
                    seen_casefolded.add(folded)

                    file_mode = _mode_type(info)
                    if file_mode in _SPECIAL_FILE_MODES:
                        raise PluginPackageInspectionError()
                    if file_mode not in {0, stat.S_IFREG, stat.S_IFDIR}:
                        raise PluginPackageInspectionError()
                    if is_dir:
                        if file_mode not in {0, stat.S_IFDIR} or info.file_size != 0:
                            raise PluginPackageInspectionError()
                    else:
                        if file_mode == stat.S_IFDIR:
                            raise PluginPackageInspectionError()
                        if file_mode not in {0, stat.S_IFREG}:
                            raise PluginPackageInspectionError()
                        regular_files.add(name)

                    if (
                        info.flag_bits & 0x1
                        or info.compress_type not in _SUPPORTED_COMPRESSION
                        or info.file_size < 0
                        or info.compress_size < 0
                    ):
                        raise PluginPackageInspectionError()
                    if is_dir:
                        continue
                    if info.file_size > MAX_MEMBER_BYTES:
                        raise PluginPackageInspectionError()
                    total_uncompressed += info.file_size
                    if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
                        raise PluginPackageInspectionError()
                    if info.file_size:
                        if info.compress_size == 0:
                            raise PluginPackageInspectionError()
                        if info.file_size > info.compress_size * MAX_COMPRESSION_RATIO:
                            raise PluginPackageInspectionError()

                    if name == _MANIFEST_PATH:
                        if manifest_info is not None:
                            raise PluginPackageInspectionError()
                        manifest_info = info

                if manifest_info is None:
                    raise PluginPackageInspectionError()
                manifest_bytes = _read_bounded_manifest(archive, manifest_info)
        except PluginManifestError:
            raise
        except PluginPackageInspectionError:
            raise
        except Exception:
            raise PluginPackageInspectionError() from None

        manifest = self._manifest_parser.parse(manifest_bytes)
        if manifest.entry_point not in regular_files:
            raise PluginPackageInspectionError()

        # The detached signature covers the exact same archive bytes from which the
        # bounded manifest and entry-point membership were read.
        signature_result = self._signature_verifier.verify(
            archive_bytes,
            signature=detached_signature,
            signer_key_ref=signer_key_ref,
        )
        return InspectedPluginPackage(
            manifest=manifest,
            signature_verification=signature_result,
            archive_item_count=len(infos),
        )
