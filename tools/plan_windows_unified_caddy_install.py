"""Read-only exact layout and service-boundary plan for the pinned P22 ZIP.

No file extraction, target-root writes, SCM registration, TLS provisioning, or migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

from package_windows_unified_candidate import safe_name
from rehearse_windows_unified_pg18_layout import target_name as previous_target_name
from verify_windows_unified_caddy_candidate import ARCHIVE_SHA256, verify
from windows_install_root_preflight import validate_install_root


META = ("manifest.json", "payload-sha256sums.txt", "third-party-inventory.json")
APPLICATION_SERVICES = (
    ("API", "PLMProjectToolApi"),
    ("AUDIT_WORKER", "PLMProjectToolAuditWorker"),
    ("PARSER_WORKER", "PLMProjectToolParserWorker"),
)


def target_name(source: str) -> str:
    safe_name(source)
    for prefix, target in (("payload/web/", "runtime/caddy/"),
                           ("payload/third-party-sources/", "app/third-party-sources/")):
        if source.startswith(prefix) and len(source) > len(prefix):
            return safe_name(target + source[len(prefix):])
    return previous_target_name(source)


def exact_mapping(names: list[str]) -> tuple[dict[str, str], str]:
    if len(names) != len(set(names)) or len(names) != len({name.casefold() for name in names}):
        raise ValueError("source path collision")
    mapping = {source: target_name(source) for source in names}
    if len(mapping) != len(names) or len(mapping) != len({target.casefold() for target in mapping.values()}):
        raise ValueError("Windows target path collision")
    digest = hashlib.sha256()
    for source, target in sorted(mapping.items(), key=lambda pair: pair[0].casefold()):
        digest.update(f"{source}\t{target}\n".encode("utf-8"))
    return mapping, digest.hexdigest()


def plan_install(candidate: Path, install_root: str) -> dict:
    root = validate_install_root(install_root)  # Reject unsafe target before touching ZIP.
    identity = verify(candidate)  # Full fixed-archive and payload hash audit.
    with zipfile.ZipFile(candidate) as archive:
        names = [item.filename for item in archive.infolist() if not item.is_dir()]
        if len(names) != 21110 + len(META) or set(META) - set(names):
            raise ValueError("candidate file set rejected")
        mapping, mapping_sha256 = exact_mapping(names)
    required = {
        "payload/web/caddy.exe": "runtime/caddy/caddy.exe",
        "payload/config/Caddyfile.template": "config/Caddyfile.template",
        "payload/third-party-sources/caddy/buildable-artifact.tar.gz":
            "app/third-party-sources/caddy/buildable-artifact.tar.gz",
        "payload/third-party-licenses/caddy/LICENSE": "app/third-party-licenses/caddy/LICENSE",
        "payload/pgsql/bin/postgres.exe": "runtime/pgsql/bin/postgres.exe",
        "manifest.json": "app/package-metadata/manifest.json",
    }
    if any(mapping.get(source) != target for source, target in required.items()):
        raise ValueError("required target layout missing")
    families = Counter(target.split("/", 1)[0] for target in mapping.values())
    return {
        "status": "NON_RELEASE_READ_ONLY_CADDY_INSTALL_PLAN",
        "candidate_sha256": ARCHIVE_SHA256,
        "payload_file_count": identity["payload_file_count"],
        "mapped_file_count": len(mapping),
        "mapping_sha256": mapping_sha256,
        "mapping_families": dict(sorted(families.items())),
        "required_mapping": required,
        "install_root": root,
        "install_root_exists": Path(root).exists(),
        "install_authorized": False,
        "release_eligible": False,
        "archive_extracted": False,
        "services_changed": False,
        "database_started": False,
        "migration_executed": False,
        "application_services": [
            {"role": role, "service_name": name, "registered": False}
            for role, name in APPLICATION_SERVICES
        ],
        "web_boundary_service": {
            "role": "HTTPS_STATIC_REVERSE_PROXY", "service_name": "PLMProjectToolWeb",
            "executable": "runtime/caddy/caddy.exe", "template": "config/Caddyfile.template",
            "registered": False, "independent_of_three_application_services": True,
        },
        "preflight_open": [
            "target service account identity, logon rights, binary/config/data/log ACL and recovery policy",
            "customer-supplied DNS name and matching certificate/private key source, ACL, renewal and recovery",
            "rendered Caddyfile validation and API loopback/trusted Host/Origin under target account",
            "formal License trust material and initial administrator ceremony",
            "PostgreSQL data location, backup/restore, migration and controlled service ordering",
            "complete third-party NOTICE/source legal clearance and platform acceptance",
        ],
        "next_safe_action": "isolated full-layout rehearsal from fixed P23 stage, never C:\\PLMTool",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--install-root", required=True)
    args = parser.parse_args()
    print(json.dumps(plan_install(args.candidate, args.install_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
