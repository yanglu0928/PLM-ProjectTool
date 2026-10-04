# RAG-04-A06-P08 Windows browser validation

This owned harness creates an isolated PostgreSQL 18 database, synthetic active
PROJECT index and login, serves the built Vue application through a same-origin
Vite preview proxy, and mounts the production FastAPI Retrieval composition.

Run `serve.py` with the backend development interpreter. After the ready line,
use a real browser to create one retrieval. Send `WORK` on stdin, refresh until
Result and Context are shown, create a second retrieval and cancel it, then send
`VERIFY`. The harness requires exactly one successful and two cancelled runs,
one candidate/context set, and cleans the database, credential and temporary
data after exit. All content is synthetic and no provider network call occurs.
