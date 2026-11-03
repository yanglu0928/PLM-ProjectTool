from __future__ import annotations

import hashlib
import uuid

import pytest

from plm_assistant.modules.document.infrastructure.local_storage import (
    LocalFileStorage,
    LocalStorageError,
)
from plm_assistant.modules.plugin.application.package_import_spool import (
    PluginPackageImportSpool,
    PluginPackageStageError,
)


def test_package_spool_writes_bounded_chunks_to_private_staging(tmp_path):
    storage = LocalFileStorage(tmp_path)
    payload = b"PK\\x03\\x04 signed plugin archive"
    digest = hashlib.sha256(payload).digest()
    upload_id = uuid.uuid4()

    staged = PluginPackageImportSpool(storage=storage).receive(
        package_upload_id=upload_id,
        chunks=(payload[:5], payload[5:]),
        declared_length=len(payload),
        declared_sha256=digest,
    )

    assert staged.package_upload_id == upload_id
    assert staged.size_bytes == len(payload)
    assert staged.sha256 == digest
    storage.verify_content(
        staged.staging_locator,
        expected_sha256=digest,
        expected_size=len(payload),
        max_bytes=MAX_TEST_BYTES,
    )


MAX_TEST_BYTES = 1024


@pytest.mark.parametrize(
    ("chunks", "length", "digest", "code"),
    [
        ([b"short"], 6, hashlib.sha256(b"short!").digest(), "FILE_INTEGRITY_MISMATCH"),
        ([b"payload!"], 7, hashlib.sha256(b"payload").digest(), "FILE_TOO_LARGE"),
        ([bytearray(b"payload")], 7, hashlib.sha256(b"payload").digest(), "VALIDATION_FAILED"),
    ],
)
def test_package_spool_rejects_invalid_stream_and_removes_its_staging(
    tmp_path, chunks, length, digest, code,
):
    storage = LocalFileStorage(tmp_path)
    upload_id = uuid.uuid4()
    locator, _ = storage.locators(
        scope="GLOBAL", project_id=None, file_object_id=upload_id,
    )

    with pytest.raises(PluginPackageStageError) as caught:
        PluginPackageImportSpool(storage=storage, max_bytes=7).receive(
            package_upload_id=upload_id,
            chunks=chunks,
            declared_length=length,
            declared_sha256=digest,
        )

    assert caught.value.code == code
    with pytest.raises(LocalStorageError):
        storage.verify_content(
            locator, expected_sha256=digest, expected_size=length, max_bytes=7,
        )


def test_package_spool_rejects_declared_size_above_archive_limit(tmp_path):
    spool = PluginPackageImportSpool(storage=LocalFileStorage(tmp_path), max_bytes=7)
    with pytest.raises(PluginPackageStageError) as caught:
        spool.receive(
            package_upload_id=uuid.uuid4(),
            chunks=[b"payload"],
            declared_length=8,
            declared_sha256=hashlib.sha256(b"payload!").digest(),
        )
    assert caught.value.code == "FILE_TOO_LARGE"
