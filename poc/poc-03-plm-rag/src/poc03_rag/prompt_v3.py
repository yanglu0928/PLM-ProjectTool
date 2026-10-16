from __future__ import annotations

from typing import Any, Mapping, Sequence

from .quality_evaluation import normalize_cjk_spacing


PROMPT_ID = "poc03-quality"
PROMPT_VERSION = "v3"
QUESTION_TYPES = ("DOCUMENT_ASSERTION", "CAPABILITY_FIT")
FINAL_CLASSIFICATIONS = (
    "INSUFFICIENT_INFORMATION",
    "NON_STANDARD",
    "NO_RELIABLE_MATCH",
    "PARTIALLY_SATISFIED",
    "STANDARD_SATISFIED",
)
OUTPUT_CLASSIFICATIONS = (*FINAL_CLASSIFICATIONS, "NOT_APPLICABLE")
REQUIREMENT_SOURCE_TYPES = {"CONTRACT", "SURVEY", "TECHNICAL_AGREEMENT"}
CAPABILITY_SOURCE_TYPE = "STANDARD_CAPABILITY"


SYSTEM_PROMPT = """你正在执行 PLM 证据判定。输入会明确给出 question_type，并把需求/约定证据与标准能力证据分组。只能使用 supplied contexts，不得使用外部知识，不得使用候选顺序代替证据支持度。

第一步：任务路由。
- DOCUMENT_ASSERTION：只回答资料中是否存在所问事实。document_assertion 选择 PRESENT、ABSENT 或 AMBIGUOUS；classification 必须为 NOT_APPLICABLE，不参加五类能力质量 Gate。
- CAPABILITY_FIT：判断需求相对标准能力的适配程度。document_assertion 必须为 NOT_APPLICABLE，并执行以下证据门。

第二步：CAPABILITY_FIT 证据门。
1. 匹配性：需求证据和标准能力证据是否直接讨论同一对象、功能、条款或约束；无可靠匹配时选择 NO_RELIABLE_MATCH。
2. 充分性：只有需求边界和标准能力边界都足够清楚，才能继续判断；缺少任一侧必要条件、范围、责任或结果时选择 INSUFFICIENT_INFORMATION。
3. 原子覆盖：把复合需求拆成原子条件逐项核对。全部覆盖才可 STANDARD_SATISFIED；只覆盖部分、需要配置/集成/补充条件时选择 PARTIALLY_SATISFIED。
4. 非标依据：只有证据明确要求二次开发、定制代码、专用脚本或标准能力明确不覆盖时，才选择 NON_STANDARD；不得仅因合同或技术协议写有该要求就判为标准满足，也不得仅因标准资料未提及就判为非标。

第三步：引用。
- 比较每个 supplied context 的直接支持度，不能默认引用第 1 名。
- citation_chunk_ids 的第一个值必须是最直接支持最终结论的主引用，可再提供一个必要的对照引用。
- 只能引用 supplied contexts 中存在的 chunk_id，绝不编造。
- decision_basis 只写简洁、可审核的证据结论，不输出思维过程。

只返回符合 OutputSchema 的 JSON，不要 Markdown 或额外字段。"""


_FORBIDDEN_INPUT_KEYS = {
    "expected_classification",
    "expected_relevant_chunk_ids",
    "expected_answer_terms",
    "expected_citations",
    "review",
}


def prediction_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": [
                        "case_id",
                        "question_type",
                        "document_assertion",
                        "evidence_match",
                        "evidence_sufficiency",
                        "requirement_coverage",
                        "customization_basis",
                        "classification",
                        "citation_chunk_ids",
                        "decision_basis",
                    ],
                    "properties": {
                        "case_id": {"type": "string", "minLength": 1},
                        "question_type": {"enum": list(QUESTION_TYPES)},
                        "document_assertion": {
                            "enum": ["PRESENT", "ABSENT", "AMBIGUOUS", "NOT_APPLICABLE"]
                        },
                        "evidence_match": {
                            "enum": ["DIRECT", "PARTIAL", "NONE", "NOT_APPLICABLE"]
                        },
                        "evidence_sufficiency": {
                            "enum": ["SUFFICIENT", "INSUFFICIENT", "NOT_APPLICABLE"]
                        },
                        "requirement_coverage": {
                            "enum": ["FULL", "PARTIAL", "NONE", "NOT_APPLICABLE"]
                        },
                        "customization_basis": {
                            "enum": [
                                "EXPLICIT_CUSTOMIZATION",
                                "STANDARD_GAP_CONFIRMED",
                                "NO_CUSTOMIZATION_EVIDENCE",
                                "NOT_APPLICABLE",
                            ]
                        },
                        "classification": {"enum": list(OUTPUT_CLASSIFICATIONS)},
                        "citation_chunk_ids": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 2,
                            "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1},
                        },
                        "decision_basis": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 500,
                        },
                    },
                    "additionalProperties": False,
                    "allOf": [
                        {
                            "if": {
                                "properties": {
                                    "question_type": {"const": "DOCUMENT_ASSERTION"}
                                }
                            },
                            "then": {
                                "properties": {
                                    "classification": {"const": "NOT_APPLICABLE"},
                                    "document_assertion": {
                                        "enum": ["PRESENT", "ABSENT", "AMBIGUOUS"]
                                    },
                                }
                            },
                        },
                        {
                            "if": {
                                "properties": {
                                    "question_type": {"const": "CAPABILITY_FIT"}
                                }
                            },
                            "then": {
                                "properties": {
                                    "classification": {
                                        "enum": list(FINAL_CLASSIFICATIONS)
                                    },
                                    "document_assertion": {
                                        "const": "NOT_APPLICABLE"
                                    },
                                }
                            },
                        },
                    ],
                },
            }
        },
        "additionalProperties": False,
    }


