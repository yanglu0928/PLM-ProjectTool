# SOL-01-A14：Reference Revise 双 Scope 边界对账

日期：2026-10-09。结果：`SOL_01_A14_BOUNDARY_AUDIT_COMPLETE_WITH_OPEN_GAPS`，仅边界审计完成；Reference 全范围和 Eligibility 未关闭。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-01-A14；输入冻结 API-04、GLOBAL 人工脱敏 API 增量、CR-SOL-013/014/015、A07～A13-P03；前置已满足。
- 单一问题：核对 PROJECT/GLOBAL Reference 修订是否在权限、来源、幂等历史回执与当前性上保持同一冻结语义，并列明仍未覆盖的合法来源和资格操作。不修改生产程序、Schema/Migration/API、依赖或权限。
- 验收：逐项标注已有实测/合同/缺失证据，不把历史 201、合成确认、只读详情或拟实施 Eligibility 误作当前资格；给出后续独立任务与回滚/迁移边界。

## 范围矩阵

|边界|PROJECT|GLOBAL|本次结论|
|---|---|---|---|
|修订角色/Scope|PM/实施成员；客户不可写，项目隔离|DeploymentAdmin；非管理员直 POST404|A09 双 Scope Win11/PG 与 A12/A13 浏览器已验；冻结双路由未接受自由 Scope|
|固定来源|活动项目文档版本必选，Evidence 可选|服务端 1～100 文档、0～500 Evidence，且需当前合格与脱敏确认|PROJECT 文档-only 页面/浏览器可用；GLOBAL 现有 UI 仅 ≥2 Evidence，文档-only 合法集合缺入口|
|GLOBAL 人工脱敏|不适用|新指纹需 Preview→逐项打开/人工确认；服务端写事务重证明确认|A13-P03 合成浏览器链通过；真人判断未验，旧确认不能推出当前有效|
|乐观锁与幂等|当前 GET ETag、原 body/ETag/Key 锁定；历史首次 201 后另 GET|同左；另需独立创建/修订 pending|A11 客户端合同、A12/A13 真实 Edge/PG 首次 201 丢失同号恢复、单版本/审计已验；回执不是当前事实|
|Eligibility|冻结 `SET_ELIGIBILITY` ProjectManager 决策|冻结 `SET_ELIGIBILITY` DeploymentAdmin 决策|`CR-SOL-014` 仅计划；无 Owner/迁移/HTTP/UI，不能以 DRAFT/ReferenceOnly 代替合格状态|
|正式部署|Win11 合成账户/临时 PG|Win11 合成账户/临时 PG|正式 License/目标账户/HTTPS、Server2025、20 并发、Gate3/UAT/发行未验|

## 本次复验

- `test_solution_reference_revise_api.py`：4 passed、16 subtests passed；覆盖双路径成功/ETag、缺 Session/Origin/CSRF/If-Match/Key、非法 Scope/Body 与错误映射。
- `validation/sol-01-a09-reference-revise-windows/verify.py`：Win11/隔离 PG PROJECT 显式写组合退出0，含真实来源、角色/跨项目、旧结果/错误边界。
- `validation/sol-01-a09-reference-revise-windows/verify_global.py`：Win11/隔离 PG GLOBAL 显式写组合退出0，含真实来源、脱敏、重放/非管理员拒绝。
- A12-P03/A13-P03 的浏览器/PG 证据当前仍在各自进度记录；本项未重复称为正式环境验收。

## 施工顺序与风险

1. `SOL-01-A15` 补 GLOBAL 文档主来源选择和 0～500 可选 Evidence，不把既有至少两证据 UI 门槛当作冻结合同；保留 Preview/逐项确认/写前重证，不提供裸 UUID 输入。先页面合同，再 Win11 Edge/PG 文档-only 验证。
2. `SOL-01-A16` 按已记录 `CR-SOL-014` 实现独立受控 Eligibility：状态机/不可变结果、受限 Guard/ORM/Alembic/空库与有数据升降级、Owner/HTTP/Windows/UI/浏览器分别验；ELIGIBLE 前现时来源与 GLOBAL 确认复验。不得让修订自动改变资格。
3. 双项之后再验 OutlineVersion 引用所需的现时合格性与正式服务账户/性能等 Gate 3 条件。

无本轮 Schema/API/生产代码变更，审计文档可回退；后续 A15 仅前端候选扩展，A16 的迁移/回滚遵从 `CR-SOL-014`，历史数据不直接删除。TraceLink：Gate2 API-04/DM-05 → CR-SOL-013/014/015 → A07～A13-P03 → 本 A14 → A15/A16 → Gate3。Debian 13 实机依用户指令暂跳过。
