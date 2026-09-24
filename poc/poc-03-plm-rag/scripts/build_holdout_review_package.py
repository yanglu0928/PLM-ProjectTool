from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any


CLASSIFICATION_NAMES = {
    "STANDARD_SATISFIED": "标准满足",
    "PARTIALLY_SATISFIED": "部分满足",
    "NON_STANDARD": "非标准",
    "INSUFFICIENT_INFORMATION": "资料不足",
    "NO_RELIABLE_MATCH": "无可靠匹配",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_documents(parsed_roots: list[Path]) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for root in parsed_roots:
        for corpus_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            for path in sorted(corpus_dir.glob("*.parsed.json")):
                stem = path.name.removesuffix(".parsed.json")
                document_id = stem if stem.startswith(f"{corpus_dir.name}-") else f"{corpus_dir.name}-{stem}"
                documents[document_id] = load_json(path)
    return documents


def find_original(source_roots: list[Path], file_name: str) -> Path | None:
    matches: list[Path] = []
    for root in source_roots:
        if root.is_dir():
            matches.extend(path for path in root.rglob(file_name) if path.is_file())
    unique = sorted({path.resolve() for path in matches})
    return unique[0] if len(unique) == 1 else None


def original_url(path: Path | None, pages: list[Any]) -> str:
    if path is None:
        return ""
    uri = path.as_uri()
    if path.suffix.lower() == ".pdf" and pages:
        return f"{uri}#page={pages[0]}"
    return uri


def location_label(candidate: dict[str, Any]) -> str:
    values = []
    if candidate.get("pages"):
        values.append("页 " + ", ".join(str(value) for value in candidate["pages"]))
    if candidate.get("sections"):
        values.append(" / ".join(str(value) for value in candidate["sections"][:3]))
    if not values:
        values.append(str((candidate.get("source_locators") or ["未标注位置"])[0]))
    return " · ".join(values)


def highlighted_content(content: str, quote: str) -> str:
    offset = content.find(quote)
    if offset < 0:
        return html.escape(content)
    return (
        html.escape(content[:offset])
        + "<mark>"
        + html.escape(quote)
        + "</mark>"
        + html.escape(content[offset + len(quote) :])
    )


def build_navigator(cases: list[dict[str, Any]]) -> str:
    cards = []
    for item in cases:
        open_link = (
            f'<a class="open" href="{html.escape(item["original_url"], quote=True)}">打开原文</a>'
            if item["original_url"]
            else '<span class="disabled">原文未定位</span>'
        )
        cards.append(
            f"""
            <section class="case" id="{html.escape(item['candidate_id'])}">
              <div class="case-head"><div><span>{html.escape(item['task_id'])}</span><h2>{html.escape(item['source_name'])}</h2></div>{open_link}</div>
              <p class="meta">{html.escape(item['source_type_display'])} · {html.escape(item['location_label'])}</p>
              <div class="question"><b>AI 建议问题</b><p>{html.escape(item['suggested_question'])}</p></div>
              <div class="classification"><b>AI 建议分类</b><p>{html.escape(item['suggested_classification_display'])}</p><p>{html.escape(item['classification_reason'])}</p></div>
              <article class="evidence"><b>锁定证据</b><p>{highlighted_content(item['candidate_content'], item['evidence_quote'])}</p></article>
              <p class="locator">定位：{html.escape('；'.join(item['source_locators']))}</p>
            </section>"""
        )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>POC-03 独立留出集证据定位</title>
<style>
body{{margin:0;background:#f4f7fb;color:#1f2937;font:15px/1.7 "Microsoft YaHei",Arial,sans-serif}}main{{max-width:1180px;margin:auto;padding:28px}}
.hero{{background:#17365d;color:white;padding:24px 28px;border-radius:12px}}.hero h1{{margin:0 0 8px}}.hero p{{margin:0;color:#dbeafe}}
.notice{{margin:14px 0;background:#fff2cc;color:#7f6000;padding:12px 16px;border-radius:8px}}.case{{background:white;margin:20px 0;padding:22px;border-radius:12px;box-shadow:0 5px 18px #17365d14;scroll-margin-top:14px}}
.case-head{{display:flex;justify-content:space-between;gap:16px;align-items:center;border-bottom:1px solid #dbe5f1;padding-bottom:12px}}h2{{font-size:18px;margin:3px 0}}.case-head span{{color:#1f4e78;font-weight:700}}.meta,.locator{{color:#64748b;font-size:13px}}
.question,.classification{{border-left:4px solid #70ad47;padding:8px 14px;margin:14px 0;background:#f3f8ef}}.classification{{border-color:#ed7d31;background:#fff7ed}}.question p,.classification p{{margin:4px 0}}
.evidence{{border:1px solid #dbe5f1;border-radius:9px;padding:14px 16px}}mark{{background:#fff2a8;padding:1px 2px}}.open{{background:#1f4e78;color:white;text-decoration:none;padding:8px 14px;border-radius:7px;white-space:nowrap}}.disabled{{color:#64748b}}
</style></head><body><main><div class="hero"><h1>POC-03 独立留出集证据定位</h1><p>50 条锁定候选。工作簿中的“打开证据”可直接跳到对应卡片。</p></div><div class="notice">AI 建议仅供人工确认。实际客户调研记录是主要事实证据；调研业务表单只作参考。</div>{''.join(cards)}</main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the local POC-03 holdout review package and evidence navigator")
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--suggestions", type=Path, required=True)
    parser.add_argument("--parsed-root", type=Path, action="append", required=True)
    parser.add_argument("--source-root", type=Path, action="append", required=True)
    parser.add_argument("--package-output", type=Path, required=True)
    parser.add_argument("--navigator-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()

    lock = load_json(args.lock)
    suggestion_payload = load_json(args.suggestions)
    candidates = list(lock.get("candidates") or [])
    suggestions = list(suggestion_payload.get("suggestions") or [])
    if len(candidates) != 50 or len(suggestions) != 50:
        raise ValueError("review package requires exactly 50 candidates and 50 suggestions")
    if suggestion_payload.get("lock_fingerprint") != lock.get("lock_fingerprint"):
        raise ValueError("suggestions do not match the holdout lock fingerprint")
    suggestion_by_id = {str(item["candidate_id"]): item for item in suggestions}
    if len(suggestion_by_id) != 50:
        raise ValueError("suggestion candidate IDs must be unique")
    documents = load_documents(args.parsed_root)
    cases = []
    unresolved_original_count = 0
    for index, candidate in enumerate(candidates, start=1):
        candidate_id = str(candidate["candidate_id"])
        suggestion = suggestion_by_id.get(candidate_id)
        if suggestion is None:
            raise ValueError(f"missing suggestion: {candidate_id}")
        document_id = str(candidate["document_id"])
        document = documents.get(document_id)
        if document is None:
            raise ValueError(f"missing parsed document: {document_id}")
        source_name = str((document.get("source") or {}).get("file_name") or document_id)
        original = find_original(args.source_root, source_name)
        unresolved_original_count += original is None
        classification = str(suggestion["classification"])
        cases.append(
            {
                "task_id": f"HO-R-{index:04d}",
                "candidate_id": candidate_id,
                "source_type": candidate["source_type"],
                "source_type_display": {
                    "STANDARD_CAPABILITY": "标准能力",
                    "CONTRACT": "合同",
                    "TECHNICAL_AGREEMENT": "技术协议",
                    "SURVEY": "实际客户调研记录",
                }[candidate["source_type"]],
                "evidence_role": candidate.get("evidence_role"),
                "suggested_question": suggestion["question"],
                "suggested_classification": classification,
                "suggested_classification_display": f"{CLASSIFICATION_NAMES[classification]}（{classification}）",
                "classification_reason": suggestion["classification_reason"],
                "answer_terms": suggestion["answer_terms"],
                "evidence_quote": suggestion["evidence_quote"],
                "evidence_quote_repaired": bool(suggestion.get("evidence_quote_repaired")),
                "answer_terms_repaired": bool(suggestion.get("answer_terms_repaired")),
                "chunk_id": candidate["chunk_id"],
                "text_sha256": candidate["text_sha256"],
                "document_id": document_id,
                "source_locators": candidate["source_locators"],
                "pages": candidate["pages"],
                "sections": candidate["sections"],
                "location_label": location_label(candidate),
                "source_name": source_name,
                "original_url": original_url(original, list(candidate.get("pages") or [])),
                "evidence_link": f"evidence-navigator.html#{candidate_id}",
                "candidate_content": candidate["candidate_content"],
            }
        )

    package = {
        "schema_version": "poc-03.holdout-review-package.v1",
        "status": "AWAITING_HUMAN_CONFIRMATION" if unresolved_original_count == 0 else "FAIL",
        "lock_fingerprint": lock["lock_fingerprint"],
        "scope_count": len(cases),
        "global_confirmation": "待确认",
        "unresolved_original_count": unresolved_original_count,
        "source_type_counts": dict(sorted(Counter(item["source_type"] for item in cases).items())),
        "classification_counts": dict(sorted(Counter(item["suggested_classification"] for item in cases).items())),
        "cases": cases,
    }
    args.package_output.parent.mkdir(parents=True, exist_ok=True)
    args.package_output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.navigator_output.write_text(build_navigator(cases), encoding="utf-8")
    report = {
        "schema_version": "poc-03.holdout-review-package-result.v1",
        "status": "PASS" if package["status"] == "AWAITING_HUMAN_CONFIRMATION" else "FAIL",
        "summary": {
            "scope_count": len(cases),
            "unresolved_original_count": unresolved_original_count,
            "source_type_counts": package["source_type_counts"],
            "classification_counts": package["classification_counts"],
        },
        "checks": {
            "all_candidates_have_suggestions": len(cases) == 50,
            "all_original_files_located": unresolved_original_count == 0,
            "all_evidence_links_created": len(cases) == 50,
            "all_rows_pending_human_confirmation": True,
        },
        "privacy": {
            "package_committed": False,
            "navigator_committed": False,
            "customer_content_committed": False,
        },
    }
    args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