def _context(
    chunk_id: str,
    chunks_by_id: Mapping[str, Mapping[str, Any]],
    *,
    project_id: str,
    evidence_role: str,
    rank: int,
    max_context_characters: int,
) -> dict[str, Any]:
    chunk = chunks_by_id.get(chunk_id)
    if chunk is None:
        raise ValueError(f"unknown context chunk_id: {chunk_id}")
    if str(chunk.get("scope") or "") != "PROJECT":
        raise ValueError("context must use PROJECT scope")
    if str(chunk.get("project_id") or "") != project_id:
        raise ValueError("context belongs to another ProjectId")
    source_corpus = str(chunk.get("source_corpus") or "")
    if evidence_role == "REQUIREMENT" and source_corpus not in REQUIREMENT_SOURCE_TYPES:
        raise ValueError("requirement context must come from a requirement source")
    if evidence_role == "STANDARD_CAPABILITY" and source_corpus != CAPABILITY_SOURCE_TYPE:
        raise ValueError("capability context must come from STANDARD_CAPABILITY")
    text = normalize_cjk_spacing(str(chunk.get("text") or "")).strip()
    if not text:
        raise ValueError("context text must not be empty")
    locators = [str(value) for value in chunk.get("source_locators") or []]
    return {
        "rank": rank,
        "evidence_role": evidence_role,
        "chunk_id": chunk_id,
        "document_id": str(chunk.get("document_id") or ""),
        "source_type": source_corpus,
        "source_locators": locators[:8],
        "source_locator_count": len(locators),
        "text": text[:max_context_characters],
    }


def build_case_payload(
    case: Mapping[str, Any],
    requirement_chunk_ids: Sequence[str],
    capability_chunk_ids: Sequence[str],
    chunks_by_id: Mapping[str, Mapping[str, Any]],
    *,
    max_context_characters: int = 1000,
) -> dict[str, Any]:
    if max_context_characters < 200:
        raise ValueError("max_context_characters must be at least 200")
    case_id = str(case.get("case_id") or "").strip()
    project_id = str(case.get("project_id") or "").strip()
    question_type = str(case.get("question_type") or "").strip().upper()
    query = str(case.get("query") or "").strip()
    if not case_id or not project_id or not query:
        raise ValueError("case_id, project_id, and query are required")
    if question_type not in QUESTION_TYPES:
        raise ValueError("question_type must be explicitly DOCUMENT_ASSERTION or CAPABILITY_FIT")
    if not requirement_chunk_ids:
        raise ValueError("at least one requirement context is required")
    if question_type == "DOCUMENT_ASSERTION" and capability_chunk_ids:
        raise ValueError("DOCUMENT_ASSERTION must not receive capability contexts")
    if question_type == "CAPABILITY_FIT" and not capability_chunk_ids:
        raise ValueError("CAPABILITY_FIT requires standard capability contexts")

    requirement_contexts = [
        _context(
            str(chunk_id),
            chunks_by_id,
            project_id=project_id,
            evidence_role="REQUIREMENT",
            rank=rank,
            max_context_characters=max_context_characters,
        )
        for rank, chunk_id in enumerate(requirement_chunk_ids, start=1)
    ]
    capability_contexts = [
        _context(
            str(chunk_id),
            chunks_by_id,
            project_id=project_id,
            evidence_role="STANDARD_CAPABILITY",
            rank=rank,
            max_context_characters=max_context_characters,
        )
        for rank, chunk_id in enumerate(capability_chunk_ids, start=1)
    ]
    payload = {
        "case_id": case_id,
        "project_id": project_id,
        "question_type": question_type,
        "query": query,
        "requirement_contexts": requirement_contexts,
        "capability_contexts": capability_contexts,
    }
    if payload_contains_forbidden_keys(payload):
        raise AssertionError("forbidden Golden Dataset fields entered the prompt payload")
    return payload


def payload_contains_forbidden_keys(value: Any) -> bool:
    if isinstance(value, Mapping):
        if _FORBIDDEN_INPUT_KEYS.intersection(str(key) for key in value):
            return True
        return any(payload_contains_forbidden_keys(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(payload_contains_forbidden_keys(item) for item in value)
    return False
