from __future__ import annotations

import copy
import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.plugin.application.retirement_owner import (
    PluginInstallationRetirementContext, PluginInstallationRetirementOwner,
    PluginInstallationRetirementOwnerError, RetirePluginInstallationCommand,
)


class _Repo:
    def __init__(self, state="ENABLED"):
        self.installation_id = uuid.uuid4()
        self.package_id = uuid.uuid4()
        self.plugin_id = "synthetic.echo"
        self.state = state
        self.version = 7
        self.ops = (("document.export", "document.render")
                    if state == "ENABLED" else ())
        self.history = []
        self.authorized = False
        self.applied = False

    def identify_plugin(self, _tx, *, installation_id):
        return self.plugin_id if installation_id == self.installation_id else None

    def lock_plugin(self, _tx, *, plugin_id):
        self.locked_plugin = plugin_id

    def load_context(self, _tx, *, installation_id):
        if installation_id != self.installation_id:
            return None
        return PluginInstallationRetirementContext(
            self.plugin_id, self.installation_id, self.package_id,
            self.state, self.version, self.ops)

    def authorize_owner_writes(self, _tx):
        self.authorized = True

    def apply_retirement(self, _tx, *, context, actor_id, changed_at):
        self.ops = ()
        self.state = "RETIRED"
        self.version += 1
        self.applied = True

    def append_disabled_operation_history(self, _tx, *, installation_id,
        package_id, plugin_id, operation_id, actor_id, trace_id, audit_event_id):
        self.history.append(operation_id)


class _Audit:
    def __init__(self, fail_on=None):
        self.events = []
        self.fail_on = fail_on

    def append(self, _tx, event):
        if self.fail_on == len(self.events) + 1:
            raise RuntimeError("synthetic audit unavailable")
        self.events.append(event)
        return uuid.uuid4()


class _Uow:
    def __init__(self, repo, audit):
        self.repo = repo
        self.audit = audit
        self.committed = False

    def __enter__(self):
        self.before = copy.deepcopy((
            self.repo.state, self.repo.version, self.repo.ops, self.repo.history,
            self.repo.authorized, self.repo.applied, self.audit.events))
        return self

    def commit(self):
        self.committed = True

    def __exit__(self, exc_type, _value, _tb):
        if exc_type is not None or not self.committed:
            (self.repo.state, self.repo.version, self.repo.ops, self.repo.history,
             self.repo.authorized, self.repo.applied, self.audit.events) = self.before
        return False


