# Capability Version 送审 HTTP V1 增量

日期：2026-10-05。实现基线：冻结 API-01/API-04、CR-CAP-003；不增加或改名 Operation。

## Operation

`CAP_VERSION_SUBMIT_REVIEW`：`POST /api/v1/global/capability-baselines/{baseline_id}/versions/{baseline_version_id}:submit-review`。Router 仅通过 `create_app(capability_review_router=...)` 显式注入，默认路径 404；Windows 生产组合留待 A05-A07。

请求必须精确包含 `reviewer_ids/policy_ref/due_at/submission_note`；`policy_ref` 固定 `DEPLOYMENT_ALL_V1`，1～32 个不重复 canonical lowercase non-zero UUID reviewer。根据 CR-CAP-003，当前 `due_at` 与 `submission_note` 必须为 null，非空返回 422，不丢数据。

请求要求可信 Origin/Host、当前 `plm_session`、`X-CSRF-Token`、16～128 字符可打印 ASCII `Idempotency-Key`、DeploymentAdmin 和有效 License。JSON 只接受 UTF-8 `application/json`，拒绝重复键、未知字段、NaN/Infinity、多余 query 和超过 2 MiB 正文。

## 成功与错误

201 返回 `review_id/review_round_id/subject_type/baseline_id/baseline_version_id/policy_ref/reviewer_ids/state/round_no/review_etag/submitted_by/submitted_at`，同时返回强 ETag 和 `Cache-Control: no-store`。首次提交与 Review/Subject/Audit/收据在同一 UOW；相同键恢复首次轮次并重验当前管理员和 Subject 权限。

权限/资源对未授权调用方统一 404；License 403；请求/业务资格 422；幂等或版本冲突 409；未知内部失败 503。新增公开错误 `BUSINESS_REVIEW_NOT_ELIGIBLE` 来自冻结 API-04 码表。

本增量无 Schema/Migration/依赖/网络/外发。停止注入 Router 可关闭新流量；已提交的合法 Review 历史不删除。
