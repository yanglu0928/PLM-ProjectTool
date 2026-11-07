# OUT-01-A01-P24 Edge UI contract validation

This hosted Windows Server 2025 harness opens the same-run frontend production build in headless Microsoft Edge. It logs in using a synthetic session, serves only local synthetic API responses, and validates the current approved RequirementVersion DOCX request action.

Checks cover the fixed request payload, CSRF and idempotency headers, accepted-request wording, output-history navigation, a simulated generic service-unavailable response representing absent publisher trust, no automatic retry, and hiding the action when the selected version is not approved.

The harness requires GitHub-hosted RUNNER_TEMP on D: and places its browser profile and evidence there. It does not call external APIs, access customer data, execute plugins, or generate a DOCX. Success is browser-contract evidence only; it does not verify the real backend publisher trust path, Windows 11 hardware, Pilot, Gate 3, or Release.

Run only from cloud-sandbox-validation.yml on a GitHub hosted Windows runner. Do not run locally.
