from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable


ALLOWED_SOURCE_TYPES = {
    "STANDARD_CAPABILITY",
    "CONTRACT",
    "TECHNICAL_AGREEMENT",
    "SURVEY",
}
ALLOWED_CLASSIFICATIONS = {
    "STANDARD_SATISFIED",
    "PARTIALLY_SATISFIED",
    "NON_STANDARD",
    "INSUFFICIENT_INFORMATION",
    "NO_RELIABLE_MATCH",
    "HUMAN_CONFIRMATION_REQUIRED",
}

DOMAIN_TERMS = (
    "PLM",
    "PDM",
    "BOM",
    "EBOM",
    "MBOM",
    "CAD",
    "CAPP",
    "ERP",
    "MES",
    "OA",
    "SAP",
    "物料编码",
    "产品结构",
    "图文档",
    "文档管理",
    "版本管理",
    "权限管理",
    "工作流",
    "生命周期",
    "设计变更",
    "工程变更",
    "变更管理",
    "数据迁移",
    "系统集成",
    "接口",
    "审批",
    "签审",
    "分类管理",
    "检索",
    "编码规则",
    "项目管理",
    "工艺管理",
    "质量管理",
    "配置管理",
    "基线",
    "零部件",
    "供应商",
    "电子签名",
    "单点登录",
    "组织架构",
    "权限",
    "版本",
    "流程",
    "文档",
    "物料",
    "图纸",
    "工艺",
    "质量",
    "项目",
)

STOP_FRAGMENTS = {
    "以下简称",
    "本项目",
    "本系统",
    "相关内容",
    "具体内容",
    "主要内容",
    "有关规定",
    "甲方",
    "乙方",
}


def _text(value: Any) -> str:
    return " ".join(str(value or "").replace("\u3000", " ").split())


def _candidate_id(record: dict[str, Any]) -> str:
    candidate_id = _text(record.get("candidate_id"))
    if not re.fullmatch(r"GD-C-\d{4}", candidate_id):
        raise ValueError("candidate_id must match GD-C-0000")
    return candidate_id


def _sentences(content: str) -> list[str]:
    raw = re.split(r"[\r\n。！？；]+", content)
    sentences: list[str] = []
    for value in raw:
        sentence = re.sub(r"\s+", " ", value).strip(" ,，、:：;；-—|_")
        if len(sentence) < 4 or not re.search(r"[\u4e00-\u9fffA-Za-z]", sentence):
            continue
        if sentence not in sentences:
            sentences.append(sentence)
    return sentences


def _term_candidates(content: str, sentences: list[str]) -> list[str]:
    terms: list[str] = []
    content_upper = content.upper()
    for term in DOMAIN_TERMS:
        if term.upper() in content_upper and term not in terms:
            terms.append(term)

    ascii_terms = re.findall(r"(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9._+-]{1,15}", content)
    for term in ascii_terms:
        normalized = term.upper() if len(term) <= 6 else term
        if normalized not in terms and normalized not in {"HTTP", "HTTPS", "WORD", "PDF"}:
            terms.append(normalized)

    for sentence in sentences:
        for fragment in re.split(r"[，、,:：()（）\[\]【】/\\]+", sentence):
            fragment = fragment.strip()
            fragment = re.sub(r"^(支持|提供|实现|采用|通过|针对|关于|要求|包括|完成)", "", fragment)
            fragment = re.sub(r"(功能|管理|模块|系统|平台)$", lambda match: match.group(0), fragment)
            if any(stop in fragment for stop in STOP_FRAGMENTS):
                continue
            if 2 <= len(fragment) <= 10 and re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9._+-]+", fragment):
                if fragment not in terms:
                    terms.append(fragment)
        if len(terms) >= 8:
            break
    return terms


def _topic(sentences: list[str], terms: list[str]) -> str:
    short_headings = [
        sentence
        for sentence in sentences[:8]
        if 4 <= len(sentence) <= 28 and not re.match(r"^\d+(?:\.\d+)*\s*$", sentence)
    ]
    if short_headings:
        topic = short_headings[0]
    elif len(terms) >= 2:
        topic = "、".join(terms[:3])
    elif terms:
        topic = terms[0]
    elif sentences:
        topic = sentences[0][:32]
    else:
        topic = "该候选片段"
    return topic[:42].rstrip("，、,:：;；")


def _classification(content: str) -> str:
    normalized = _text(content)
    rules = (
        ("HUMAN_CONFIRMATION_REQUIRED", ("待确认", "需确认", "需要确认", "人工确认", "双方确认")),
        ("NON_STANDARD", ("不支持", "无法实现", "不能实现", "未实现", "非标准", "定制开发", "二次开发")),
        ("INSUFFICIENT_INFORMATION", ("未明确", "暂无", "不详", "资料不足", "缺少资料", "未提供")),
        ("PARTIALLY_SATISFIED", ("部分满足", "部分支持", "需配置", "需要配置", "需扩展", "需要扩展")),
        ("STANDARD_SATISFIED", ("标准功能", "原生支持", "系统支持", "可以实现", "可实现", "具备", "满足")),
    )
    for classification, phrases in rules:
        if any(phrase in normalized for phrase in phrases):
            return classification
    return "HUMAN_CONFIRMATION_REQUIRED"


