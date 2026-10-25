"""Workflow artifact proof requires actual verified bytes, not DB metadata only."""

import hashlib
import uuid
from types import SimpleNamespace as Row

import plm_assistant.modules.document.infrastructure.prototype_workflow_integrity as module
from plm_assistant.modules.document.application.prototype_artifact_proof import (
    PrototypeVersionDocumentArtifactProof,
)
from plm_assistant.modules.document.application.prototype_workflow_integrity import (
    PrototypeWorkflowArtifactIntegrityProof,
)


class _Result:
    def __init__(self, value):
        self.value = value

    def one_or_none(self):
        return self.value


class _Session:
    def __init__(self, row):
        self.row = row

    def in_transaction(self):
        return True

    def execute(self, _statement):
        return _Result(self.row)


class _Storage:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def verify_content(self, _locator, **_kwargs):
        self.calls += 1
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def _facts():
    project, document, version = (uuid.uuid4() for _ in range(3))
    content = b"fixed document bytes"
    digest = hashlib.sha256(content).digest()
    metadata = PrototypeVersionDocumentArtifactProof(
        version, document, "PROJECT", project, digest.hex(), len(content),
        "application/pdf",
    )
    db_version = Row(scope="PROJECT", project_id=project,
                     size_bytes=len(content), detected_mime="application/pdf",
                     content_sha256=digest)
    file = Row(scope="PROJECT", project_id=project,
               size_bytes=len(content), detected_mime="application/pdf",
               sha256=digest, storage_locator="documents/fixed.bin")
    physical = Row(sha256=digest, size_bytes=len(content))
    return project, metadata, db_version, file, physical


def _prove(monkeypatch, project, metadata, version, file, storage):
    monkeypatch.setattr(module, "Session", _Session)
    return module.SqlAlchemyPrototypeWorkflowArtifactIntegrityProof(
        storage=storage).prove_actual_content(
            Row(session=_Session((version, file))), project_id=project,
            metadata=metadata,
        )


def test_actual_matching_content_is_required(monkeypatch):
    project, metadata, version, file, physical = _facts()
    storage = _Storage(physical)
    result = _prove(monkeypatch, project, metadata, version, file, storage)
    assert type(result) is PrototypeWorkflowArtifactIntegrityProof
    assert storage.calls == 1


def test_metadata_drift_rejects_before_file_read(monkeypatch):
    project, metadata, version, file, physical = _facts()
    file.sha256 = b"x" * 32
    storage = _Storage(physical)
    assert _prove(monkeypatch, project, metadata, version, file, storage) is None
    assert storage.calls == 0


def test_missing_or_tampered_file_fails_closed(monkeypatch):
    project, metadata, version, file, physical = _facts()
    assert _prove(monkeypatch, project, metadata, version, file,
                  _Storage(OSError("missing"))) is None
    assert _prove(monkeypatch, project, metadata, version, file,
                  _Storage(Row(sha256=b"z" * 32,
                               size_bytes=metadata.size_bytes))) is None
    assert _prove(monkeypatch, uuid.uuid4(), metadata, version, file,
                  _Storage(physical)) is None
