"""Release-gate check for the installed product-only public trust anchor."""

from __future__ import annotations

import sys

from plm_assistant.modules.license.infrastructure.packaged_product_key import (
    PackagedProductKey, PackagedProductKeyError,
)


def main() -> int:
    if len(sys.argv) != 1:
        print("No arguments accepted.", file=sys.stderr)
        return 2
    try:
        PackagedProductKey()
    except PackagedProductKeyError:
        print("Release product public key unavailable.", file=sys.stderr)
        return 1
    print("Release product public key available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
