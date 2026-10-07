# PRT-01-A07-A03-P03 validation

Run `verify.py` with the repository Windows Python runtime. It creates and removes an isolated PostgreSQL 18 database, runs the real PROJECT Review create/start/approve/replay/drift/withdraw chain, verifies the immutable Approval Trace manifests and exact business-version edges, and injects a Trace persistence failure to prove the terminal Review decision, formal pointer, receipt, audit, manifest and links all roll back together.
