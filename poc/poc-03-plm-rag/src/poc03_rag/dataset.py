from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict, deque
from typing import Any, Iterable


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").split())


def _text_segments(text: str, max_chars: int) -> list[str]:
    clean = _normalize(text)
    if len(clean) <= max_chars:
        return [clean] if clean else []
    segments: list[str] = []
    cursor = 0
    while cursor < len(clean):
        end = min(cursor + max_chars, len(clean))
        if end < len(clean):
            boundary = clean.rfind(" ", cursor + max_chars // 2, end)
            if boundary > cursor:
                end = boundary
        segment = clean[cursor:end].strip()
        if segment:
            segments.append(segment)
        cursor = end
        while cursor < len(clean) and clean[cursor].isspace():
            cursor += 1
    return segments


def _emit_chunk(
    document_id: str,
    project_id: str,
    source_corpus: str,
    atoms: list[dict[str, Any]],
) -> dict[str, Any]:
    text = "\n".join(atom["text"] for atom in atoms)
    locators = list(dict.fromkeys(atom["source_locator"] for atom in atoms))
    pages = list(dict.fromkeys(atom["page"] for atom in atoms if atom["page"] is not None))
    sections = list(dict.fromkeys(atom["section"] for atom in atoms if atom["section"]))
    block_types = list(dict.fromkeys(atom["type"] for atom in atoms))
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    identity = f"{document_id}|{'|'.join(locators)}|{text_hash}"
    chunk_id = f"{document_id}-C-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]}"
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "source_corpus": source_corpus,
        "scope": "PROJECT",
        "project_id": project_id,
        "text": text,
        "text_sha256": text_hash,
        "character_count": len(text),
        "source_locators": locators,
        "pages": pages,
        "sections": sections,
        "block_types": block_types,
    }


def chunk_document(
    document_id: str,
    parsed_document: dict[str, Any],
    project_id: str,
    *,
    source_corpus: str = "UNSPECIFIED",
    max_chars: int = 900,
    overlap_blocks: int = 1,
) -> list[dict[str, Any]]:
    if not document_id or not project_id:
        raise ValueError("document_id and project_id are required")
    if max_chars < 100:
        raise ValueError("max_chars must be at least 100")
    atoms: list[dict[str, Any]] = []
    for block in parsed_document.get("blocks", []):
        for segment in _text_segments(block.get("text", ""), max_chars):
            atoms.append(
                {
                    "text": segment,
                    "source_locator": _normalize(block.get("source_locator")) or "unknown",
                    "page": block.get("page"),
                    "section": _normalize(block.get("section")) or None,
                    "type": _normalize(block.get("type")) or "unknown",
                }
            )

    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_length = 0
    for atom in atoms:
        separator_length = 1 if current else 0
        if current and current_length + separator_length + len(atom["text"]) > max_chars:
            chunks.append(_emit_chunk(document_id, project_id, source_corpus, current))
            current = current[-overlap_blocks:] if overlap_blocks else []
            current_length = sum(len(item["text"]) for item in current) + max(0, len(current) - 1)
            while current and current_length + 1 + len(atom["text"]) > max_chars:
                current.pop(0)
                current_length = sum(len(item["text"]) for item in current) + max(0, len(current) - 1)
        current.append(atom)
        current_length += (1 if len(current) > 1 else 0) + len(atom["text"])
    if current:
        chunks.append(_emit_chunk(document_id, project_id, source_corpus, current))
    return chunks


def build_candidate_records(
    chunks: Iterable[dict[str, Any]],
    *,
    target_count: int = 120,
    min_chars: int = 120,
) -> list[dict[str, Any]]:
    if not 100 <= target_count <= 200:
        raise ValueError("target_count must be between 100 and 200")
    grouped: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    for chunk in sorted(chunks, key=lambda item: (item["document_id"], item["chunk_id"])):
        if chunk["character_count"] >= min_chars:
            grouped[chunk["document_id"]].append(chunk)
    if not grouped:
        return []

    records: list[dict[str, Any]] = []
    document_ids = sorted(grouped)
    while len(records) < target_count and any(grouped.values()):
        for document_id in document_ids:
            if len(records) >= target_count:
                break
            if not grouped[document_id]:
                continue
            chunk = grouped[document_id].popleft()
            records.append(
                {
                    "schema_version": "poc-03.candidate.v1",
                    "candidate_id": f"GD-C-{len(records) + 1:04d}",
                    "status": "PENDING_HUMAN_REVIEW",
                    "scope": chunk["scope"],
                    "project_id": chunk["project_id"],
                    "source_corpus": chunk["source_corpus"],
                    "source_type": None,
                    "query_suggestion": None,
                    "expected_classification": None,
                    "expected_relevant_chunk_ids": [chunk["chunk_id"]],
                    "expected_answer_terms": [],
                    "expected_citations": [
                        {
                            "document_id": document_id,
                            "chunk_id": chunk["chunk_id"],
                            "source_locators": chunk["source_locators"],
                        }
                    ],
                    "review": {"status": "PENDING", "reviewed_by": None, "reviewed_at": None},
                    "candidate_content": chunk["text"],
                    "candidate_content_sha256": chunk["text_sha256"],
                }
            )
    return records


def build_sanitized_report(
    *,
    documents: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    target_count: int,
    local_output_location: str,
    generated_at: str,
) -> dict[str, Any]:
    document_candidate_counts = Counter(
        candidate["expected_citations"][0]["document_id"] for candidate in candidates
    )
    status = "PASS" if len(candidates) == target_count and 100 <= target_count <= 200 else "FAIL"
    return {
        "status": status,
        "generated_at": generated_at,
        "quality_scope": "candidate_generation_only_not_human_approved_golden_dataset",
        "privacy": {
            "source_files_committed": False,
            "source_names_committed": False,
            "source_hashes_committed": False,
            "parsed_content_committed": False,
            "candidate_content_committed": False,
            "local_output_location": local_output_location,
        },
        "summary": {
            "parsed_document_count": len(documents),
            "input_block_count": sum(len(document.get("blocks", [])) for document in documents),
            "chunk_count": len(chunks),
            "candidate_target_count": target_count,
            "candidate_count": len(candidates),
            "candidate_status": "PENDING_HUMAN_REVIEW",
            "document_coverage_count": len(document_candidate_counts),
            "scope_counts": dict(sorted(Counter(chunk["scope"] for chunk in chunks).items())),
            "source_corpus_counts": dict(
                sorted(Counter(chunk["source_corpus"] for chunk in chunks).items())
            ),
        },
        "per_document": [
            {
                "document_id": document_id,
                "source_corpus": next(
                    chunk["source_corpus"]
                    for chunk in chunks
                    if chunk["document_id"] == document_id
                ),
                "chunk_count": sum(chunk["document_id"] == document_id for chunk in chunks),
                "candidate_count": document_candidate_counts[document_id],
            }
            for document_id in sorted(document_candidate_counts)
        ],
    }


def write_json_lines(path: Any, records: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            stream.write("\n")
