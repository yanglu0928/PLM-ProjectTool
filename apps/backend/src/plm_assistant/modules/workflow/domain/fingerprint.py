"""Stable content fingerprint for a fixed Workflow definition."""

import hashlib
import json

from .definition import WorkflowDefinition, WorkflowDefinitionError


def definition_fingerprint(definition: WorkflowDefinition) -> bytes:
    if type(definition) is not WorkflowDefinition:
        raise WorkflowDefinitionError()
    payload = [definition.version, [[
        stage.stage_key, stage.order, stage.gate_policy_ref,
        [[item.item_key, item.required, item.evidence_policy_ref,
          item.review_policy_ref] for item in stage.checklist_items],
    ] for stage in definition.stages]]
    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=True, separators=(",", ":"), allow_nan=False,
    ).encode("ascii")).digest()
