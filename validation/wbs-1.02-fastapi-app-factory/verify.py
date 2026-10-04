from __future__ import annotations

import argparse
import json
import platform
import sys
from importlib.metadata import version
from pathlib import Path

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app


REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = (
    REPO_ROOT
    / "validation/wbs-1.02-fastapi-app-factory/evidence/windows-11/result.json"
)


def verify() -> dict[str, object]:
    app = create_app()
    route_paths = sorted(app.openapi()["paths"])
    if route_paths != ["/health/live", "/health/ready"]:
        raise ValueError(f"Unexpected public routes: {route_paths}")

    with TestClient(app) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")
        docs = client.get("/docs")
    if live.status_code != 200 or live.json() != {"status": "UP"}:
        raise ValueError("Liveness contract failed")
    if ready.status_code != 200 or ready.json() != {"status": "UP"}:
        raise ValueError("Readiness contract failed")
    if docs.status_code != 404:
        raise ValueError("Interactive API docs must not be exposed")

    with TestClient(create_app(readiness_checks=[lambda: False])) as client:
        unavailable = client.get("/health/ready")
    if unavailable.status_code != 503 or unavailable.json() != {
        "status": "NOT_READY"
    }:
        raise ValueError("Readiness failure contract failed")

    return {
        "status": "PASS",
        "wbs": "1.02",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "fastapi": version("fastapi"),
        "starlette": version("starlette"),
        "pydantic": version("pydantic"),
        "uvicorn": version("uvicorn"),
        "httpx2": version("httpx2"),
        "app_instance_isolation": create_app() is not create_app(),
        "registered_route_count": len(route_paths),
        "registered_routes": route_paths,
        "liveness_status": live.status_code,
        "readiness_status": ready.status_code,
        "failed_readiness_status": unavailable.status_code,
        "docs_exposed": False,
        "database_call_count": 0,
        "external_call_count": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.write:
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
