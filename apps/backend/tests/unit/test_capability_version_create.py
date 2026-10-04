from __future__ import annotations

import importlib
import inspect
import unittest
import uuid
from dataclasses import replace
from unittest.mock import patch

from plm_assistant.modules.capability.application.create_version import (
    CapabilityItemDraft, CapabilityVersionCreateError,
    CapabilityVersionCreateService, CreateCapabilityVersion,
)
from plm_assistant.modules.capability.application.source_validation import (
    CapabilityDocumentRef,
)


def _item() -> CapabilityItemDraft:
    return CapabilityItemDraft(
        uuid.uuid4(), "PLM.DOCUMENT.VERSION", "PLM", "Document", "Versioning",
        "Document versioning", "Immutable document versions",
        "GLOBAL standards only", ("PostgreSQL 18",), ("DOC-V1",),
        "AVAILABLE", (CapabilityDocumentRef(uuid.uuid4(), uuid.uuid4()),),
        (uuid.uuid4(),),
    )


class CapabilityVersionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.command = CreateCapabilityVersion(
            b"s" * 32, b"c" * 32, uuid.uuid4(), uuid.uuid4(), 0,
            (_item(),), str(uuid.uuid4()),
        )
        self.service = CapabilityVersionCreateService(
            unit_of_work=lambda: None, access=object(), license_guard=object(),
            sources=object(), evidence=object(), repository=object(),
            receipts=object(), audit=object(),
        )

    def test_untrusted_aggregate_fails_before_io(self) -> None:
        item = self.command.items[0]
        changes = (
            {"session_token": b"short"}, {"csrf_token": b"short"},
            {"trace_id": uuid.UUID(int=0)}, {"baseline_id": uuid.UUID(int=0)},
            {"expected_lock_version": -1}, {"items": ()},
            {"items": (replace(item, capability_code="lower"),)},
            {"items": (replace(item, evidence_refs=()),)},
            {"items": (replace(item, prerequisites=("duplicate", "duplicate")),)},
            {"idempotency_key": "short"},
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises(
                    CapabilityVersionCreateError) as caught:
                self.service.create(replace(self.command, **change))
            self.assertEqual(caught.exception.code, "VALIDATION_FAILED")

    def test_tokens_key_and_content_fingerprint_are_not_repr_exposed(self) -> None:
        view = repr(self.command)
        self.assertNotIn("s" * 32, view)
        self.assertNotIn("c" * 32, view)
        self.assertNotIn(self.command.idempotency_key, view)

    def test_schema0092_only_opens_metadata_stable_lock_increment(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261005_0092_capability_version_owner"
        )
        self.assertEqual(migration.down_revision, "20261005_0091")
        sql = migration._VERSION_OWNER_GUARD
        for required in (
            "NEW.source_collection_ref IS DISTINCT FROM OLD.source_collection_ref",
            "NEW.current_approved_version_ref IS DISTINCT FROM OLD.current_approved_version_ref",
            "NEW.lock_version<>OLD.lock_version+1",
            "Capability version content is immutable",
        ):
            self.assertIn(required, sql)

    def test_schema0092_downgrade_is_offline_closed_and_history_safe(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261005_0092_capability_version_owner"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline Capability"):
                migration.downgrade()
        execute.assert_not_called()
        self.assertIn("Capability history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
