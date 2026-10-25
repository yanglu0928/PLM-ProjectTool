# AI-04-A01：AITask/Invocation 冻结边界与前置核查

日期：2026-10-02；依据 Gate2 冻结 API-03、DM-04 与 DB Schema V1；本项仅静态核查，无运行行为变化。

## 核对结果

- 冻结 `AI_TASK_CREATE/LIST/GET/INVOCATION_LIST/SUGGESTION_GET/CANCEL/RETRY/ACCEPT/REJECT` 均为 PROJECT 资源；创建只允许 ProjectManager/ImplementationMember、不可变同项目输入版本、受控 TaskType/策略引用与最小参数，不接受客户端指定原始 Prompt、API Key、任意 Provider/endpoint。
- `AITask` 是项目范围 Root，`AIInvocation` 是不可变 Attempt；每次实际调用必须保存 Provider/Model/PromptVersion/Input/Context/Schema与授权快照。Suggestion 始终 `NOT_FORMAL_FACT`，正式化只能由业务 Owner 在人工确认和 Review 约束下建立 Draft。
- 外发授权要按每次 Provider、地区、用途、数据类别和输入/Context 复核；此前某轮特定候选的授权不构成所有后续 AI 任务的通用外发授权。当前任务不外发客户数据，不激活厂商调用。
- 当前代码有 Provider、Model、Prompt Registry 与 Probe Worker；未发现 `ai_tasks` / `ai_invocations` 的生产 ORM/Migration 或统一 AIService 任务内核。冻结 Schema 目录仅规定逻辑身份/关联和敏感字段边界，不能把概念性表格当已部署物理 Schema。Prompt 增版/激活正式准入、真实目标账户发行信任仍未完成。

## 独立实施顺序

1. `AI-04-A02` 定义 AITask/Invocation 最小物理 Schema 与 ORM，先核对冻结字段与已有 Job/Project/Prompt 引用；如与冻结模型冲突，先登记 Change Request。空库、有数据升级、up/down、约束与历史保护必须在隔离PG18验证。此步不开放 API、不调用厂商。
2. 后续内部创建与项目授权/同事务幂等、输入版本与外发授权准入、统一 AIService/Job Attempt，再分别接只读与写 HTTP。Prompt `RETIRED` 必须拒绝新 Invocation，即使保留历史指针；旧 Attempt 快照仍可追溯。
3. 真实外发、质量、性能、正式平台信任及 Gate3/UAT 独立验收；不把本项静态检查写成任务链 PASS。

Changed：仅本进度、状态和版本说明。Migration/API/依赖：无。Tests：静态核对冻结 API/DM/Schema 与现有源码，未运行新测试。兼容/回滚：无行为变化。Known Issues：完整 AI Task/Invocation、RAG、正式信任、质量 Gate 与可用包未完成。
