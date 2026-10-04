"""Read-only, fail-closed inventory for the pinned Windows non-release install layout.

This is not an installer or a release clearance. It never starts services, reads
Credential Manager for another account, or prints certificate/private-key data.
"""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import json
import re
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cryptography import x509

from preflight_packaged_production_startup_windows import PUBLIC_KEY_RELATIVE
from smoke_caddy_go_layout_https import verify_layout
from windows_install_root_preflight import validate_install_root


_ACCOUNT = re.compile(r"(?:\.|[A-Za-z0-9_.-]{1,64})\\[A-Za-z0-9_.\-$]{1,64}\Z")
_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z")


def valid_public_host(host: str | None) -> bool:
    if not host or len(host) > 253 or host.lower() == "localhost":
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    labels = host.split(".")
    return len(labels) >= 2 and all(_LABEL.fullmatch(label) for label in labels)


def tls_certificate_codes(host: str | None, cert: Path | None, key: Path | None) -> list[str]:
    if not valid_public_host(host):
        return ["PUBLIC_DNS_NAME_MISSING_OR_INVALID"]
    if cert is None or key is None:
        return ["TLS_CERTIFICATE_AND_KEY_NOT_SUPPLIED"]
    if not cert.is_file() or not key.is_file() or cert.resolve() == key.resolve():
        return ["TLS_CERTIFICATE_OR_KEY_UNAVAILABLE"]
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(cert), str(key))
        certificate = x509.load_pem_x509_certificate(cert.read_bytes())
        names = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        dns_names = names.get_values_for_type(x509.DNSName)
        if host.lower() not in {name.lower() for name in dns_names}:
            return ["TLS_CERTIFICATE_DNS_SAN_MISMATCH"]
        now = dt.datetime.now(dt.timezone.utc)
        if not certificate.not_valid_before_utc <= now < certificate.not_valid_after_utc:
            return ["TLS_CERTIFICATE_NOT_CURRENTLY_VALID"]
    except (OSError, ValueError, ssl.SSLError, x509.ExtensionNotFound):
        return ["TLS_CERTIFICATE_OR_KEY_INVALID"]
    return []


def preflight(candidate: Path, source: Path, stage: Path, layout: Path, *,
              install_root: str, target_account: str | None,
              public_host: str | None, tls_cert: Path | None, tls_key: Path | None) -> dict:
    root = validate_install_root(install_root)
    verified = verify_layout(candidate, source, stage, layout)
    blockers = []
    if Path(root).exists():
        blockers.append("FORMAL_INSTALL_ROOT_ALREADY_EXISTS_REQUIRES_SEPARATE_UPGRADE_PLAN")
    if not target_account or not _ACCOUNT.fullmatch(target_account) or target_account.upper().startswith(
            ("NT AUTHORITY\\", "NT SERVICE\\")):
        blockers.append("TARGET_SERVICE_ACCOUNT_NOT_IDENTIFIED")
    tls_codes = tls_certificate_codes(public_host, tls_cert, tls_key)
    blockers.extend(tls_codes)
    if not (layout / PUBLIC_KEY_RELATIVE).is_file():
        blockers.append("FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED")
    # The target account's Vault, file ACL, SCM logon right, and recovery cannot
    # be inferred from this developer process, even if an account name is given.
    blockers.extend((
        "TARGET_ACCOUNT_VAULT_AND_ACL_NOT_VERIFIED",
        "SCM_LOGON_AND_SERVICE_RECOVERY_NOT_VERIFIED",
        "TLS_CHAIN_TRUST_AND_RENEWAL_NOT_VERIFIED",
        "DATABASE_BACKUP_RESTORE_AND_MIGRATION_NOT_VERIFIED",
        "THIRD_PARTY_RELEASE_CLEARANCE_NOT_VERIFIED",
        "TARGET_PLATFORM_INSTALLATION_NOT_VERIFIED",
    ))
    return {
        "status": "FORMAL_WINDOWS_INSTALL_PREFLIGHT_BLOCKED",
        "release_eligible": False,
        "install_authorized": False,
        "verified_layout_file_count": verified["file_count"],
        "mapping_sha256": verified["mapping_sha256"],
        "install_root": root,
        "target_account_name_supplied": bool(target_account),
        "tls_pair_structurally_valid": not tls_codes,
        "blocker_codes": blockers,
        "services_changed": False,
        "database_connected": False,
        "target_root_written": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "source", "stage", "layout"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--install-root", default=r"C:\PLMTool")
    parser.add_argument("--target-account")
    parser.add_argument("--public-host")
    parser.add_argument("--tls-cert", type=Path)
    parser.add_argument("--tls-key", type=Path)
    args = parser.parse_args()
    try:
        result = preflight(args.candidate, args.source, args.stage, args.layout,
                           install_root=args.install_root, target_account=args.target_account,
                           public_host=args.public_host, tls_cert=args.tls_cert, tls_key=args.tls_key)
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "PREFLIGHT_INPUT_REJECTED", "release_eligible": False,
                          "reason": type(error).__name__}), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
