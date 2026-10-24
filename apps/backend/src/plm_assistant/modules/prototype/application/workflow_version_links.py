"""Current approved PrototypeVersion and Link inputs for Workflow qualification."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from .create_version import PrototypeVersionInitialView
from .requirement_links import RequirementPrototypeLinkView


@dataclass(frozen=True, slots=True)
class PrototypeWorkflowVersionLock:
    snapshot: PrototypeVersionInitialView
    review_id: uuid.UUID
    review_round_id: uuid.UUID
    approval_result_id: uuid.UUID
    approved_by: uuid.UUID


@dataclass(frozen=True, slots=True)
class PrototypeWorkflowVersionLinksLock:
    versions: tuple[PrototypeWorkflowVersionLock, ...]
    active_links: tuple[RequirementPrototypeLinkView, ...]
