from __future__ import annotations

import copy
import uuid
import unittest

from plm_assistant.modules.platform.application.configuration_commands import (
    ActivateConfigurationVersion,
    ConfigurationCommandError,
    ConfigurationCommandService,
    ConfigurationSnapshot,
    ConfigurationVersionSnapshot,
    CreateConfigurationVersion,
)
from plm_assistant.modules.platform.domain.configuration import (
    ConfigurationValueError,
    ConfigurationValuePolicy,
    ConfigurationValueType,
)
from plm_assistant.modules.platform.application.errors import COMMON_ERRORS


CONFIG_ID = uuid.uuid4()
ACTOR_ID = uuid.uuid4()
POLICY = ConfigurationValuePolicy(
    "app.mode", 1, ConfigurationValueType.STRING, ("enabled", "disabled")
)


class FakeStore:
    def __init__(self) -> None:
        self.root = ConfigurationSnapshot(CONFIG_ID, "app.mode", 0, None)
        self.versions: list[dict] = []
        self.audit: list[dict] = []


class FakeUow:
    def __init__(self, store: FakeStore) -> None:
        self.store = store
        self.working = copy.deepcopy(store)
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self) -> None:
        self.store.root = self.working.root
        self.store.versions = self.working.versions
        self.store.audit = self.working.audit
        self.committed = True

    def rollback(self) -> None:
        pass


class FakeRepo:
    def lock(self, uow, configuration_id):
        return uow.working.root if configuration_id == CONFIG_ID else None

    def latest(self, uow, configuration_id):
        rows = uow.working.versions
        return None if not rows else ConfigurationVersionSnapshot(
            rows[-1]["version_id"], rows[-1]["version_no"]
        )

    def get_version(self, uow, configuration_id, version_no):
        for row in uow.working.versions:
            if row["version_no"] == version_no:
                return ConfigurationVersionSnapshot(row["version_id"], version_no)
        return None

    def add_version(self, uow, **kwargs):
        uow.working.versions.append(kwargs)

    def update_root(self, uow, *, configuration_id, expected_lock_version,
                    actor_id, active_version_id=None):
        root = uow.working.root
        if root.lock_version != expected_lock_version:
            return False
        uow.working.root = ConfigurationSnapshot(
            root.configuration_id, root.config_key, root.lock_version + 1,
            active_version_id if active_version_id is not None else root.active_version_id,
        )
        return True


class FakeAccess:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def require_deployment_write(self, uow, actor_id):
        if not self.allowed:
            raise ConfigurationCommandError("RESOURCE_NOT_FOUND")


class FakeAudit:
    def __init__(self, fail=False):
        self.fail = fail

    def append(self, uow, **kwargs):
        if self.fail:
            raise RuntimeError("audit unavailable")
        uow.working.audit.append(kwargs)


class ConfigurationCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = FakeStore()
        self.access = FakeAccess()
        self.audit = FakeAudit()
        self.service = self._service()

    def _service(self, policies=None):
        return ConfigurationCommandService(
            unit_of_work=lambda: FakeUow(self.store), repository=FakeRepo(),
            access=self.access, audit=self.audit,
            policies={"app.mode": POLICY} if policies is None else policies,
        )

    def _create(self, value="enabled", lock=0, schema=1):
        return self.service.create_version(CreateConfigurationVersion(
            CONFIG_ID, ACTOR_ID, lock, schema, value
        ))

    def test_version_numbers_increase_and_history_is_preserved(self):
        first = self._create()
        second = self._create("disabled", lock=1)
        self.assertEqual((first.version_no, second.version_no), (1, 2))
        self.assertEqual(self.store.versions[1]["supersedes_version_id"], first.version_id)
        self.assertEqual(len(self.store.audit), 2)
        self.assertEqual(self.store.root.lock_version, 2)

    def test_activation_moves_only_root_pointer(self):
        first = self._create()
        second = self._create("disabled", lock=1)
        result = self.service.activate_version(ActivateConfigurationVersion(
            CONFIG_ID, ACTOR_ID, 2, 1
        ))
        self.assertEqual(result.version_id, first.version_id)
        self.assertEqual(self.store.root.active_version_id, first.version_id)
        self.assertEqual(self.store.versions[1]["version_id"], second.version_id)
        self.assertEqual(len(self.store.audit), 3)

    def test_stale_lock_rejects_without_write(self):
        self._create()
        with self.assertRaisesRegex(ConfigurationCommandError, "CONFLICT_VERSION"):
            self._create(lock=0)
        self.assertEqual(len(self.store.versions), 1)

    def test_unauthorized_actor_cannot_write(self):
        self.access.allowed = False
        with self.assertRaises(ConfigurationCommandError):
            self._create()
        self.assertEqual(self.store.versions, [])

    def test_audit_failure_rolls_back_business_write(self):
        self.audit.fail = True
        with self.assertRaisesRegex(ConfigurationCommandError, "SYSTEM_UNAVAILABLE"):
            self._create()
        self.assertEqual(self.store.versions, [])
        self.assertEqual(self.store.root.lock_version, 0)

    def test_activation_audit_failure_rolls_back_pointer(self):
        self._create()
        self.audit.fail = True
        with self.assertRaisesRegex(ConfigurationCommandError, "SYSTEM_UNAVAILABLE"):
            self.service.activate_version(ActivateConfigurationVersion(
                CONFIG_ID, ACTOR_ID, 1, 1
            ))
        self.assertIsNone(self.store.root.active_version_id)
        self.assertEqual(self.store.root.lock_version, 1)

    def test_unknown_policy_and_unlisted_value_are_denied(self):
        self.service = self._service({})
        with self.assertRaisesRegex(ConfigurationCommandError, "PLATFORM_SENSITIVE_VALUE_FORBIDDEN"):
            self._create()
        self.service = self._service()
        with self.assertRaisesRegex(ConfigurationCommandError, "PLATFORM_SENSITIVE_VALUE_FORBIDDEN"):
            self._create("client-secret")
        self.assertEqual(self.store.versions, [])

    def test_schema_mismatch_and_wrong_type_are_denied(self):
        for value, schema in (("enabled", 2), (True, 1), (123, 1)):
            with self.assertRaisesRegex(ConfigurationCommandError, "PLATFORM_SENSITIVE_VALUE_FORBIDDEN"):
                self._create(value=value, schema=schema)
        self.assertEqual(self.store.versions, [])

    def test_missing_or_repeated_activation_is_rejected(self):
        with self.assertRaisesRegex(ConfigurationCommandError, "RESOURCE_NOT_FOUND"):
            self.service.activate_version(ActivateConfigurationVersion(
                CONFIG_ID, ACTOR_ID, 0, 1
            ))
        self._create()
        self.service.activate_version(ActivateConfigurationVersion(
            CONFIG_ID, ACTOR_ID, 1, 1
        ))
        with self.assertRaisesRegex(ConfigurationCommandError, "CONFLICT_STATE"):
            self.service.activate_version(ActivateConfigurationVersion(
                CONFIG_ID, ACTOR_ID, 2, 1
            ))

    def test_command_repr_excludes_value(self):
        command = CreateConfigurationVersion(CONFIG_ID, ACTOR_ID, 0, 1, "client-secret")
        self.assertNotIn("client-secret", repr(command))

    def test_sensitive_value_error_matches_frozen_api_contract(self):
        self.assertEqual(
            COMMON_ERRORS["PLATFORM_SENSITIVE_VALUE_FORBIDDEN"].status_code, 422
        )


class ConfigurationPolicyTests(unittest.TestCase):
    def test_strict_integer_boolean_and_json_shapes(self):
        for kind, allowed, rejected in (
            (ConfigurationValueType.INTEGER, (5,), True),
            (ConfigurationValueType.BOOLEAN, (True,), 1),
            (ConfigurationValueType.JSON, ({"flag": True},), {"flag": False}),
        ):
            policy = ConfigurationValuePolicy("app.safe", 1, kind, allowed)
            self.assertEqual(len(policy.fingerprint(schema_version=1, value=allowed[0])), 32)
            with self.assertRaises(ConfigurationValueError):
                policy.fingerprint(schema_version=1, value=rejected)

    def test_sensitive_key_and_invalid_policy_are_rejected(self):
        for key in ("app.secret", "app.api_key", "APP.MODE", "single"):
            with self.assertRaises(ConfigurationValueError):
                ConfigurationValuePolicy(key, 1, ConfigurationValueType.STRING, ("yes",))


if __name__ == "__main__":
    unittest.main()
