"""Read-only trust inventory and bounded fail-closed launch of packaged Windows API.

Never provisions credentials, License keys, certificates, a database, or SCM.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from smoke_caddy_isolated_layout_https import verify_layout


DATABASE_CREDENTIAL_TARGET = "PLMProjectTool/Database"
PUBLIC_KEY_RELATIVE = "runtime/python/Lib/site-packages/plm_assistant/modules/license/trust/product_public_key.json"


def database_credential_present() -> bool:
    if sys.platform != "win32":
        raise ValueError("Windows-only trust inventory")
    library = ctypes.WinDLL("Advapi32", use_last_error=True)
    library.CredReadW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong,
                                 ctypes.POINTER(ctypes.c_void_p)]
    library.CredReadW.restype = ctypes.c_int
    library.CredFree.argtypes = [ctypes.c_void_p]
    pointer = ctypes.c_void_p()
    found = library.CredReadW(DATABASE_CREDENTIAL_TARGET, 1, 0, ctypes.byref(pointer))
    if found:
        library.CredFree(pointer)
        return True
    if ctypes.get_last_error() != 1168:
        raise ValueError("database credential existence check unavailable")
    return False


def free_port() -> int:
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


def preflight(candidate: Path, stage: Path, layout: Path) -> dict:
    verified = verify_layout(candidate, stage, layout)
    layout = layout.resolve(strict=True)
    public_key_present = (layout / PUBLIC_KEY_RELATIVE).is_file()
    credential_present = database_credential_present()
    result = {"status": "NON_RELEASE_PACKAGED_PRODUCTION_PREFLIGHT",
              "release_eligible": False, "verified_layout_file_count": verified["file_count"],
              "mapping_sha256": verified["mapping_sha256"],
              "packaged_product_public_key_present": public_key_present,
              "current_account_database_credential_present": credential_present,
              "formal_trust_provisioned": False, "services_changed": False,
              "existing_database_connected": False}
    if credential_present:
        # An existing account credential may point at production; do not launch against it.
        return {**result, "startup_probe": "SKIPPED_EXISTING_CREDENTIAL_UNSCOPED"}
    python = layout / "runtime/python/python.exe"
    if not python.is_file():
        raise ValueError("packaged runtime missing")
    with tempfile.TemporaryDirectory(prefix="plm-packaged-startup-preflight-") as directory:
        root = Path(directory)
        if not str(root).isascii():
            raise ValueError("preflight root must be ASCII")
        data = root / "data"
        data.mkdir()
        config = root / "bootstrap.yaml"
        port = free_port()
        config.write_text(f'bind_host: "127.0.0.1"\nbind_port: {port}\n'
                          f'data_root: "{data.as_posix()}"\nlog_level: "ERROR"\n'
                          'trusted_origins: ["https://localhost"]\n', encoding="ascii")
        env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PLM_")}
        env.pop("PYTHONPATH", None)
        env["PATH"] = os.pathsep.join((str(layout / "runtime/python"),
                                       str(Path(os.environ["WINDIR"]) / "System32"), os.environ["WINDIR"]))
        launch = subprocess.run([str(python), "-I", "-B", "-m",
                                 "plm_assistant.entrypoints.serve_windows", str(config), "--platform-write"],
                                capture_output=True, text=True, errors="replace", timeout=20, env=env)
        if (launch.returncode != 1 or launch.stdout.strip()
                or launch.stderr.strip() != "Production server unavailable; configuration or credential rejected."):
            raise ValueError("packaged production startup did not fail closed without DB credential")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))
        result["startup_probe"] = "FAIL_CLOSED_MISSING_ACCOUNT_DATABASE_CREDENTIAL"
        result["api_port_unbound_after_exit"] = True
        result["production_mode_exercised"] = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(preflight(args.candidate, args.stage, args.layout), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