def _source_type(source_corpus: str) -> str:
    mapping = {
        "CONTRACT": "CONTRACT",
        "TECHNICAL_AGREEMENT": "TECHNICAL_AGREEMENT",
        "SURVEY": "SURVEY",
        "STANDARD_CAPABILITY": "STANDARD_CAPABILITY",
    }
    return mapping.get(source_corpus.upper(), "")


def build_review_suggestions(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    query_counts: Counter[str] = Counter()
    for record in records:
        candidate_id = _candidate_id(record)
        if candidate_id in seen_ids:
            raise ValueError(f"duplicate candidate_id: {candidate_id}")
        seen_ids.add(candidate_id)

        content = _text(record.get("candidate_content"))
        if not content:
            raise ValueError(f"candidate_content is required: {candidate_id}")
        source_corpus = _text(record.get("source_corpus")).upper()
        sentences = _sentences(content)
        terms = _term_candidates(content, sentences)
        topic = _topic(sentences, terms)
        if source_corpus == "CONTRACT":
            query = f"合同或技术要求中，关于“{topic}”有哪些明确约定？"
        else:
            query = f"参考资料中，关于“{topic}”采用了什么实现方式或配置？"

        query_counts[query] += 1
        if query_counts[query] > 1:
            differentiator = "、".join(terms[1:4]) or (sentences[1][:24] if len(sentences) > 1 else topic)
            query = f"参考资料中，“{topic}”与“{differentiator}”之间有哪些具体要求或做法？"
            query_counts[query] += 1
        if query_counts[query] > 1:
            ordinal = query_counts[query]
            query = f"{query[:-1]}（同主题第{ordinal}处）？"

        source_type = _source_type(source_corpus)
        notes = "本地规则预填；查询、分类、术语与引用定位均需人工确认。"
        if not source_type:
            notes += f" 来源语料 {source_corpus or 'UNKNOWN'} 不在锁定来源类型枚举中，来源类型留空。"

        citation = (record.get("expected_citations") or [{}])[0]
        locators = [_text(value) for value in citation.get("source_locators") or [] if _text(value)]
        answer_terms = terms[:5]
        if len(answer_terms) < 2:
            answer_terms.extend(
                sentence[:10]
                for sentence in sentences
                if sentence[:10] not in answer_terms
            )
            answer_terms = answer_terms[:5]

        suggestion = {
            "candidate_id": candidate_id,
            "query": query,
            "source_type": source_type,
            "classification": _classification(content),
            "answer_terms": answer_terms,
            "citation_locators": locators,
            "review_status": "PENDING",
            "reviewed_by": "",
            "reviewed_at": "",
            "notes": notes,
        }
        if suggestion["source_type"] and suggestion["source_type"] not in ALLOWED_SOURCE_TYPES:
            raise ValueError(f"invalid source type suggestion: {candidate_id}")
        if suggestion["classification"] not in ALLOWED_CLASSIFICATIONS:
            raise ValueError(f"invalid classification suggestion: {candidate_id}")
        suggestions.append(suggestion)
    return suggestions


def build_sanitized_suggestion_report(
    suggestions: Iterable[dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    rows = list(suggestions)
    queries = [row["query"] for row in rows]
    source_counts = Counter(row["source_type"] or "UNRESOLVED" for row in rows)
    classification_counts = Counter(row["classification"] for row in rows)
    unresolved_source_count = source_counts.get("UNRESOLVED", 0)
    status = "PASS_FOR_HUMAN_REVIEW" if rows and len(set(queries)) == len(rows) else "FAIL"
    return {
        "schema_version": "poc-03.review-suggestion-result.v1",
        "generated_at": generated_at,
        "status": status,
        "generation_mode": "LOCAL_DETERMINISTIC_RULES",
        "summary": {
            "suggestion_count": len(rows),
            "unique_query_count": len(set(queries)),
            "unresolved_source_type_count": unresolved_source_count,
            "source_type_suggestion_counts": dict(sorted(source_counts.items())),
            "classification_suggestion_counts": dict(sorted(classification_counts.items())),
            "pending_review_count": sum(row["review_status"] == "PENDING" for row in rows),
            "citation_prefill_count": sum(bool(row["citation_locators"]) for row in rows),
        },
        "privacy": {
            "external_ai_service_called": False,
            "customer_content_uploaded": False,
            "customer_content_committed": False,
            "queries_committed": False,
            "answer_terms_committed": False,
            "workbook_committed": False,
        },
        "quality_scope": "local_prefill_suggestions_only_not_human_approved_ground_truth",
        "conclusion": (
            "Local suggestions are ready for human review; no row is approved and no Golden Dataset quality metric may be claimed."
            if status == "PASS_FOR_HUMAN_REVIEW"
            else "Suggestion generation requires correction before human review."
        ),
    }
