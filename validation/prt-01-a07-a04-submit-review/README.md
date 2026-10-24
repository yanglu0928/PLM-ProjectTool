# PRT-01-A07-A04 validation

Run `verify.py` with the repository Windows Python runtime. It creates and removes an isolated PostgreSQL 18 database, completes the Prototype Review/Approval Trace prerequisites, injects current-input drift to prove zero-write rollback, then verifies atomic `PRT_VERSION_SUBMIT_REVIEW`, durable replay/conflict handling, ProjectManager authorization, License denial, Review/round/Prototype binding, Audit and receipt closure.
