"""Synthetic Win11 Edge bridge for the real fixed Review API and isolated PG fixture."""

from __future__ import annotations

import subprocess
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from uuid import uuid4

import uvicorn
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "apps" / "frontend" / "dist"


def run(*, app, sock, origin: str, review_id: str, baseline_id: str,
        version_id: str, reviewer_id: str, reviewer_token: bytes,
        csrf_token: bytes) -> None:
    assert DIST.joinpath("index.html").is_file(), "build frontend before Edge proof"
    token = reviewer_token.hex()
    view = {
        "user": {"user_id": reviewer_id,
                 "username_display": "Synthetic Assigned Reviewer"},
        "deployment_role": "NONE", "password_change_required": False,
        "authorized_projects": [],
        "absolute_expires_at": "2030-01-01T12:00:00Z",
        "idle_expires_at": "2030-01-01T11:00:00Z",
        "csrf_token": csrf_token.hex(),
    }
    auth = APIRouter()

    @auth.get("/api/v1/auth/session")
    def session(request: Request):
        if request.cookies.get("plm_session") != token:
            return JSONResponse({"error": {"code": "AUTH_SESSION_EXPIRED"},
                                 "trace_id": str(uuid4())}, status_code=401)
        return JSONResponse({"data": view, "trace_id": str(uuid4())})

    @auth.post("/api/v1/auth/login")
    def login():
        response = JSONResponse({"data": view, "trace_id": str(uuid4())})
        response.set_cookie("plm_session", token, httponly=True, samesite="strict")
        return response

    app.include_router(auth)
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="edge-assets")

    @app.get("/{frontend_path:path}", include_in_schema=False)
    def frontend(frontend_path: str):
        if frontend_path.startswith("api/"):
            return JSONResponse({"error": {"code": "NOT_FOUND"},
                                 "trace_id": str(uuid4())}, status_code=404)
        return FileResponse(DIST / "index.html", media_type="text/html")

    server = uvicorn.Server(uvicorn.Config(
        app, log_level="critical", access_log=False, proxy_headers=False,
        lifespan="on", timeout_graceful_shutdown=5,
    ))
    worker = Thread(target=lambda: server.run(sockets=[sock]), daemon=False)
    worker.start()
    try:
        deadline = monotonic() + 15
        while not server.started:
            if not worker.is_alive() or monotonic() > deadline:
                raise RuntimeError("synthetic fixed Review server did not start")
            sleep(.05)
        result = subprocess.run(
            ["node", str(Path(__file__).with_name("run-edge-browser.mjs")), origin,
             str(baseline_id), str(version_id), str(review_id)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            check=False, timeout=150,
        )
        if result.returncode:
            raise AssertionError(
                "fixed Review Edge proof failed: "
                + result.stdout[-3500:] + result.stderr[-3500:]
            )
        print(result.stdout.strip(), flush=True)
    finally:
        server.should_exit = True
        worker.join(timeout=15)
        if worker.is_alive():
            raise RuntimeError("synthetic fixed Review server did not stop")
