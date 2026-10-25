# SOL-05-A04-P10-P01：SectionVersion 当前 Trace 维精确证明

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：内部 Trace 维接入与纯 Owner 合同验收通过；Windows 实际装配留下一片。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-05-A04-P10-P01`|
|输入基线|冻结 DM-05 Requirement→SectionVersion Trace 一致性、API-04 `SOL_SECTION_VERSION_VALIDATE`；TRC-01-A03-P03 精确 ACTIVE `IMPLEMENTS` 内部证明；现有 Section 六维报告|
|前置任务|REQ-03/SOL-05 Trace Target Owner、统一 Trace 精确覆盖服务已验；SectionVersion 固定 RequirementVersion 列表可安全反读，当前前四维 VALIDATE 已装配|
|涉及模块/实体|solution.application 的 SectionVersion 当前事实评估；不改 TraceLink/SectionVersion 物理表|
|涉及 API/权限|本片只接内部 Trace Port；仍由后续/现有 VALIDATE Owner 保证 Session、CSRF、Project、License，同一事务内服务逐边重验两端 Owner|
|验收标准|固定目标和完整 RequirementVersion 集合构造、精确 ACTIVE 边证明、缺/多/失效/跨项目/错版/端口故障失败关闭；缺 Trace Port 仍不可用；Spec 维不误报 PASS|
|风险|把存在性当当前有效覆盖；服务返回错误目标或重复边仍 PASS；空 Requirement 集合被当作覆盖；Trace 通过误判 Section 已可送审|

设计：可选注入已验 `TraceImplementsCoverageService`，无注入维持 `UNAVAILABLE` 以保留旧独立组合的安全行为；显式组合另片验收。存在注入时使用固定 Section/RequirementVersion 构造 PROJECT `SOL-05`/`REQ-03` refs，在调用者原事务与 Session 下校验精确覆盖结果。当前 `spec` 维继续 `UNAVAILABLE`，故本片不使 `ready_for_review` 自动通过。

无 Schema/Migration、冻结 API、角色、License、依赖或旧历史变化；关闭新注入即可回滚。若精确服务要求与冻结业务规则冲突，先登记 CR，不弱化覆盖。

## 实施与验收

- `SectionVersionCurrentValidator` 现在可注入统一 Trace 覆盖 Port；构造固定 `SOL-05` 目标和完整 `REQ-03` 版本集合，在当前事务/Session/Trace 下校验返回证明的目标、全集、边数量、唯一及规范 UUID。缺/多边映射 FAIL，端口/权限或证明异常映射 UNAVAILABLE；不注入时继续 UNAVAILABLE。
- 定向 Section/Trace 合同 20 项通过，包括精确证明、错误目标/边数、缺边、端口不可用与已有幂等/Audit 回放；完整后端回归 `3890 passed, 3 skipped, 6023 subtests passed`，退出码 0。`git diff --check`通过。
- 此片不修改 Windows 路由装配，未运行新的实际 PG/浏览器；`spec` 维仍 UNAVAILABLE，VALIDATE 的 `ready_for_review` 不因此通过。实际创建/撤销 ACTIVE Trace 和精确服务的 PostgreSQL 验收已有 TRC-01-A03-P03 证据，但不代替下一片 Windows 组合验收。
