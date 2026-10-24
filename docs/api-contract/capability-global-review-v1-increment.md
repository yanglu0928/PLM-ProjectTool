# Capability GLOBAL Review V1 增量合同草案

日期：2026-10-24；状态：`CR-CAP-005 APPROVED_FOR_IMPLEMENTATION / OPT_IN_HTTP_CONTRACT_PASS / WINDOWS_NOT_MOUNTED`。原 Gate 2 API-02/API-04 冻结提交 `64cdf09` 保持不变。

|Operation|方法与路径|受权|成功|边界|
|---|---|---|---|---|
|`GLOBAL_REVIEW_GET`|GET `/api/v1/global/reviews/{review_id}`|当前 DeploymentAdmin 或本轮已分配且启用 Reviewer + License + 精确 `CAP-01` GLOBAL Scope|200 固定首轮/决定投影、强 ETag、Trace/no-store|只暴露元数据，不读文档正文；未知 Subject 404|
|`GLOBAL_REVIEW_DECIDE`|POST `/api/v1/global/reviews/{review_id}/rounds/{round_id}:decide`|当前已分配且启用 Reviewer + License + Origin/CSRF|200 决定与汇总状态、强 ETag、Trace/no-store|精确 `{decision,comment}`、幂等号；`RETURN` 必须有实质意见；同事务消费 Capability 终态|

GET `data` 精确含 `review_id/subject_type/baseline_id/baseline_version_id/policy_ref/review_round_id/round_no/reviewer_ids/decisions/state/review_etag/round_etag/submitted_by/submitted_at`；每条决定含 `decision_id/reviewer_id/decision/comment/decided_at`。DECIDE `data` 精确含 `review_id/review_round_id/baseline_version_id/actor_id/decision/decision_id/state/review_etag/round_etag/occurred_at/event_id`。两端响应均为 `Cache-Control: no-store`、强 Review ETag 与 Trace；GET 不接收 query，POST 精确 `{decision,comment}`、16～128 可打印 ASCII 幂等号、可信 Origin/CSRF 和 UTF-8 JSON。当前 Router 只有显式注入才可用，默认应用仍 404；Windows 运行组合未装配。不得把项目 Review 路径重命名或把合成提交当真实批准。
