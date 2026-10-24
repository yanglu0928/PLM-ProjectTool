# Review 读取 HTTP 增量合同 V1

日期：2026-10-19；WBS：`SOL-06-A15-P03`；来源：Gate 2 冻结 API-02 `REVIEW_GET`、DM-05、RVW-01-A04/A05 与 SOL-06-A15-P01/P02。本文只细化冻结的单个 Review GET，不新增 LIST、query 或主题正文读取。

## 边界与授权

- `GET /api/v1/projects/{project_id}/reviews/{review_id}` 仅在显式注入 Router 时存在；默认应用保持 404。
- 请求只接受 canonical UUID 路径、受信 Host 和单一当前 Cookie Session；禁止 query，GET 不要求 CSRF 或 Idempotency-Key。
- 服务在同一事务内依次检查有效 License、当前 Session、`REVIEW_GET` Project member、Review Project 身份、主题 Owner 当前身份；读取活动轮时再独立证明该轮固定主题版本仍属于同一 SOL-06 系列。
- SOL-06 Owner 重新确认调用者是当前 ACTIVE Project member，并分别以系列共享读锁和精确历史版本共享读锁证明访问；历史 Review/Decision 不能替代当前成员事实。
- 只读 Subject Registry 与写生命周期 Registry 分离。当前只注册 SOL-06；未知主题返回 404，不因其他 Subject 已有写 Owner 自动获得读能力。

## 严格成功投影

顶层响应精确为 `data/trace_id`，状态 200，`Cache-Control: no-store`，响应 `ETag` 与 `data.etag` 均为 Review 强版本。

`data` 精确包含：

- `review_id/project_id`；
- `subject_ref.resource_type/resource_id`，不复制主题正文或内部版本集合；
- `policy_code/state/etag`；
- `active_round`：非活动状态为 null；活动状态包含 `review_round_id/round_no/subject_version_ref/state/round_etag/started_by/started_at/assignments`；
- Assignment 精确包含 `assignment_id/reviewer_id/state/decision`；未决定为 null，已决定包含 `decision_id/decision/comment/decided_at`。

不返回来源证据、内容指纹、快照/锁 ID、内部 SQL/Owner 名称或其他主题数据。终态历史轮和 Review 列表不在本增量中，不能由客户端 query 猜测或由精确 GET 冒充任务发现。

## 错误、兼容与组合前置

无 Session 为 401；不受信 Host、License 为 403；未知/无权 Project、Review、Subject 或固定版本为 404；非 canonical UUID 为 422；query 为 400；可信运行异常为 503。错误不泄露内部事实。

本增量不改冻结路径、角色、License 权益、Schema 或旧数据；应用工厂只增加可选 Router，未注入时行为不变。Windows 生产组合、真实 PostgreSQL/HTTP、前端 Reviewer 页面和 Edge 决定链由 P04～P06 独立验收；P03 通过不代表 Pilot、Gate 3、正式信任或 Release 通过。
