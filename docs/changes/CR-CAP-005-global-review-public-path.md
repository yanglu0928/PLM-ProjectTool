# CR-CAP-005：为 Capability GLOBAL Review 增补受控读取与决定路径

- 日期：2026-10-24
- 状态：`APPROVED_FOR_IMPLEMENTATION / NOT_IMPLEMENTED`（依据用户 2026-09-24 持续授权；批准实施不等于验收通过）
- 关联：`CAP-02-A05-P04-P03`、`CR-EXEC-002`、Gate 2 冻结 API-02/API-04 提交 `64cdf09`、既有 `CR-CAP-003`
- 原冻结版本：PROJECT Review 六个 Operation 和 Capability `CAP_VERSION_SUBMIT_REVIEW` 固定不变；本 CR 不追写冻结提交。

## 事实、差异与影响

Capability Version 现可用冻结 `CAP_VERSION_SUBMIT_REVIEW` 由 DeploymentAdmin 建立 `CAP-01`、`GLOBAL` 的 `IN_REVIEW` 轮次；Review 持久化内核及 Capability Subject 终态消费已存在。冻结 API-02 公开 Review 列表、读取与决定均限定 `/api/v1/projects/{project_id}/reviews...`；仓库没有 `/api/v1/global/reviews...` 公开路由及对应会话/License/幂等服务。因此送审后的管理员无法从产品界面读取轮次并作正式决定，当前批准版本无法由该路径真实形成，阻断 HND-05-A02 和 Windows 11 Pilot 纵向链。不能把当前 VALIDATE、送审回执或合成 Review 当作批准。

## 方案与选择

- A（选定）：只新增显式 GLOBAL Review GET 和 DECIDE `/api/v1` 操作，按 GLOBAL Scope/DeploymentAdmin 与固定 Capability Subject 复用现有 Review 状态机；不改变 PROJECT 路径、现有请求字段或冻结错误语义。Capability 详情已有 `review_ref`，首版不需另造列表或新状态。
- B（未选）：把 GLOBAL Review 塞入 PROJECT 路径、伪造 ProjectId 或让前端直写 Capability 批准状态；会混淆项目隔离和 Review Owner，且绕过原子决定，禁止。
- C（未选）：只保留内部 Review 内核与送审入口；无法完成用户可操作的真实批准链，不满足 Pilot 目标。

## 新增合同和边界

1. `GLOBAL_REVIEW_GET`：`GET /api/v1/global/reviews/{review_id}`；当前有效会话、License 和 DeploymentAdmin 可读取已绑定 `CAP-01` 的 GLOBAL 固定 Review/首轮投影，返回 `review_id/subject_type/baseline_id/baseline_version_id/policy_ref/review_round_id/reviewer_ids/decisions/state/review_etag/round_etag`。响应 `no-store`、强 ETag、Trace；不返回源文档正文、AI 建议或 License/Secret。
2. `GLOBAL_REVIEW_DECIDE`：`POST /api/v1/global/reviews/{review_id}/rounds/{round_id}:decide`；当前有效 Session、可信 Origin/CSRF、License、受分配且仍有资格的 DeploymentAdmin 才可对 `IN_REVIEW` 轮次提交精确 `{decision,comment}`（`APPROVE` 或有实质意见的 `RETURN`），16～128 可打印 ASCII 幂等号；响应决定/汇总状态和强 ETag。Review、Capability 状态/批准指针、Audit、收据在同一事务；同 Key 回放复核访问，不自动重试不明结果。不能由提交者身份推定 Reviewer 资格。
3. 未授权或错 Scope/未知 Subject 统一 404；License 403；坏请求/缺意见 422；幂等/状态冲突 409；未知 503。不得把 API 返回 `APPROVED` 等同客户确认、Gate 或正式发行。
4. 先按 Capability 单一 GLOBAL Subject 显式注册；不得把其他 GLOBAL Subject 静默纳入。`/api/v1/projects` 保持原行为，PROJECT 数据隔离不变；首版无需 Schema、迁移、外部网络、客户数据或新增依赖。

## 风险、兼容、迁移与回滚

- 风险：未授权历史可见、错轮/重放重复决定、来源/资格撤销后错误批准、Review 与 Capability 指针不一致、把单管理员自审误称“独立客户确认”。因此读/决定都重验当前身份和精确 GLOBAL Scope；决定仍交给 Subject Owner 现时来源重证；UI 仅称部署管理员正式评审，不称客户签署。
- 兼容：仅新增路径，冻结 API-02 PROJECT Operation 和现有 Capability Version/送审响应均不变；旧客户端不受影响。新前端需与显式装配后端同版本部署，未装配时新路径 404 并保持旧行为。
- 迁移：不改 Schema/ORM，不回填旧 Review、不改写已有批准/退回历史。现有 `GLOBAL` Review 行仅在当前服务重证后可读/决定；不可信历史失败关闭。
- 回滚：关闭新路由和前端入口，保留合法 Review、Capability、Audit、收据，不删除业务历史；若新决定已提交，不自动撤销批准或指针，只能按既有正式流程追加新版本/限制。

## 验证计划与执行顺序

1. `P04-P03-A01` 冻结新增合同及本 CR；不声称功能已实现。
2. `A02` 内部 GLOBAL Read/Decision 服务：Session/License/Scope/Reviewer/幂等/终态 Owner 重证，单元及隔离 PG 正反例和并发回放。
3. `A03` 默认关闭的 GET/DECIDE HTTP、Windows 显式装配；合同测试、真实 PG、匿名/普通用户/错误 Scope/失效 License/撤源拒绝。
4. `A04` 前端从 Capability Version `review_ref` 进入正式评审详情和本人决定操作；真实 Edge/PG 全链。随后 P05 在固定非发行包清洁解包，核实来源→Evidence 人工资格→Version→VALIDATE→Review→批准指针与 Handover 前置；客户确认和正式信任另行验收。

本 CR 仅采用已授权的实现方向；后续任何 Schema、身份粒度或已有冻结字段的破坏性变化须另行记录，不能借本 CR 静默扩大。
