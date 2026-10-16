from __future__ import annotations

from typing import Any, Mapping, Sequence

from .quality_evaluation import normalize_cjk_spacing


PROMPT_ID = "poc03-quality"
PROMPT_VERSION = "v2"
FINAL_CLASSIFICATIONS = (
    "INSUFFICIENT_INFORMATION",
    "NON_STANDARD",
    "NO_RELIABLE_MATCH",
    "PARTIALLY_SATISFIED",
    "STANDARD_SATISFIED",
)

SYSTEM_PROMPT = """你正在依据 PLM 项目资料判断一个问题的业务结论。只能使用用户消息中提供的 contexts，不得使用外部知识，不得把来源类型本身当作结论。

请在内部严格按以下顺序判断：
1. 匹配性：contexts 是否直接讨论问题所问的对象、功能、条款或约束？若没有可靠匹配，选择 NO_RELIABLE_MATCH。
2. 充分性：若有相关内容，它是否足以得出明确结论？若相关但缺少必要条件、范围、责任或结果，选择 INSUFFICIENT_INFORMATION。
3. 满足程度：只有证据充分时才继续判断：
   - STANDARD_SATISFIED：证据明确、完整地表明现有标准能力或明确约定满足问题。
   - PARTIALLY_SATISFIED：只满足一部分，或仍需要配置、集成、补充条件才能满足。
   - NON_STANDARD：证据明确表明需要非标准开发、二次开发或定制；不能仅因资料未提及就判为 NON_STANDARD。

重要约束：
- 最终分类只能是上述五类；HUMAN_CONFIRMATION_REQUIRED 是工作流状态，不是本任务的最终业务标签。
- 合同、技术协议、标准能力和调研资料都只是证据来源；不得仅凭 source_type 推断满足或不满足。
- 优先引用最直接支持结论的一个 chunk_id；只能引用 supplied contexts 中存在的 id，绝不编造。
- 不要输出分析过程、Markdown 或额外字段。

仅返回一个 JSON 对象，精确结构如下：
{"items":[{"case_id":"输入中的 case_id","classification":"五类之一","citation_chunk_ids":["一个 supplied chunk_id"]}]}"""

RECOVERY_JSON_PROMPT = """只使用提供的问题和 contexts，并按“匹配性 → 充分性 → 满足程度”的顺序判断。
最终分类只能是 STANDARD_SATISFIED、PARTIALLY_SATISFIED、NON_STANDARD、INSUFFICIENT_INFORMATION、NO_RELIABLE_MATCH。
仅返回有效 JSON，不要 Markdown、解释或额外字段。必须引用一个 supplied chunk_id，不能编造。
精确结构：{"items":[{"case_id":"输入 id","classification":"五类之一","citation_chunk_ids":["一个 supplied chunk_id"]}]}"""

PLAIN_RECOVERY_PROMPT = """只使用提供的问题和 contexts，并按“匹配性 → 充分性 → 满足程度”的顺序判断。
最后只输出一行：FINAL:CLASSIFICATION|CHUNK_ID
CLASSIFICATION 只能是 STANDARD_SATISFIED、PARTIALLY_SATISFIED、NON_STANDARD、INSUFFICIENT_INFORMATION、NO_RELIABLE_MATCH。
CHUNK_ID 必须是一个 supplied id。不要 JSON、Markdown 或多个 FINAL 行。"""

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
                    "required": ["case_id", "classification", "citation_chunk_ids"],
                    "properties": {
                        "case_id": {"type": "string", "minLength": 1},
                        "classification": {"enum": list(FINAL_CLASSIFICATIONS)},
                        "citation_chunk_ids": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 1,
                            "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1},
                        },
                    },
                    "additionalProperties": False,
                },
            }
        },
        "additionalProperties": False,
    }


def build_case_payload(
    case: Mapping[str, Any],
    ranked_chunk_ids: Sequence[str],
    chunks_by_id: Mapping[str, Mapping[str, Any]],
    *,
    max_context_characters: int = 1000,
) -> dict[str, Any]:
    if max_context_characters < 200:
        raise ValueError("max_context_characters must be at least 200")
    case_id = str(case.get("case_id") or "").strip()
    source_type = str(case.get("source_type") or "").strip()
    query = str(case.get("query") or "").strip()
    if not case_id or not source_type or not query:
        raise ValueError("case_id, source_type, and query are required")
    if not ranked_chunk_ids:
        raise ValueError("at least one ranked context is required")

    contexts = []
    for rank, chunk_id_value in enumerate(ranked_chunk_ids, start=1):
        chunk_id = str(chunk_id_value)
        if chunk_id not in chunks_by_id:
            raise ValueError(f"unknown context chunk_id: {chunk_id}")
        chunk = chunks_by_id[chunk_id]
        chunk_source = str(chunk.get("source_corpus") or "")
        if chunk_source != source_type:
            raise ValueError("context source type does not match case source type")
        text = normalize_cjk_spacing(str(chunk.get("text") or "")).strip()
        if not text:
            raise ValueError("context text must not be empty")
        locators = [str(value) for value in chunk.get("source_locators") or []]
        contexts.append(
            {
                "rank": rank,
                "chunk_id": chunk_id,
                "document_id": str(chunk.get("document_id") or ""),
                "source_locators": locators[:8],
                "source_locator_count": len(locators),
                "text": text[:max_context_characters],
            }
        )
    payload = {
        "case_id": case_id,
        "source_type": source_type,
        "query": query,
        "contexts": contexts,
    }
    if _FORBIDDEN_INPUT_KEYS.intersection(payload):
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
