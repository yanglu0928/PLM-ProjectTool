"""Run the Windows login assembly from explicit non-secret deployment YAML."""

from __future__ import annotations

import ipaddress
import sys
from pathlib import Path

import uvicorn

from plm_assistant.entrypoints.production_login import create_production_login_app
from plm_assistant.modules.platform.infrastructure.bootstrap_config import load_bootstrap_settings


def main() -> int:
    if sys.platform != "win32" or len(sys.argv) != 2:
        print("Usage: python -m plm_assistant.entrypoints.serve_windows <bootstrap.yaml>", file=sys.stderr)
        return 2
    try:
        settings = load_bootstrap_settings(Path(sys.argv[1]).resolve(strict=True))
        if not ipaddress.ip_address(settings.bind_host).is_loopback:
            raise ValueError("non-loopback HTTP bind is unavailable")
        # Uvicorn calls the factory; no database URL or Secret enters argv/env.
        uvicorn.run(
            lambda: create_production_login_app(settings),
            factory=True, host=settings.bind_host, port=settings.bind_port,
            log_level=settings.log_level.value.lower(),
            proxy_headers=False, forwarded_allow_ips="",
        )
        return 0
    except Exception:
        print("Production server unavailable; configuration or credential rejected.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
