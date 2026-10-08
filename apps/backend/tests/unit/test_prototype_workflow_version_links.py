"""Approved-version/active-link scan rejects stale projections before Owner PASS."""

import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace as Row

import plm_assistant.modules.prototype.infrastructure.workflow_version_links_repository as module
from plm_assistant.modules.prototype.application.create_version import (
    PrototypeVersionInitialView,
    VersionArtifactRef,
    VersionRequirementRef,
)
from plm_assistant.modules.prototype.application.workflow_scope_lock import (
    PrototypeRootLock,
)


class _One:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self.value


class _Session:
    def __init__(self, *values):
        self.values = iter(values)

    def execute(self, _query):
        return _One(next(self.values))


def _facts():
    project, prototype, version = (uuid.uuid4() for _ in range(3))
    review, round_id, result_id, approver = (uuid.uuid4() for _ in range(4))
    template, template_version = uuid.uuid4(), uuid.uuid4()
    requirement, requirement_version = uuid.uuid4(), uuid.uuid4()
    digest = bytes.fromhex("ab" * 32)
    root = PrototypeRootLock(project, prototype, "ACTIVE", version, 4, None)
    snapshot = PrototypeVersionInitialView(
        version, prototype, project, 1, None, template, template_version,
        (VersionArtifactRef("DOCUMENT_VERSION", uuid.uuid4()),),
        (VersionRequirementRef(requirement, requirement_version),),
        {}, {}, digest.hex(), datetime.now(timezone.utc), "APPROVED", 0,
    )
    version_row = Row(version_state="APPROVED", review_ref=review,
                      review_round_ref=round_id, content_fingerprint=digest)
    approval = Row(current_approved_version_ref=version, review_id=review,
                   review_round_id=round_id, lock_version=3,
                   review_state_result_id=result_id, actor_id=approver)
    manifest = Row(review_state_result_id=result_id, review_id=review,
                   review_round_id=round_id, approved_by=approver,
                   content_fingerprint=digest, declared_artifact_count=1,
                   declared_requirement_count=1, template_id=template,
                   template_version_id=template_version)
    return root, snapshot, version_row, approval, manifest


def _prove(monkeypatch, root, snapshot, version_row, approval, manifest,
           links=()):
    repository = module.SqlAlchemyPrototypeWorkflowVersionLinksRepository()
    monkeypatch.setattr(module, "_session", lambda _tx: _Session(
        version_row, approval, manifest, links,
    ))
    monkeypatch.setattr(repository._versions, "get", lambda *_a, **_k: snapshot)
    monkeypatch.setattr(repository._traces, "manifest_matches",
                        lambda *_a, **_k: True)
    return repository.lock_current_versions_and_links(
        object(), project_id=root.project_id, roots=(root,),
    )


def test_current_approved_version_and_trace_projection_is_lock_input(monkeypatch):
    root, snapshot, version, approval, manifest = _facts()
    proof = _prove(monkeypatch, root, snapshot, version, approval, manifest)
    assert proof is not None
    assert len(proof.versions) == 1
    assert proof.active_links == ()


def test_stale_version_review_or_manifest_fails_closed(monkeypatch):
    for mutation in (
        lambda r, s, v, a, m: replace(r, current_approved_version_ref=uuid.uuid4()),
        lambda r, s, v, a, m: setattr(v, "version_state", "DRAFT"),
        lambda r, s, v, a, m: setattr(a, "review_round_id", uuid.uuid4()),
        lambda r, s, v, a, m: setattr(a, "lock_version", 5),
        lambda r, s, v, a, m: setattr(m, "content_fingerprint", b"z" * 32),
        lambda r, s, v, a, m: setattr(m, "declared_requirement_count", 2),
    ):
        root, snapshot, version, approval, manifest = _facts()
        changed = mutation(root, snapshot, version, approval, manifest)
        if isinstance(changed, PrototypeRootLock):
            root = changed
        assert _prove(monkeypatch, root, snapshot, version, approval, manifest) is None


def test_active_link_to_old_version_fails_closed(monkeypatch):
    root, snapshot, version, approval, manifest = _facts()
    stale = Row(prototype_id=root.prototype_id,
                prototype_version_id=uuid.uuid4(), lock_version=0,
                superseded_by_ref=None)
    assert _prove(monkeypatch, root, snapshot, version, approval, manifest,
                  (stale,)) is None


def test_all_not_required_rejects_unexplained_active_link(monkeypatch):
    project, prototype = uuid.uuid4(), uuid.uuid4()
    from plm_assistant.modules.prototype.application.workflow_scope_lock import (
        PrototypeDecisionLock,
    )
    decision = PrototypeDecisionLock(uuid.uuid4(), (uuid.uuid4(),), uuid.uuid4(),
                                     "No prototype", "No impact", None, None)
    root = PrototypeRootLock(project, prototype, "NOT_REQUIRED", None, 1, decision)
    repository = module.SqlAlchemyPrototypeWorkflowVersionLinksRepository()
    stale = Row(prototype_id=prototype, prototype_version_id=uuid.uuid4(),
                lock_version=0, superseded_by_ref=None)
    monkeypatch.setattr(module, "_session", lambda _tx: _Session((stale,)))
    assert repository.lock_current_versions_and_links(
        object(), project_id=project, roots=(root,),
    ) is None
