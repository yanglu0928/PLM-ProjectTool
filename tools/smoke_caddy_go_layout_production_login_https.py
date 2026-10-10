"""Replay real PG/Vault login assertions through fixed P35 layout Caddy over HTTPS."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from smoke_caddy_go_layout_https import verify_layout
from smoke_caddy_layout_production_login_https import smoke as original_smoke


def smoke(candidate: Path, source: Path, stage: Path, layout: Path) -> dict:
    verified = verify_layout(candidate, source, stage, layout)
    result = original_smoke(
        candidate, stage, layout,
        layout_verifier=lambda *_: verified,
        expected_file_count=21115,
        payload_count=21112,
        result_status="NON_RELEASE_CADDY_GO_LAYOUT_PRODUCTION_LOGIN_HTTPS_PASS",
    )
    if result["mapping_sha256"] != verified["mapping_sha256"] or result["packaged_api_binary_exercised"] is not False:
        raise ValueError("new candidate login proof scope differs")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.candidate, args.source, args.stage, args.layout),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
