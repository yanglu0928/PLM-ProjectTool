# WFL-02-A02-A02 Stage Transition append validation

Runs the caller-transaction Stage Transition repository against a disposable
PostgreSQL 18 database on the existing local Windows PoC cluster at port 55434.
It creates only synthetic projects, records both Handover Checklist items with
the production append repository, re-observes Evidence, and then verifies the
atomic `HANDOVER -> SURVEY` history/state change.

The verifier covers rollback without caller commit, exact immutable result
readback, fixed Record/ref links, current Evidence re-observation, lock holding,
stale version rejection and two-writer convergence. It does not provide
Session/License/Project authorization, Handover Owner, Audit, idempotency or HTTP
evidence; those belong to the next WBS.
