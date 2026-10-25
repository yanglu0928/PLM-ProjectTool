"""Windows 11/PG18 proof using the formal Bootstrap Egress policy source."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from plm_assistant.entrypoints.ai_egress_policy import create_deployment_ai_egress_policies
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings


ROOT = Path(__file__).resolve().parents[2]
P08 = ROOT / "validation" / "ai-04-a04-p08-egress-http-windows" / "verify.py"


def main() -> None:
    if sys.platform != "win32":
        raise RuntimeError("Windows validation required")
    settings = BootstrapSettings(
        data_root=ROOT / "artifacts",
        ai_egress_policies=({
            "reference": "minimum.document.text.v1",
            "operation_types": ["AI_TASK"],
            "data_categories": ["TECHNICAL_DOCUMENT"],
            "ttl_minutes": 30,
            "max_record_count": 10,
            "max_payload_bytes": 131_072,
            "max_input_tokens": 8_192,
            "max_retry_attempts": 3,
            "risk_codes": ["EXTERNAL_PROVIDER", "CUSTOMER_DATA"],
            "approval_roles": ["PROJECT_MANAGER", "CUSTOMER_MANAGER"],
            "data_regions": ["cn-beijing"],
        },),
    )
    previews, approvals = create_deployment_ai_egress_policies(settings)
    spec = importlib.util.spec_from_file_location("ai04a04p08_proof", P08)
    if spec is None or spec.loader is None:
        raise RuntimeError("P08 validation unavailable")
    proof = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proof)
    # Reuse the already-reviewed real PG/HTTP proof while replacing both test
    # policy constructors with the formal immutable Bootstrap-derived pair.
    proof.EgressPreviewPolicyRegistry = lambda _: previews
    proof.ApprovalPolicy = lambda: approvals
    proof.main()
    print(
        "AI_04_A04_P09_EGRESS_DEPLOYMENT_POLICY_PASS: Windows 11/PG18 real "
        "Egress chain used Bootstrap policy; no Provider connection or external call"
    )


if __name__ == "__main__":
    main()
