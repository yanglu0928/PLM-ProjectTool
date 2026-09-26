from __future__ import annotations

import base64
import json
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from plm_assistant.modules.license.infrastructure.packaged_product_key import (
    PRODUCT_CODE, PRODUCT_KEY_REF, PackagedProductKey, PackagedProductKeyError,
)


def _manifest(public: bytes, **changes: str) -> bytes:
    value = {
        "schema_version": "plm.product-public-key.v1",
        "product_code": PRODUCT_CODE,
        "key_ref": PRODUCT_KEY_REF,
        "public_key": base64.b64encode(public).decode("ascii"),
    }
    value.update(changes)
    return json.dumps(value, sort_keys=True).encode("utf-8")


class PackagedProductKeyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw,
        )

    def test_product_only_reference_and_signature(self) -> None:
        source = PackagedProductKey(read_manifest=lambda: _manifest(self.public))
        self.assertEqual(source.product_key_ref(), PRODUCT_KEY_REF)
        self.assertEqual(source.resolve_public_key(PRODUCT_KEY_REF), self.public)
        self.assertIsNone(source.resolve_public_key("other-product-key"))
        signature = self.private.sign(b"synthetic-license-payload")
        Ed25519PublicKey.from_public_bytes(source.resolve_public_key(PRODUCT_KEY_REF)).verify(
            signature, b"synthetic-license-payload",
        )

    def test_malformed_or_wrong_product_fails_closed(self) -> None:
        candidates = (
            b"", b"{}", b"x" * 513,
            _manifest(self.public, product_code="OTHER_PRODUCT"),
            _manifest(self.public, key_ref="arbitrary-key"),
            _manifest(self.public, public_key="not-base64"),
            _manifest(b"short"),
            b'not-json',
            b'{"product_code":"PLM_PROJECT_TOOL","product_code":"PLM_PROJECT_TOOL"}',
        )
        for payload in candidates:
            with self.subTest(length=len(payload)):
                with self.assertRaises(PackagedProductKeyError):
                    PackagedProductKey(read_manifest=lambda: payload)
        with self.assertRaises(PackagedProductKeyError):
            PackagedProductKey(read_manifest=lambda: (_ for _ in ()).throw(FileNotFoundError()))

if __name__ == "__main__":
    unittest.main()
