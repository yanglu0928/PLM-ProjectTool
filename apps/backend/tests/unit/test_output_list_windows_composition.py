from unittest.mock import Mock, patch

import pytest

from plm_assistant.entrypoints.windows_output_list import (
    ProductionOutputListStartupError,
    create_windows_output_request_list_router,
)
from plm_assistant.entrypoints.windows_output_list_cursor import (
    OUTPUT_REQUEST_LIST_CURSOR_KEY_REF,
    ProductionOutputRequestListCursorStartupError,
    create_windows_output_request_list_cursor_codec,
)
from plm_assistant.modules.output.api.list_cursor import OutputRequestListCursorCodec


class Resolver:
    def __init__(self, key):
        self.key = key
        self.refs = []

    def resolve_key(self, key_ref):
        self.refs.append(key_ref)
        return self.key


def test_cursor_key_uses_dedicated_reference_and_returns_codec():
    resolver = Resolver(b"o" * 32)
    codec = create_windows_output_request_list_cursor_codec(resolver=resolver)
    assert type(codec) is OutputRequestListCursorCodec
    assert resolver.refs == [OUTPUT_REQUEST_LIST_CURSOR_KEY_REF]


@pytest.mark.parametrize("key", [None, b"x" * 31, b"x" * 33])
def test_cursor_key_missing_or_wrong_length_fails_closed(key):
    with pytest.raises(ProductionOutputRequestListCursorStartupError):
        create_windows_output_request_list_cursor_codec(resolver=Resolver(key))


def test_cursor_key_does_not_expose_secret_on_failure():
    with patch(
        "plm_assistant.entrypoints.windows_output_list_cursor.WindowsSecretKeyProvider",
        return_value=Resolver(None),
    ):
        with pytest.raises(ProductionOutputRequestListCursorStartupError) as caught:
            create_windows_output_request_list_cursor_codec()
    assert "secret" not in str(caught.value).lower()


def test_list_composition_requires_all_trust_dependencies():
    with pytest.raises(ProductionOutputListStartupError):
        create_windows_output_request_list_router(
            runtime=None, sessions=Mock(), origins=Mock(),
            license_guard=Mock(), cursors=OutputRequestListCursorCodec(b"o" * 32),
        )


def test_list_composition_mounts_only_frozen_list_route():
    runtime = Mock()
    runtime.unit_of_work = Mock()
    router = create_windows_output_request_list_router(
        runtime=runtime, sessions=Mock(), origins=Mock(),
        license_guard=Mock(), cursors=OutputRequestListCursorCodec(b"o" * 32),
    )
    routes = {(route.path, tuple(route.methods or ())) for route in router.routes}
    assert ("/api/v1/projects/{project_id}/output-requests", ("GET",)) in routes
    assert len(routes) == 1
