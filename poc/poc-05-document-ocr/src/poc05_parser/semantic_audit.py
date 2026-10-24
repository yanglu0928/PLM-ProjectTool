from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from statistics import median
from typing import Any


@dataclass(frozen=True)
class CheckpointResult:
    document_id: str
    page: int
    checkpoint_index: int
    critical: bool
    exact: bool
    score: float
    matched: bool


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def reconstruct_page_text(blocks: list[dict[str, Any]], page: int) -> str:
    page_blocks = [block for block in blocks if block.get("page") == page]
    positioned: list[tuple[float, float, float, str]] = []
    fallback: list[str] = []
    for block in page_blocks:
        text = str(block.get("text") or "").strip()
        if not text:
            continue
        bbox = (block.get("metadata") or {}).get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4:
            x, y, _width, height = (float(value) for value in bbox)
            positioned.append((y + height / 2, x, height, text))
        else:
            fallback.append(text)

    if not positioned:
        return " ".join(fallback)

    typical_height = median(item[2] for item in positioned)
    tolerance = max(3.0, typical_height * 0.65)
    lines: list[dict[str, Any]] = []
    for y_center, x, _height, text in sorted(positioned, key=lambda item: (item[0], item[1])):
        nearest = min(lines, key=lambda line: abs(line["y"] - y_center), default=None)
        if nearest is None or abs(nearest["y"] - y_center) > tolerance:
            lines.append({"y": y_center, "items": [(x, text)]})
            continue
        nearest["items"].append((x, text))
        count = len(nearest["items"])
        nearest["y"] = ((nearest["y"] * (count - 1)) + y_center) / count

    ordered_lines = []
    for line in sorted(lines, key=lambda item: item["y"]):
        ordered_lines.append(" ".join(text for _x, text in sorted(line["items"])))
    ordered_lines.extend(fallback)
    return "\n".join(ordered_lines)


def best_window_similarity(expected: str, actual: str) -> float:
    expected_normalized = normalize_text(expected)
    actual_normalized = normalize_text(actual)
    if not expected_normalized or not actual_normalized:
        return 0.0
    if expected_normalized in actual_normalized:
        return 1.0

    expected_length = len(expected_normalized)
    minimum = max(1, expected_length - 2)
    maximum = min(len(actual_normalized), expected_length + 2)
    best = 0.0
    for window_length in range(minimum, maximum + 1):
        for start in range(0, len(actual_normalized) - window_length + 1):
            candidate = actual_normalized[start : start + window_length]
            score = SequenceMatcher(None, expected_normalized, candidate).ratio()
            if score > best:
                best = score
                if best >= 0.999:
                    return 1.0
    return best


def _evaluate_with_page_text(
    annotation: dict[str, Any],
    page_text: dict[tuple[str, int], str],
    *,
    match_threshold: float = 0.85,
    exact_threshold: float = 1.0,
) -> dict[str, Any]:
    results: list[CheckpointResult] = []

    for document in annotation["documents"]:
        document_id = document["document_id"]
        for sample in document["samples"]:
            page = int(sample["page"])
            cache_key = (document_id, page)
            actual_text = page_text[cache_key]
            for index, checkpoint in enumerate(sample["checkpoints"], start=1):
                critical = bool(checkpoint.get("critical", False))
                exact = bool(checkpoint.get("exact", False))
                score = best_window_similarity(checkpoint["text"], actual_text)
                threshold = exact_threshold if exact else match_threshold
                results.append(
                    CheckpointResult(
                        document_id=document_id,
                        page=page,
                        checkpoint_index=index,
                        critical=critical,
                        exact=exact,
                        score=score,
                        matched=score >= threshold,
                    )
                )

    matched = sum(item.matched for item in results)
    critical_errors = sum(item.critical and not item.matched for item in results)
    exact_errors = sum(item.exact and not item.matched for item in results)
    recall = matched / len(results) if results else 0.0
    status = (
        "PASS"
        if recall >= 0.95 and critical_errors == 0 and exact_errors == 0
        else "FAIL"
    )
    return {
        "status": status,
        "method": "visual-transcription-checkpoint-recall",
        "thresholds": {
            "checkpoint_similarity": match_threshold,
            "exact_similarity": exact_threshold,
            "minimum_recall": 0.95,
            "maximum_critical_errors": 0,
        },
        "summary": {
            "document_count": len(annotation["documents"]),
            "sampled_page_count": len(page_text),
            "checkpoint_count": len(results),
            "matched_checkpoint_count": matched,
            "checkpoint_recall": round(recall, 6),
            "critical_checkpoint_count": sum(item.critical for item in results),
            "critical_error_count": critical_errors,
            "exact_checkpoint_count": sum(item.exact for item in results),
            "exact_error_count": exact_errors,
        },
        "results": [
            {
                "document_id": item.document_id,
                "page": item.page,
                "checkpoint_index": item.checkpoint_index,
                "critical": item.critical,
                "exact": item.exact,
                "score": round(item.score, 6),
                "matched": item.matched,
            }
            for item in results
        ],
    }


def evaluate_annotation(
    annotation: dict[str, Any],
    parsed_directory: Path,
    *,
    match_threshold: float = 0.85,
    exact_threshold: float = 1.0,
) -> dict[str, Any]:
    page_text: dict[tuple[str, int], str] = {}
    for document in annotation["documents"]:
        document_id = document["document_id"]
        parsed_path = parsed_directory / f"{document_id}.parsed.json"
        parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
        for sample in document["samples"]:
            page = int(sample["page"])
            page_text[(document_id, page)] = reconstruct_page_text(parsed["blocks"], page)
    return _evaluate_with_page_text(
        annotation,
        page_text,
        match_threshold=match_threshold,
        exact_threshold=exact_threshold,
    )


def evaluate_text_directory(
    annotation: dict[str, Any],
    text_directory: Path,
    *,
    match_threshold: float = 0.85,
    exact_threshold: float = 1.0,
) -> dict[str, Any]:
    page_text: dict[tuple[str, int], str] = {}
    for document in annotation["documents"]:
        document_id = document["document_id"]
        for sample in document["samples"]:
            page = int(sample["page"])
            text_path = text_directory / f"{document_id}-p{page:02d}.txt"
            page_text[(document_id, page)] = text_path.read_text(encoding="utf-8")
    return _evaluate_with_page_text(
        annotation,
        page_text,
        match_threshold=match_threshold,
        exact_threshold=exact_threshold,
    )
