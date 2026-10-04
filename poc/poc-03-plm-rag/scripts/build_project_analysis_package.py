from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote


SOURCE_PRIORITY = {
    "ACTUAL_SURVEY": 100,
    "CONTRACT": 90,
    "TECHNICAL_AGREEMENT": 85,
    "RISK_ASSESSMENT": 75,
    "SOLUTION": 60,
    "STANDARD_CAPABILITY": 50,
    "SURVEY_TEMPLATE": 10,
}

SOURCE_LABELS = {
    "ACTUAL_SURVEY": "实际调研记录",
    "CONTRACT": "合同",
    "TECHNICAL_AGREEMENT": "技术协议",
    "RISK_ASSESSMENT": "项目风险评估",
    "SOLUTION": "既有方案",
    "STANDARD_CAPABILITY": "标准能力库",
    "SURVEY_TEMPLATE": "调研业务表单（仅参考）",
}


@dataclass(frozen=True)
class SourceDocument:
    source_type: str
    file_name: str
    original_path: Path | None
    parsed_path: Path
    blocks: list[dict[str, Any]]
    warnings: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a local, project-oriented PLM function/gap analysis package"
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized_name(value: str) -> str:
    return re.sub(r"\.(docx|doc|pdf|pptx)$", "", value.strip(), flags=re.I)


def compact_text(value: str, limit: int = 520) -> str:
    value = re.sub(r"\s+", " ", value or "").strip(" |")
    parts = [part.strip() for part in value.split(" | ") if part.strip()]
    deduped: list[str] = []
    for part in parts:
        if not deduped or part != deduped[-1]:
            deduped.append(part)
    value = " | ".join(deduped)
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def file_url(path: Path | None, page: int | None = None) -> str:
    if path is None:
        return ""
    posix = path.resolve().as_posix()
    url = "file:///" + quote(posix, safe="/:()[]-_.~")
    if page:
        url += f"#page={page}"
    return url


def source_page(locator: str) -> int | None:
    match = re.search(r"(?:pages?|slides)/(\d+)", locator or "")
    return int(match.group(1)) if match else None


def original_for(workspace: Path, file_name: str) -> Path | None:
    roots = [
        workspace / "方案库",
        workspace / "标准能力库",
        workspace / "技术协议&合同",
        workspace / "artifacts/poc-03/holdout/source-drop",
    ]
    direct_candidates = [file_name]
    if file_name.lower().endswith(".docx"):
        direct_candidates.append(file_name[:-1])
    for root in roots:
        for candidate in direct_candidates:
            path = root / candidate
            if path.is_file():
                return path
    target = normalized_name(file_name)
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.iterdir():
            if path.is_file() and normalized_name(path.name) == target:
                return path
    return None


def load_parsed_dir(
    workspace: Path, parsed_dir: Path, source_type: str
) -> list[SourceDocument]:
    result: list[SourceDocument] = []
    if not parsed_dir.is_dir():
        return result
    for path in sorted(parsed_dir.glob("*.parsed.json")):
        payload = load_json(path)
        file_name = payload.get("source", {}).get("file_name") or path.name
        effective_type = source_type
        if source_type == "CONVERTED":
            if "风险评估" in file_name:
                effective_type = "RISK_ASSESSMENT"
            elif "合同" in file_name:
                effective_type = "CONTRACT"
            else:
                effective_type = "SOLUTION"
        result.append(
            SourceDocument(
                source_type=effective_type,
                file_name=file_name,
                original_path=original_for(workspace, file_name),
                parsed_path=path,
                blocks=payload.get("blocks") or [],
                warnings=payload.get("warnings") or [],
            )
        )
    return result


