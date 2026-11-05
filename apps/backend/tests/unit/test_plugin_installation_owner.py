from __future__ import annotations

import copy
import hashlib
import unittest
import uuid

from plm_assistant.modules.plugin.application.installation_owner import (
    InstallablePluginPackage,
    PluginPackageArchiveProof,
    PluginInstallationEvidence,
    PluginInstallationIdentity,
    PluginInstallationOwner,
    PluginInstallationOwnerError,
    RecordPluginInstallationCommand,
)


class _Repository:
    def __init__(self):
        self.package_id = uuid.uuid4()
        self.actor = uuid.uuid4()
        self.package = InstallablePluginPackage(
            self.package_id, "synthetic.echo", hashlib.sha256(b"synthetic package").digest(),
            {"schema_version": "plm.plugin.manifest.v1"},
            "1.0.0", b"s" * 64, "test-key:fixture",
            "host.platforms.v1", "VERIFIED",
        )
        self.installations = {}
        self.validations = []
        self.authorized = False

    def lock_installation(self, _tx, *, installation_id):
        return None

    def find_installation(self, _tx, *, installation_id):
        return self.installations.get(installation_id)

    def find_verified_package(self, _tx, *, package_id):
        return self.package if package_id == self.package_id else None

    def authorize_owner_inserts(self, _tx):
        self.authorized = True

    def create_installed(self, _tx, *, installation_id, package, actor_id, runtime_snapshot):
        value = PluginInstallationIdentity(
            installation_id, package.plugin_package_id, package.plugin_id_normalized,
            actor_id, "INSTALLED", copy.deepcopy(runtime_snapshot),
        )
        self.installations[installation_id] = value
        return value

    def append_runtime_validation(self, _tx, *, installation_id, actor_id, runtime_snapshot):
        self.validations.append((installation_id, actor_id, copy.deepcopy(runtime_snapshot)))


class _ArchiveEvidence:
    def __init__(self, repo):
        self.repo = repo
        self.response = PluginPackageArchiveProof(
            repo.package_id, repo.package.plugin_id_normalized,
            repo.package.plugin_version, repo.package.package_sha256, True,
        )
        self.calls = 0

    def inspect_registered_package(self, _package):
        self.calls += 1
        return self.response


class _Evidence:
    def __init__(self, repo):
        self.repo = repo
        self.response = PluginInstallationEvidence(
            repo.package_id, repo.package.package_sha256, True, True,
            {"schema_version":"1", "os":"windows-11", "architecture":"x86_64",
             "python_version":"3.13.15", "dependency_versions":{"example":"1.2.3"}},
        )
        self.calls = 0

    def inspect_installed_package(self, _package):
        self.calls += 1
        return self.response


class _Audit:
    def __init__(self, fail=False):
        self.events = []
        self.fail = fail

    def append(self, _tx, event):
        if self.fail:
            raise RuntimeError("synthetic audit failure")
        self.events.append(event)


class _Uow:
    def __init__(self, repository, audit):
        self.repository, self.audit = repository, audit
        self.committed = False

    def __enter__(self):
        self.before = copy.deepcopy(
            (self.repository.installations, self.repository.validations, self.audit.events)
        )
        return self

    def commit(self):
        self.committed = True

    def __exit__(self, exc_type, _value, _traceback):
        if exc_type is not None or not self.committed:
            (self.repository.installations, self.repository.validations,
             self.audit.events) = self.before
        return False


