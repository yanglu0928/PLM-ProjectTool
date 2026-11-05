"""Bounded, non-executing materialization of a verified Plugin archive.

This adapter is intentionally unassembled. It writes data files only, never
imports plugin code, installs dependencies, or enables operations.
"""
from __future__ import annotations

import hashlib
import io
import hmac
import os
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Callable

from plm_assistant.modules.plugin.application.installation_owner import (
    InstallablePluginPackage,
    PluginInstallationEvidence,
)
from plm_assistant.modules.plugin.application.package_archive_inspector import (
    PluginPackageArchiveInspector,
    _canonical_archive_path,
)
from plm_assistant.modules.plugin.application.package_registration import (
    PluginPackageRegistrationService,
)
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage

_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_CHUNK = 1024 * 1024


class PluginInstallationMaterializationError(RuntimeError):
    """Non-sensitive failure for local package materialization/evidence."""

    def __init__(self, code: str = "PLUGIN_INSTALLATION_EVIDENCE_INVALID") -> None:
        self.code = code
        super().__init__(code)


def _is_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & _REPARSE
    )


def _directory(path: Path, *, create: bool = False) -> None:
    try:
        if create:
            path.mkdir(mode=0o700, exist_ok=True)
        info = path.lstat()
    except OSError:
        raise PluginInstallationMaterializationError() from None
    if not stat.S_ISDIR(info.st_mode) or _is_reparse(info):
        raise PluginInstallationMaterializationError()


def _validate_package(package: object, installation_id: object) -> None:
    if (type(package) is not InstallablePluginPackage
            or package.package_state != "VERIFIED"
            or type(package.plugin_package_id) is not uuid.UUID
            or package.plugin_package_id.int == 0
            or type(package.package_sha256) is not bytes
            or len(package.package_sha256) != 32
            or type(package.signature) is not bytes
            or len(package.signature) != 64
            or type(package.signer_key_ref) is not str
            or not package.signer_key_ref
            or type(installation_id) is not uuid.UUID
            or installation_id.int == 0):
        raise PluginInstallationMaterializationError("PLUGIN_INSTALLATION_INVALID")


