"""Own the Prototype fixture and real Edge driver as one auditable validation."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
READY = re.compile(
    r"SUR_SOURCE_BROWSER_READY (?P<url>http://127\.0\.0\.1:\d+/login) "
    r"PROJECT=(?P<project>[0-9a-f-]{36}).*EVIDENCE=(?P<evidence>[0-9a-f-]{36})"
)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    source = str(ROOT / "apps/backend/src")
    environment["PYTHONPATH"] = source + os.pathsep + environment.get("PYTHONPATH", "")
    creation = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    server = subprocess.Popen(
        [sys.executable, str(HERE / "serve.py")],
        cwd=ROOT,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=creation,
    )
    transcript: list[str] = []
    try:
        assert server.stdout is not None
        match = None
        while True:
            line = server.stdout.readline()
            if not line:
                raise RuntimeError(
                    "fixture stopped before ready\n" + "".join(transcript[-80:])
                )
            print(line, end="")
            transcript.append(line)
            match = READY.search(line)
            if match:
                break
        origin = match.group("url").removesuffix("/login")
        output = ROOT / "artifacts/prt-01-a10-a07-windows-browser"
        driver = subprocess.run(
            [
                "node",
                str(HERE / "run-edge-browser.mjs"),
                origin,
                match.group("project"),
                str(output),
            ],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=creation,
            timeout=180,
        )
        print(driver.stdout, end="")
        if driver.returncode:
            assert server.stdin is not None
            server.stdin.write("ABORT\n")
            server.stdin.flush()
            for line in server.stdout:
                print(line, end="")
            server.wait(timeout=60)
            raise RuntimeError(f"Edge driver failed with {driver.returncode}")
        assert server.stdin is not None
        server.stdin.write("VERIFY\n")
        server.stdin.flush()
        for line in server.stdout:
            print(line, end="")
            transcript.append(line)
        code = server.wait(timeout=60)
        if code:
            raise RuntimeError(
                f"fixture failed with {code}\n" + "".join(transcript[-80:])
            )
        required = (
            "PRT_01_A10_A07_WINDOWS_EDGE_BROWSER_PASS",
            "SUR_01_A06_A05_P02_WINDOWS_BROWSER_CLEANUP_PASS",
        )
        complete = driver.stdout + "".join(transcript)
        if any(marker not in complete for marker in required):
            raise RuntimeError("validation marker missing")
        print("PRT_01_A10_A07_OWNED_VALIDATION_PASS")
    finally:
        if server.poll() is None:
            server.kill()
            server.wait(timeout=20)
        for stream in (server.stdin, server.stdout):
            if stream is not None:
                stream.close()


if __name__ == "__main__":
    main()
