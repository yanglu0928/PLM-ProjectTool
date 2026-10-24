"""Interactive Windows-only Secret master-key lifecycle entrypoint."""

from __future__ import annotations

import getpass
import sys
import warnings
from pathlib import Path

from plm_assistant.modules.platform.infrastructure.windows_secret_key_lifecycle import (
    export_backup, provision_new, restore_backup,
)


def main() -> int:
    if (sys.platform != "win32" or not sys.stdin.isatty()
            or len(sys.argv) not in (3, 4)):
        print("Interactive Windows terminal and valid arguments required.", file=sys.stderr)
        return 2
    action = sys.argv[1]
    if (action == "restore" and len(sys.argv) == 3):
        key_ref = None
        path_text = sys.argv[2]
    elif action in ("provision", "export") and len(sys.argv) == 4:
        key_ref = sys.argv[2]
        path_text = sys.argv[3]
    else:
        print("Usage: provision|export <key-ref> <absolute-backup-path>, or restore <absolute-backup-path>.", file=sys.stderr)
        return 2
    try:
        path = Path(path_text)
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            passphrase = getpass.getpass("Recovery passphrase (hidden): ")
            confirmation = getpass.getpass("Confirm recovery passphrase (hidden): ")
        if passphrase != confirmation:
            print("Passphrase confirmation failed.", file=sys.stderr)
            return 2
        if action == "provision":
            provision_new(key_ref=key_ref, backup_path=path, passphrase=passphrase)
        elif action == "export":
            export_backup(key_ref=key_ref, backup_path=path, passphrase=passphrase)
        else:
            restore_backup(backup_path=path, passphrase=passphrase)
        print("Secret key operation completed. Store backup and passphrase separately offline.")
        return 0
    except Exception:
        print("Secret key operation failed; no key material was printed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
