from __future__ import annotations

import html
from collections import Counter
from typing import Any, Iterable


CLASSIFICATION_LABELS = {
    "STANDARD_SATISFIED": "标准满足",
    "PARTIALLY_SATISFIED": "部分满足",
    "NON_STANDARD": "潜在非标",
    "INSUFFICIENT_INFORMATION": "资料不足",
    "NO_RELIABLE_MATCH": "无可靠匹配",
    "HUMAN_CONFIRMATION_REQUIRED": "需人工确认",
}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _confirmation_prompt(*, source_type: str, classification: str) -> str:
    if not source_type:
        return (
            "请在“补充说明/修改后结论”填写资料类型：标准能力、合同、技术协议或调研；"
            "若均不适用，请填写“不适用”并说明原因。"
        )
    prompts = {
        "NON_STANDARD": "请确认是否确属非标或定制内容，并说明是否需要范围变更、专项开发或商务澄清。",
        "PARTIALLY_SATISFIED": "请确认已满足范围与缺口，并在补充栏写明边界条件和后续动作。",
        "STANDARD_SATISFIED": "请确认能力判断是否正确，并补充适用范围、前提条件或例外。",
        "INSUFFICIENT_INFORMATION": "请确认缺少哪类资料、由谁补充，以及期望完成时间。",
        "NO_RELIABLE_MATCH": "请确认是否需要重新检索、补充证据，或判定为不构成待办。",
        "HUMAN_CONFIRMATION_REQUIRED": "请确认该描述是否形成项目约束、风险、缺口或后续行动。",
    }
    return prompts.get(classification, "请确认 AI 建议是否正确；如需修改，请写明正式结论和理由。")


def _risk_level(*, source_type: str, classification: str) -> str:
    if classification == "NON_STANDARD":
        return "高"
    if not source_type or classification in {
        "PARTIALLY_SATISFIED",
        "INSUFFICIENT_INFORMATION",
        "NO_RELIABLE_MATCH",
        "HUMAN_CONFIRMATION_REQUIRED",
    }:
        return "中"
    return "低"


