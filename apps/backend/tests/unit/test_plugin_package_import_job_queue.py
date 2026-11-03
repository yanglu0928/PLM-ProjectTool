from __future__ import annotations

import uuid

import pytest

from plm_assistant.modules.platform.application.idempotency import IdempotencyScope
from plm_assistant.modules.plugin.application.package_import_job_queue import (
    EnqueuePluginPackageImport,
    PluginPackageImportJobRef,
    PluginPackageImportQueue,
    PluginPackageImportQueueError,
)


class Repository:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def enqueue_import(self, transaction, *, request):
        self.calls.append((transaction, request))
        return self.result


def _scope(key="0123456789abcdef"):
    return IdempotencyScope.from_key(
        actor_id=uuid.uuid4(), project_id=None,
        operation="V1_PLUGIN_PACKAGE_IMPORT", key=key,
    )


def _request(*, scope=None, upload_id=None, digest=b"d" * 32, size=123):
    return EnqueuePluginPackageImport(
        scope=scope or _scope(),
        package_upload_id=upload_id or uuid.uuid4(),
        package_sha256=digest,
        package_size_bytes=size,
        trace_id=uuid.uuid4(),
    )


def test_queue_validates_and_delegates_to_transactional_repository():
    request = _request()
    ref = PluginPackageImportJobRef(
        uuid.uuid4(), uuid.uuid4(), request.package_upload_id,
        request.package_sha256, request.package_size_bytes,
    )
    repository = Repository(ref)
    transaction = object()

    result = PluginPackageImportQueue(repository).enqueue(
        transaction, request=request,
    )

    assert result == ref
    assert repository.calls == [(transaction, request)]


@pytest.mark.parametrize(
    "request",
    [
        _request(scope=_scope("0123456789abcdef")).__class__(
            scope=IdempotencyScope.from_key(
                actor_id=uuid.uuid4(), project_id=None,
                operation="V1_PLUGIN_PACKAGE_IMPORT", key="0123456789abcdef",
            ),
            package_upload_id=uuid.uuid4(),
            package_sha256=b"x" * 31,
            package_size_bytes=123,
            trace_id=uuid.uuid4(),
        ),
        _request(size=0),
        _request(size=256 * 1024 * 1024 + 1),
    ],
)
def test_request_rejects_invalid_package_evidence(request):
    with pytest.raises(PluginPackageImportQueueError) as caught:
        request.__post_init__()
    assert caught.value.code == "VALIDATION_FAILED"


def test_request_rejects_wrong_idempotency_operation():
    scope = IdempotencyScope.from_key(
        actor_id=uuid.uuid4(), project_id=None,
        operation="V1_AI_PROVIDER_CREATE", key="0123456789abcdef",
    )
    with pytest.raises(PluginPackageImportQueueError) as caught:
        _request(scope=scope)
    assert caught.value.code == "VALIDATION_FAILED"


def test_queue_rejects_repository_digest_mismatch():
    request = _request()
    wrong = PluginPackageImportJobRef(
        uuid.uuid4(), uuid.uuid4(), request.package_upload_id,
        b"z" * 32, request.package_size_bytes,
    )
    with pytest.raises(PluginPackageImportQueueError) as caught:
        PluginPackageImportQueue(Repository(wrong)).enqueue(
            object(), request=request,
        )
    assert caught.value.code == "CONFLICT_IDEMPOTENCY"
