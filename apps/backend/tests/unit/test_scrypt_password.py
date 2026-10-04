from __future__ import annotations

import unittest
from unittest.mock import patch

from plm_assistant.modules.auth.infrastructure.scrypt_password import (
    ALGORITHM_ID, PARAMETERS, PasswordHashUnavailable, ScryptPasswordHasher,
)


class ScryptPasswordTests(unittest.TestCase):
    def test_invalid_password_buffers_never_invoke_kdf(self):
        hasher = ScryptPasswordHasher()
        encoded = '$scrypt$1$131072$8$1$' + '00' * 16 + '$' + '00' * 32
        views = (memoryview(bytearray()), memoryview(bytearray(1025)))
        try:
            with patch('hashlib.scrypt') as kdf:
                for value in (None, b'password', bytearray(b'password'), *views):
                    with self.assertRaises(PasswordHashUnavailable):
                        hasher.hash_password(value)
                    self.assertFalse(hasher.verify_password(value, password_hash=encoded,
                        algorithm_id=ALGORITHM_ID, parameter_set=dict(PARAMETERS)))
                kdf.assert_not_called()
        finally:
            for view in views: view.release()

    def test_invalid_hash_type_structure_and_decoded_lengths_never_invoke_kdf(self):
        hasher = ScryptPasswordHasher()
        prefix = '$scrypt$1$131072$8$1$'
        valid = prefix + '00' * 16 + '$' + '00' * 32
        secret = memoryview(bytearray(b'synthetic-unit-password'))
        try:
            with patch('hashlib.scrypt') as kdf:
                for encoded in (None, 1, '', valid[1:] + '_', valid.replace('$scrypt$', '_scrypt$'),
                                prefix + '00' * 15 + '$' + '00' * 33,
                                prefix + '00' * 17 + '$' + '00' * 31):
                    self.assertFalse(hasher.verify_password(secret, password_hash=encoded,
                        algorithm_id=ALGORITHM_ID, parameter_set=dict(PARAMETERS)))
                kdf.assert_not_called()
        finally:
            secret.release()

    def test_verify_backend_failure_is_fixed_and_never_returns_success(self):
        hasher = ScryptPasswordHasher()
        secret = memoryview(bytearray(b'synthetic-unit-password'))
        encoded = '$scrypt$1$131072$8$1$' + '00' * 16 + '$' + '00' * 32
        try:
            for failure in (AttributeError, ValueError, TypeError, MemoryError):
                with patch('hashlib.scrypt', side_effect=failure('private backend detail')):
                    with self.assertRaises(PasswordHashUnavailable) as caught:
                        hasher.verify_password(secret, password_hash=encoded,
                            algorithm_id=ALGORITHM_ID, parameter_set=dict(PARAMETERS))
                    self.assertEqual(str(caught.exception), 'password verification unavailable')
        finally:
            secret.release()

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
