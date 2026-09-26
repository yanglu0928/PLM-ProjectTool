from __future__ import annotations

import unittest

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)


class LoginOriginPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = LoginOriginPolicy(["https://plm.example.test", "http://127.0.0.1:8000"])

    def test_exact_https_and_local_loopback(self):
        self.policy.require_trusted([(b"host", b"PLM.EXAMPLE.TEST"),
                                     (b"origin", b"https://plm.example.test")])
        self.policy.require_trusted([(b"host", b"127.0.0.1:8000"),
                                     (b"origin", b"http://127.0.0.1:8000")])

    def test_missing_duplicate_and_ambiguous_headers_deny(self):
        base = [(b"host", b"plm.example.test"), (b"origin", b"https://plm.example.test")]
        for headers in (base[:1], base[1:], base + [base[0]], base + [base[1]],
                        [(b"host", b"plm.example.test,attacker.test"), base[1]],
                        [(b"host", b"plm.example.test"), (b"origin", b"null")],
                        [(b"host", b"plm.example.test"), (b"origin", b"https://plm.example.test.evil")],
                        [(b"host", b"plm.example.test"), (b"origin", b"https://plm.example.test/path")],
                        [(b"host", b"plm.example.test"), (b"origin", b"https://plm.example.test:443")],
                        [(b"host", b"plm.example.test"), (b"origin", b"https://plm.example.test\n")],
                        [(b"host", b"plm.example.test"), (b"origin", b"\xff")]):
            with self.subTest(headers=headers), self.assertRaises(LoginOriginError):
                self.policy.require_trusted(headers)

    def test_rejects_insecure_nonloopback_configuration(self):
        for origin in ("http://plm.example.test", "https://*.example.test",
                       "https://plm.example.test/path", "https://plm.example.test:0",
                       "https://plm.example.test:65536", "https://user@plm.example.test"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                LoginOriginPolicy([origin])
        with self.assertRaises(ValueError):
            LoginOriginPolicy([])

    def test_untrusted_forwarded_host_cannot_override_host(self):
        with self.assertRaises(LoginOriginError):
            self.policy.require_trusted([
                (b"host", b"internal.example.test"),
                (b"origin", b"https://plm.example.test"),
                (b"x-forwarded-host", b"plm.example.test"),
            ])

    def test_read_only_host_without_origin_and_optional_origin(self):
        self.policy.require_trusted_host([(b"host", b"plm.example.test")])
        self.policy.require_trusted_host([
            (b"host", b"plm.example.test"), (b"origin", b"https://plm.example.test")
        ])
        for headers in (
            [],
            [(b"host", b"plm.example.test"), (b"host", b"plm.example.test")],
            [(b"host", b"evil.test")],
            [(b"host", b"plm.example.test"), (b"origin", b"https://evil.test")],
            [(b"host", b"plm.example.test"), (b"origin", b"https://plm.example.test"),
             (b"origin", b"https://plm.example.test")],
        ):
            with self.subTest(headers=headers), self.assertRaises(LoginOriginError):
                self.policy.require_trusted_host(headers)


if __name__ == "__main__":
    unittest.main()
