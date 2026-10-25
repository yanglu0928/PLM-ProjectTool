from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.prototype.api.cursors import PrototypePackageCursorCodec
from plm_assistant.modules.prototype.api.packages import create_prototype_package_router
from plm_assistant.modules.prototype.application.create_identity import (
    PrototypeIdentityCreateError,
    PrototypePackageInitialView,
)
from plm_assistant.modules.prototype.application.mutate_package import (
    PrototypePackageMutationError,
    PrototypePackageView as MutatedPackageView,
)
from plm_assistant.modules.prototype.application.read_identities import (
    PrototypeIdentityReadError,
    PrototypePackagePage,
    PrototypePackageSummary,
    PrototypePackageView,
)


NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)
PROJECT, PACKAGE, ACTOR = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
PROTOTYPES = tuple(sorted((uuid.uuid4(), uuid.uuid4()), key=lambda value: value.bytes))
SUMMARY = PrototypePackageSummary(
    PACKAGE, PROJECT, "Delivery prototypes", "ACTIVE", ACTOR, NOW,
    None, NOW, '"v0"',
)


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if token != b"s" * 32 or require_csrf and csrf_token != b"c" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    fail = None

    def _check(self, query):
        self.query = query
        if self.fail:
            raise PrototypeIdentityReadError(self.fail)

    def list_packages(
        self, query, *, page_size, after_updated_at=None,
        after_prototype_package_id=None,
    ):
        self._check(query)
        self.after = (after_updated_at, after_prototype_package_id)
        more = after_updated_at is None
        return PrototypePackagePage(
            (SUMMARY,), NOW if more else None, PACKAGE if more else None, more,
        )

    def get_package(self, query, package_id):
        self._check(query)
        return PrototypePackageView(SUMMARY, PROTOTYPES)


class Creates:
    fail = None

    def create_package(self, command):
        self.command = command
        if self.fail:
            raise PrototypeIdentityCreateError(self.fail)
        return PrototypePackageInitialView(
            PACKAGE, PROJECT, command.name, NOW,
        )


class Mutations:
    fail = None

    def _result(self, command):
        self.command = command
        if self.fail:
            raise PrototypePackageMutationError(self.fail)
        members = getattr(command, "prototype_ids", PROTOTYPES)
        return MutatedPackageView(
            PACKAGE, PROJECT, getattr(command, "name", "Delivery prototypes"),
            "ACTIVE", tuple(sorted(members, key=str)),
            f'"v{command.expected_version + 1}"',
        )

    def patch(self, command):
        return self._result(command)

    def set_members(self, command):
        return self._result(command)