def load_documents(workspace: Path) -> list[SourceDocument]:
    specs = [
        (
            workspace / "artifacts/poc-05/solution-library/2026-09-17-r3",
            "SOLUTION",
        ),
        (
            workspace
            / "artifacts/poc-03/source-corpora/partitioned/2026-09-18-r1/STANDARD_CAPABILITY",
            "STANDARD_CAPABILITY",
        ),
        (
            workspace
            / "artifacts/poc-03/source-corpora/partitioned/2026-09-18-r1/SURVEY",
            "SURVEY_TEMPLATE",
        ),
        (
            workspace
            / "artifacts/poc-03/source-corpora/partitioned/2026-09-18-r1/CONTRACT",
            "CONTRACT",
        ),
        (
            workspace
            / "artifacts/poc-03/source-corpora/partitioned/2026-09-18-r1/TECHNICAL_AGREEMENT",
            "TECHNICAL_AGREEMENT",
        ),
        (
            workspace / "artifacts/poc-03/holdout/2026-09-20-r2/parsed/SURVEY",
            "ACTUAL_SURVEY",
        ),
        (
            workspace / "artifacts/project-analysis/source-converted/2026-09-21-r1/parsed",
            "CONVERTED",
        ),
    ]
    documents: list[SourceDocument] = []
    for path, source_type in specs:
        documents.extend(load_parsed_dir(workspace, path, source_type))
    unique: dict[tuple[str, str], SourceDocument] = {}
    for document in documents:
        key = (document.source_type, normalized_name(document.file_name))
        unique[key] = document
    return list(unique.values())


def belongs_to(document: SourceDocument, aliases: Iterable[str]) -> bool:
    name = document.file_name.lower()
    return any(alias.lower() in name for alias in aliases)


