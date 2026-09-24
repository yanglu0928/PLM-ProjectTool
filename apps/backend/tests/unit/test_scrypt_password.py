from __future__ import annotations

import unittest
from unittest.mock import patch

from plm_assistant.modules.auth.infrastructure.scrypt_password import (
    ALGORITHM_ID, PARAMETERS, PasswordHashUnavailable, ScryptPasswordHasher,
)


class ScryptPasswordTests(unittest.TestCase):
    def test_random_salt_and_correct_verification(self):
        hasher = ScryptPasswordHasher()
        secret = bytearray(b"synthetic-unit-password")
        view = memoryview(secret)
        try:
            first = hasher.hash_password(view)
            second = hasher.hash_password(view)
            self.assertNotEqual(first.password_hash, second.password_hash)
            self.assertEqual(first.algorithm_id, ALGORITHM_ID)
            self.assertEqual(first.parameter_set, PARAMETERS)
            self.assertNotIn(secret.decode(), first.password_hash)
            self.assertTrue(hasher.verify_password(
                view, password_hash=first.password_hash,
                algorithm_id=first.algorithm_id, parameter_set=dict(first.parameter_set),
            ))
            self.assertFalse(hasher.verify_password(
                memoryview(bytearray(b"wrong-password")), password_hash=first.password_hash,
                algorithm_id=first.algorithm_id, parameter_set=dict(first.parameter_set),
            ))
        finally:
            view.release()
            secret[:] = b"\x00" * len(secret)

    def test_malformed_or_unapproved_metadata_fails_before_kdf(self):
        hasher = ScryptPasswordHasher()
        secret = memoryview(bytearray(b"synthetic-unit-password"))
        try:
            result = hasher.hash_password(secret)
            with patch("hashlib.scrypt", side_effect=AssertionError("KDF should not run")):
                for kwargs in (
                    {"password_hash": result.password_hash, "algorithm_id": "TEST_ONLY", "parameter_set": dict(PARAMETERS)},
                    {"password_hash": result.password_hash, "algorithm_id": ALGORITHM_ID, "parameter_set": {**PARAMETERS, "n": 1 << 22}},
                    {"password_hash": result.password_hash.replace("$scrypt$", "$unknown$"), "algorithm_id": ALGORITHM_ID, "parameter_set": dict(PARAMETERS)},
                    {"password_hash": result.password_hash[:-1] + "z", "algorithm_id": ALGORITHM_ID, "parameter_set": dict(PARAMETERS)},
                ):
                    self.assertFalse(hasher.verify_password(secret, **kwargs))
        finally:
            secret.release()

    def test_resource_failure_is_fixed_and_fail_closed(self):
        hasher = ScryptPasswordHasher()
        secret = memoryview(bytearray(b"synthetic-unit-password"))
        try:
            with patch("hashlib.scrypt", side_effect=ValueError("raw OpenSSL detail")):
                with self.assertRaises(PasswordHashUnavailable) as caught:
                    hasher.hash_password(secret)
            self.assertEqual(str(caught.exception), "password hashing unavailable")
        finally:
            secret.release()


if __name__ == "__main__":
    unittest.main()
