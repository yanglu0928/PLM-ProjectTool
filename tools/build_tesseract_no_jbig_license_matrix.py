"""Reconcile the no-JBIG PoC PE graph with prior package license evidence.

The output is evidence location only; it never grants release approval.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


NEW_DLL = "libtiff-6.dll"
REMOVED_DLL = "libjbig-0.dll"
LIBTIFF_SOURCE_SHA256 = "672bd7d10aee4606171afb864f3570b83340f6a33e2c186dc0512f7145ffdf6a"
LIBTIFF_LICENSE_SHA256 = "0e27c2382d7b8147972bbb746e04059a1152c8d0fda9d03ef1399d1a433c4ade"
FIELDS = (
    "binary", "binary_sha256", "source_kind", "source_name", "source_version",
    "source_sha256", "package_declared_license", "license_evidence_status",
    "license_evidence_path", "license_evidence_sha256", "prior_binary_sha256",
    "release_obligations_reviewed",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_rows(prior_csv: Path, graph_json: Path, candidate_root: Path,
               source_tar: Path, license_file: Path) -> list[dict[str, str]]:
    with prior_csv.open(encoding="utf-8-sig", newline="") as source:
        prior = {row["binary"]: row for row in csv.DictReader(source)}
    if len(prior) != 35 or NEW_DLL not in prior or REMOVED_DLL not in prior:
        raise ValueError("prior 35-PE evidence is incomplete")
    graph = json.loads(graph_json.read_text(encoding="utf-8"))
    names = graph["needed_local_files"]
    expected = set(prior) - {REMOVED_DLL}
    if len(names) != 34 or set(names) != expected or len(names) != len(set(names)):
        raise ValueError("no-JBIG static graph differs from prior PE set")
    if graph["needed_sha256"].keys() != expected:
        raise ValueError("static graph SHA set differs")
    if graph.get("unused_local_dlls") or graph.get("non_root_dlls_not_in_static_graph"):
        raise ValueError("static graph has unused or unresolved local DLLs")
    if REMOVED_DLL.lower() in json.dumps(graph).lower():
        raise ValueError("static graph still refers to JBIG")
    if digest(source_tar) != LIBTIFF_SOURCE_SHA256:
        raise ValueError("libtiff source archive differs")
    if digest(license_file) != LIBTIFF_LICENSE_SHA256:
        raise ValueError("libtiff source license differs")
    rows = []
    for name in sorted(names):
        actual = digest(candidate_root / name)
        if actual != graph["needed_sha256"][name]:
            raise ValueError(f"candidate binary differs from graph: {name}")
        old = prior[name]
        if name == NEW_DLL:
            if actual == old["binary_sha256"]:
                raise ValueError("new libtiff unexpectedly equals official package binary")
            row = dict(binary=name, binary_sha256=actual, source_kind="UPSTREAM_SOURCE_BUILD",
                       source_name="libtiff", source_version="4.7.2",
                       source_sha256=LIBTIFF_SOURCE_SHA256,
                       package_declared_license="SOURCE_TEXT_ONLY_NOT_CLASSIFIED",
                       license_evidence_status="SOURCE_TEXT_HASH_VERIFIED",
                       license_evidence_path="tiff-4.7.2/LICENSE.md",
                       license_evidence_sha256=LIBTIFF_LICENSE_SHA256,
                       prior_binary_sha256=old["binary_sha256"],
                       release_obligations_reviewed="NO")
        else:
            if actual != old["binary_sha256"]:
                raise ValueError(f"inherited package binary changed: {name}")
            row = dict(binary=name, binary_sha256=actual, source_kind="MSYS2_PACKAGE_BYTES",
                       source_name=old["package"], source_version=old["package_version"],
                       source_sha256=old["archive_sha256"],
                       package_declared_license=old["package_declared_license"],
                       license_evidence_status=old["evidence_status"],
                       license_evidence_path=old["evidence_paths"],
                       license_evidence_sha256=old["evidence_sha256"],
                       prior_binary_sha256=old["binary_sha256"],
                       release_obligations_reviewed="NO")
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prior-csv", required=True, type=Path)
    parser.add_argument("--graph-json", required=True, type=Path)
    parser.add_argument("--candidate-root", required=True, type=Path)
    parser.add_argument("--source-tar", required=True, type=Path)
    parser.add_argument("--license-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output exists; no overwrite")
    rows = build_rows(args.prior_csv, args.graph_json, args.candidate_root,
                      args.source_tar, args.license_file)
    with args.output.open("x", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"status": "NON_RELEASE_EVIDENCE", "rows": len(rows),
                      "source_built": 1, "inherited_bytes": 33,
                      "release_eligible": False, "output_sha256": digest(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
