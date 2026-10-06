# WFL-01-A07-P07-A10 Windows browser validation

This owned harness reuses the Handover qualification fixture to create an
isolated PostgreSQL 18 database with synthetic project, review, Action,
DocumentVersion and eligible Evidence facts. It activates the Handover workflow,
installs a disposable synthetic ProjectManager credential, then serves the built
Vue application through the production Windows `platform-write` FastAPI
composition and same-origin preview proxy.

Use real Microsoft Edge to log in, open the synthetic project workflow, request
the server-owned qualification for `HANDOVER_ISSUES`, explicitly confirm PASS,
and refresh the workflow. Send `VERIFY` on stdin only after Edge shows the first
receipt and the independent refresh shows `HANDOVER_ISSUES · PASS` at `"v2"`.

The harness then verifies exactly one Checklist record, the exact fixed
qualification references, one `WORKFLOW_CHECKLIST_RECORDED` Audit event and one
completed `V1_WORKFLOW_CHECKLIST_RECORD` idempotency receipt. It removes the
database credential and temporary files. All content and credentials are
synthetic; no provider or Internet call occurs.

If the managed Windows browser kernel cannot initialize, use
`run-edge-browser.mjs`. It launches the installed Microsoft Edge binary with a
disposable profile, captures the same qualification/receipt/current-state
observations and removes the profile. This is a browser-control fallback, not a
substitute browser engine.
