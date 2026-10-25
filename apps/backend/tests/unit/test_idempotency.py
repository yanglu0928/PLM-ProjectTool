from __future__ import annotations

import hashlib
import unittest
import uuid

from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint,
)


class IdempotencyTests(unittest.TestCase):
    def test_key_validation_and_digest_only_scope(self) -> None:
        actor = uuid.uuid4()
        key = "synthetic-test-key-1234"
        scope = IdempotencyScope.from_key(
            actor_id=actor, project_id=None, operation="V1_AUTH_LOGOUT", key=key,
        )
        self.assertEqual(scope.key_digest, hashlib.sha256(key.encode("ascii")).digest())
        self.assertNotIn(key, repr(scope))
        for invalid in ("short", "x" * 129, "客户正文" + "x" * 20, "x" * 15 + "\n"):
            with self.subTest(invalid=invalid), self.assertRaises(IdempotencyError):
                IdempotencyScope.from_key(
                    actor_id=actor, project_id=None, operation="V1_AUTH_LOGOUT", key=invalid,
                )
        with self.assertRaises(IdempotencyError):
            IdempotencyScope.from_key(actor_id=actor, project_id=None,
                                      operation="AUTH_LOGOUT", key=key)

    def test_canonical_payload_hash_and_result_validation(self) -> None:
        self.assertEqual(
            canonical_payload_fingerprint({"b": 2, "a": [1, True]}),
            canonical_payload_fingerprint({"a": [1, True], "b": 2}),
        )
        with self.assertRaises(IdempotencyError):
            canonical_payload_fingerprint({"value": float("nan")})
        with self.assertRaises(IdempotencyError):
            canonical_payload_fingerprint({"value": b"secret"})
        result = IdempotencyResult("V1_AUTH_SESSION", uuid.uuid4(), 200)
        self.assertEqual(result.status_code, 200)
        with self.assertRaises(IdempotencyError):
            IdempotencyResult("V1_AUTH_SESSION", uuid.uuid4(), 500)


if __name__ == "__main__":
    unittest.main()
