"""Full-hash-check P35 layout and smoke its packaged Caddy/API over loopback HTTPS."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from package_windows_embedded_candidate import digest_path
from plan_windows_unified_caddy_install import META, exact_mapping
from smoke_caddy_isolated_layout_https import smoke as original_smoke
from verify_windows_unified_caddy_go_source_candidate import verify as verify_candidate
from verify_windows_unified_extract import verify as verify_stage
from build_windows_unified_caddy_go_source_candidate import KIND


def verify_layout(candidate: Path, source: Path, stage: Path, layout: Path) -> dict:
    temp = Path(tempfile.gettempdir()).resolve(strict=True)
    layout = layout.resolve(strict=True)
    stage = stage.resolve(strict=True)
    if (layout.parent != temp or stage.parent != temp or not str(layout).isascii()
            or not str(stage).isascii() or layout == stage
            or not layout.name.startswith("plm-install-rehearsal-")
            or Path("C:\\PLMTool").exists()):
        raise ValueError("new isolated layout/stage root rejected")
    identity = verify_candidate(candidate, source)
    checked = verify_stage(stage, expected_kind=KIND)
    if checked["payload_file_count"] != identity["payload_file_count"]:
        raise ValueError("new stage count differs")
    hashes = {}
    for line in (stage / "payload-sha256sums.txt").read_text(encoding="ascii").splitlines():
        value, separator, name = line.partition("  ")
        if separator != "  " or name in hashes:
            raise ValueError("new stage manifest rejected")
        hashes[name] = value
    with zipfile.ZipFile(candidate) as archive:
        if any((stage / name).read_bytes() != archive.read(name) for name in META):
            raise ValueError("new stage metadata differs")
    mapping, mapping_sha256 = exact_mapping([*hashes, *META])
    if len(hashes) != 21112 or len(mapping) != 21115:
        raise ValueError("new layout mapping count differs")
    landed = {str(path.relative_to(layout)).replace("\\", "/").casefold()
              for path in layout.rglob("*") if path.is_file()}
    if landed != {target.casefold() for target in mapping.values()}:
        raise ValueError("new layout file set differs")
    for original, target in mapping.items():
        expected = hashes[original] if original in hashes else digest_path(stage / original)
        if digest_path(layout / target) != expected:
            raise ValueError("new layout target hash differs")
    return {"mapping_sha256": mapping_sha256, "file_count": len(mapping)}


def smoke(candidate: Path, source: Path, stage: Path, layout: Path) -> dict:
    verified = verify_layout(candidate, source, stage, layout)
    result = original_smoke(candidate, stage, layout,
                            layout_verifier=lambda *_: verified)
    if result["verified_file_count"] != 21115:
        raise ValueError("new layout HTTPS verification count differs")
    return {**result, "status": "NON_RELEASE_CADDY_GO_LAYOUT_HTTPS_PASS"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(smoke(args.candidate, args.source, args.stage, args.layout),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
