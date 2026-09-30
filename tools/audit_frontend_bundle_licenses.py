"""Collect exact front-end bundle source and license evidence without release approval."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


HASH_LINE = re.compile(r"([0-9a-f]{64})  ([A-Za-z0-9_./-]+)")
LICENSE_NAME = re.compile(r"^(?:LICENSE|LICENCE|COPYING|NOTICE)(?:$|[.-])", re.IGNORECASE)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_hashes(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="ascii").splitlines()
    hashes: dict[str, str] = {}
    for line in lines:
        match = HASH_LINE.fullmatch(line)
        if not match or ".." in match.group(2).split("/") or match.group(2) in hashes:
            raise ValueError("frontend hash manifest rejected")
        hashes[match.group(2)] = match.group(1)
    if len(hashes) != 3:
        raise ValueError("frontend dist count rejected")
    return hashes


def audit_frontend(frontend_run: Path) -> dict:
    frontend_run = frontend_run.resolve(strict=True)
    summary = json.loads((frontend_run / "summary.json").read_text(encoding="utf-8"))
    if summary.get("status") != "WINDOWS11_FRONTEND_PNPM_OFFLINE_PASS" or summary.get("dist_file_count") != 3:
        raise ValueError("frontend source checkpoint rejected")
    app = frontend_run / "offline-source" / "apps" / "frontend"
    if sha256((app / "pnpm-lock.yaml").read_bytes()) != summary.get("lock_sha256"):
        raise ValueError("frontend lock hash mismatch")
    frozen = app / "dist"
    audit_dir = app / "dist-license-audit"
    hashes = _read_hashes(frontend_run / "dist-sha256sums.txt")
    if {p.relative_to(frozen).as_posix() for p in frozen.rglob("*") if p.is_file()} != set(hashes):
        raise ValueError("frozen frontend inventory mismatch")
    for name, expected in hashes.items():
        if sha256((frozen / name).read_bytes()) != expected:
            raise ValueError("frozen frontend hash mismatch")
    js_names = [name for name in hashes if name.endswith(".js")]
    if len(js_names) != 1:
        raise ValueError("frontend entry JS not unique")
    js_name = js_names[0]
    map_path = audit_dir / (js_name + ".map")
    if not map_path.is_file():
        raise ValueError("audit source map missing")
    if {p.relative_to(audit_dir).as_posix() for p in audit_dir.rglob("*") if p.is_file()} != set(hashes) | {js_name + ".map"}:
        raise ValueError("audit build inventory mismatch")
    for name in hashes:
        frozen_bytes = (frozen / name).read_bytes()
        audit_bytes = (audit_dir / name).read_bytes()
        if name == js_name:
            suffix = ("\n//# sourceMappingURL=" + Path(js_name).name + ".map").encode("ascii")
            if audit_bytes != frozen_bytes + suffix:
                raise ValueError("audit JS differs from frozen bundle")
        elif audit_bytes != frozen_bytes:
            raise ValueError("audit asset differs from frozen bundle")
    source_map = json.loads(map_path.read_text(encoding="utf-8"))
    if len(source_map.get("sources", [])) != len(source_map.get("sourcesContent", [])):
        raise ValueError("source map content count mismatch")
    package_modules: dict[tuple[str, str], dict] = {}
    for raw_path, source_content in zip(source_map["sources"], source_map["sourcesContent"]):
        if "/node_modules/.pnpm/" not in raw_path:
            continue
        if not isinstance(source_content, str):
            raise ValueError("source map content missing")
        source_path = (map_path.parent / raw_path).resolve(strict=True)
        if not source_path.is_relative_to((app / "node_modules" / ".pnpm").resolve(strict=True)):
            raise ValueError("source map package path rejected")
        if source_path.read_text(encoding="utf-8") != source_content:
            raise ValueError("source map package content mismatch")
        package_root = next((p for p in source_path.parents if (p / "package.json").is_file()), None)
        if package_root is None or not package_root.is_relative_to((app / "node_modules" / ".pnpm").resolve(strict=True)):
            raise ValueError("source map package identity missing")
        metadata = json.loads((package_root / "package.json").read_text(encoding="utf-8"))
        key = (metadata["name"], metadata["version"])
        item = package_modules.setdefault(key, {
            "name": key[0], "version": key[1], "declared_license": metadata.get("license"),
            "source_modules": [], "license_files": [], "review_status": "REVIEW_REQUIRED",
        })
        item["source_modules"].append({
            "path": source_path.relative_to(package_root).as_posix(),
            "sha256": sha256(source_content.encode("utf-8")),
        })
        if not item["license_files"]:
            item["license_files"] = [
                {"name": p.name, "sha256": sha256(p.read_bytes())}
                for p in sorted(package_root.iterdir()) if p.is_file() and LICENSE_NAME.match(p.name)
            ]
    if not package_modules:
        raise ValueError("no third-party bundle modules found")
    packages = [package_modules[key] for key in sorted(package_modules)]
    app_manifest = json.loads((app / "package.json").read_text(encoding="utf-8"))
    direct_dependencies = []
    for name, requested in sorted(app_manifest.get("dependencies", {}).items()):
        root = (app / "node_modules" / name).resolve(strict=True)
        if not root.is_relative_to((app / "node_modules").resolve(strict=True)):
            raise ValueError("direct dependency source path rejected")
        metadata = json.loads((root / "package.json").read_text(encoding="utf-8"))
        if metadata.get("name") != name or metadata.get("version") != requested:
            raise ValueError("direct dependency identity mismatch")
        direct_dependencies.append({
            "name": name, "version": requested, "declared_license": metadata.get("license"),
            "mapped_into_bundle": (name, requested) in package_modules,
            "license_files": [
                {"name": p.name, "sha256": sha256(p.read_bytes())}
                for p in sorted(root.iterdir()) if p.is_file() and LICENSE_NAME.match(p.name)
            ],
            "review_status": "REVIEW_REQUIRED",
        })
    return {
        "schema_version": "plm.frontend-bundle-license-evidence.v1",
        "status": "REVIEW_REQUIRED",
        "release_eligible": False,
        "source_commit": summary["source_commit"],
        "lock_sha256": summary["lock_sha256"],
        "frozen_dist_hashes": hashes,
        "audit_map_sha256": sha256(map_path.read_bytes()),
        "mapped_source_count": len(source_map["sources"]),
        "third_party_module_count": sum(len(item["source_modules"]) for item in packages),
        "mapped_package_count": len(packages),
        "packages": packages,
        "direct_dependencies": direct_dependencies,
        "limits": ["Source-map-covered JS modules only", "No build-tool, CSS, generated-runtime or native/system legal clearance"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit exact frozen frontend bundle sources and license evidence")
    parser.add_argument("--frontend-run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = audit_frontend(args.frontend_run)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "release_eligible", "mapped_source_count", "third_party_module_count", "mapped_package_count")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
