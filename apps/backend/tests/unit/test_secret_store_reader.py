from __future__ import annotations

import unittest
import uuid

from sqlalchemy.orm import Session

from plm_assistant.modules.platform.application.secret_access import SecretRef
from plm_assistant.modules.platform.infrastructure.secret_store_reader import SqlAlchemyEncryptedSecretStore


class SecretStoreReaderTests(unittest.TestCase):
    def test_requires_transaction_factory(self):
        with self.assertRaises(ValueError):
            SqlAlchemyEncryptedSecretStore(None)

    def test_invalid_reference_fails_without_database_read(self):
        reader = SqlAlchemyEncryptedSecretStore(lambda: None)
        self.assertIsNone(reader.load(None))

    def test_inactive_transaction_fails_closed(self):
        class FakeTransaction:
            session = Session()

            def __enter__(self):
                return self

            def __exit__(self, *_):
                self.session.close()

        reader = SqlAlchemyEncryptedSecretStore(FakeTransaction)
        with self.assertRaises(RuntimeError):
            reader.load(SecretRef(uuid.uuid4()))


if __name__ == "__main__":
    unittest.main()
