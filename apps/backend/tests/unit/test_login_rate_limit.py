from __future__ import annotations

import unittest

from plm_assistant.modules.auth.application.login_rate_limit import (
    ACCOUNT_LIMIT, SOURCE_LIMIT, LoginRateLimitError, LoginRateLimiter,
)


class Tx:
    def __init__(self, deps):
        self.deps = deps

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        self.deps.commits += 1


class FakeRepository:
    def __init__(self):
        self.counts = {}
        self.commits = 0
        self.fail = False

    def uow(self):
        return Tx(self)

    def reserve(self, tx, *, bucket_key, limit, window):
        if self.fail:
            raise RuntimeError("synthetic database error")
        assert type(bucket_key) is bytes and len(bucket_key) == 32
        assert window.total_seconds() == 300
        count = self.counts.get(bucket_key, 0)
        if count >= limit:
            return False
        self.counts[bucket_key] = count + 1
        return True


class LoginRateLimitTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepository()
        self.limiter = LoginRateLimiter(unit_of_work=self.repo.uow, repository=self.repo)

    def test_account_limit_applies_across_sources(self):
        for index in range(ACCOUNT_LIMIT):
            self.limiter.require_slot(client_ip=f"127.0.0.{index+1}", username="Alice")
        with self.assertRaises(LoginRateLimitError) as caught:
            self.limiter.require_slot(client_ip="127.0.0.12", username=" ALICE ")
        self.assertEqual(caught.exception.code, "AUTH_RATE_LIMITED")
        self.assertEqual(self.repo.commits, ACCOUNT_LIMIT + 1)

    def test_source_limit_applies_across_accounts(self):
        for index in range(SOURCE_LIMIT):
            self.limiter.require_slot(client_ip="::1", username=f"person{index}")
        with self.assertRaises(LoginRateLimitError):
            self.limiter.require_slot(client_ip="0:0:0:0:0:0:0:1", username="newperson")
        self.assertEqual(len(self.repo.counts), SOURCE_LIMIT + 1)

    def test_malformed_username_still_consumes_source(self):
        self.limiter.require_slot(client_ip="127.0.0.1", username="\x00")
        self.assertEqual(len(self.repo.counts), 1)

    def test_invalid_source_and_database_failure_deny(self):
        with self.assertRaises(LoginRateLimitError):
            self.limiter.require_slot(client_ip="forwarded.invalid", username="Alice")
        self.repo.fail = True
        with self.assertRaises(LoginRateLimitError) as caught:
            self.limiter.require_slot(client_ip="127.0.0.1", username="Alice")
        self.assertEqual(caught.exception.code, "SYSTEM_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
