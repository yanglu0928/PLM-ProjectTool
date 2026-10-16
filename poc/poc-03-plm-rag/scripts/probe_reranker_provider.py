from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
POC_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(POC_DIR / "src"))

from poc03_rag.reranker import (  # noqa: E402
    RerankCandidate,
    RerankerConfig,
    rerank_with_fallback,
)


CANDIDATES = (
    RerankCandidate("R-01", "工程变更申请应完成影响分析并经过授权人员审批。"),
    RerankCandidate("R-02", "产品结构中的物料编码需要遵守统一编码规则。"),
    RerankCandidate("R-03", "工程变更审批完成后，应保留审批记录和版本追溯信息。"),
    RerankCandidate("R-04", "项目周会应提前准备会议室和参会名单。"),
    RerankCandidate("R-05", "文档发布前需要检查版本状态和访问权限。"),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe an external configurable reranker.")
    parser.add_argument("--provider", default="aliyun-bailian")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", default="qwen3-rerank")
    parser.add_argument("--api-key-env", default="DASHSCOPE_API_KEY")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    api_key = os.environ.get(args.api_key_env, "")
    config = RerankerConfig(
        provider=args.provider,
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=args.timeout,
        fail_open=True,
    )
    live = rerank_with_fallback(
        config=config,
        api_key=api_key,
        query="工程变更如何完成审批并保留追溯记录？",
        candidates=CANDIDATES,
        top_n=3,
    )
    simulated_429 = rerank_with_fallback(
        config=config,
        api_key=api_key or "simulation-key",
        query="fixed simulation query",
        candidates=CANDIDATES,
        top_n=3,
        transport=lambda *_: (429, b""),
    )

    def timeout_transport(*_):
        raise TimeoutError("simulated timeout")

    simulated_timeout = rerank_with_fallback(
        config=config,
        api_key=api_key or "simulation-key",
        query="fixed simulation query",
        candidates=CANDIDATES,
        top_n=3,
        transport=timeout_transport,
    )
    simulated_invalid = rerank_with_fallback(
        config=config,
        api_key=api_key or "simulation-key",
        query="fixed simulation query",
        candidates=CANDIDATES,
        top_n=3,
        transport=lambda *_: (200, b'{"results":[]}'),
    )
    scenarios = {
        "live_success": live.to_sanitized_dict(),
        "simulated_http_429": simulated_429.to_sanitized_dict(),
        "simulated_timeout": simulated_timeout.to_sanitized_dict(),
        "simulated_invalid_response": simulated_invalid.to_sanitized_dict(),
    }
    expected_live_ids = {"R-01", "R-03"}
    live_ids = {item.candidate_id for item in live.items}
    status = (
        "PASS"
        if live.provider_used
        and not live.degraded
        and bool(expected_live_ids.intersection(live_ids))
        and simulated_429.error_code == "HTTP_429"
        and simulated_timeout.error_code == "NETWORK_ERROR"
        and simulated_invalid.error_code == "INVALID_RESPONSE"
        else "FAIL"
    )
    report = {
        "schema_version": "poc-03.reranker-probe-result.v1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "status": status,
        "configuration": {
            "provider": config.provider,
            "model": config.model,
            "timeout_seconds": config.timeout_seconds,
            "fail_open": config.fail_open,
            "candidate_count": len(CANDIDATES),
            "top_n": 3,
        },
        "scenarios": scenarios,
        "privacy": {
            "customer_content_used": False,
            "api_key_committed": False,
            "query_text_committed": False,
            "document_text_committed": False,
            "provider_response_body_committed": False,
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
