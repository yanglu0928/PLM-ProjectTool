from __future__ import annotations
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_windows_authenticode as verifier  # noqa: E402

class AuthenticodeVerifierTests(unittest.TestCase):
    def test_valid_signature_and_exact_external_pin(self):
        good="A"*40
        proc=Mock(returncode=0,stdout=json.dumps({"status":"Valid","thumbprint":good}),stderr="")
        with patch.object(verifier.subprocess,"run",return_value=proc) as run:
            result=verifier.verify(Path(__file__),good)
        self.assertTrue(result["signature_verified"])
        self.assertEqual(result["status"],"AUTHENTICODE_VERIFIED_TEST_ONLY")
        self.assertEqual(run.call_count,1)

    def test_unsigned_and_invalid_chain_are_rejected(self):
        for status in ("NotSigned","HashMismatch","NotTrusted","UnknownError"):
            proc=Mock(returncode=0,stdout=json.dumps({"status":status,"thumbprint":"A"*40}),stderr="")
            with self.subTest(status=status), patch.object(verifier.subprocess,"run",return_value=proc):
                self.assertFalse(verifier.verify(Path(__file__),"A"*40)["signature_verified"])

    def test_publisher_mismatch_is_rejected(self):
        proc=Mock(returncode=0,stdout=json.dumps({"status":"Valid","thumbprint":"B"*40}),stderr="")
        with patch.object(verifier.subprocess,"run",return_value=proc):
            result=verifier.verify(Path(__file__),"A"*40)
        self.assertEqual(result["reason_code"],"PUBLISHER_MISMATCH")

    def test_invalid_pin_never_invokes_powershell(self):
        with patch.object(verifier.subprocess,"run") as run:
            result=verifier.verify(Path(__file__),"")
        self.assertEqual(result["reason_code"],"INVALID_PUBLISHER_PIN")
        run.assert_not_called()

    def test_process_failure_and_malformed_output_fail_closed(self):
        with patch.object(verifier.subprocess,"run",side_effect=OSError("path-like detail")):
            result=verifier.verify(Path(__file__),"A"*40)
        self.assertEqual(result["reason_code"],"INSPECTION_FAILED")
        self.assertNotIn("path",json.dumps(result))
        proc=Mock(returncode=0,stdout="not json",stderr="")
        with patch.object(verifier.subprocess,"run",return_value=proc):
            self.assertFalse(verifier.verify(Path(__file__),"A"*40)["signature_verified"])

if __name__=="__main__":
    unittest.main()