def block_score(block: dict[str, Any], terms: list[str], priority: int) -> int:
    text = (block.get("text") or "").lower()
    matched = sum(1 for term in terms if term.lower() in text)
    if not matched:
        return -1
    exact_bonus = 8 if all(term.lower() in text for term in terms) else 0
    length_penalty = min(len(text) // 500, 10)
    return priority + matched * 14 + exact_bonus - length_penalty


def find_evidence(
    documents: list[SourceDocument],
    terms: list[str],
    aliases: list[str] | None = None,
    source_types: set[str] | None = None,
) -> dict[str, Any] | None:
    if not terms:
        return None
    best: tuple[int, SourceDocument, dict[str, Any]] | None = None
    for document in documents:
        if source_types and document.source_type not in source_types:
            continue
        if aliases is not None and not belongs_to(document, aliases):
            continue
        for block in document.blocks:
            score = block_score(
                block, terms, SOURCE_PRIORITY.get(document.source_type, 0)
            )
            if score < 0:
                continue
            if best is None or score > best[0]:
                best = (score, document, block)
    if best is None:
        return None
    _, document, block = best
    locator = block.get("source_locator") or "未提供定位"
    return {
        "source_type": document.source_type,
        "source_type_display": SOURCE_LABELS.get(
            document.source_type, document.source_type
        ),
        "source_name": document.file_name,
        "source_locator": locator,
        "excerpt": compact_text(block.get("text") or ""),
        "original_url": file_url(document.original_path, source_page(locator)),
        "parsed_path": str(document.parsed_path),
    }


def evidence_location(evidence: dict[str, Any] | None) -> str:
    if evidence is None:
        return "未定位到直接证据"
    return f"{evidence['source_type_display']}｜{evidence['source_name']}｜{evidence['source_locator']}"


def render_evidence_html(package: dict[str, Any], output_path: Path) -> None:
    cards: list[str] = []
    for item in package["items"]:
        evidence_parts: list[str] = []
        for label, evidence in [
            ("项目侧证据", item.get("project_evidence")),
            ("标准能力对照", item.get("standard_evidence")),
        ]:
            if evidence:
                open_link = (
                    f'<a class="open" href="{html.escape(evidence["original_url"], quote=True)}">打开原文</a>'
                    if evidence.get("original_url")
                    else '<span class="muted">原文路径未定位</span>'
                )
                evidence_parts.append(
                    f"<section><h3>{html.escape(label)}</h3>"
                    f"<p class=\"meta\">{html.escape(evidence_location(evidence))}</p>"
                    f"<blockquote>{html.escape(evidence['excerpt'])}</blockquote>{open_link}</section>"
                )
        if not evidence_parts:
            evidence_parts.append(
                '<section><h3>证据缺口</h3><p>现有可解析资料中未定位到能直接支持该判断的段落，因此本条只能作为待确认建议。</p></section>'
            )
        cards.append(
            f'<article id="{html.escape(item["item_id"])}">'
            f'<div class="case-head"><div><span>{html.escape(item["item_id"])}</span>'
            f'<h2>{html.escape(item["project_name"])} · {html.escape(item["title"])}</h2></div>'
            f'<b class="tag {item["category_code"]}">{html.escape(item["category"])}</b></div>'
            f'<p class="summary">{html.escape(item["basis"])}</p>'
            f'{"".join(evidence_parts)}</article>'
        )
    output_path.write_text(
        """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>项目功能差异证据定位</title>
<style>
:root{--navy:#17365d;--blue:#1f4e78;--bg:#f4f7fb;--line:#d9e2f3;--amber:#fff2cc;--text:#1f2937}*{box-sizing:border-box}body{margin:0;background:var(--bg);font-family:"Microsoft YaHei",Arial,sans-serif;color:var(--text)}main{max-width:1180px;margin:auto;padding:28px}.hero{background:linear-gradient(135deg,var(--navy),var(--blue));color:white;padding:28px;border-radius:14px}.hero h1{margin:0 0 8px}.notice{margin:18px 0;padding:14px 16px;background:var(--amber);border-left:5px solid #d6a600;border-radius:8px}article{background:white;margin:18px 0;padding:22px;border-radius:12px;box-shadow:0 3px 16px #17365d18}.case-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}.case-head span{font-size:12px;color:#607085}.case-head h2{margin:5px 0 0;font-size:20px}.tag{padding:6px 10px;border-radius:999px;white-space:nowrap}.standard{background:#e2f0d9;color:#375623}.nonstandard{background:#fce4d6;color:#9c0006}.gap{background:#ddebf7;color:#1f4e78}.pending{background:#fff2cc;color:#7f6000}.summary{font-weight:600}section{border-top:1px solid var(--line);padding-top:12px;margin-top:14px}h3{font-size:15px;margin:0 0 7px}.meta,.muted{color:#607085;font-size:13px}blockquote{margin:10px 0;padding:12px 14px;border-left:4px solid #9dc3e6;background:#f8fbff;white-space:pre-wrap}.open{display:inline-block;background:#1f4e78;color:white;text-decoration:none;padding:8px 14px;border-radius:7px}
</style></head><body><main><div class="hero"><h1>项目级标准/非标/差异证据定位</h1><p>工作簿只保留短结论；点击“打开证据”回到这里，再打开本地原文。</p></div><div class="notice">所有结论均为 AI 初步建议，必须经人工确认后才能转为正式业务事实。实际调研记录优先于业务表单；业务表单仅用于补全提问。</div>"""
        + "".join(cards)
        + "</main></body></html>",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    workspace = args.workspace.resolve()
    config = load_json(args.config.resolve())
    documents = load_documents(workspace)
    standard_types = {"STANDARD_CAPABILITY"}
    items: list[dict[str, Any]] = []
    projects: list[dict[str, Any]] = []
    survey_rows: list[dict[str, Any]] = []
    category_codes = {
        "标准功能": "standard",
        "非标功能": "nonstandard",
        "差异项": "gap",
        "待确认项": "pending",
    }

    for project in config["projects"]:
        aliases = project["aliases"]
        project_documents = [doc for doc in documents if belongs_to(doc, aliases)]
        source_counts: dict[str, int] = {}
        for document in project_documents:
            source_counts[document.source_type] = source_counts.get(document.source_type, 0) + 1
        category_counts = {key: 0 for key in category_codes}
        for index, raw_row in enumerate(project["items"], start=1):
            if isinstance(raw_row, list):
                (
                    category,
                    domain,
                    title,
                    basis,
                    action,
                    project_terms,
                    standard_terms,
                ) = raw_row
                row = {
                    "category": category,
                    "domain": domain,
                    "title": title,
                    "basis": basis,
                    "action": action,
                    "project_terms": project_terms,
                    "standard_terms": standard_terms,
                }
            else:
                row = raw_row
            category = row["category"]
            category_counts[category] += 1
            item_id = f"{project['project_id']}-{index:02d}"
            project_evidence = find_evidence(
                documents,
                row.get("project_terms") or [],
                aliases=aliases,
                source_types={
                    "ACTUAL_SURVEY",
                    "CONTRACT",
                    "TECHNICAL_AGREEMENT",
                    "RISK_ASSESSMENT",
                    "SOLUTION",
                },
            )
            standard_evidence = find_evidence(
                documents,
                row.get("standard_terms") or [],
                source_types=standard_types,
            )
            evidence_count = int(project_evidence is not None) + int(
                standard_evidence is not None
            )
            confidence = (
                "较高"
                if evidence_count == 2 and category != "待确认项"
                else "中"
                if evidence_count >= 1
                else "低"
            )
            items.append(
                {
                    "item_id": item_id,
                    "project_id": project["project_id"],
                    "project_name": project["name"],
                    "category": category,
                    "category_code": category_codes[category],
                    "domain": row["domain"],
                    "title": row["title"],
                    "basis": row["basis"],
                    "action": row["action"],
                    "confidence": confidence,
                    "project_evidence": project_evidence,
                    "standard_evidence": standard_evidence,
                    "evidence_location": evidence_location(project_evidence),
                    "standard_location": evidence_location(standard_evidence),
                    "evidence_link": f"evidence-navigator.html#{item_id}",
                    "review_decision": "待确认",
                }
            )
        projects.append(
            {
                "project_id": project["project_id"],
                "project_name": project["name"],
                "summary": project["summary"],
                "source_counts": source_counts,
                "category_counts": category_counts,
                "source_count": len(project_documents),
                "has_actual_survey": source_counts.get("ACTUAL_SURVEY", 0) > 0,
                "has_contract_or_tech": (
                    source_counts.get("CONTRACT", 0)
                    + source_counts.get("TECHNICAL_AGREEMENT", 0)
                    > 0
                ),
            }
        )
        for order, raw_topic in enumerate(project["survey_outline"], start=1):
            if isinstance(raw_topic, list):
                topic = dict(
                    zip(
                        ("topic", "questions", "participants", "expected_output", "why"),
                        raw_topic,
                        strict=True,
                    )
                )
            else:
                topic = raw_topic
            survey_rows.append(
                {
                    "outline_id": f"{project['project_id']}-Q{order:02d}",
                    "project_id": project["project_id"],
                    "project_name": project["name"],
                    "order": order,
                    "topic": topic["topic"],
                    "questions": topic["questions"],
                    "participants": topic["participants"],
                    "expected_output": topic["expected_output"],
                    "why": topic["why"],
                }
            )

    assigned = {
        normalized_name(doc.file_name)
        for project in config["projects"]
        for doc in documents
        if belongs_to(doc, project["aliases"])
    }
    coverage: list[dict[str, Any]] = []
    for document in sorted(documents, key=lambda doc: (doc.source_type, doc.file_name)):
        project_names = [
            project["name"]
            for project in config["projects"]
            if belongs_to(document, project["aliases"])
        ]
        coverage.append(
            {
                "source_type": SOURCE_LABELS.get(document.source_type, document.source_type),
                "project_name": "、".join(project_names) if project_names else "未归属/通用资料",
                "source_name": document.file_name,
                "parse_status": "已解析",
                "warning_count": len(document.warnings),
                "original_url": file_url(document.original_path),
                "is_assigned": normalized_name(document.file_name) in assigned,
            }
        )

    package = {
        "schema_version": "1.0",
        "package_id": config["package_id"],
        "version": config["version"],
        "generated_at": config["generated_at"],
        "status": "AWAITING_HUMAN_CONFIRMATION",
        "evidence_policy": [
            "实际调研记录优先",
            "合同/技术协议用于约束范围",
            "标准能力库用于能力对照",
            "既有方案用于补充，不覆盖真实调研",
            "调研业务表单仅作提问参考",
        ],
        "projects": projects,
        "items": items,
        "survey_outline": survey_rows,
        "coverage": coverage,
        "unassigned_source_count": sum(1 for row in coverage if not row["is_assigned"]),
        "fingerprint": "",
    }
    digest_payload = json.dumps(package, ensure_ascii=False, sort_keys=True).encode("utf-8")
    package["fingerprint"] = hashlib.sha256(digest_payload).hexdigest()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    package_path = args.output_dir / "project-analysis-package.json"
    package_path.write_text(
        json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    render_evidence_html(package, args.output_dir / "evidence-navigator.html")
    print(
        json.dumps(
            {
                "status": package["status"],
                "project_count": len(projects),
                "item_count": len(items),
                "survey_outline_count": len(survey_rows),
                "coverage_count": len(coverage),
                "unassigned_source_count": package["unassigned_source_count"],
                "output": str(package_path),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
