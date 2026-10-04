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


R6_CASE_IDS = ("GD-0016", "GD-0018", "GD-0020", "GD-0023", "GD-0075", "GD-0091")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def mappings(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        label, separator, raw_path = value.partition("=")
        if not separator:
            raise ValueError(f"Expected LABEL=PATH: {value}")
        result[label.strip().upper()] = Path(raw_path.strip()).resolve()
    return result


def build_chunk_index(parsed_root: Path, project_id: str) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
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


def suggested_query(case: dict[str, Any], primary: dict[str, Any], source_name: str) -> str:
    document_label = Path(source_name).stem
    sections = [compact(value, 32) for value in primary.get("sections") or [] if len(compact(value, 32)) >= 2]
    pages = [str(value) for value in primary.get("pages") or []]
    if sections:
        location = f"“{' / '.join(sections[:3])}”部分"
    elif pages:
        location = f"第{'、'.join(pages)}页"
    else:
        location = "对应证据段落"
    original = compact(case.get("query"), 180)
    return f"在《{document_label}》的{location}中，针对以下问题给出该段落明确记载的功能、条件和处理结果：{original}"


def build_navigator(cases: list[dict[str, Any]]) -> str:
    cards: list[str] = []
    for item in cases:
        candidates = []
        for candidate in item["candidate_chunks"]:
            badge = "原核定引用" if candidate["is_expected"] else f"检索候选 #{candidate['rank']}"
            candidates.append(
                f"""
                <article class="chunk {'expected' if candidate['is_expected'] else ''}" id="{html.escape(candidate['chunk_id'])}">
                  <div class="chunk-head"><strong>{html.escape(badge)}</strong><code>{html.escape(candidate['chunk_id'])}</code></div>
                  <p class="meta">{html.escape(candidate['document_id'])} · {html.escape(candidate['location_label'])}</p>
                  <p>{html.escape(candidate['snippet'])}</p>
                </article>"""
            )
        open_link = (
            f'<a class="open" href="{html.escape(item["original_url"], quote=True)}">打开原始文档</a>'
            if item["original_url"]
            else '<span class="disabled">原始文档未定位</span>'
        )
        cards.append(
            f"""
            <section class="case" id="{html.escape(item['case_id'])}">
              <div class="case-head"><div><span class="case-id">{html.escape(item['case_id'])}</span><h2>{html.escape(item['source_name'])}</h2></div>{open_link}</div>
              <div class="query"><b>当前问题</b><p>{html.escape(item['original_query'])}</p></div>
              <div class="query suggested"><b>AI 建议问题</b><p>{html.escape(item['suggested_query'])}</p></div>
              <p class="rank">原核定 Chunk 当前排名：<strong>{item['expected_rank']}</strong>；下方同时列出 Top-5 对照。</p>
              {''.join(candidates)}
            </section>"""
        )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>POC-03 R6 证据定位</title>
<style>
body{{margin:0;background:#f4f7fb;color:#1f2937;font:15px/1.65 "Microsoft YaHei",Arial,sans-serif}}main{{max-width:1180px;margin:auto;padding:28px}}
.hero{{background:#17365d;color:white;padding:24px 28px;border-radius:14px;box-shadow:0 8px 24px #17365d22}}.hero h1{{margin:0 0 8px}}.hero p{{margin:0;color:#dbeafe}}
.case{{background:white;margin:22px 0;padding:24px;border-radius:14px;box-shadow:0 6px 20px #17365d14;scroll-margin-top:16px}}.case-head{{display:flex;justify-content:space-between;gap:16px;align-items:center;border-bottom:1px solid #dbe5f1;padding-bottom:14px}}h2{{font-size:18px;margin:4px 0}}.case-id{{color:#1f4e78;font-weight:700}}.open{{background:#1f4e78;color:#fff;text-decoration:none;padding:9px 16px;border-radius:8px;white-space:nowrap}}.disabled{{color:#64748b}}
.query{{border-left:4px solid #94a3b8;padding:8px 14px;margin:16px 0;background:#f8fafc}}.query p{{margin:4px 0}}.suggested{{border-color:#70ad47;background:#f0f8ec}}.rank{{color:#8a4b08}}
.chunk{{border:1px solid #dbe5f1;border-radius:10px;padding:14px 16px;margin:12px 0}}.chunk.expected{{border:2px solid #70ad47;background:#f6fbf3}}.chunk-head{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}}code{{color:#475569}}.meta{{color:#64748b;font-size:13px;margin:5px 0}}
</style></head><body><main><div class="hero"><h1>POC-03 R6 证据定位</h1><p>仅复核 6 个低区分度样本。绿色卡片为 R5 已核定引用，其他卡片为当前 Top-5 检索对照。</p></div>{''.join(cards)}</main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the six-case POC-03 R6 review package")
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--quality", type=Path, required=True)
    parser.add_argument("--parsed-root", type=Path, required=True)
    parser.add_argument("--source-root", action="append", default=[])
    parser.add_argument("--package-output", type=Path, required=True)
    parser.add_argument("--navigator-output", type=Path, required=True)
    args = parser.parse_args()

    golden = load_json(args.golden)
    quality = load_json(args.quality)
    cases_by_id = {case["case_id"]: case for case in golden.get("cases") or []}
    retrieval_by_id = {item["case_id"]: item for item in quality.get("cases") or []}
    project_id = str((golden.get("cases") or [{}])[0].get("project_id") or "POC03-SOURCE-CORPUS")
    chunks, documents = build_chunk_index(args.parsed_root.resolve(), project_id)
    source_roots = mappings(args.source_root)

    review_cases: list[dict[str, Any]] = []
    unresolved = 0
    for index, case_id in enumerate(R6_CASE_IDS, start=1):
        case = cases_by_id[case_id]
        retrieval = retrieval_by_id[case_id]
        expected_ids = list(case.get("expected_relevant_chunk_ids") or [])
        top5_ids = list(retrieval.get("top5_ids") or [])
        candidate_ids = list(dict.fromkeys(expected_ids + top5_ids))
        expected_rank = int(retrieval.get("best_expected_rank") or 0)
        primary = chunks[expected_ids[0]]
        document = documents[primary["document_id"]]
        source_name = str((document.get("source") or {}).get("file_name") or primary["document_id"])
        original = find_original(source_roots.get(case["source_type"]), source_name)
        unresolved += original is None
        candidate_chunks = []
        for candidate_id in candidate_ids:
            chunk = chunks[candidate_id]
            rank = top5_ids.index(candidate_id) + 1 if candidate_id in top5_ids else expected_rank
            location_parts = []
            if chunk.get("pages"):
                location_parts.append("页 " + ", ".join(str(value) for value in chunk["pages"]))
            if chunk.get("sections"):
                location_parts.append(" / ".join(chunk["sections"][:3]))
            if not location_parts:
                location_parts.append(chunk["source_locators"][0])
            candidate_chunks.append(
                {
                    "chunk_id": candidate_id,
                    "document_id": chunk["document_id"],
                    "rank": rank,
                    "is_expected": candidate_id in expected_ids,
                    "location_label": " · ".join(location_parts),
                    "source_locators": list(chunk["source_locators"]),
                    "snippet": compact(chunk["text"]),
                }
            )
        review_cases.append(
            {
                "task_id": f"R6-{index:02d}",
                "case_id": case_id,
                "source_type": case["source_type"],
                "classification": case["expected_classification"],
                "original_query": case["query"],
                "issue_reason": "原问题只包含通用短语或 OCR 片段，缺少文档、模块或业务场景限定，容易召回同类操作。",
                "suggested_query": suggested_query(case, primary, source_name),
                "suggested_chunk_ids": expected_ids,
                "allowed_chunk_ids": candidate_ids,
                "expected_rank": expected_rank,
                "source_name": source_name,
                "original_url": original_url(original, primary["source_locators"]),
                "evidence_link": f"evidence-navigator.html#{case_id}",
                "candidate_chunks": candidate_chunks,
            }
        )

    package = {
        "schema_version": "poc-03.r6-citation-review-package.v1",
        "status": "AWAITING_HUMAN_CONFIRMATION" if unresolved == 0 else "FAIL",
        "global_confirmation": "确认全部AI建议",
        "source_dataset_id": golden.get("dataset_id"),
        "scope_case_ids": list(R6_CASE_IDS),
        "scope_count": len(R6_CASE_IDS),
        "preserved_case_count": len(golden.get("cases") or []) - len(R6_CASE_IDS),
        "unresolved_original_count": unresolved,
        "cases": review_cases,
    }
    args.package_output.parent.mkdir(parents=True, exist_ok=True)
    args.package_output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.navigator_output.write_text(build_navigator(review_cases), encoding="utf-8")
    print(json.dumps({key: package[key] for key in ("status", "scope_count", "preserved_case_count", "unresolved_original_count")}, ensure_ascii=False))
    return 0 if package["status"] == "AWAITING_HUMAN_CONFIRMATION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
