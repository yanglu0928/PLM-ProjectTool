# Handover Action source location API increment

- Status: optional V1 read-only increment under CR-HND-009; not a breaking change to the frozen HND Action GET contract.
- Operation: `GET /api/v1/projects/{project_id}/handover-action-items/{action_item_id}/source-location`
- Request: canonical Project ID and Action item ID in path; no caller-supplied Analysis/Version/Item target.
- Authorization: same Session, License and current Project membership read gate as HND_ACTION_GET. The repository query is constrained by Project and resolves only the immutable Analysis version/item reference belonging to the Action.
- Analysis-backed response: `project_id`, `handover_analysis_id`, `handover_analysis_version_id`, and `analysis_item_id`; the client may construct only the first-party fixed-version detail route.
- HUMAN-backed source: controlled `UNAVAILABLE` result with `MANUAL_SOURCE_NOT_FIXED`; no fabricated location.
- Not found, cross-project, revoked access, invalid/mismatched immutable references: fail closed using existing hidden/not-found and authorization error mapping. The endpoint is no-store.
- The operation returns no issue正文, file path, Evidence Locator, download URL or arbitrary redirect URL. The destination page separately reloads and authorizes Project/Analysis/Version/Item; Evidence Viewer still performs its own authorization.
- Persistence: none. No schema/migration change. Existing HND Action GET remains unchanged.
- Validation: run 41391544470 passed backend 3,850 tests, frontend 2,075 tests (200 files), frontend typecheck/build and all 12 workflow jobs. This is not a dedicated hosted Edge test of this operation; A50-E01 is pending.
