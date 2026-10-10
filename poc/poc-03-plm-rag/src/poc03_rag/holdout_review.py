from __future__ import annotations

import re
from collections import Counter
from typing import Any


PROMPT_ID = "poc03-holdout-review"
PROMPT_VERSION = "v1"

FINAL_CLASSIFICATIONS = {
    "STANDARD_SATISFIED",
    "PARTIALLY_SATISFIED",
    "NON_STANDARD",
    "INSUFFICIENT_INFORMATION",
    "NO_RELIABLE_MATCH",
}

CLASSIFICATION_NAMES = {
    "STANDARD_SATISFIED": "标准满足",
    "PARTIALLY_SATISFIED": "部分满足",
    "NON_STANDARD": "非标准",
    "INSUFFICIENT_INFORMATION": "资料不足",
    "NO_RELIABLE_MATCH": "无可靠匹配",
}

DEFAULT_CLASSIFICATION_REASONS = {
    "STANDARD_SATISFIED": "候选证据直接描述了可用于判断该问题的标准能力。",
    "PARTIALLY_SATISFIED": "候选证据描述了部分能力、适用条件或仍需确认的限制。",
    "NON_STANDARD": "候选证据出现了定制、二次开发、特殊接口或特殊交付要求。",
    "INSUFFICIENT_INFORMATION": "候选证据与问题相关，但不足以判断完整满足程度或实施边界。",
    "NO_RELIABLE_MATCH": "候选证据不足以支持可靠的PLM业务判断。",
}

SYSTEM_PROMPT = """你是PLM项目实施质量评审助手。你将收到一个已经锁定且未参与历史调优的候选证据。
只能根据候选正文生成一条可供人工确认的验收建议，不得使用外部知识，不得补写客户未表达的事实。

要求：
1. question 必须是具体、可判定、可由该段证据直接核对的PLM实施问题，避免泛泛的“请概述本文”。
2. classification 只能选择以下五类：
   - STANDARD_SATISFIED：证据明确表明现有标准能力直接满足问题。
   - PARTIALLY_SATISFIED：证据明确表明只满足部分范围，或存在条件、限制、缺口。
   - NON_STANDARD：证据明确要求定制、二次开发、特殊接口、特殊交付或偏离标准能力。
   - INSUFFICIENT_INFORMATION：证据与问题有关，但不足以判断是否满足、如何实现或责任边界。
   - NO_RELIABLE_MATCH：证据不能可靠支持一个有意义的PLM业务判断。
3. 合同、技术协议和实际调研记录可以证明需求或约定，但在没有标准能力交叉证据时，不得仅因提出需求就判断为标准满足。
4. evidence_quote 必须逐字摘录候选正文中的连续片段，长度控制在8至160个字符，不得改写。
5. answer_terms 提供2至5个正文中实际出现、可辅助人工核对的短语。
6. 只返回符合JSON Schema的JSON对象，不要使用Markdown代码块。"""


def suggestion_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": [
            "candidate_id",
            "question",
            "classification",
            "classification_reason",
            "answer_terms",
            "evidence_quote",
        ],
        "properties": {
            "candidate_id": {"type": "string", "minLength": 1},
            "question": {"type": "string", "minLength": 8, "maxLength": 300},
            "classification": {"enum": sorted(FINAL_CLASSIFICATIONS)},
            "classification_reason": {"type": "string", "maxLength": 500},
            "answer_terms": {
                "type": "array",
                "minItems": 2,
                "maxItems": 5,
                "items": {"type": "string", "minLength": 1, "maxLength": 80},
            },
            "evidence_quote": {"type": "string", "minLength": 8, "maxLength": 200},
        },
        "additionalProperties": False,
    }


def compact_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def grounded_quote(content: str, answer_terms: list[str], limit: int = 160) -> str:
    sentences = [compact_text(value) for value in re.split(r"(?<=[。！？；!?;])|\n+", content)]
    candidates = [value for value in sentences if len(value) >= 8]
    if candidates:
        ranked = sorted(
            candidates,
            key=lambda value: (-sum(term in value for term in answer_terms), len(value)),
        )
        best = ranked[0]
        if any(term in best for term in answer_terms):
            return best[:limit]
    positions = [content.find(term) for term in answer_terms if term in content]
    if positions:
        start = max(0, min(positions) - 40)
        return content[start : start + limit]
    return content[:limit]


