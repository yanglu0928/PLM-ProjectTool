"""Map fixed Caddy SBOM Go modules to exact vendored license-like source bytes.

This is file provenance, not license classification or release clearance.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import tarfile
import zipfile
from pathlib import Path

from audit_caddy_windows_offline_input import ASSETS
from build_caddy_sbom_review_queue import SBOM, rows_from_sbom
from verify_windows_unified_caddy_candidate import ARCHIVE_SHA256, verify


SOURCE = "payload/third-party-sources/caddy/buildable-artifact.tar.gz"
QUEUE_SHA256 = "3b72ab936c13ff04aff00b2bfae2002c17a00430734943725efc2c5712aca232"
FIELDS = ("bom_ref", "module", "version", "archive_path", "sha256", "bytes", "review_status")
SPECIAL_NAMES = {"Caddy", "caddy", "stdlib",
                 "/home/runner/work/caddy/caddy/dist/caddy_windows_amd64_v1/caddy.exe"}
LICENSE_PREFIXES = ("license", "copying", "notice")


def module_versions(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        match = re.fullmatch(r"# (\S+) (v\S+)", line)
        if not match:
            continue
        name, version = match.groups()
        if name in result:
            raise ValueError("duplicate vendored module identity")
        result[name] = version
    if not result:
        raise ValueError("vendored module identities absent")
    return result


def direct_license_paths(members: dict[str, tarfile.TarInfo], module: str) -> list[str]:
    prefix = f"vendor/{module}/"
    return sorted(name for name, member in members.items()
                  if name.startswith(prefix) and member.isfile()
                  and "/" not in name[len(prefix):]
                  and name[len(prefix):].casefold().startswith(LICENSE_PREFIXES))


def map_evidence(candidate: Path, queue: Path) -> tuple[bytes, dict]:
    identity = verify(candidate)
    if not queue.is_file() or hashlib.sha256(queue.read_bytes()).hexdigest() != QUEUE_SHA256:
        raise ValueError("P29 review queue identity differs")
    with zipfile.ZipFile(candidate) as archive:
        sbom_raw, source_raw = archive.read(SBOM), archive.read(SOURCE)
    if (hashlib.sha256(sbom_raw).hexdigest() != ASSETS["windows_amd64.sbom"][1]
            or hashlib.sha256(source_raw).hexdigest() != ASSETS["buildable-artifact.tar.gz"][1]):
        raise ValueError("fixed SBOM/source identity differs")
    components = rows_from_sbom(json.loads(sbom_raw))
    with queue.open("r", encoding="utf-8", newline="") as stream:
        queue_rows = list(csv.DictReader(stream))
    if len(queue_rows) != 149 or any(queue_rows[index] != row for index, row in enumerate(components)):
        raise ValueError("P29 review queue content differs")
    evidence = []
    special = []
    with tarfile.open(fileobj=io.BytesIO(source_raw), mode="r:gz") as source:
        entries = source.getmembers()
        members = {member.name: member for member in entries}
        if len(members) != len(entries) or "vendor/modules.txt" not in members:
            raise ValueError("source archive member identity rejected")
        modules_file = source.extractfile(members["vendor/modules.txt"])
        if modules_file is None:
            raise ValueError("vendored module manifest unreadable")
        versions = module_versions(modules_file.read().decode("utf-8"))
        for row in components:
            module, version = row["name"], row["version"]
            if module not in versions:
                special.append(module)
                continue
            if version != versions[module] or row["purl"] != f"pkg:golang/{module}@{version}":
                raise ValueError("SBOM/vendored module version or PURL mismatch")
            paths = direct_license_paths(members, module)
            if not paths:
                raise ValueError("vendored module has no direct license-like file")
            for path in paths:
                file = source.extractfile(members[path])
                if file is None:
                    raise ValueError("vendored license-like file unreadable")
                body = file.read()
                if not body:
                    raise ValueError("vendored license-like file empty")
                evidence.append({"bom_ref": row["bom_ref"], "module": module,
                                 "version": version, "archive_path": path,
                                 "sha256": hashlib.sha256(body).hexdigest(),
                                 "bytes": str(len(body)), "review_status": "REVIEW_REQUIRED"})
    if len(evidence) != 154 or len({row["module"] for row in evidence}) != 145 or set(special) != SPECIAL_NAMES:
        raise ValueError("fixed Caddy source coverage differs")
    evidence.sort(key=lambda row: (row["module"].casefold(), row["archive_path"].casefold()))
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(evidence)
    body = output.getvalue().encode("utf-8")
    return body, {"status": "NON_RELEASE_CADDY_VENDOR_SOURCE_EVIDENCE",
                  "release_eligible": False, "legal_clearance": False,
                  "candidate_sha256": ARCHIVE_SHA256,
                  "payload_file_count": identity["payload_file_count"],
                  "source_sha256": hashlib.sha256(source_raw).hexdigest(),
                  "matched_vendor_modules": 145,
                  "version_and_purl_match_count": 145,
                  "direct_license_like_files": len(evidence),
                  "special_components_not_mapped_to_vendor": sorted(special),
                  "queue_sha256": QUEUE_SHA256,
                  "evidence_sha256": hashlib.sha256(body).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    body, report = map_evidence(args.candidate, args.queue)
    if args.output.exists() or not args.output.parent.is_dir():
        raise ValueError("evidence output must be a new file in an existing directory")
    with args.output.open("xb") as stream:
        stream.write(body)
    if args.output.read_bytes() != body:
        raise ValueError("evidence output readback differs")
    print(json.dumps({**report, "output": str(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