class PluginInstallationRetirementOwnerTests(unittest.TestCase):
    def setUp(self):
        self.repo = _Repo()
        self.audit = _Audit()
        self.owner = self._owner()
        self.command = RetirePluginInstallationCommand(
            self.repo.installation_id, self.repo.version, uuid.uuid4(), uuid.uuid4())

    def _owner(self):
        return PluginInstallationRetirementOwner(
            unit_of_work=lambda: _Uow(self.repo, self.audit),
            repository=self.repo, audit=self.audit,
            clock=lambda: datetime(2026, 11, 4, tzinfo=timezone.utc))

    def test_enabled_installation_retires_and_disables_every_operation(self):
        result = self.owner.retire(self.command)
        self.assertEqual(result.installation_state, "RETIRED")
        self.assertEqual(result.lock_version, 8)
        self.assertEqual(result.disabled_operations,
                         ("document.export", "document.render"))
        self.assertEqual(self.repo.state, "RETIRED")
        self.assertEqual(self.repo.ops, ())
        self.assertEqual(self.repo.history,
                         ["document.export", "document.render"])
        self.assertEqual(len(self.audit.events), 3)
        self.assertTrue(all(x.reason_code == "INSTALLATION_RETIRED"
                            for x in self.audit.events))
        self.assertEqual(self.audit.events[-1].action,
                         "PLUGIN_INSTALLATION_RETIRE")
        self.assertTrue(self.repo.authorized)

    def test_installed_without_operations_retires_with_installation_audit(self):
        self.repo = _Repo(state="INSTALLED")
        self.owner = self._owner()
        command = RetirePluginInstallationCommand(
            self.repo.installation_id, self.repo.version, uuid.uuid4(), uuid.uuid4())
        result = self.owner.retire(command)
        self.assertEqual(result.disabled_operations, ())
        self.assertEqual(self.repo.state, "RETIRED")
        self.assertEqual(len(self.audit.events), 1)

    def test_stale_version_rejected_without_mutation(self):
        stale = RetirePluginInstallationCommand(
            self.command.plugin_installation_id, self.command.expected_lock_version - 1,
            self.command.actor_id, self.command.trace_id)
        with self.assertRaisesRegex(PluginInstallationRetirementOwnerError,
                                    "PLUGIN_LOCK_VERSION_CONFLICT"):
            self.owner.retire(stale)
        self.assertEqual(self.repo.state, "ENABLED")
        self.assertEqual(self.repo.ops, ("document.export", "document.render"))
        self.assertEqual(self.audit.events, [])

    def test_retired_installation_rejected_without_new_audit(self):
        self.repo.state = "RETIRED"
        with self.assertRaisesRegex(PluginInstallationRetirementOwnerError,
                                    "PLUGIN_RETIREMENT_NOT_ALLOWED"):
            self.owner.retire(self.command)
        self.assertEqual(self.audit.events, [])

    def test_audit_failure_rolls_back_all_retirement_facts(self):
        self.audit.fail_on = 2
        with self.assertRaisesRegex(PluginInstallationRetirementOwnerError,
                                    "PLUGIN_RETIREMENT_STORE_UNAVAILABLE"):
            self.owner.retire(self.command)
        self.assertEqual(self.repo.state, "ENABLED")
        self.assertEqual(self.repo.version, 7)
        self.assertEqual(self.repo.ops, ("document.export", "document.render"))
        self.assertEqual(self.repo.history, [])
        self.assertEqual(self.audit.events, [])

    def test_incompatible_installation_can_be_retired_without_revalidation(self):
        self.repo = _Repo(state="INCOMPATIBLE")
        self.owner = self._owner()
        command = RetirePluginInstallationCommand(
            self.repo.installation_id, self.repo.version, uuid.uuid4(), uuid.uuid4())
        self.assertEqual(self.owner.retire(command).installation_state, "RETIRED")

    def test_inconsistent_enabled_operation_context_fails_closed(self):
        self.repo.ops = ()
        with self.assertRaisesRegex(PluginInstallationRetirementOwnerError,
                                    "PLUGIN_RETIREMENT_NOT_ALLOWED"):
            self.owner.retire(self.command)
        self.assertFalse(self.repo.applied)

    def test_naive_clock_is_rejected_before_writes(self):
        self.owner = PluginInstallationRetirementOwner(
            unit_of_work=lambda: _Uow(self.repo, self.audit),
            repository=self.repo, audit=self.audit,
            clock=lambda: datetime(2026, 11, 4))
        with self.assertRaisesRegex(PluginInstallationRetirementOwnerError,
                                    "PLUGIN_RETIREMENT_INVALID"):
            self.owner.retire(self.command)
        self.assertFalse(self.repo.applied)

    def test_history_failure_rolls_back_operation_history_and_audit(self):
        class HistoryFailureRepo(_Repo):
            def append_disabled_operation_history(self, *_args, **_kwargs):
                raise RuntimeError("synthetic history unavailable")
        self.repo = HistoryFailureRepo()
        self.audit = _Audit()
        self.owner = self._owner()
        command = RetirePluginInstallationCommand(
            self.repo.installation_id, self.repo.version, uuid.uuid4(), uuid.uuid4())
        with self.assertRaisesRegex(PluginInstallationRetirementOwnerError,
                                    "PLUGIN_RETIREMENT_STORE_UNAVAILABLE"):
            self.owner.retire(command)
        self.assertEqual(self.repo.state, "ENABLED")
        self.assertEqual(self.repo.ops, ("document.export", "document.render"))
        self.assertEqual(self.audit.events, [])
        self.assertEqual(self.repo.history, [])


if __name__ == "__main__":
    unittest.main()
