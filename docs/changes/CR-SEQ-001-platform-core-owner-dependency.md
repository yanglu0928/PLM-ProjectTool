# CR-SEQ-001：Platform Core 真实业务 Owner 与阶段验收的时序解环

日期：2026-10-02；状态：依据 CR-EXEC-001 持续授权记录并实施时序调整；原 Gate 2 冻结提交 `64cdf09` 保留，Gate 3 未通过。

## 来源与冲突

V2.1 §Phase 2 把 Review、Trace、Workflow 列为 Platform Core，并要求“完整模拟项目可以走通权限与阶段”；正式顺序为 Phase 2 → Phase 3 AI/RAG → Phase 4 项目交接及后续业务。冻结的 Review Subject 和六阶段 Checklist 却需要交接、调研、需求、原型、方案、计划的真实固定业务版本、当前资格、Evidence 与人工决定。当前生产 Review Subject Read/Start/Transition Port 没有业务 Owner；`ApprovedException` 没有实体或审批 Owner；Trace 只有 DOC-02 Owner。合成 Subject/Review 状态只能测平台机制，不能成为业务 Gate 事实。Phase 2 要求全部真实 Owner 才退出、又禁止先进入后续 Owner 阶段，会形成实施顺序循环。

证据：`docs/progress/rvw-02-a10-public-precheck.md`、`docs/progress/wfl-01-a07-p05-review-exception-precondition.md`、`docs/workflow/six-stage-definition-v1.md`、`docs/changes/CR-TRC-002-http-owner-resolution-sequence.md`；V2.1 §Phase 2～4 与正式开发真实顺序。POC-03 新留出集不足及历史质量失败仍独立阻塞 Gate 3。

## 方案比较与选择

- 不选伪造业务 Subject/ApprovedException、凭旧 Review APPROVED 放行 Gate，或把合成项目验收记为真实 PASS：会违反冻结资格/人工确认语义。
- 不选原地削减 Phase 2 验收或取消 Review/Trace/Workflow：破坏冻结 Scope。
- 不选为等待 Phase 2 全部 Owner 无限暂停所有后续模块：使依赖循环无法收敛。
- 选择**按依赖前置后续阶段可独立验证的任务**：Phase 2 持续保持 `IN_PROGRESS`，其未完成的 Owner/Gate 条件逐项登记；先实施不依赖这些 Owner 的 Phase 3 AI/RAG 基础合同、Provider/Model/Prompt、授权边界及独立 RAG 基础任务，再实现真实业务 Owner，回接 Review/Trace/Workflow 并重做 Phase 2 端到端验收。必要时以同一规则前置 Phase 4 起的最小真实 Owner，不把提前编码等同于该阶段或 Gate 通过。每个 WBS 仍只解决一个问题，任何新的 Schema/API 差异单独建立 CR。

这只是任务拓扑顺序修订，不改变模块化单体、技术栈、冻结实体/`/api/v1` 合同、六阶段规则或 AI 建议态；对照 CR-PAR-001 的 Parser 基础任务前置做法。Phase 标签、完成率和 Gate 结论仍以实际证据为准，不因开始后续代码而自动迁移。

## 风险、迁移与回滚

风险是提前实现的 AI/RAG 端口与后续业务输入不吻合、外发权限误复用及过早宣称可用。对策：先按冻结 ADR-004、DM-04、API-03 固定版本化合同；PROJECT 强制 ProjectId；业务模块只经 AIService/RetrievalService；真实客户数据外发始终需当轮明确授权，不能沿用本 CR；建议不能自动正式化。新留出集质量、真实 Owner、生产信任/密钥、三平台发行和 UAT 各自保留未通过状态。

本 CR 本身无数据库或用户数据迁移、无运行 API/依赖更改。可停止前置任务并恢复原排期；已完成的独立代码和历史审计保留，不追写冻结版本。每个后续实现自带兼容、数据库升降级及回滚验证；已产生客户数据、外发或签署不在本 CR 授权内。

## 验证与关闭条件

本项以冻结基线、当前源码/进度和依赖图静态核查验证，只证明冲突与排序决定，不证明 Phase 2/3、Gate 3、业务 Owner 或发行通过。后续依次验证 AI/RAG 模块合同与安全、真实业务 Owner 的身份/版本/来源/撤权、Review/Trace/Workflow 同事务集成、完整模拟项目的真实授权与阶段、POC-03 新独立留出集质量及正式目标平台/发行。全部证据满足前 Phase 2 与 Gate 3 保持 OPEN；未知或阻塞按 STATUS 登记并转独立任务。
