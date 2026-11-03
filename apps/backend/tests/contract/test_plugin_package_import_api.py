from __future__ import annotations

import base64
import hashlib

import pytest

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.plugin.api.package_import import _claims


def _headers(payload: bytes = b"PK\\x03\\x04"):
    return (
        (b"content-type", b"application/octet-stream"),
        (b"content-length", str(len(payload)).encode("ascii")),
        (b"x-content-sha256", hashlib.sha256(payload).hexdigest().encode("ascii")),
        (b"x-plugin-signature", base64.b64encode(b"s" * 64)),
        (b"x-plugin-signer-key-ref", b"test-key:fixture"),
        (b"idempotency-key", b"stable-plugin-import-key"),
    )


def test_import_claims_parse_bounded_raw_package_metadata():
    key, length, digest, signature, signer = _claims(_headers())

    assert key == "stable-plugin-import-key"
    assert length == 4
    assert digest == hashlib.sha256(b"PK\\x03\\x04").digest()
    assert signature == b"s" * 64
    assert signer == "test-key:fixture"


@pytest.mark.parametrize(
    "headers",
    [
        _headers()[:-1],
        _headers() + ((b"idempotency-key", b"another-key-value"),),
        tuple((name, b"application/json" if name == b"content-type" else value)
              for name, value in _headers()),
        tuple((name, b"not-base64!" if name == b"x-plugin-signature" else value)
              for name, value in _headers()),
        tuple((name, b"UPPERCASE" if name == b"x-content-sha256" else value)
              for name, value in _headers()),
    ],
)
def test_import_claims_reject_malformed_or_ambiguous_headers(headers):
    with pytest.raises(ApplicationError):
        _claims(headers)


def test_import_router_is_opt_in_and_uses_only_the_frozen_write_path():
    from plm_assistant.entrypoints.api import create_app
    from plm_assistant.modules.plugin.api.package_import import (
        create_plugin_package_import_router,
    )

    default_app = create_app()
    assert not any(
        route.path == "/api/v1/admin/plugins/packages:import"
        for route in default_app.routes
    )

    router = create_plugin_package_import_router(
        sessions=object(), origins=object(), service_factory=lambda token, csrf: object(),
    )
    write_app = create_app(plugin_package_import_router=router)
    matching = [
        route for route in write_app.routes
        if route.path == "/api/v1/admin/plugins/packages:import"
    ]
    assert len(matching) == 1
    assert matching[0].methods == {"POST"}
