# SOL-06-A14-P03：结构化专项精确 Trace 覆盖

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_TRACE_COVERAGE_PASS`；已完成 SOL-06 固定目标证明与当前 Requirement 集的精确 ACTIVE `IMPLEMENTS` 覆盖，不表示 Review、送审、批准或实施验收已完成。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A14-P03`|
|输入基线|CR-SOL-021；SOL-06 不可变系列/版本身份；统一 Trace `IMPLEMENTS`；A14-P02 V2 设计就绪合同|
|前置任务|SOL-06 创建、修订、详情与当前事实评估器已完成；REQ-03 固定版本 Owner 与 SOL-05 精确覆盖服务可复用|
|涉及模块/实体|solution、trace、requirement；`StructuredSolutionSpec`、`RequirementVersion`、`TraceLink`|
|涉及 API / Schema / 权限|不改冻结 URL、JSON、角色、数据库 Schema 或 License；只扩展内部固定目标证明和 Windows 组合|
|验收标准|同项目固定 SOL-06 series/version；精确匹配全部当前 RequirementVersion；只认 ACTIVE `IMPLEMENTS`；旧目标、额外/缺失、跨项目、撤销均失败；评估期间锁定已证明边|
|风险|只按 series 或只按任意历史版本误判；撤销边被继续消费；Owner 开新事务造成竞态；缺链被误报为系统不可用|

## 实施结果

- 新增 `StructuredSpecTraceOwner`，以 `solution / SOL-06 / spec_series_id / structured_solution_spec_id / PROJECT / project_id` 证明固定目标；读取复用调用方事务，并重验 License、Session、项目 GET 授权、系列与版本身份。`RESTRICTED`、跨项目、错系列和错版本均按不可见处理。
- 将既有精确 `IMPLEMENTS` 覆盖从硬编码 SOL-05 扩展为受控 SOL-05/SOL-06 目标。查询仍只接受 PROJECT、ACTIVE、`IMPLEMENTS`，在同一事务重新证明目标和每个 RequirementVersion，并对命中行持共享锁；不放宽到其他对象类型。
- SOL-06 当前事实评估器现在以专项正文中的精确 RequirementVersion 元组核对 Trace。缺少、额外、重复、错目标、历史目标或撤销边为 `FAIL`；Owner/数据库不可用、畸形证明为 `UNAVAILABLE`。只有精确证明才为 `PASS`。
- Windows 显式读写组合安装真实 Requirement/SOL-06 Trace Owner 与 Repository。冻结 VALIDATE 路径和响应形状不变；在其他事实与 V2 设计声明均通过时，精确 Trace 可使 `ready_for_review=true`，但仍不创建 Review、改变 DRAFT 或表示批准。
- 既有 A13 历史验证脚本显式使用不可用 Stub，保留各自当时的历史证据语义；当前真实 Windows/Edge 链把“已知缺链”显示为 `未通过 / TRACE_COVERAGE_FAIL`，不再误写为无法核验。

## 验证证据

- 后端定向：35 项、53 子测试通过，覆盖 SOL-05 回归、SOL-06 Owner、同事务详情读取、当前事实评估和 Windows 组合。
- 后端全量：`3735 passed, 3 skipped, 5823 subtests passed`；最终 `py_compile`、Node 语法检查和 `git diff --check` 通过。
- Windows 11 / 可弃 PostgreSQL 18.6：缺链、指向 v1 的旧目标和跨项目创建拒绝；精确 v2 链后报告 `valid=true / ready_for_review=true`；撤销后立即失败，替代 ACTIVE 链恢复；竞争 `FOR UPDATE NOWAIT` 被评估持有的共享锁阻止。
- 既有 A13 当前事实、服务与 Windows HTTP 回归通过；Windows 11 Edge → 构建 Vue → 生产 FastAPI/Uvicorn → PostgreSQL 18.6 验证缺链显示、首次观察、原 Key 重放和跨项目清屏通过。
- Python 3.13.15 开发 wheel 共 1409 项，新增 SOL-06 Trace Owner 入包；SHA-256 `a6854eb0a9cac9047760d883250d589d759ad8c3c86dbe2929a7cb3c998da6c8`。该 wheel 仅为开发验证产物，不是 Pilot 或正式发行包。

## 偏差、兼容、升级与回滚

- 首次执行新 PG 验证时，复用夹具的模块链少引用一级，导致入口 `AttributeError`；修正为与 A13-P05/P07 一致的四级链后，从全新可弃库重跑通过。未改变产品行为。
- Edge 首轮正确显示 `TRACE_COVERAGE_FAIL`，但验收脚本仍使用旧“暂无法核验”及错误的“失败”标签；按产品统一状态文案改为“未通过”，并让失败信息列出缺失文本后重跑通过。未放宽断言。
- 无 Migration、冻结 API、角色、License、依赖或既有业务数据变化。升级需同版部署后端；可通过关闭 SOL_SPEC_VALIDATE 显式组合回滚新运行入口，既有 Trace/Audit/收据历史保留。不得改写或删除已存在 Trace 历史。
- 非空 Artifact、Review 状态窄门、Subject Owner、原子送审、正式信任、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 和正式发行状态不变。

Next：`SOL-06-A14-P04` 实施 Review 状态窄门 Migration 与 SOL-06 Review Subject Repository/Owner，验证开始、终态映射、旧 APPROVED 替代和历史保护；不提前开放冻结送审 HTTP。
