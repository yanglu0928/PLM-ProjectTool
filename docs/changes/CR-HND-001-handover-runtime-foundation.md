# CR-HND-001：Handover 运行时基础与固定来源物理化

日期：2026-10-05。状态：依据 `CR-EXEC-001` 持续授权批准分步实施。Gate 2 原冻结提交 `64cdf09` 保留；本 CR 不代表交接业务事实、Phase 4 或 Gate 3 已通过。

## 来源与冲突

冻结 DM-05、SC-01/02 与 API-04 定义 HND-01 `HandoverAnalysis`、HND-02 `HandoverAnalysisVersion`、HND-03 `ActionItem` 三个 PROJECT Root、版本内六类 AnalysisItem、固定项目 DocumentVersion、固定 Approved CapabilityBaselineVersion、Evidence 定位、统一 Review、Trace 和二十个 Operation。当前运行仓库没有 `handover` 模块、`hnd_*` 表、Owner、Router 或生产组合；Workflow 只有 HANDOVER 阶段/Checklist 名称，Audit/Trace/AI 只预留了类型白名单。

SC-01 的 HND-02 owned-table 清单列出 Item/Evidence/Capability/Option，却没有为 DM-05/API-04 要求的多值 `source_document_version_refs` 与 `ai_task_refs` 给出物理集合。把动态“当前文档”、路径、JSONB UUID 数组或文本正文当固定来源会失去外键、顺序、项目归属和逐项授权；复用 TraceLink 也不能替代 Draft 输入快照及 AI 建议来源身份。

## 方案比较与选择

- 不选直接挂二十个 API 或先做页面：没有物理 Root/Owner，会形成不可验证的空壳合同。
- 不选把资料目录、当前最新版或大段原文写入 Handover 表：违反固定版本、Document Owner 和 Evidence 定位边界。
- 不选让 AI 直接创建 CONFIRMED/RESOLVED Item 或正式 ActionItem：AI 只能形成 Suggestion/Draft，正式状态必须由项目成员与 Review 决定。
- 选择在冻结三 Root 内追加最小运行时物理层；除 SC-01 已列 owned tables 外，增加 HND-02 的固定 `source_document_version_refs` 与 `ai_task_refs` owned tables。所有 PROJECT 引用经 Owner Port 重验；固定来源与内容指纹在提交时计算，正式指针只由统一 Review 终态消费更新。

## 分步实施

1. `HND-01-A02`：新增 Handover Schema/ORM 基础，覆盖三 Root、固定来源、六类 Item、NEED_CONFIRM 结构、Action 状态历史和初始 Owner 关闭；不导入资料、不开放 HTTP。
2. `HND-01-A03`：实现 Analysis identity、完整 Draft Version 与 Validate Owner；固定 Project DocumentVersion 和 Approved CapabilityBaselineVersion，服务端计算来源/内容指纹、Audit 与持久幂等。
3. `HND-01-A04`：实现 PROJECT Review Subject、送审和终态消费；只有真实 APPROVED/CONFIRMED Version 更新正式指针，退回/撤回保留历史。
4. `HND-02`：按独立 WBS 实现 ActionItem 创建、修改、OPEN→IN_PROGRESS→SUBMITTED→VERIFIED→CLOSED 以及 CANCELLED；SUBMITTED 永不等同 CLOSED，关闭要求验证结果、Evidence 与 resolution Trace。
5. 后续按读取/写 HTTP、独立游标与 Windows 组合、前端 Evidence 定位/输入提示、真实 PostgreSQL/浏览器和 Workflow Checklist Adapter 分项验证。

## 影响、迁移与回滚

这是 Gate 2 冻结模型的物理化与 owned-table 补足，不增加 Root、公开 Operation、角色、技术栈或业务 Scope。新增表只能由 Handover Owner 写；不得跨模块直写 Document、Capability、Evidence、Review、Trace 或 Workflow 表。PROJECT 资源必须双检 path/project/resource 归属；DeploymentAdmin 没有项目成员身份时不得读取项目正文。

每个 Schema 增量提供 ORM、Alembic up/down、空库/有数据升级、drift 与历史拒降。无 Handover 历史时可降级；产生任何 Root/Version/Item/Action/来源历史后拒绝物理降级并向前修复或恢复备份。应用回滚可停止 Handover Router/Worker，不删除历史、Evidence、Review、Trace 或 Audit。

## 验证与剩余风险

本项静态交叉核对冻结 DM-05、SC-01/02、API-04、模块边界、Workflow 六阶段定义与当前源码，确认 3 Root、20 Operation 和零运行实现；只标记 `HND_01_A01_RUNTIME_PRECHECK_PASS`。POC-03 质量、真实客户确认、正式资料导入、Review/Trace/Workflow回接、性能、正式信任和目标平台发行仍未验证，不得据此关闭 Gate 3。
