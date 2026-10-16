from __future__ import annotations

import base64
import json
import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.prototype.api.cursors import (
    PrototypeCursorCodec,
    PrototypePackageCursorCodec,
    PrototypeTemplateCursorCodec,
    PrototypeVersionCursorCodec,
    RequirementPrototypeLinkCursorCodec,
)


class PrototypeCursorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = uuid.uuid4()
        self.other_project = uuid.uuid4()
        self.identity = uuid.uuid4()
        self.session = b"s" * 32
        self.instant = datetime(2026, 10, 8, 1, 2, 3, 456789, timezone.utc)

    def test_package_and_prototype_round_trip(self) -> None:
        package = PrototypePackageCursorCodec(b"a" * 32)
        token = package.encode(
            project_id=self.project, session_token=self.session, page_size=50,
            updated_at=self.instant, package_id=self.identity,
        )
        self.assertEqual(
            (self.instant, self.identity),
            package.decode(
                token, project_id=self.project, session_token=self.session,
                page_size=50,
            ),
        )
        prototype = PrototypeCursorCodec(b"b" * 32)
        token = prototype.encode(
            project_id=self.project, session_token=self.session, page_size=200,
            updated_at=self.instant, prototype_id=self.identity,
        )
        self.assertEqual(
            (self.instant, self.identity),
            prototype.decode(
                token, project_id=self.project, session_token=self.session,
                page_size=200,
            ),
        )

    def test_version_binds_project_prototype_session_and_page_size(self) -> None:
        codec = PrototypeVersionCursorCodec(b"c" * 32)
        prototype = uuid.uuid4()
        token = codec.encode(
            project_id=self.project, prototype_id=prototype,
            session_token=self.session, page_size=100, version_no=7,
        )
        self.assertEqual(7, codec.decode(
            token, project_id=self.project, prototype_id=prototype,
            session_token=self.session, page_size=100,
        ))
        invalid = (
            dict(project_id=self.other_project, prototype_id=prototype,
                 session_token=self.session, page_size=100),
            dict(project_id=self.project, prototype_id=uuid.uuid4(),
                 session_token=self.session, page_size=100),
            dict(project_id=self.project, prototype_id=prototype,
                 session_token=b"x" * 32, page_size=100),
            dict(project_id=self.project, prototype_id=prototype,
                 session_token=self.session, page_size=99),
        )
        for binding in invalid:
            with self.subTest(binding=binding), self.assertRaises(ApplicationError):
                codec.decode(token, **binding)

    def test_template_project_and_global_scopes_are_distinct(self) -> None:
        codec = PrototypeTemplateCursorCodec(b"d" * 32)
        project_token = codec.encode(
            scope="PROJECT", project_id=self.project,
            session_token=self.session, page_size=20,
            updated_at=self.instant, template_id=self.identity,
        )
        global_token = codec.encode(
            scope="GLOBAL", project_id=None,
            session_token=self.session, page_size=20,
            updated_at=self.instant, template_id=self.identity,
        )
        self.assertNotEqual(project_token, global_token)
        self.assertEqual((self.instant, self.identity), codec.decode(
            project_token, scope="PROJECT", project_id=self.project,
            session_token=self.session, page_size=20,
        ))
        self.assertEqual((self.instant, self.identity), codec.decode(
            global_token, scope="GLOBAL", project_id=None,
            session_token=self.session, page_size=20,
        ))
        with self.assertRaises(ApplicationError):
            codec.decode(
                project_token, scope="GLOBAL", project_id=None,
                session_token=self.session, page_size=20,
            )
        for scope, project in (("GLOBAL", self.project), ("PROJECT", None)):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                codec.encode(
                    scope=scope, project_id=project,
                    session_token=self.session, page_size=20,
                    updated_at=self.instant, template_id=self.identity,
                )

    def test_link_round_trip_and_binding(self) -> None:
        codec = RequirementPrototypeLinkCursorCodec(b"e" * 32)
        token = codec.encode(
            project_id=self.project, session_token=self.session,
            page_size=200, link_id=self.identity,
        )
        self.assertEqual(self.identity, codec.decode(
            token, project_id=self.project, session_token=self.session,
            page_size=200,
        ))
        with self.assertRaises(ApplicationError):
            codec.decode(
                token, project_id=self.other_project,
                session_token=self.session, page_size=200,
            )

    def test_tamper_extra_field_noncanonical_and_wrong_key_fail_closed(self) -> None:
        codec = PrototypePackageCursorCodec(b"a" * 32)
        token = codec.encode(
            project_id=self.project, session_token=self.session, page_size=25,
            updated_at=self.instant, package_id=self.identity,
        )
        encoded, signature = token.split(".")
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        payload = json.loads(raw)
        payload["extra"] = True
        changed = base64.urlsafe_b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("ascii"),
        ).rstrip(b"=").decode("ascii") + "." + signature
        for invalid in (
            token[:-1] + ("A" if token[-1] != "A" else "B"),
            changed,
            token + "=",
        ):
            with self.subTest(invalid=invalid[-8:]), self.assertRaises(ApplicationError):
                codec.decode(
                    invalid, project_id=self.project, session_token=self.session,
                    page_size=25,
                )
        with self.assertRaises(ApplicationError):
            PrototypePackageCursorCodec(b"z" * 32).decode(
                token, project_id=self.project, session_token=self.session,
                page_size=25,
            )

    def test_family_separation_even_with_same_key(self) -> None:
        key = b"k" * 32
        package = PrototypePackageCursorCodec(key)
        prototype = PrototypeCursorCodec(key)
        token = package.encode(
            project_id=self.project, session_token=self.session, page_size=50,
            updated_at=self.instant, package_id=self.identity,
        )
        with self.assertRaises(ApplicationError):
            prototype.decode(
                token, project_id=self.project, session_token=self.session,
                page_size=50,
            )

    def test_invalid_key_and_positions_are_rejected(self) -> None:
        for key in (b"", b"x" * 31, bytearray(b"x" * 32)):
            with self.subTest(key=type(key)), self.assertRaises(ValueError):
                PrototypeCursorCodec(key)
        with self.assertRaises(ValueError):
            PrototypeVersionCursorCodec(b"v" * 32).encode(
                project_id=self.project, prototype_id=self.identity,
                session_token=self.session, page_size=101, version_no=2,
            )
        with self.assertRaises(ValueError):
            RequirementPrototypeLinkCursorCodec(b"l" * 32).encode(
                project_id=self.project, session_token=self.session,
                page_size=True, link_id=self.identity,
            )


if __name__ == "__main__":
    unittest.main()
