from __future__ import annotations

import copy
import unittest
import uuid

from plm_assistant.modules.auth.application.user_commands import (
    CreateUser, PasswordHashResult, UserCommandError, UserCommandService,
)
from plm_assistant.modules.auth.domain.username import UsernameValidationError, normalize_username


ACTOR_ID = uuid.uuid4()
TRACE_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
CREDENTIAL_ID = uuid.uuid4()


class FakeUow:
    def __init__(self, store: dict) -> None:
        self.store = store
        self.working = copy.deepcopy(store)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.store.clear()
        self.store.update(self.working)


class FakeRepo:
    def __init__(self) -> None:
        self.add_called = 0

    def add_user(self, tx, *, username_display, username_normalized, actor_id):
        self.add_called += 1
        if username_normalized in tx.working["users"]:
            return None
        tx.working["users"][username_normalized] = (USER_ID, username_display, actor_id)
        return USER_ID

    def add_credential(self, tx, *, user_id, password_hash, actor_id):
        tx.working["credentials"].append((user_id, password_hash, actor_id))
        return CREDENTIAL_ID

    def activate_initial_credential(self, tx, *, user_id, credential_id, actor_id):
        tx.working["active"] = (user_id, credential_id, actor_id)
        return True


class FakeAccess:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.calls = 0

    def can_create_user(self, tx, actor_id):
        self.calls += 1
        return self.allowed


class FakeHasher:
    def __init__(self, result: PasswordHashResult | None = None) -> None:
        self.calls = 0
        self.result = result or PasswordHashResult("$synthetic$not-for-login", "TEST_ONLY", {})

    def hash_password(self, password):
        self.calls += 1
        return self.result


class BrokenHasher:
    def hash_password(self, password):
        raise RuntimeError("synthetic hasher outage")


class FakeAudit:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = []

    def append(self, tx, event):
        self.calls.append(event)
        if self.fail:
            raise RuntimeError("audit unavailable")
        tx.working["audit"].append(event)
        return uuid.uuid4()


def service(store=None, *, access=None, hasher=None, audit=None, repo=None):
    store = store if store is not None else {"users": {}, "credentials": [], "active": None, "audit": []}
    access = access or FakeAccess()
    hasher = hasher or FakeHasher()
    audit = audit or FakeAudit()
    repo = repo or FakeRepo()
    return UserCommandService(
        unit_of_work=lambda: FakeUow(store), repository=repo, access=access,
        hasher=hasher, audit=audit, accepted_algorithms=frozenset({"TEST_ONLY"}),
    ), store, access, hasher, audit, repo


def command(username="  Stra\u00dfe  ", password=None):
    return CreateUser(ACTOR_ID, TRACE_ID, username, password if password is not None else bytearray(b"synthetic-passphrase"))


class UserCommandsTests(unittest.TestCase):
    def test_unicode_username_normalization(self):
        value = normalize_username("  STRASSE  ")
        self.assertEqual(value.display, "STRASSE")
        self.assertEqual(value.normalized, "strasse")
        self.assertEqual(normalize_username("Stra\u00dfe").normalized, value.normalized)
        self.assertEqual(normalize_username("e\u0301").display, "\u00e9")
        for raw in ("   ", "a\x00b", "x" * 256):
            with self.assertRaises(UsernameValidationError):
                normalize_username(raw)

    def test_create_is_normalized_audited_and_password_wiped(self):
        commands, store, _, hasher, audit, _ = service()
        request = command()
        self.assertNotIn("synthetic-passphrase", repr(request))
        result = commands.create_user(request)
        self.assertEqual((result.user_id, result.credential_version, result.lock_version), (USER_ID, 1, 1))
        self.assertEqual(set(store["users"]), {"strasse"})
        self.assertEqual(len(store["credentials"]), 1)
        self.assertEqual(audit.calls[0].action, "USER_CREATED")
        self.assertEqual(audit.calls[0].target_object_id, USER_ID)
        self.assertEqual(store["audit"], audit.calls)
        self.assertEqual(hasher.calls, 1)
        self.assertEqual(request.password, bytearray(len(request.password)))

    def test_duplicate_canonical_username_rejected_without_second_audit(self):
        commands, store, _, _, _, _ = service()
        commands.create_user(command("STRASSE"))
        request = command("Stra\u00dfe")
        with self.assertRaises(UserCommandError) as caught:
            commands.create_user(request)
        self.assertEqual(caught.exception.code, "AUTH_USERNAME_CONFLICT")
        self.assertEqual(len(store["credentials"]), 1)
        self.assertEqual(len(store["audit"]), 1)
        self.assertEqual(request.password, bytearray(len(request.password)))

    def test_denial_precedes_hash_and_write(self):
        access, hasher, repo = FakeAccess(False), FakeHasher(), FakeRepo()
        commands, store, _, _, _, _ = service(access=access, hasher=hasher, repo=repo)
        request = command()
        with self.assertRaises(UserCommandError) as caught:
            commands.create_user(request)
        self.assertEqual(caught.exception.code, "AUTH_ACCESS_DENIED")
        self.assertEqual((access.calls, hasher.calls, repo.add_called), (1, 0, 0))
        self.assertEqual(store["users"], {})
        self.assertEqual(request.password, bytearray(len(request.password)))

    def test_audit_failure_rolls_back_user_and_credential(self):
        commands, store, _, _, _, _ = service(audit=FakeAudit(fail=True))
        request = command()
        with self.assertRaisesRegex(RuntimeError, "audit unavailable"):
            commands.create_user(request)
        self.assertEqual(store, {"users": {}, "credentials": [], "active": None, "audit": []})
        self.assertEqual(request.password, bytearray(len(request.password)))

    def test_invalid_hash_or_input_fails_closed(self):
        bad = FakeHasher(PasswordHashResult("raw", "UNAPPROVED", {}))
        commands, store, _, _, _, _ = service(hasher=bad)
        request = command()
        with self.assertRaises(UserCommandError) as caught:
            commands.create_user(request)
        self.assertEqual(caught.exception.code, "AUTH_HASH_UNAVAILABLE")
        self.assertEqual(store["users"], {})
        for request in (command(password=bytearray()), command(password=bytearray(b"bad\x00pass")), command(password=bytearray(b"\xff"))):
            with self.assertRaises(UserCommandError):
                commands.create_user(request)
            self.assertEqual(request.password, bytearray(len(request.password)))

    def test_hasher_exception_wipes_input_and_rolls_back(self):
        commands, store, _, _, _, _ = service(hasher=BrokenHasher())
        request = command()
        with self.assertRaisesRegex(RuntimeError, "synthetic hasher outage"):
            commands.create_user(request)
        self.assertEqual(store["users"], {})
        self.assertEqual(request.password, bytearray(len(request.password)))

    def test_required_dependencies(self):
        with self.assertRaises(ValueError):
            UserCommandService(unit_of_work=None, repository=FakeRepo(), access=FakeAccess(), hasher=FakeHasher(), audit=FakeAudit(), accepted_algorithms=frozenset({"TEST_ONLY"}))
        with self.assertRaises(ValueError):
            UserCommandService(unit_of_work=lambda: FakeUow({}), repository=FakeRepo(), access=FakeAccess(), hasher=FakeHasher(), audit=FakeAudit(), accepted_algorithms=frozenset())


if __name__ == "__main__":
    unittest.main()
