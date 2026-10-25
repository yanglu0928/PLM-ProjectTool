"""Map fixed MSYS2 Tesseract PoC binaries to license-text evidence, not legal rights."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from build_tesseract_msys2_poc import audit_inputs, sha256


FIELDS = (
    "binary", "binary_sha256", "package", "package_version", "archive_sha256",
    "delta_from_official_installer", "package_declared_license", "evidence_status",
    "evidence_paths", "evidence_sha256", "release_obligations_reviewed",
)


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def claims(root: Path) -> str:
    values = [line.split(" = ", 1)[1] for line in
              (root / ".PKGINFO").read_text(encoding="utf-8").splitlines()
              if line.startswith("license = ")]
    if not values:
        raise ValueError(f"Package declaration lacks license: {root}")
    return " | ".join(values)


def create_inventory(manifest_path: Path, graph_path: Path, package_dir: Path, matrix: Path,
                     prior_licenses: Path, prior_source_fallback: Path) -> list[dict[str, str]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    if manifest.get("release_eligible") is not False or manifest.get("local_binary_count") != 35:
        raise ValueError("Expected exact non-release 35-binary PoC manifest")
    if graph.get("release_eligible") is not False or graph.get("unused_local_dlls") or \
            graph.get("non_root_dlls_not_in_static_graph"):
        raise ValueError("Static graph boundary is not a clean non-release candidate")
    binaries = {item["path"]: item["sha256"] for item in manifest["files"]
                if not item["path"].startswith("tessdata/")}
    if binaries != graph.get("needed_sha256") or \
            set(binaries) != set(graph.get("needed_local_files", [])):
        raise ValueError("Manifest disagrees with fixed static graph")
    packages = audit_inputs(matrix, package_dir)
    old = {row["dll"]: row for row in rows(matrix)}
    license_by_dll: dict[str, list[dict[str, str]]] = {}
    for row in rows(prior_licenses):
        license_by_dll.setdefault(row["dll"], []).append(row)
    source_by_dll: dict[str, list[dict[str, str]]] = {}
    for row in rows(prior_source_fallback):
        source_by_dll.setdefault(row["dll"], []).append(row)

    result = []
    seen = set()
    for item in manifest["files"]:
        name = item["path"]
        if name.startswith("tessdata/"):
            continue
        if Path(name).name != name or name in seen:
            raise ValueError(f"Binary name invalid or repeated: {name}")
        seen.add(name)
        key = (item["package"], item["version"])
        package = packages[key]
        if package["archive_sha256"] != item["archive_sha256"]:
            raise ValueError(f"Archive changed: {name}")
        binary = package["root"] / "mingw64/bin" / name
        if sha256(binary) != item["sha256"]:
            raise ValueError(f"Binary changed: {name}")

        previous = old.get(name)
        same = previous is not None and previous["official_sha256"] == item["sha256"]
        if same and (previous["package"], previous["package_version"],
                     previous["archive_sha256"]) != (key[0], key[1], item["archive_sha256"]):
            raise ValueError(f"Prior source disagrees: {name}")
        evidence_paths = []
        evidence_hashes = []
        if same and license_by_dll.get(name):
            for evidence in license_by_dll[name]:
                relative = evidence["license_relative_path"]
                if sha256(package["root"] / relative) != evidence["license_sha256"]:
                    raise ValueError(f"Prior package license changed: {name}: {relative}")
                evidence_paths.append(relative)
                evidence_hashes.append(evidence["license_sha256"])
            status = "PACKAGE_TEXT_HASH_VERIFIED"
        elif same and source_by_dll.get(name):
            for evidence in source_by_dll[name]:
                evidence_paths.append(evidence["source_package"] + "/" +
                                      evidence["source_relative_path"])
                evidence_hashes.append(evidence["text_sha256"])
            status = "PRIOR_A04_SOURCE_TEXT_REFERENCE"
        else:
            files = sorted(path for path in
                           (package["root"] / "mingw64/share/licenses").rglob("*")
                           if path.is_file())
            if not files:
                raise ValueError(f"New binary package lacks license text: {name}")
            for evidence in files:
                evidence_paths.append(evidence.relative_to(package["root"]).as_posix())
                evidence_hashes.append(sha256(evidence))
            status = "PACKAGE_TEXT_HASH_VERIFIED"
        result.append({
            "binary": name, "binary_sha256": item["sha256"],
            "package": key[0], "package_version": key[1],
            "archive_sha256": item["archive_sha256"],
            "delta_from_official_installer": "SAME_BYTES" if same else
                ("DIFFERENT_BYTES" if previous else "NEW_BINARY"),
            "package_declared_license": claims(package["root"]),
            "evidence_status": status,
            "evidence_paths": " | ".join(evidence_paths),
            "evidence_sha256": " | ".join(evidence_hashes),
            "release_obligations_reviewed": "NO",
        })
    if len(result) != 35:
        raise ValueError(f"Expected 35 binaries, got {len(result)}")
    return sorted(result, key=lambda row: row["binary"])


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("manifest", "graph", "package-dir", "matrix", "prior-licenses",
                 "prior-source-fallback", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    inventory = create_inventory(args.manifest, args.graph, args.package_dir, args.matrix,
                                 args.prior_licenses, args.prior_source_fallback)
    if args.output.exists():
        raise ValueError("Output exists; do not overwrite an earlier evidence matrix")
    with args.output.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(inventory)
    print(json.dumps({"binary_count": len(inventory),
                      "status_counts": {status: sum(row["evidence_status"] == status
                                                    for row in inventory)
                                        for status in sorted({row["evidence_status"]
                                                              for row in inventory})},
                      "release_obligations_reviewed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