def grounded_terms(content: str, suggested_terms: list[str], limit: int = 5) -> tuple[list[str], bool]:
    terms = list(dict.fromkeys(term for term in suggested_terms if term and term in content))
    repaired = len(terms) != len(suggested_terms) or len(terms) < 2
    if len(terms) >= 2:
        return terms[:limit], repaired
    segments = [
        compact_text(value)
        for value in re.split(r"[，。！？；、：:（）()\n]+", content)
        if compact_text(value)
    ]
    for segment in segments:
        candidates = [segment] if len(segment) <= 16 else [segment[:12], segment[-12:]]
        for value in candidates:
            if len(value) >= 2 and value not in terms:
                terms.append(value)
            if len(terms) >= 2:
                return terms[:limit], True
    cursor = 0
    while len(terms) < 2 and cursor < len(content):
        value = content[cursor : cursor + 8]
        if len(value) >= 2 and value not in terms:
            terms.append(value)
        cursor += 8
    return terms[:limit], True


def build_suggestion_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": str(candidate["candidate_id"]),
        "source_type": str(candidate["source_type"]),
        "evidence_role": str(candidate.get("evidence_role") or "UNSPECIFIED"),
        "candidate_content": str(candidate["candidate_content"]),
    }


def validate_suggestion(candidate: dict[str, Any], suggestion: dict[str, Any]) -> dict[str, Any]:
    candidate_id = str(candidate["candidate_id"])
    if str(suggestion.get("candidate_id") or "") != candidate_id:
        raise ValueError(f"candidate ID mismatch: {candidate_id}")
    classification = str(suggestion.get("classification") or "")
    if classification not in FINAL_CLASSIFICATIONS:
        raise ValueError(f"invalid classification: {candidate_id}")

    question = compact_text(suggestion.get("question"))
    reason = compact_text(suggestion.get("classification_reason"))
    if not reason:
        reason = DEFAULT_CLASSIFICATION_REASONS[classification]
    content = compact_text(candidate.get("candidate_content"))
    if not 8 <= len(question) <= 300 or not question.endswith(("？", "?")):
        raise ValueError(f"question is not a bounded question: {candidate_id}")
    if len(reason) > 500:
        raise ValueError(f"classification reason is invalid: {candidate_id}")
    suggested_terms = list(dict.fromkeys(compact_text(value) for value in suggestion.get("answer_terms") or []))
    suggested_terms = [value for value in suggested_terms if value]
    answer_terms, terms_repaired = grounded_terms(content, suggested_terms)
    if not 2 <= len(answer_terms) <= 5 or sum(term in content for term in answer_terms) < 2:
        raise ValueError(f"answer terms are not grounded: {candidate_id}")

    evidence_quote = compact_text(suggestion.get("evidence_quote"))
    quote_repaired = not (8 <= len(evidence_quote) <= 200 and evidence_quote in content)
    if quote_repaired:
        evidence_quote = grounded_quote(content, answer_terms)
    if not 8 <= len(evidence_quote) <= 200 or evidence_quote not in content:
        raise ValueError(f"evidence quote is not grounded: {candidate_id}")

    return {
        "candidate_id": candidate_id,
        "question": question,
        "classification": classification,
        "classification_display": f"{CLASSIFICATION_NAMES[classification]}（{classification}）",
        "classification_reason": reason,
        "answer_terms": answer_terms,
        "answer_terms_repaired": terms_repaired,
        "evidence_quote": evidence_quote,
        "evidence_quote_repaired": quote_repaired,
    }


def sanitized_suggestion_report(
    suggestions: list[dict[str, Any]],
    *,
    expected_count: int,
    api_call_count: int,
    cached_count: int,
) -> dict[str, Any]:
    classifications = Counter(str(item["classification"]) for item in suggestions)
    questions = [compact_text(item["question"]) for item in suggestions]
    all_classes_present = FINAL_CLASSIFICATIONS <= set(classifications)
    return {
        "schema_version": "poc-03.holdout-suggestion-result.v1",
        "status": "PASS" if len(suggestions) == expected_count and len(set(questions)) == expected_count else "FAIL",
        "summary": {
            "expected_count": expected_count,
            "suggestion_count": len(suggestions),
            "unique_question_count": len(set(questions)),
            "classification_counts": dict(sorted(classifications.items())),
            "all_five_classifications_present": all_classes_present,
            "api_call_count": api_call_count,
            "cached_count": cached_count,
            "evidence_quote_repair_count": sum(
                bool(item.get("evidence_quote_repaired")) for item in suggestions
            ),
            "answer_terms_repair_count": sum(
                bool(item.get("answer_terms_repaired")) for item in suggestions
            ),
        },
        "checks": {
            "all_candidates_complete": len(suggestions) == expected_count,
            "questions_unique": len(set(questions)) == expected_count,
            "evidence_quotes_grounded": True,
            "answer_terms_grounded": True,
        },
        "quality_scope": "ai_prefill_only_pending_human_confirmation",
        "privacy": {
            "customer_content_committed": False,
            "questions_committed": False,
            "suggestions_committed": False,
            "provider_responses_committed": False,
        },
    }
