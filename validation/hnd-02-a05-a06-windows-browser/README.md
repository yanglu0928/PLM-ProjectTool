# HND-02-A05-A06 Windows browser validation

This owned harness creates an isolated PostgreSQL 18 database, synthetic
ProjectManager login, one fixed response DocumentVersion and two eligible
Evidence records. It serves the built Vue app through a same-origin preview and
mounts the production Windows platform-write composition.

Use a real Windows browser to create, patch, start, submit and verify one Action,
then create and cancel a second Action. The VERIFIED view must show CLOSE as
disabled with CR-HND-008. Send `VERIFY` on stdin only after the browser facts are
visible. The harness checks database state/Audit counts and removes the database,
temporary credential and files. All content and credentials are synthetic; no
provider or Internet call occurs.
