# WFL-02-A02-A03 authorized Transition validation

Runs the authorized Stage Transition service against the disposable Windows 11
PostgreSQL 18 Handover qualification fixture. It uses the real current-fact
Handover Owner, project authorization, Session/CSRF source, License guard,
Checklist append/read repositories, Transition repository, Audit service and
persistent idempotency receipts.

The verifier records both current Handover Checklist PASS facts, proves Audit
failure rolls the whole attempted transition back, and then proves one atomic
`HANDOVER -> SURVEY` command plus exact replay. It does not mount an
HTTP route, Windows production composition or UI; those remain separate WBS
items.