class LocalPluginInstallationMaterializer:
    """Materialize and independently re-inspect one exact installation UUID."""

    def __init__(
        self,
        *,
        storage: LocalFileStorage,
        inspector: PluginPackageArchiveInspector,
        runtime_snapshot_provider: Callable[[], dict],
    ) -> None:
        if storage is None or inspector is None or not callable(runtime_snapshot_provider):
            raise ValueError("installation materializer dependencies are required")
        self._storage = storage
        self._inspector = inspector
        self._runtime_snapshot_provider = runtime_snapshot_provider
        self._data_root = storage._root

    def materialize(
        self, package: InstallablePluginPackage, *, installation_id: uuid.UUID,
    ) -> Path:
        """Create the installation directory, or prove an existing exact replay."""
        _validate_package(package, installation_id)
        archive_bytes, inspected, entries = self._verified_archive(package)
        parent = self._installation_parent()
        target = parent / installation_id.hex
        if os.path.lexists(target):
            self._verify_tree(target, entries)
            return target

        staging = Path(tempfile.mkdtemp(
            prefix=f".{installation_id.hex}.staging-", dir=parent,
        ))
        _directory(staging)
        self._write_archive_members(staging, archive_bytes, entries)
        self._verify_tree(staging, entries)
        # The service data root must be ACL-private. On Windows os.rename refuses
        # an existing destination; the preceding no-follow check also rejects links.
        if os.path.lexists(target):
            raise PluginInstallationMaterializationError()
        try:
            os.rename(staging, target)
        except OSError:
            # A concurrent exact replay may have won. Never replace its directory.
            if os.path.lexists(target):
                self._verify_tree(target, entries)
                return target
            raise PluginInstallationMaterializationError() from None
        self._verify_tree(target, entries)
        return target

    def inspect_installed_package(
        self, package: InstallablePluginPackage, *, installation_id: uuid.UUID,
    ) -> PluginInstallationEvidence | None:
        """Return Host evidence only when the UUID directory exactly matches the ZIP."""
        try:
            _validate_package(package, installation_id)
            _archive, inspected, entries = self._verified_archive(package)
            target = self._installation_parent() / installation_id.hex
            self._verify_tree(target, entries)
            runtime = self._runtime_snapshot_provider()
            if type(runtime) is not dict:
                return None
            supported_os = package.manifest_snapshot.get("supported_os")
            architecture = package.manifest_snapshot.get("architecture")
            compatible = (
                type(supported_os) is list and runtime.get("os") in supported_os
                and architecture == runtime.get("architecture")
            )
            return PluginInstallationEvidence(
                plugin_package_id=package.plugin_package_id,
                installed_package_sha256=bytes(inspected.signature_verification.package_sha256),
                installation_present=True,
                compatible=compatible,
                runtime_snapshot=dict(runtime),
                plugin_installation_id=installation_id,
            )
        except Exception:
            return None

    def _installation_parent(self) -> Path:
        _directory(self._data_root)
        plugins = self._data_root / "plugins"
        installations = plugins / "installations"
        _directory(plugins, create=True)
        _directory(installations, create=True)
        return installations

    def _verified_archive(self, package: InstallablePluginPackage):
        try:
            body = self._storage.load_verified_plugin_package_archive(
                package_id=package.plugin_package_id,
                expected_sha256=package.package_sha256,
            )
            inspected = self._inspector.inspect_and_verify(
                body, detached_signature=package.signature,
                signer_key_ref=package.signer_key_ref,
            )
            snapshot = PluginPackageRegistrationService._manifest_snapshot(
                inspected.manifest,
            )
            if (not hmac.compare_digest(
                    inspected.signature_verification.package_sha256,
                    package.package_sha256)
                    or snapshot != package.manifest_snapshot
                    or inspected.manifest.plugin_id != package.plugin_id_normalized
                    or inspected.manifest.version != package.plugin_version):
                raise PluginInstallationMaterializationError()
            with zipfile.ZipFile(io.BytesIO(body), "r") as archive:
                files: dict[str, tuple[zipfile.ZipInfo, bytes, int]] = {}
                directories: set[str] = set()
                for info in archive.infolist():
                    name = _canonical_archive_path(info.filename, directory=info.is_dir())
                    parts = name.split("/")
                    directories.update("/".join(parts[:i]) for i in range(1, len(parts)))
                    if info.is_dir():
                        directories.add(name)
                    else:
                        files[name] = (info, b"", info.file_size)
                if directories.intersection(files):
                    raise PluginInstallationMaterializationError()
                for relative, (info, _digest, expected_size) in tuple(files.items()):
                    digest = hashlib.sha256()
                    size = 0
                    with archive.open(info, "r") as stream:
                        while True:
                            chunk = stream.read(_CHUNK)
                            if not chunk:
                                break
                            size += len(chunk)
                            if size > expected_size:
                                raise PluginInstallationMaterializationError()
                            digest.update(chunk)
                    if size != expected_size:
                        raise PluginInstallationMaterializationError()
                    files[relative] = (info, digest.digest(), expected_size)
            return body, inspected, (files, directories)
        except PluginInstallationMaterializationError:
            raise
        except Exception:
            raise PluginInstallationMaterializationError() from None

    def _write_archive_members(self, staging: Path, archive_bytes: bytes, entries) -> None:
        files, directories = entries
        try:
            for relative in sorted(directories, key=lambda value: (value.count("/"), value)):
                path = staging.joinpath(*relative.split("/"))
                _directory(path, create=True)
            with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
                by_name = {
                    _canonical_archive_path(info.filename, directory=info.is_dir()): info
                    for info in archive.infolist() if not info.is_dir()
                }
                for relative, (info, expected_digest, expected_size) in files.items():
                    destination = staging.joinpath(*relative.split("/"))
                    _directory(destination.parent)
                    digest = hashlib.sha256()
                    written = 0
                    with archive.open(by_name[relative], "r") as source, destination.open("xb") as sink:
                        while True:
                            chunk = source.read(_CHUNK)
                            if not chunk:
                                break
                            written += len(chunk)
                            if written > expected_size:
                                raise PluginInstallationMaterializationError()
                            digest.update(chunk)
                            sink.write(chunk)
                        sink.flush()
                        os.fsync(sink.fileno())
                    if written != expected_size or not hmac.compare_digest(digest.digest(), expected_digest):
                        raise PluginInstallationMaterializationError()
                    actual = destination.lstat()
                    if (not stat.S_ISREG(actual.st_mode) or _is_reparse(actual)
                            or actual.st_nlink != 1):
                        raise PluginInstallationMaterializationError()
        except PluginInstallationMaterializationError:
            raise
        except Exception:
            raise PluginInstallationMaterializationError() from None

    def _verify_tree(self, root: Path, entries) -> None:
        files, expected_directories = entries
        _directory(root)
        actual_files: set[str] = set()
        actual_directories: set[str] = set()
        stack = [(root, "")]
        try:
            while stack:
                directory, prefix = stack.pop()
                with os.scandir(directory) as children:
                    for child in children:
                        relative = f"{prefix}/{child.name}" if prefix else child.name
                        info = child.stat(follow_symlinks=False)
                        if _is_reparse(info):
                            raise PluginInstallationMaterializationError()
                        if stat.S_ISDIR(info.st_mode):
                            actual_directories.add(relative)
                            stack.append((Path(child.path), relative))
                        elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                            actual_files.add(relative)
                        else:
                            raise PluginInstallationMaterializationError()
            if actual_files != set(files) or actual_directories != expected_directories:
                raise PluginInstallationMaterializationError()
            for relative, (zip_info, expected_digest, expected_size) in files.items():
                path = root.joinpath(*relative.split("/"))
                digest = hashlib.sha256()
                size = 0
                with path.open("rb") as stream:
                    while True:
                        chunk = stream.read(_CHUNK)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > expected_size:
                            raise PluginInstallationMaterializationError()
                        digest.update(chunk)
                if size != expected_size or not hmac.compare_digest(
                        digest.digest(), expected_digest):
                    raise PluginInstallationMaterializationError()
        except PluginInstallationMaterializationError:
            raise
        except Exception:
            raise PluginInstallationMaterializationError() from None
