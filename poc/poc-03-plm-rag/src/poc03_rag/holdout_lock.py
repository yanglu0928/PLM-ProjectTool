from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

from .dataset import chunk_document
from .source_roles import ACTUAL_SURVEY_RECORD_ROLE


DEFAULT_QUOTAS = {
    "STANDARD_CAPABILITY": 33,
    "CONTRACT": 7,
    "TECHNICAL_AGREEMENT": 8,
    "SURVEY": 2,
}


class HoldoutQuotaError(ValueError):
    def __init__(self, shortages: dict[str, dict[str, int]], eligible_counts: dict[str, int]) -> None:
        self.shortages = shortages
        self.eligible_counts = eligible_counts
        super().__init__(f"holdout quotas cannot be satisfied: {shortages}")


def load_json_lines(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def load_partitioned_chunks(parsed_root: Path, project_id: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for corpus_dir in sorted(path for path in parsed_root.iterdir() if path.is_dir()):
        for path in sorted(corpus_dir.glob("*.parsed.json")):
            parsed = json.loads(path.read_text(encoding="utf-8"))
            stem = path.name.removesuffix(".parsed.json")
            document_id = stem if stem.startswith(f"{corpus_dir.name}-") else f"{corpus_dir.name}-{stem}"
            document_chunks = chunk_document(
                    document_id,
                    parsed,
                    project_id,
                    source_corpus=corpus_dir.name,
                )
            evidence_role = str((parsed.get("metadata") or {}).get("evidence_role") or "UNSPECIFIED")
            for chunk in document_chunks:
                chunk["evidence_role"] = evidence_role
            chunks.extend(document_chunks)
    return chunks


def collect_contaminated_chunk_ids(
    calibration_dataset: dict[str, Any],
    prompt_payloads: Iterable[dict[str, Any]],
    review_package: dict[str, Any],
    retrieval_rows: Iterable[dict[str, Any]],
) -> set[str]:
    contaminated: set[str] = set()
    for case in calibration_dataset.get("cases") or []:
        contaminated.update(str(value) for value in case.get("expected_relevant_chunk_ids") or [])
    for payload in prompt_payloads:
        contaminated.update(
            str(context.get("chunk_id") or "")
            for context in payload.get("contexts") or []
        )
    for case in review_package.get("cases") or []:
        contaminated.update(
            str(chunk.get("chunk_id") or "")
            for chunk in case.get("candidate_chunks") or []
        )
    for row in retrieval_rows:
        for field in ("top5_ids", "reranker_top5_ids"):
            contaminated.update(str(value) for value in row.get(field) or [])
    contaminated.discard("")
    return contaminated


def _stable_order(seed: str, chunk_id: str) -> str:
    return hashlib.sha256(f"{seed}|{chunk_id}".encode("utf-8")).hexdigest()


def _lock_fingerprint(
    candidates: list[dict[str, Any]],
    contaminated_ids: set[str],
    quotas: dict[str, int],
) -> str:
    payload = {
        "candidate_chunks": [
            {
                "chunk_id": candidate["chunk_id"],
                "text_sha256": candidate["text_sha256"],
                "source_locators": candidate["source_locators"],
            }
            for candidate in candidates
        ],
        "contaminated_chunk_ids": sorted(contaminated_ids),
        "quotas": dict(sorted(quotas.items())),
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_holdout_lock(
    chunks: list[dict[str, Any]],
    contaminated_ids: set[str],
    *,
    project_id: str,
    quotas: dict[str, int] | None = None,
    min_chars: int = 160,
    seed: str = "poc03-holdout-v1",
) -> tuple[dict[str, Any], dict[str, Any]]:
    quotas = dict(quotas or DEFAULT_QUOTAS)
    chunks_by_id = {str(chunk["chunk_id"]): chunk for chunk in chunks}
    contaminated_locators: dict[str, set[str]] = defaultdict(set)
    for chunk_id in contaminated_ids:
        chunk = chunks_by_id.get(chunk_id)
        if chunk:
            contaminated_locators[str(chunk["document_id"])].update(
                str(value) for value in chunk.get("source_locators") or []
            )

    exclusion_counts: Counter[str] = Counter()
    eligible_by_source: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    seen_text_hashes: set[str] = set()
    for chunk in chunks:
        source_type = str(chunk.get("source_corpus") or "")
        if source_type not in quotas:
            exclusion_counts["outside_quota_sources"] += 1
            continue
        if source_type == "SURVEY" and chunk.get("evidence_role") != ACTUAL_SURVEY_RECORD_ROLE:
            exclusion_counts["survey_reference_only"] += 1
            continue
        chunk_id = str(chunk["chunk_id"])
        if chunk_id in contaminated_ids:
            exclusion_counts["contaminated_chunk"] += 1
            continue
        if int(chunk.get("character_count") or 0) < min_chars:
            exclusion_counts["too_short"] += 1
            continue
        document_id = str(chunk["document_id"])
        locators = {str(value) for value in chunk.get("source_locators") or []}
        if locators & contaminated_locators.get(document_id, set()):
            exclusion_counts["overlapping_source_locator"] += 1
            continue
        text_hash = str(chunk.get("text_sha256") or "")
        if not text_hash or text_hash in seen_text_hashes:
            exclusion_counts["duplicate_text"] += 1
            continue
        seen_text_hashes.add(text_hash)
        eligible_by_source[source_type][document_id].append(chunk)

    eligible_counts = {
        source_type: sum(len(values) for values in eligible_by_source.get(source_type, {}).values())
        for source_type in quotas
    }
    shortages = {
        source_type: {"required": quota, "eligible": eligible_counts[source_type]}
        for source_type, quota in quotas.items()
        if eligible_counts[source_type] < quota
    }
    if shortages:
        raise HoldoutQuotaError(shortages, eligible_counts)

    selected: list[dict[str, Any]] = []
    for source_type, quota in quotas.items():
        documents = eligible_by_source.get(source_type, {})
        queues = {
            document_id: deque(sorted(values, key=lambda chunk: _stable_order(seed, str(chunk["chunk_id"]))))
            for document_id, values in documents.items()
        }
        document_ids = sorted(queues)
        source_selected: list[dict[str, Any]] = []
        while len(source_selected) < quota and any(queues.values()):
            for document_id in document_ids:
                if len(source_selected) >= quota:
                    break
                if queues[document_id]:
                    source_selected.append(queues[document_id].popleft())
        selected.extend(source_selected)

    selected.sort(key=lambda chunk: (str(chunk["source_corpus"]), str(chunk["document_id"]), str(chunk["chunk_id"])))
    candidates = [
        {
            "candidate_id": f"HO-C-{index:04d}",
            "status": "LOCKED_PENDING_HUMAN_REVIEW",
            "scope": "PROJECT",
            "project_id": project_id,
            "source_type": chunk["source_corpus"],
            "evidence_role": chunk.get("evidence_role", "UNSPECIFIED"),
            "document_id": chunk["document_id"],
            "chunk_id": chunk["chunk_id"],
            "candidate_content": chunk["text"],
            "text_sha256": chunk["text_sha256"],
            "source_locators": list(chunk.get("source_locators") or []),
            "pages": list(chunk.get("pages") or []),
            "sections": list(chunk.get("sections") or []),
        }
        for index, chunk in enumerate(selected, start=1)
    ]
    fingerprint = _lock_fingerprint(candidates, contaminated_ids, quotas)
    lock = {
        "schema_version": "poc-03.holdout-lock.v1",
        "status": "LOCKED_PENDING_HUMAN_REVIEW",
        "lock_id": f"poc-03-holdout-{fingerprint[:16]}",
        "lock_fingerprint": fingerprint,
        "project_id": project_id,
        "target_count": sum(quotas.values()),
        "source_type_quotas": quotas,
        "isolation": {
            "case_and_query_disjoint": True,
            "chunk_id_disjoint": True,
            "source_locator_disjoint": True,
            "document_disjoint": False,
            "document_disjoint_reason": "All 29 available source documents already appear in the calibration set.",
        },
        "candidates": candidates,
    }
    selected_documents = {candidate["document_id"] for candidate in candidates}
    contaminated_documents = {
        str(chunk["document_id"])
        for chunk in chunks
        if str(chunk["chunk_id"]) in contaminated_ids
    }
    overlapping_documents = selected_documents & contaminated_documents
    lock["isolation"]["document_disjoint"] = not overlapping_documents
    lock["isolation"]["document_disjoint_reason"] = (
        "All selected documents are disjoint from prior exposure."
        if not overlapping_documents
        else (
            "Legacy standard, contract or technical-agreement sources cannot be fully separated at document "
            "level; the lock enforces unseen chunks and source locators. Actual survey records are new sources."
        )
    )
    report = {
        "schema_version": "poc-03.holdout-lock-result.v1",
        "status": "PASS",
        "summary": {
            "target_count": sum(quotas.values()),
            "selected_count": len(candidates),
            "selected_document_count": len(selected_documents),
            "selected_document_overlap_count": len(overlapping_documents),
            "source_type_counts": dict(sorted(Counter(candidate["source_type"] for candidate in candidates).items())),
            "eligible_counts": dict(sorted(eligible_counts.items())),
            "contaminated_chunk_count": len(contaminated_ids),
            "exclusion_counts": dict(sorted(exclusion_counts.items())),
            "lock_fingerprint": fingerprint,
        },
        "checks": {
            "target_count_50": len(candidates) == 50,
            "all_source_type_quotas_met": Counter(candidate["source_type"] for candidate in candidates) == Counter(quotas),
            "selected_chunk_ids_disjoint": not ({candidate["chunk_id"] for candidate in candidates} & contaminated_ids),
            "selected_source_locators_disjoint": all(
                not (
                    set(candidate["source_locators"])
                    & contaminated_locators.get(candidate["document_id"], set())
                )
                for candidate in candidates
            ),
            "unique_selected_text": len({candidate["text_sha256"] for candidate in candidates}) == len(candidates),
            "survey_candidates_use_actual_records": all(
                candidate["evidence_role"] == ACTUAL_SURVEY_RECORD_ROLE
                for candidate in candidates
                if candidate["source_type"] == "SURVEY"
            ),
        },
        "privacy": {
            "candidate_content_committed": False,
            "chunk_ids_committed": False,
            "source_names_committed": False,
            "source_locators_committed": False,
            "lock_file_committed": False,
        },
        "source_governance": {
            "actual_survey_records": "PRIMARY_EVIDENCE",
            "survey_form_templates": "REFERENCE_ONLY_NOT_ELIGIBLE_FOR_HOLDOUT_QUOTA",
        },
        "known_limit": (
            "Legacy standard, contract and technical-agreement documents overlap the calibration corpus at "
            "document level. The lock therefore enforces unseen cases, queries, chunks and source locators for "
            "those sources; survey candidates are drawn only from new actual customer discovery records."
        ),
    }
    if not all(report["checks"].values()):
        report["status"] = "FAIL"
    return lock, report