class PluginInstallationOwnerTests(unittest.TestCase):
    def setUp(self):
        self.repo = _Repository()
        self.evidence = _Evidence(self.repo)
        self.archive_evidence = _ArchiveEvidence(self.repo)
        self.audit = _Audit()
        self.owner = self._owner()
        self.command = RecordPluginInstallationCommand(
            uuid.uuid4(), self.repo.package_id, self.repo.actor, uuid.uuid4(),
        )

    def _owner(self):
        return PluginInstallationOwner(
            unit_of_work=lambda: _Uow(self.repo, self.audit),
            evidence=self.evidence, archive_evidence=self.archive_evidence,
            repository=self.repo, audit=self.audit,
        )

    def test_records_only_observed_exact_compatible_installation_atomically(self):
        result = self.owner.record(self.command)
        self.assertEqual(result.installation_state, "INSTALLED")
        self.assertEqual(result.plugin_package_id, self.repo.package_id)
        self.assertEqual(len(self.repo.validations), 1)
        self.assertEqual(len(self.audit.events), 1)
        self.assertTrue(self.repo.authorized)
        self.assertEqual(self.archive_evidence.calls, 1)
        self.assertEqual(self.evidence.calls, 1)

    def test_same_id_and_actor_replay_is_idempotent_without_second_audit(self):
        first = self.owner.record(self.command)
        second = self.owner.record(self.command)
        self.assertEqual(first, second)
        self.assertEqual(self.archive_evidence.calls, 1)
        self.assertEqual(self.evidence.calls, 1)
        self.assertEqual(len(self.repo.validations), 1)
        self.assertEqual(len(self.audit.events), 1)

    def test_same_id_with_different_actor_or_package_is_conflict(self):
        self.owner.record(self.command)
        conflict = RecordPluginInstallationCommand(
            self.command.plugin_installation_id, self.repo.package_id,
            uuid.uuid4(), self.command.trace_id,
        )
        with self.assertRaisesRegex(PluginInstallationOwnerError, "PLUGIN_INSTALLATION_ID_CONFLICT"):
            self.owner.record(conflict)

    def test_missing_archive_evidence_fails_before_host_probe_or_writes(self):
        self.archive_evidence.response = None
        with self.assertRaisesRegex(
            PluginInstallationOwnerError,
            "PLUGIN_PACKAGE_ARCHIVE_EVIDENCE_UNAVAILABLE",
        ):
            self.owner.record(self.command)
        self.assertEqual(self.archive_evidence.calls, 1)
        self.assertEqual(self.evidence.calls, 0)
        self.assertEqual(self.repo.installations, {})
        self.assertEqual(self.repo.validations, [])
        self.assertEqual(self.audit.events, [])

    def test_mismatched_archive_evidence_fails_before_host_probe_or_writes(self):
        proof = self.archive_evidence.response
        self.archive_evidence.response = PluginPackageArchiveProof(
            proof.plugin_package_id, proof.plugin_id_normalized,
            proof.plugin_version, b"x" * 32, True,
        )
        with self.assertRaisesRegex(
            PluginInstallationOwnerError,
            "PLUGIN_PACKAGE_ARCHIVE_EVIDENCE_INVALID",
        ):
            self.owner.record(self.command)
        self.assertEqual(self.evidence.calls, 0)
        self.assertEqual(self.repo.installations, {})
        self.assertEqual(self.audit.events, [])

    def test_missing_or_mismatched_package_evidence_fails_closed(self):
        self.evidence.response = PluginInstallationEvidence(
            self.repo.package_id, b"x" * 32, True, True,
            {"schema_version":"1", "os":"windows-11", "architecture":"x86_64",
             "python_version":"3.13.15", "dependency_versions":{}},
        )
        with self.assertRaisesRegex(PluginInstallationOwnerError, "PLUGIN_INSTALLATION_EVIDENCE_INVALID"):
            self.owner.record(self.command)
        self.assertEqual(self.repo.installations, {})
        self.assertEqual(self.repo.validations, [])
        self.assertEqual(self.audit.events, [])

    def test_incompatible_runtime_fails_without_install_fact(self):
        evidence = self.evidence.response
        self.evidence.response = PluginInstallationEvidence(
            evidence.plugin_package_id, evidence.installed_package_sha256, True, False,
            evidence.runtime_snapshot,
        )
        with self.assertRaisesRegex(PluginInstallationOwnerError, "PLUGIN_RUNTIME_INCOMPATIBLE"):
            self.owner.record(self.command)
        self.assertEqual(self.repo.installations, {})

    def test_audit_failure_rolls_back_all_installation_rows(self):
        self.audit.fail = True
        with self.assertRaisesRegex(PluginInstallationOwnerError, "PLUGIN_INSTALLATION_STORE_UNAVAILABLE"):
            self.owner.record(self.command)
        self.assertEqual(self.repo.installations, {})
        self.assertEqual(self.repo.validations, [])
        self.assertEqual(self.audit.events, [])

    def test_runtime_snapshot_rejects_absolute_path_or_unknown_fields(self):
        evidence = self.evidence.response
        snapshot = dict(evidence.runtime_snapshot)
        snapshot["install_path"] = "D:\\plugins\\example"
        self.evidence.response = PluginInstallationEvidence(
            evidence.plugin_package_id, evidence.installed_package_sha256, True, True, snapshot,
        )
        with self.assertRaisesRegex(PluginInstallationOwnerError, "PLUGIN_INSTALLATION_EVIDENCE_INVALID"):
            self.owner.record(self.command)


if __name__ == "__main__":
    unittest.main()