def build_confirmation_tasks(
    candidates: Iterable[dict[str, Any]],
    review_rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate_by_id = {_text(item.get("candidate_id")): item for item in candidates}
    tasks: list[dict[str, Any]] = []
    for row in review_rows:
        candidate_id = _text(row.get("candidate_id"))
        candidate = candidate_by_id.get(candidate_id)
        if candidate is None:
            raise ValueError(f"review row has no candidate source: {candidate_id}")
        source_type = _text(row.get("source_type")).upper()
        classification = _text(row.get("classification")).upper()
        original_status = _text(row.get("review_status")).upper()
        label = CLASSIFICATION_LABELS.get(classification, classification or "待判断")
        source_corpus = _text(candidate.get("source_corpus")).upper()
        formally_complete = original_status == "APPROVED" and all(
            _text(row.get(field))
            for field in (
                "query",
                "source_type",
                "classification",
                "answer_terms",
                "confirmed_locator",
                "reviewed_by",
                "reviewed_at",
            )
        )
        current_status = "已确认" if formally_complete else "待补充"
        default_decision = "同意AI建议" if formally_complete else "需要补充资料"
        ai_advice = f"建议标记为“{label}”（仅为 AI/规则建议）。"
        if not source_type:
            ai_advice += " 当前资料来源为方案库，锁定枚举无直接对应项，不能自动代填。"
        tasks.append(
            {
                "task_id": f"CONF-{candidate_id.removeprefix('GD-C-')}",
                "candidate_id": candidate_id,
                "issue_type": "资料类型待确认" if not source_type else label,
                "risk_level": _risk_level(
                    source_type=source_type,
                    classification=classification,
                ),
                "ai_finding": _text(row.get("query")),
                "confirmation_prompt": _confirmation_prompt(
                    source_type=source_type,
                    classification=classification,
                ),
                "ai_advice": ai_advice,
                "evidence_link": f"evidence-navigator.html#{candidate_id}",
                "evidence_label": "打开证据 ►",
                "human_decision": default_decision,
                "human_note": "",
                "original_review_status": original_status,
                "reviewed_by": _text(row.get("reviewed_by")),
                "reviewed_at": _text(row.get("reviewed_at")),
                "current_status": current_status,
                "source_corpus": source_corpus,
                "source_type": source_type,
                "classification": classification,
            }
        )
    if set(candidate_by_id) != {task["candidate_id"] for task in tasks}:
        raise ValueError("candidate and review task ids do not match")
    return tasks


def build_sanitized_confirmation_report(
    tasks: Iterable[dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    rows = list(tasks)
    return {
        "schema_version": "poc-03.confirmation-ux-prototype-result.v1",
        "generated_at": generated_at,
        "status": "PASS_FOR_UX_REVIEW" if rows else "FAIL",
        "summary": {
            "task_count": len(rows),
            "risk_counts": dict(sorted(Counter(row["risk_level"] for row in rows).items())),
            "current_status_counts": dict(
                sorted(Counter(row["current_status"] for row in rows).items())
            ),
            "original_review_status_counts": dict(
                sorted(Counter(row["original_review_status"] for row in rows).items())
            ),
            "evidence_link_count": sum(bool(row["evidence_link"]) for row in rows),
            "source_type_unresolved_count": sum(not row["source_type"] for row in rows),
        },
        "privacy": {
            "external_ai_service_called": False,
            "customer_content_uploaded": False,
            "customer_content_committed": False,
            "reviewer_names_committed": False,
            "navigator_committed": False,
            "workbook_committed": False,
        },
        "scope": "POC-03 confirmation UX prototype, not formal handover ActionItem output",
        "conclusion": (
            "The local confirmation prototype is ready for UX review; source evidence and human decisions remain local."
        ),
    }


def build_evidence_navigator_html(entries: Iterable[dict[str, Any]]) -> str:
    cards: list[str] = []
    for entry in entries:
        candidate_id = html.escape(_text(entry.get("candidate_id")))
        title = html.escape(_text(entry.get("query")) or "待确认事项")
        source_name = html.escape(_text(entry.get("source_name")) or "未解析文件名")
        document_id = html.escape(_text(entry.get("document_id")))
        content = html.escape(_text(entry.get("content")))
        locators = [html.escape(_text(value)) for value in entry.get("locators") or []]
        locator_html = "".join(f"<li><code>{value}</code></li>" for value in locators)
        original_url = _text(entry.get("original_url"))
        open_button = (
            f'<a class="button secondary" href="{html.escape(original_url, quote=True)}">打开原文件</a>'
            if original_url
            else '<span class="button disabled">原文件路径未解析</span>'
        )
        cards.append(
            f"""
            <article class="card" id="{candidate_id}" data-search="{html.escape((candidate_id + ' ' + title + ' ' + source_name).lower(), quote=True)}">
              <div class="card-head">
                <div><span class="badge">{candidate_id}</span><h2>{title}</h2></div>
                <div class="actions">{open_button}</div>
              </div>
              <dl><dt>来源文件</dt><dd>{source_name}</dd><dt>文档编号</dt><dd>{document_id}</dd></dl>
              <details open><summary>定位信息</summary><ul>{locator_html}</ul></details>
              <details open><summary>证据上下文</summary><pre>{content}</pre></details>
            </article>
            """
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>POC-03 本地证据定位器</title>
  <style>
    :root {{ color-scheme: light; --navy:#1f4e78; --blue:#2f75b5; --line:#d7e0e8; --bg:#f4f7fa; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font:14px/1.55 "Microsoft YaHei", Arial, sans-serif; color:#1f2937; background:var(--bg); }}
    header {{ position:sticky; top:0; z-index:2; padding:18px 24px; color:#fff; background:var(--navy); box-shadow:0 2px 10px #0002; }}
    header h1 {{ margin:0 0 8px; font-size:22px; }}
    header p {{ margin:0 0 12px; color:#dbeafe; }}
    input {{ width:min(720px,100%); padding:10px 12px; border:0; border-radius:6px; font-size:14px; }}
    main {{ max-width:1180px; margin:24px auto; padding:0 18px 80px; }}
    .card {{ scroll-margin-top:150px; margin:0 0 18px; padding:20px; background:#fff; border:1px solid var(--line); border-radius:10px; box-shadow:0 3px 12px #1f4e7810; }}
    .card:target {{ border:2px solid #f59e0b; box-shadow:0 0 0 4px #fef3c7; }}
    .card-head {{ display:flex; gap:18px; justify-content:space-between; align-items:flex-start; }}
    h2 {{ margin:8px 0 12px; font-size:18px; }}
    .badge {{ display:inline-block; padding:2px 8px; border-radius:999px; color:#fff; background:var(--blue); font-size:12px; }}
    .button {{ display:inline-block; padding:8px 12px; border-radius:6px; color:#fff; background:var(--blue); text-decoration:none; white-space:nowrap; }}
    .button.secondary {{ background:#475569; }} .button.disabled {{ background:#94a3b8; }}
    dl {{ display:grid; grid-template-columns:90px 1fr; gap:4px 12px; }} dt {{ font-weight:700; }} dd {{ margin:0; }}
    details {{ margin-top:12px; }} summary {{ cursor:pointer; color:var(--navy); font-weight:700; }}
    code {{ word-break:break-all; }} pre {{ white-space:pre-wrap; word-break:break-word; padding:14px; background:#f8fafc; border-left:4px solid #93c5fd; }}
    .hidden {{ display:none; }}
  </style>
</head>
<body>
  <header><h1>本地证据定位器</h1><p>仅用于 PoC 人工确认。点击 Excel 中的“打开证据”可直接跳到对应位置；内容不得上传外部服务。</p><input id="search" placeholder="搜索候选编号、问题或来源文件"></header>
  <main>{''.join(cards)}</main>
  <script>
    const input = document.getElementById('search');
    input.addEventListener('input', () => {{
      const query = input.value.trim().toLowerCase();
      document.querySelectorAll('.card').forEach(card => card.classList.toggle('hidden', query && !card.dataset.search.includes(query)));
    }});
  </script>
</body>
</html>
"""
