"""Document-owned Audit bytes; caller separately proves Root, authority and Lease."""
from contextlib import contextmanager
import os
from .local_storage import LocalFileStorage, LocalStorageError
from ..application.audit_export_storage import (
    AuditFileCoordinate, AuditFileContent, AuditFileStorageError, MAX_AUDIT_FILE_BYTES,
)


class _BoundedSink:
    def __init__(self, stream):
        self._stream = stream
        self._size = 0
        self.failed = False

    def write(self, data):
        if self.failed:
            raise AuditFileStorageError()
        if type(data) is not bytes:
            self.failed = True
            raise AuditFileStorageError()
        if self._size + len(data) > MAX_AUDIT_FILE_BYTES:
            self.failed = True
            raise AuditFileStorageError("FILE_SIZE_EXCEEDED")
        try:
            count = self._stream.write(data)
        except (OSError, ValueError):
            self.failed = True
            raise AuditFileStorageError() from None
        if type(count) is not int or count != len(data):
            self.failed = True
            raise AuditFileStorageError()
        self._size += count
        return count


def _locators(coordinate):
    if type(coordinate) is not AuditFileCoordinate:
        raise AuditFileStorageError()
    coordinate.__post_init__()
    base = "deployment" if coordinate.scope == "DEPLOYMENT" else "projects/" + coordinate.project_id.hex
    final = f"generated/audit/{base}/objects/{coordinate.file_id.hex[:2]}/{coordinate.file_id.hex}"
    return "temp/" + final, final


class LocalAuditExportFileStorage:
    def __init__(self, storage: LocalFileStorage):
        if not isinstance(storage, LocalFileStorage):
            raise ValueError("Local storage is required")
        self._storage = storage

    def open_snapshot(self,expected):
        (_,final),arguments=self._expected(expected)
        try:
            return self._storage.open_audit_export_snapshot(final,expected_sha256=arguments['expected_sha256'],
                expected_size=arguments['expected_size'])
        except LocalStorageError:raise AuditFileStorageError() from None

    @contextmanager
    def staging_sink(self, coordinate):
        stage, final = _locators(coordinate)
        try:
            # This is only an absence probe, not a content/ownership proof.
            shape = self._storage.inspect_recovery(stage, final, expected_sha256=b'\0'*32,
                expected_size=0, max_bytes=MAX_AUDIT_FILE_BYTES).shape
            if shape != "NONE":
                raise AuditFileStorageError()
            # Writer lock lives until close. Existing same-ID files are not reopened.
            with self._storage.reserve_staging(stage) as stream:
                sink = _BoundedSink(stream)
                yield sink
                if sink.failed:
                    raise AuditFileStorageError()
                stream.flush()
                os.fsync(stream.fileno())
        except (LocalStorageError, OSError):
            raise AuditFileStorageError() from None
        # No delete on failure; caller's recorded attempt controls future recovery.

    @staticmethod
    def _expected(expected):
        if type(expected) is not AuditFileContent:
            raise AuditFileStorageError()
        expected.__post_init__()
        return _locators(expected.coordinate), dict(expected_sha256=expected.sha256,
            expected_size=expected.size_bytes, max_bytes=MAX_AUDIT_FILE_BYTES)

    def verify_staged(self, expected):
        (stage, _), arguments = self._expected(expected)
        try:
            proof = self._storage.verify_content(stage, **arguments)
            if (proof.locator, proof.sha256, proof.size_bytes) != (stage, expected.sha256, expected.size_bytes):
                raise AuditFileStorageError()
        except LocalStorageError:
            raise AuditFileStorageError() from None
        return expected

    def inspect(self, expected):
        (stage, final), arguments = self._expected(expected)
        try:
            return self._storage.inspect_recovery(stage, final, **arguments).shape
        except LocalStorageError:
            raise AuditFileStorageError() from None

    def promote(self, expected, *, mode="new"):
        (stage, final), arguments = self._expected(expected)
        if type(mode) is not str or mode not in ("new", "final_only", "linked_pair"):
            raise AuditFileStorageError()
        method = {"new": self._storage.publish_verified,
            "final_only": self._storage.recover_verified_final,
            "linked_pair": self._storage.recover_linked_pair}[mode]
        try:
            proof = method(stage, final, **arguments)
            if (proof.locator, proof.sha256, proof.size_bytes) != (final, expected.sha256, expected.size_bytes):
                raise AuditFileStorageError()
        except LocalStorageError:
            raise AuditFileStorageError() from None
        return expected
