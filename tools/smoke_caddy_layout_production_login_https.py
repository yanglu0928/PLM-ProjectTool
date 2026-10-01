"""Replay original real PG/Vault production-login assertions through P25 layout Caddy.

This is synthetic loopback acceptance, not provisioned release trust or target SCM.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_caddy_windows_offline_input import EXE_SHA256, digest
from build_windows_unified_caddy_candidate import TEMPLATE_SHA256
from smoke_caddy_isolated_layout_https import verify_layout
from smoke_caddy_production_login_https import smoke as original_smoke
from smoke_staged_caddy_template import render


def smoke(candidate: Path, stage: Path, layout: Path) -> dict:
    verified = verify_layout(candidate, stage, layout)
    layout = layout.resolve(strict=True)
    caddy = layout / "runtime/caddy/caddy.exe"
    template = layout / "config/Caddyfile.template"

    def audit_boundary(root: Path) -> None:
        if root.resolve(strict=True) != layout or digest(caddy) != EXE_SHA256 or digest(template) != TEMPLATE_SHA256:
            raise ValueError("layout Caddy/template identity rejected")

    def config_builder(frontend: Path, cert: Path, key: Path, api_port: int, https_port: int) -> str:
        if frontend.resolve(strict=True) != (layout / "app/frontend/dist").resolve(strict=True):
            raise ValueError("layout frontend root rejected")
        return render(template.read_text(encoding="ascii"), cert=cert, key=key,
                      frontend=frontend, api_port=api_port, https_port=https_port)

    result = original_smoke(layout, candidate, layout,
                            layout_verifier=lambda *_: verified["file_count"],
                            boundary_audit=audit_boundary,
                            caddy_relative="runtime/caddy/caddy.exe",
                            config_builder=config_builder)
    if result["payload_file_count"] != 21113 or not result["vault_target_unique_and_absence_verified"]:
        raise ValueError("layout login acceptance incomplete")
    return {**result, "status": "NON_RELEASE_CADDY_LAYOUT_PRODUCTION_LOGIN_HTTPS_PASS",
            "payload_file_count": 21110, "verified_layout_file_count": 21113,
            "mapping_sha256": verified["mapping_sha256"],
            "packaged_api_binary_exercised": False, "formal_install_performed": False,
            "services_changed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.candidate, args.stage, args.layout), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
