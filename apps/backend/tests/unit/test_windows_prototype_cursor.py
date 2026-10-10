from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.entrypoints.windows_prototype_cursor import (
    PROTOTYPE_CURSOR_KEY_REFS,
    PROTOTYPE_LINK_CURSOR_KEY_REF,
    PROTOTYPE_PACKAGE_CURSOR_KEY_REF,
    PROTOTYPE_TEMPLATE_CURSOR_KEY_REF,
    PROTOTYPE_VERSION_CURSOR_KEY_REF,
    ProductionPrototypeCursorStartupError,
    create_windows_prototype_cursor_codecs,
)


class Resolver:
    def __init__(self, values: dict[str, bytes | None], failure: Exception | None = None):
        self.values, self.failure, self.refs = values, failure, []

    def __bool__(self) -> bool:
        return False

    def resolve_key(self, key_ref: str) -> bytes | None:
        self.refs.append(key_ref)
        if self.failure is not None:
            raise self.failure
        return self.values.get(key_ref)


def keys() -> dict[str, bytes]:
    return {ref: bytes([index]) * 32
            for index, ref in enumerate(PROTOTYPE_CURSOR_KEY_REFS, start=1)}


class WindowsPrototypeCursorTests(unittest.TestCase):
    def test_resolves_five_dedicated_refs_and_round_trips(self) -> None:
        resolver = Resolver(keys())
        codecs = create_windows_prototype_cursor_codecs(resolver=resolver)
        self.assertEqual(list(PROTOTYPE_CURSOR_KEY_REFS), resolver.refs)
        project, identity = uuid.uuid4(), uuid.uuid4()
        session = b"s" * 32
        instant = datetime.now(timezone.utc)
        package = codecs.package.encode(
            project_id=project, session_token=session, page_size=1,
            updated_at=instant, package_id=identity,
        )
        self.assertEqual((instant, identity), codecs.package.decode(
            package, project_id=project, session_token=session, page_size=1,
        ))
        link = codecs.link.encode(
            project_id=project, session_token=session, page_size=1,
            link_id=identity,
        )
        self.assertEqual(identity, codecs.link.decode(
            link, project_id=project, session_token=session, page_size=1,
        ))

    def test_missing_wrong_duplicate_or_provider_failure_fails_closed(self) -> None:
        cases: list[Resolver] = []
        for ref in PROTOTYPE_CURSOR_KEY_REFS:
            values = keys()
            values[ref] = None
            cases.append(Resolver(values))
        wrong = keys()
        wrong[PROTOTYPE_VERSION_CURSOR_KEY_REF] = b"short"
        cases.append(Resolver(wrong))
        duplicate = keys()
        duplicate[PROTOTYPE_TEMPLATE_CURSOR_KEY_REF] = duplicate[
            PROTOTYPE_PACKAGE_CURSOR_KEY_REF
        ]
        cases.append(Resolver(duplicate))
        cases.append(Resolver({}, RuntimeError("private vault path")))
        for resolver in cases:
            with self.subTest(refs=resolver.values.keys()), self.assertRaisesRegex(
                ProductionPrototypeCursorStartupError,
                "^Prototype cursor keys unavailable$",
            ) as caught:
                create_windows_prototype_cursor_codecs(resolver=resolver)
            self.assertNotIn("private", str(caught.exception))

    def test_cross_key_family_tokens_are_not_interchangeable(self) -> None:
        codecs = create_windows_prototype_cursor_codecs(resolver=Resolver(keys()))
        project, identity = uuid.uuid4(), uuid.uuid4()
        session = b"s" * 32
        instant = datetime.now(timezone.utc)
        token = codecs.package.encode(
            project_id=project, session_token=session, page_size=20,
            updated_at=instant, package_id=identity,
        )
        with self.assertRaises(Exception):
            codecs.prototype.decode(
                token, project_id=project, session_token=session, page_size=20,
            )
        self.assertEqual(
            {
                PROTOTYPE_PACKAGE_CURSOR_KEY_REF,
                PROTOTYPE_VERSION_CURSOR_KEY_REF,
                PROTOTYPE_TEMPLATE_CURSOR_KEY_REF,
                PROTOTYPE_LINK_CURSOR_KEY_REF,
            }.issubset(PROTOTYPE_CURSOR_KEY_REFS),
            True,
        )


if __name__ == "__main__":
    unittest.main()
