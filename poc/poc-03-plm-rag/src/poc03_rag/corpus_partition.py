from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


LOCKED_SOURCE_TYPES = {
    "STANDARD_CAPABILITY",
    "CONTRACT",
    "TECHNICAL_AGREEMENT",
    "SURVEY",
}


def classify_library_document(*, library_kind: str, file_name: str) -> str:
    normalized_kind = library_kind.strip().upper()
    normalized_name = "".join(file_name.split()).lower()
    if normalized_kind == "STANDARD_LIBRARY":
        return "SURVEY" if "调研" in normalized_name else "STANDARD_CAPABILITY"
    if normalized_kind == "CONTRACT_LIBRARY":
        has_technical_agreement = "技术协议" in normalized_name
        has_contract = "合同" in normalized_name
        if has_technical_agreement and not has_contract:
            return "TECHNICAL_AGREEMENT"
        if has_contract and not has_technical_agreement:
            return "CONTRACT"
        raise ValueError("contract library document title is ambiguous")
    raise ValueError(f"unsupported library kind: {library_kind}")


def partition_parsed_documents(
    entries: Iterable[dict[str, Any]],
    *,
    parsed_dir: Path,
    output_root: Path,
    library_kind: str,
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for entry in entries:
        if entry.get("status") != "PASS":
            continue
        document_id = str(entry.get("document_id") or "").strip()
        file_name = str(entry.get("relative_path") or "").strip()
        parsed_output = str(entry.get("parsed_output") or "").strip()
        if not document_id or not file_name or not parsed_output:
            raise ValueError("validated corpus entry is incomplete")
        source_type = classify_library_document(
            library_kind=library_kind,
            file_name=file_name,
        )
        if source_type not in LOCKED_SOURCE_TYPES:
            raise ValueError(f"unsupported source type: {source_type}")
        source = parsed_dir / parsed_output
        if not source.is_file():
            raise FileNotFoundError(source)
        destination_dir = output_root / source_type
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination_dir / f"{document_id}.parsed.json")
        counts[source_type] += 1
    return dict(sorted(counts.items()))
