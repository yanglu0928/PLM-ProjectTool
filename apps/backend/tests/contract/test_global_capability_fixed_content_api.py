"""CR-CAP-006 fixed content is opt-in and bound to the Review identity."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.capability.application.read_capability import (
    CapabilityItemView, CapabilityVersionView,
)
from plm_assistant.modules.review.api.global_capability import (
    create_global_capability_fixed_content_router,
)
from plm_assistant.modules.review.api.global_capability_cursor import (
    GlobalCapabilityFixedItemsCursorCodec,
)
from plm_assistant.modules.review.application.global_capability_read import (
    AuthorizedGlobalCapabilityFixedItems, AuthorizedGlobalCapabilityFixedVersion,
    AuthorizedGlobalCapabilityReview, GlobalCapabilityReviewReadError,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.domain.round_progress import ReviewRoundProgress


NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)
REVIEW, ROUND, BASELINE, VERSION, ACTOR = (uuid.uuid4() for _ in range(5))
TOKEN = b"s" * 32


def fixed():
    identity = ReviewIdentitySnapshot(
        REVIEW, "GLOBAL", None, "CAP-01", BASELINE,
        "DEPLOYMENT_ALL_V1", "IN_REVIEW", ROUND, 1,
    )
    round_snapshot = FixedReviewRoundSnapshot(
        identity, 1, VERSION, ACTOR,
        ReviewRoundProgress(ROUND, NOW, (ACTOR,)),
        (uuid.uuid4(),), 0, uuid.uuid4(), b"x" * 32, 1,
        NOW, (), uuid.uuid4(), NOW, None,
    )
    review = AuthorizedGlobalCapabilityReview(identity, round_snapshot)
    version = CapabilityVersionView(
        VERSION, BASELINE, 1, "IN_REVIEW", "sha256:" + "a" * 64,
        "b" * 64, 2, 1, 1, None, REVIEW, ROUND, NOW,
    )
    return AuthorizedGlobalCapabilityFixedVersion(review, version)


def item(ordinal):
    return CapabilityItemView(
        uuid.uuid4(), VERSION, BASELINE, ordinal, "PLM.REVIEW.ITEM",
        "PLM", "Capability", "Review", "Item", "Description", "GLOBAL",
        (), (), "AVAILABLE", (uuid.uuid4(),), (uuid.uuid4(),),
    )


class Reads:
    fail = None
    def __init__(self):
        self.calls = []

    def fixed_version(self, query):
        self.calls.append(("version", query))
        if self.fail:
            raise GlobalCapabilityReviewReadError(self.fail)
        return fixed()

    def fixed_items(self, query, *, page_size, after_ordinal):
        self.calls.append(("items", query, page_size, after_ordinal))
        if self.fail:
            raise GlobalCapabilityReviewReadError(self.fail)
        bound = fixed()
        rows = (item(0), item(1)) if after_ordinal is None else (item(1),)
        chosen = rows[:page_size]
        next_ordinal = chosen[-1].ordinal if len(rows) > page_size else None
        return AuthorizedGlobalCapabilityFixedItems(
            bound.review, bound.version, chosen, next_ordinal,
        )


class GlobalCapabilityFixedContentApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.codec = GlobalCapabilityFixedItemsCursorCodec(b"k" * 32)
        router = create_global_capability_fixed_content_router(
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads, cursors=self.codec,
        )
        self.client = TestClient(create_app(
            global_capability_fixed_content_router=router,
        ), base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.base = f"/api/v1/global/reviews/{REVIEW}"
        self.headers = {"cookie": "plm_session=" + TOKEN.hex()}

    def test_default_closed_and_exact_fixed_version(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(
                self.base + "/fixed-version", headers=self.headers,
            ).status_code)
            self.assertEqual(404, bare.get(
                self.base + "/fixed-items", headers=self.headers,
            ).status_code)
        response = self.client.get(self.base + "/fixed-version", headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual('"v1"', response.headers["etag"])
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        self.assertEqual({
            "review_id", "review_round_id", "version", "review_etag",
        }, set(response.json()["data"]))
        self.assertEqual(str(VERSION), response.json()["data"]["version"]["baseline_version_id"])

    def test_bounded_page_and_session_bound_cursor(self):
        path = self.base + "/fixed-items?page_size=1"
        first = self.client.get(path, headers=self.headers)
        self.assertEqual(200, first.status_code)
        data = first.json()["data"]
        self.assertEqual(1, len(data["items"]))
        self.assertTrue(data["has_more"])
        self.assertEqual(0, data["items"][0]["ordinal"])
        self.assertEqual(str(VERSION), data["baseline_version_id"])
        cursor = data["next_cursor"]
        second = self.client.get(path + "&cursor=" + cursor, headers=self.headers)
        self.assertEqual(200, second.status_code)
        self.assertEqual(1, second.json()["data"]["items"][0]["ordinal"])
        self.assertFalse(second.json()["data"]["has_more"])
        self.assertEqual(400, self.client.get(
            path + "&cursor=" + cursor,
            headers={"cookie": "plm_session=" + (b"t" * 32).hex()},
        ).status_code)

    def test_bad_query_and_safe_denials(self):
        for suffix, status in (
            ("/fixed-version?x=1", 400),
            ("/fixed-items?page_size=51", 422),
            ("/fixed-items?page_size=1&page_size=1", 400),
            ("/fixed-items?cursor=bad", 400),
        ):
            with self.subTest(suffix=suffix):
                self.assertEqual(status, self.client.get(
                    self.base + suffix, headers=self.headers,
                ).status_code)
        for code, status in (
            ("AUTH_ACCESS_DENIED", 401), ("RESOURCE_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403), ("GLOBAL_REVIEW_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.reads.fail = code
                result = self.client.get(self.base + "/fixed-version", headers=self.headers)
                self.assertEqual(status, result.status_code)
                self.assertNotIn("Traceback", result.text)
        self.reads.fail = None


if __name__ == "__main__":
    unittest.main()
