# SOL-05-A04-P10-P02：Windows SectionVersion VALIDATE Trace 装配

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：Windows 显式组合与实际 HTTP/PG 内部验收通过；Section 仍不可送审。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-05-A04-P10-P02`|
|输入基线|冻结 API-04 `SOL_SECTION_VERSION_VALIDATE`；P10-P01 内部 Trace 精确维；TRC-01-A03-P03 当前 ACTIVE `IMPLEMENTS` 受权服务；现有 Windows 显式 Section VALIDATE 组合|
|前置任务|Section/Requirement Trace Owner 与受权读取服务、Trace Repository、当前 Session/Project/License、独立 PG 脚本均已存在|
|涉及模块/实体|Windows Solution 组合根、Section 当前评估器与统一 Trace Owner；无新实体/表|
|API/权限|冻结路由/响应不变；显式模式的 Trace 事实由真实边重算，匿名/跨项目/License/Owner 故障失败关闭；幂等同 Key 保持首次历史观察|
|验收标准|无边 FAIL、精确 ACTIVE 边 PASS、撤销后新 Key FAIL、旧 Key 回放原结果；实际 Windows 11/PG/HTTP、权限/License和后端全量通过|
|风险|组合时遗漏 Section/Requirement Owner、把旧 VALIDATE Audit 重写、错版边误判、测试合成信任冒充正式发行|

本片仅在已有显式 Windows Section VALIDATE 路由中注入同事务的统一 Trace 覆盖服务，不新增游标 Key、不修改冻结 API 或旧 SectionVersion 内容。关闭/撤除这项装配可回滚，已有历史 Audit/收据不删除。`spec` 维仍不可用，故 Trace 通过也不能使 Section Review ready。

## 独立验收

- 组合注册当前 RequirementVersion 与 SectionVersion Trace Owner、统一 Trace Repository，使用既有 Session/Project/License 与原 UoW。原 Windows Section 验证脚本适配“无边”为 `FAIL` 的新现时事实，仍覆盖默认404、真实来源、首次/重放、证据漂移、项目隔离、CSRF/Origin 与 License。
- 新一次性 Windows 11/PostgreSQL 18.6 HTTP 脚本退出码 0：无边 `trace=FAIL`；真实创建精确 ACTIVE `IMPLEMENTS` 后新 Key `trace=PASS`；经正式 Trace 撤销命令后新 Key `trace=FAIL`；撤销后旧 Key 保持首次 `PASS` 观察，未重写历史结果。`spec=UNAVAILABLE` 且 `ready_for_review=false` 始终保持。
- 后端完整回归 `3890 passed, 3 skipped, 6023 subtests passed`，退出码 0；`git diff --check`通过。该验证使用合成用户/License、临时数据库和来源，不代表正式服务账户/公钥/发行信任。

剩余：SectionVersion 固定 StructuredSpec 引用与当前资格、正式 Review，Outline coverage/Review、PlanVersion、Pilot/Release 验收。
