"""Read-only Windows Authenticode verifier with an out-of-band publisher pin."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_THUMBPRINT = re.compile(r"^[0-9A-Fa-f]{40}$")
_POWERSHELL = r"""
$ErrorActionPreference = 'Stop'
$s = Get-AuthenticodeSignature -LiteralPath $env:PLM_AUTHENTICODE_FILE
$t = ''
if ($null -ne $s.SignerCertificate) { $t = ($s.SignerCertificate.Thumbprint -replace '\\s','').ToUpperInvariant() }
[pscustomobject]@{ status = [string]$s.Status; thumbprint = $t } | ConvertTo-Json -Compress
"""

def verify(path: Path, expected_thumbprint: str) -> dict:
    if not isinstance(expected_thumbprint, str) or not _THUMBPRINT.fullmatch(expected_thumbprint):
        return {"status":"AUTHENTICODE_REJECTED","reason_code":"INVALID_PUBLISHER_PIN","signature_verified":False}
    try:
        candidate = path.resolve(strict=True)
        if not candidate.is_file() or path.is_symlink():
            raise ValueError("not a regular file")
        env = os.environ.copy()
        env["PLM_AUTHENTICODE_FILE"] = str(candidate)
        proc = subprocess.run(
            ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", _POWERSHELL],
            capture_output=True, text=True, timeout=30, check=False, env=env,
        )
        if proc.returncode != 0:
            raise ValueError("signature inspection failed")
        result = json.loads(proc.stdout)
        status = result.get("status")
        signer = result.get("thumbprint", "")
        if status != "Valid":
            reason = "SIGNATURE_NOT_VALID"
        elif not isinstance(signer, str) or signer.upper() != expected_thumbprint.upper():
            reason = "PUBLISHER_MISMATCH"
        else:
            return {"status":"AUTHENTICODE_VERIFIED_TEST_ONLY","reason_code":None,"signature_verified":True}
        return {"status":"AUTHENTICODE_REJECTED","reason_code":reason,"signature_verified":False}
    except Exception:
        return {"status":"AUTHENTICODE_REJECTED","reason_code":"INSPECTION_FAILED","signature_verified":False}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--expected-thumbprint", required=True)
    args = parser.parse_args()
    result = verify(args.file, args.expected_thumbprint)
    print(json.dumps(result, sort_keys=True, separators=(",",":")))
    return 0 if result["signature_verified"] else 2

if __name__ == "__main__":
    sys.exit(main())
