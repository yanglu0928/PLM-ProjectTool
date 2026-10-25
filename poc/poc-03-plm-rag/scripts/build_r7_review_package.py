from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any


POC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.dataset import chunk_document  # noqa: E402


CLASSIFICATIONS = {
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


def classification_display(code: str) -> str:
    return f"{CLASSIFICATION_NAMES[code]}（{code}）"


def semantic_suggestion(source_type: str, prompt_classification: str) -> str:
    if source_type != "STANDARD_CAPABILITY":
        if prompt_classification == "NO_RELIABLE_MATCH":
            return "NO_RELIABLE_MATCH"
        return "INSUFFICIENT_INFORMATION"
    if prompt_classification == "NON_STANDARD":
        return "INSUFFICIENT_INFORMATION"
    return prompt_classification


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"Expected JSON object at {path}:{line_number}")
        rows.append(value)
    return rows


def mappings(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        label, separator, raw_path = value.partition("=")
        if not separator:
            raise ValueError(f"Expected LABEL=PATH: {value}")
        result[label.strip().upper()] = Path(raw_path.strip()).resolve()
    return result


def build_chunk_index(
    parsed_root: Path,
    project_id: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    chunks: dict[str, dict[str, Any]] = {}
    documents: dict[str, dict[str, Any]] = {}
    for parsed_path in sorted(parsed_root.glob("*/*.parsed.json")):
        source_type = parsed_path.parent.name.upper()
        document_id = f"{source_type}-{parsed_path.name.split('.', 1)[0]}"
        document = load_json(parsed_path)
        documents[document_id] = document
        for chunk in chunk_document(
            document_id,
            document,
            project_id,
            source_corpus=source_type,
            max_chars=900,
        ):
            chunks[chunk["chunk_id"]] = chunk
    return chunks, documents


def find_original(root: Path | None, file_name: str) -> Path | None:
    if root is None or not root.is_dir():
        return None
    matches = [path for path in root.rglob(file_name) if path.is_file()]
    return matches[0] if len(matches) == 1 else None


def original_url(path: Path | None, locators: list[str]) -> str:
    if path is None:
        return ""
    uri = path.as_uri()
    if path.suffix.lower() == ".pdf":
        for locator in locators:
            parts = locator.split("/")
            if len(parts) >= 3 and parts[:2] == ["pdf", "pages"]:
                return f"{uri}#page={parts[2]}"
    return uri


def compact(value: Any, limit: int = 420) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else f"{text[:limit].rstrip()}…"


def location_label(chunk: dict[str, Any]) -> str:
    parts = []
    if chunk.get("pages"):
        parts.append("页 " + ", ".join(str(value) for value in chunk["pages"]))
    if chunk.get("sections"):
        parts.append(" / ".join(str(value) for value in chunk["sections"][:3]))
    if not parts:
        parts.append(str((chunk.get("source_locators") or ["未标注位置"])[0]))
    return " · ".join(parts)


def suggested_target(case: dict[str, Any], source_name: str, primary: dict[str, Any]) -> str:
    document_label = Path(source_name).stem
    where = location_label(primary)
    original = compact(case.get("query"), 220)
    return (
        f"围绕《{document_label}》{where}中与“{original}”相关的事项，依据本表列出的证据判断："
        "现有资料能否证明该事项由标准能力直接满足、仅部分满足、需要非标准开发，"
        "还是证据不足或无可靠匹配；同时确认功能范围、适用条件、限制和最直接引用。"
    )


def rationale(
    classification: str,
    *,
    differs: bool,
    source_type: str,
    prompt_classification: str,
) -> str:
    if source_type != "STANDARD_CAPABILITY" and prompt_classification not in {
        "INSUFFICIENT_INFORMATION",
        "NO_RELIABLE_MATCH",
    }:
        return (
            "Prompt v2 给出了满足程度结论，但当前证据来自合同、技术协议或调研材料，"
            "只能证明需求或约定，不能单独证明标准能力是否满足。AI 建议保守判为资料不足；"
            "如要改为标准满足、部分满足或非标准，需补充标准能力交叉证据。"
        )
    prefix = "AI 建议与 R6 分类不一致，需要人工重点确认。" if differs else "AI 建议与 R6 分类一致，仍需核对证据边界。"
    details = {
        "STANDARD_SATISFIED": "候选证据被模型判断为可直接证明现有标准能力满足目标；请确认没有遗漏前置条件或定制工作。",
        "PARTIALLY_SATISFIED": "候选证据被模型判断为只覆盖部分范围或带有条件；请确认缺口和限制足以支持部分满足。",
        "NON_STANDARD": "该结论必须有明确的定制、二次开发或标准能力不支持证据；只有需求描述时不应直接判为非标准。",
        "INSUFFICIENT_INFORMATION": "候选证据与事项相关，但不足以完整证明满足程度、实施方式或责任边界。",
        "NO_RELIABLE_MATCH": "当前候选没有直接回答判定目标；请确认是否确无可靠证据，而不是仅仅召回排序较低。",
    }
    return f"{prefix}{details[classification]}"


def issue_reason(
    current_classification: str,
    suggested_classification: str,
    expected_ids: list[str],
    suggested_ids: list[str],
) -> str:
    label_differs = current_classification != suggested_classification
    citation_differs = set(expected_ids) != set(suggested_ids)
    if label_differs and citation_differs:
        return "R6 分类与 Prompt v2 建议不一致，且模型引用不在原唯一期望集合中；需同时复核判定语义和可接受引用。"
    if label_differs:
        return "R6 分类与 Prompt v2 建议不一致；原问题缺少稳定的满足程度判定目标，需复核分类语义。"
    if citation_differs:
        return "分类一致，但模型选择了不同证据；需确认是否属于语义等价的可接受引用。"
    return "分类与引用在本轮一致；仍需确认标准化判定目标和证据边界。"


def build_navigator(cases: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for item in cases:
        candidates = []
        for candidate in item["candidate_chunks"]:
            tags = []
            if candidate["is_current_expected"]:
                tags.append("R6原引用")
            if candidate["is_ai_suggested"]:
                tags.append("AI建议引用")
            if candidate["retrieval_rank"]:
                tags.append(f"R5 Top-{candidate['retrieval_rank']}")
            badge = " / ".join(tags) or "证据候选"
            open_link = (
                f'<a class="open small" href="{html.escape(candidate["original_url"], quote=True)}">打开原文</a>'
                if candidate["original_url"]
                else '<span class="disabled">原文未定位</span>'
            )
            candidates.append(
                f"""
                <article class="chunk {'suggested' if candidate['is_ai_suggested'] else ''}" id="{html.escape(candidate['chunk_id'])}">
                  <div class="chunk-head"><div><strong>{html.escape(badge)}</strong><code>{html.escape(candidate['chunk_id'])}</code></div>{open_link}</div>
                  <p class="meta">{html.escape(candidate['document_id'])} · {html.escape(candidate['location_label'])}</p>
                  <p>{html.escape(candidate['snippet'])}</p>
                </article>"""
            )
        cards.append(
            f"""
            <section class="case" id="{html.escape(item['case_id'])}">
              <div class="case-head"><div><span class="case-id">{html.escape(item['case_id'])}</span><h2>{html.escape(item['source_name'])}</h2></div><span class="label">R6 {html.escape(item['current_classification'])} → AI {html.escape(item['suggested_classification'])}</span></div>
              <div class="query"><b>R6 当前问题</b><p>{html.escape(item['original_query'])}</p></div>
              <div class="query suggested-query"><b>R7 AI 建议判定目标</b><p>{html.escape(item['suggested_target'])}</p></div>
              <div class="reason"><b>建议理由</b><p>{html.escape(item['classification_rationale'])}</p></div>
              {''.join(candidates)}
            </section>"""
        )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>POC-03 R7 证据定位</title>
<style>
body{{margin:0;background:#f4f7fb;color:#1f2937;font:15px/1.65 "Microsoft YaHei",Arial,sans-serif}}main{{max-width:1200px;margin:auto;padding:28px}}
.hero{{background:#17365d;color:white;padding:24px 28px;border-radius:14px;box-shadow:0 8px 24px #17365d22}}.hero h1{{margin:0 0 8px}}.hero p{{margin:0;color:#dbeafe}}
.notice{{margin-top:14px;background:#fff2cc;color:#7f6000;padding:12px 16px;border-radius:8px}}.case{{background:white;margin:22px 0;padding:24px;border-radius:14px;box-shadow:0 6px 20px #17365d14;scroll-margin-top:16px}}
.case-head{{display:flex;justify-content:space-between;gap:16px;align-items:center;border-bottom:1px solid #dbe5f1;padding-bottom:14px}}h2{{font-size:18px;margin:4px 0}}.case-id{{color:#1f4e78;font-weight:700}}.label{{background:#d9eaf7;padding:6px 10px;border-radius:8px}}
.query{{border-left:4px solid #94a3b8;padding:8px 14px;margin:16px 0;background:#f8fafc}}.query p,.reason p{{margin:4px 0}}.suggested-query{{border-color:#70ad47;background:#f0f8ec}}.reason{{border-left:4px solid #ed7d31;padding:8px 14px;background:#fff7ed}}
.chunk{{border:1px solid #dbe5f1;border-radius:10px;padding:14px 16px;margin:12px 0}}.chunk.suggested{{border:2px solid #70ad47;background:#f6fbf3}}.chunk-head{{display:flex;justify-content:space-between;gap:12px;align-items:center}}.chunk-head div{{display:flex;gap:12px;flex-wrap:wrap}}code{{color:#475569}}.meta{{color:#64748b;font-size:13px;margin:5px 0}}.open{{background:#1f4e78;color:#fff;text-decoration:none;padding:9px 16px;border-radius:8px;white-space:nowrap}}.open.small{{font-size:13px;padding:5px 10px}}.disabled{{color:#64748b}}
</style></head><body><main><div class="hero"><h1>POC-03 R7 语义与引用证据定位</h1><p>覆盖 120 条 R6 样本，展示当前结论、AI 诊断建议和所有允许人工选择的证据。</p></div><div class="notice">R7 是 AI 辅助校准集。即使全部确认，也不能用同一批 120 条数据关闭质量 Gate；后续必须建立独立留出集。</div>{''.join(cards)}</main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the POC-03 R7 semantic review package")
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--prediction-cache", type=Path, required=True)
    parser.add_argument("--retrieval-cache", type=Path, required=True)
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument("--source-root", action="append", default=[])
    parser.add_argument("--package-output", type=Path, required=True)
    parser.add_argument("--navigator-output", type=Path, required=True)
    args = parser.parse_args()

    golden = load_json(args.golden)
    source_cases = list(golden.get("cases") or [])
    if len(source_cases) != 120:
        raise ValueError(f"R7 requires exactly 120 R6 cases, got {len(source_cases)}")
    predictions = load_jsonl(args.prediction_cache)
    retrievals = load_jsonl(args.retrieval_cache)
    prediction_by_id = {item["case_id"]: item for item in predictions}
    retrieval_by_id = {item["case_id"]: item for item in retrievals}
    if len(prediction_by_id) != 120 or len(retrieval_by_id) != 120:
        raise ValueError("R7 requires 120 unique Prompt v2 predictions and 120 unique R5 retrieval rows")
    if any(item.get("prompt_version") != "v2" for item in predictions):
        raise ValueError("R7 accepts only the locked Prompt v2 prediction cache")

    project_id = str(source_cases[0].get("project_id") or "POC03-SOURCE-CORPUS")
    chunks, documents = build_chunk_index(args.parsed_root.resolve(), project_id)
    source_roots = mappings(args.source_root)
    review_cases: list[dict[str, Any]] = []
    unresolved_originals = 0
    missing_chunks: set[str] = set()
    label_change_count = 0
    citation_change_count = 0

    for index, case in enumerate(source_cases, start=1):
        case_id = str(case["case_id"])
        prediction = prediction_by_id.get(case_id)
        retrieval = retrieval_by_id.get(case_id)
        if prediction is None or retrieval is None:
            raise ValueError(f"R7 cache row missing: {case_id}")
        prompt_classification = str(prediction.get("classification") or "")
        if prompt_classification not in CLASSIFICATIONS:
            raise ValueError(f"Invalid Prompt v2 classification for {case_id}: {prompt_classification}")
        source_type = str(case["source_type"]).upper()
        suggested_classification = semantic_suggestion(source_type, prompt_classification)
        current_ids = [str(value) for value in case.get("expected_relevant_chunk_ids") or []]
        suggested_ids = [str(value) for value in prediction.get("citation_chunk_ids") or []]
        top5_ids = [str(value) for value in retrieval.get("top5_ids") or []]
        reranker_ids = [str(value) for value in retrieval.get("reranker_top5_ids") or []]
        if not suggested_ids:
            raise ValueError(f"Prompt v2 returned no citation for {case_id}")
        candidate_ids = list(dict.fromkeys(suggested_ids + current_ids + top5_ids + reranker_ids))
        current_missing = {chunk_id for chunk_id in candidate_ids if chunk_id not in chunks}
        missing_chunks.update(current_missing)
        if current_missing:
            continue

        primary = chunks[suggested_ids[0]]
        primary_document = documents[primary["document_id"]]
        source_name = str((primary_document.get("source") or {}).get("file_name") or primary["document_id"])
        primary_original = find_original(source_roots.get(str(case["source_type"]).upper()), source_name)
        unresolved_originals += primary_original is None
        candidate_chunks = []
        for candidate_id in candidate_ids:
            chunk = chunks[candidate_id]
            document = documents[chunk["document_id"]]
            candidate_source_name = str((document.get("source") or {}).get("file_name") or chunk["document_id"])
            candidate_original = find_original(
                source_roots.get(str(case["source_type"]).upper()),
                candidate_source_name,
            )
            candidate_chunks.append(
                {
                    "chunk_id": candidate_id,
                    "document_id": chunk["document_id"],
                    "is_current_expected": candidate_id in current_ids,
                    "is_ai_suggested": candidate_id in suggested_ids,
                    "retrieval_rank": top5_ids.index(candidate_id) + 1 if candidate_id in top5_ids else 0,
                    "location_label": location_label(chunk),
                    "source_locators": list(chunk["source_locators"]),
                    "snippet": compact(chunk["text"]),
                    "source_name": candidate_source_name,
                    "original_url": original_url(candidate_original, list(chunk["source_locators"])),
                }
            )
        current_classification = str(case["expected_classification"])
        label_differs = current_classification != suggested_classification
        citation_differs = set(current_ids) != set(suggested_ids)
        label_change_count += label_differs
        citation_change_count += citation_differs
        review_cases.append(
            {
                "task_id": f"R7-{index:04d}",
                "case_id": case_id,
                "source_type": case["source_type"],
                "current_classification": current_classification,
                "current_classification_display": classification_display(current_classification),
                "prompt_v2_classification": prompt_classification,
                "prompt_v2_classification_display": classification_display(prompt_classification),
                "original_query": case["query"],
                "issue_reason": issue_reason(
                    current_classification,
                    suggested_classification,
                    current_ids,
                    suggested_ids,
                ),
                "suggested_target": suggested_target(case, source_name, primary),
                "suggested_classification": suggested_classification,
                "suggested_classification_display": classification_display(suggested_classification),
                "classification_rationale": rationale(
                    suggested_classification,
                    differs=label_differs,
                    source_type=source_type,
                    prompt_classification=prompt_classification,
                ),
                "suggested_chunk_ids": suggested_ids,
                "current_chunk_ids": current_ids,
                "allowed_chunk_ids": candidate_ids,
                "source_name": source_name,
                "evidence_link": f"evidence-navigator.html#{case_id}",
                "candidate_chunks": candidate_chunks,
            }
        )

    if missing_chunks:
        raise ValueError(f"R7 cache references unknown chunks: {sorted(missing_chunks)[:10]}")
    package = {
        "schema_version": "poc-03.r7-semantic-review-package.v1",
        "status": "AWAITING_HUMAN_CONFIRMATION" if unresolved_originals == 0 else "FAIL",
        "global_confirmation": "确认全部AI建议",
        "source_dataset_id": golden.get("dataset_id"),
        "scope_case_ids": [case["case_id"] for case in source_cases],
        "scope_count": len(review_cases),
        "label_change_suggestion_count": label_change_count,
        "citation_change_suggestion_count": citation_change_count,
        "unresolved_original_count": unresolved_originals,
        "validation_limit": (
            "R7 is an AI-assisted calibration dataset; the same 120 cases cannot be used to close "
            "P03-A12/P03-A13 after confirmation. Build an independent holdout set."
        ),
        "cases": review_cases,
    }
    args.package_output.parent.mkdir(parents=True, exist_ok=True)
    args.package_output.write_text(
        json.dumps(package, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.navigator_output.write_text(build_navigator(review_cases), encoding="utf-8")
    print(
        json.dumps(
            {
                key: package[key]
                for key in (
                    "status",
                    "scope_count",
                    "label_change_suggestion_count",
                    "citation_change_suggestion_count",
                    "unresolved_original_count",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0 if package["status"] == "AWAITING_HUMAN_CONFIRMATION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
