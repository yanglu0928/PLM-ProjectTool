"""Interactive, local-only Windows database credential provisioning."""

from __future__ import annotations

import getpass
import sys
import warnings

from plm_assistant.modules.platform.infrastructure.windows_database_credential import (
    read_database_url,
    write_database_url,
)


def main() -> int:
    if len(sys.argv) != 1 or sys.platform != "win32" or not sys.stdin.isatty():
        print("Interactive Windows terminal required; no arguments accepted.", file=sys.stderr)
        return 2
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            url = getpass.getpass("Database URL (hidden): ")
            confirmation = getpass.getpass("Confirm database URL (hidden): ")
        if url != confirmation:
            print("Credential confirmation failed.", file=sys.stderr)
            return 2
        write_database_url(url)
        read_database_url()
        print("Database credential stored for the current Windows account.")
        return 0
    except Exception:
        print("Database credential provisioning failed; no value was printed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