class PrototypePackageApiTests(unittest.TestCase):
    def setUp(self):
        self.reads, self.creates, self.mutations = Reads(), Creates(), Mutations()
        self.reads.fail = self.creates.fail = self.mutations.fail = None
        router = create_prototype_package_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads, creates=self.creates, mutations=self.mutations,
            cursors=PrototypePackageCursorCodec(b"p" * 32),
        )
        self.client = TestClient(
            create_app(prototype_package_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.root = f"/api/v1/projects/{PROJECT}/prototype-packages"
        self.detail = f"{self.root}/{PACKAGE}"
        self.read_headers = {"cookie": "plm_session=" + (b"s" * 32).hex()}
        self.write_headers = {
            **self.read_headers,
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()),
            "if-match": '"v0"',
        }

    def test_default_closed_and_five_success_contracts(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.root).status_code)
            self.assertEqual(404, bare.post(self.root).status_code)
            self.assertEqual(404, bare.get(self.detail).status_code)
            self.assertEqual(404, bare.patch(self.detail).status_code)
            self.assertEqual(404, bare.post(
                self.detail + ":set-members",
            ).status_code)

        first = self.client.get(
            self.root + "?page_size=1", headers=self.read_headers,
        )
        self.assertEqual(200, first.status_code)
        cursor = first.json()["data"]["next_cursor"]
        second = self.client.get(
            self.root + f"?page_size=1&cursor={cursor}",
            headers=self.read_headers,
        )
        self.assertEqual((NOW, PACKAGE), self.reads.after)
        self.assertFalse(second.json()["data"]["has_more"])

        created = self.client.post(
            self.root, headers=self.write_headers,
            json={"name": "Delivery prototypes"},
        )
        self.assertEqual(201, created.status_code)
        self.assertEqual('"v0"', created.headers["etag"])
        self.assertEqual(self.detail, created.headers["location"])

        detail = self.client.get(self.detail, headers=self.read_headers)
        self.assertEqual(200, detail.status_code)
        self.assertEqual('"v0"', detail.headers["etag"])
        self.assertEqual(
            [str(value) for value in PROTOTYPES],
            detail.json()["data"]["prototype_ids"],
        )

        patch_headers = {
            key: value for key, value in self.write_headers.items()
            if key != "idempotency-key"
        }
        patched = self.client.patch(
            self.detail, headers=patch_headers,
            json={"name": "Updated prototypes"},
        )
        self.assertEqual(200, patched.status_code)
        self.assertEqual("Updated prototypes", self.mutations.command.name)
        self.assertFalse(hasattr(self.mutations.command, "idempotency_key"))

        changed = self.client.post(
            self.detail + ":set-members", headers=self.write_headers,
            json={"prototype_ids": [str(value) for value in PROTOTYPES]},
        )
        self.assertEqual(200, changed.status_code)
        self.assertEqual(PROTOTYPES, self.mutations.command.prototype_ids)

    def test_security_query_json_and_preconditions_fail_closed(self):
        self.assertEqual(401, self.client.get(self.root).status_code)
        self.assertEqual(403, self.client.get(
            self.root, headers={**self.read_headers, "host": "evil.test"},
        ).status_code)
        self.assertEqual(403, self.client.post(
            self.root,
            headers={**self.write_headers, "origin": "https://evil.test"},
            json={"name": "Package"},
        ).status_code)
        no_match = {
            key: value for key, value in self.write_headers.items()
            if key != "if-match"
        }
        self.assertEqual(428, self.client.patch(
            self.detail, headers=no_match, json={"name": "Package"},
        ).status_code)
        no_key = {
            key: value for key, value in self.write_headers.items()
            if key != "idempotency-key"
        }
        self.assertEqual(422, self.client.post(
            self.detail + ":set-members", headers=no_key,
            json={"prototype_ids": [str(PROTOTYPES[0])]},
        ).status_code)
        self.assertEqual(400, self.client.get(
            self.root + "?page_size=1&page_size=1",
            headers=self.read_headers,
        ).status_code)
        self.assertEqual(400, self.client.get(
            self.detail + "?extra=1", headers=self.read_headers,
        ).status_code)
        self.assertEqual(422, self.client.patch(
            self.detail, headers=self.write_headers, json={"name": None},
        ).status_code)
        self.assertEqual(400, self.client.post(
            self.root,
            headers={**self.write_headers, "content-type": "application/json"},
            content=b'{"name":"A","name":"B"}',
        ).status_code)

    def test_cursor_scope_and_output_shape_fail_closed(self):
        first = self.client.get(
            self.root + "?page_size=1", headers=self.read_headers,
        )
        cursor = first.json()["data"]["next_cursor"]
        self.assertEqual(400, self.client.get(
            f"/api/v1/projects/{uuid.uuid4()}/prototype-packages"
            f"?page_size=1&cursor={cursor}", headers=self.read_headers,
        ).status_code)
        original = self.reads.list_packages
        self.reads.list_packages = lambda *_a, **_k: PrototypePackagePage(
            (SUMMARY,), None, None, True,
        )
        self.assertEqual(503, self.client.get(
            self.root, headers=self.read_headers,
        ).status_code)
        self.reads.list_packages = original
        original_create = self.creates.create_package
        self.creates.create_package = lambda command: PrototypePackageInitialView(
            PACKAGE, uuid.uuid4(), command.name, NOW,
        )
        self.assertEqual(503, self.client.post(
            self.root, headers=self.write_headers, json={"name": "Package"},
        ).status_code)
        self.creates.create_package = original_create

    def test_safe_error_mapping(self):
        for owner, code, method, status in (
            (self.reads, "AUTH_ACCESS_DENIED", "get", 404),
            (self.reads, "LICENSE_OPERATION_DENIED", "get", 403),
            (self.creates, "CONFLICT_IDEMPOTENCY", "post", 409),
            (self.mutations, "CONFLICT_VERSION", "patch", 409),
            (self.mutations, "PROTOTYPE_STATE_INVALID", "patch", 409),
        ):
            with self.subTest(code=code):
                owner.fail = code
                if method == "get":
                    response = self.client.get(
                        self.root, headers=self.read_headers,
                    )
                elif method == "post":
                    response = self.client.post(
                        self.root, headers=self.write_headers,
                        json={"name": "Package"},
                    )
                else:
                    response = self.client.patch(
                        self.detail, headers=self.write_headers,
                        json={"name": "Package"},
                    )
                self.assertEqual(status, response.status_code)
                self.assertNotIn("Traceback", response.text)
                owner.fail = None


if __name__ == "__main__":
    unittest.main()
