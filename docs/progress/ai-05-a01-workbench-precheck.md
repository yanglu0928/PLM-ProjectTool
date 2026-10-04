# AI-05-A01 AI 建议工作台编码前核查

日期：2026-10-03；状态：`PRECHECK_PASS_WITH_REQUIRED_BACKEND_SPLIT`；依据冻结 API-01/API-03、用户确认的“问题可快速定位原文、人工维护项给出明确提示、AI 建议不直接成为正式事实”交互要求，以及 AI-04 已完成的 Task/Worker 安全闭环。

## 编码前检查

|字段|结论|
|---|---|
|当前 Phase|Phase 2 Platform Core|
|当前 WBS|`AI-05-A01`|
|输入基线|Gate 2 冻结 API-03 AITask/Invocation/Suggestion/Job/Egress 合同；API-01 公共响应与安全协议；AI-04 Schema0064～0075及运行实现|
|前置任务|AI-04-A06-P09-P06 Windows 服务闭环 PASS；Task Create/GET、Egress Preview/Get/Authorize/Revoke、Job List/Get/Cancel/Retry 已有显式 Windows 组合|
|涉及模块|前端 `ai` 工作台；后端 `ai` 只读 API；复用 `jobs`、`document`、`evidence` 页面|
|涉及实体|AITask、AIInvocation、SuggestionPayload、SuggestionEvidenceRef、EgressPreview/Authorization、Job|
|涉及 API|冻结 `AI_TASK_LIST/GET/CREATE/INVOCATION_LIST/SUGGESTION_GET` 与既有 Egress/Job 路径；后续 Accept/Reject 独立处理|
|涉及权限|创建者、ProjectManager、ImplementationMember、CustomerManager的项目内差异；无权/跨项目统一隐藏；DeploymentAdmin无项目通配权|
|验收标准|严格客户端 DTO；建议始终标记 `NOT_FORMAL_FACT`；每条问题可由 Evidence/Document Version 引用跳转定位；人工字段显示“维护什么/为何需要/依据/必填性”；未知写结果不自动重试；权限撤销后清空旧数据|
|风险|后端缺 Task List、Invocation List、Suggestion GET 与 Accept/Reject；现有 Job `result_ref` 不承载 Suggestion；POC-03 分类/引用质量仍未达 Gate 3|

## 现状与结论

仓库没有前端 `ai` 模块或 AI Task 路由。后端已实现并显式组合 `POST /projects/{project_id}/ai-tasks`、`GET /projects/{project_id}/ai-tasks/{ai_task_id}`、完整 Egress Preview/Authorize/Revoke，以及通用项目 Job 列表、详情、取消和重试；因此提交后的状态跟踪可以复用 Job 页面，但不能把 Job 当作 AI 建议结果。

冻结 API-03 仍有四个直接阻塞完整工作台的实现缺口：`AI_TASK_LIST`、`AI_TASK_INVOCATION_LIST`、`AI_TASK_SUGGESTION_GET`、Suggestion Accept/Reject。数据库已有不可变 SuggestionPayload/EvidenceRef，但当前没有受权安全投影或公开读取路径。前端若直接依赖内部表、Worker 响应或 Job payload，将违反 `UI → API → Application Service → Repository`、项目隔离和响应最小化约束。

采用以下拆分：

1. `AI-04-A07` 先补冻结只读闭环：P01核查精确 DTO/定位引用；P02 Task List稳定游标；P03 Invocation List；P04 Suggestion安全读取与 Evidence/Document定位投影；P05 Windows组合与真实 PostgreSQL HTTP 验证。Accept/Reject 因涉及目标业务 Draft Owner 与Review锁，另立写闭环，不与读取混做。
2. `AI-05-A02` 实现前端严格只读客户端；A03任务/建议列表；A04详情、运行状态、取消/重试复用；A05建议卡片的“定位原文”动作和人工维护提示；A06提交与逐次外发授权；A07 Windows 11真实浏览器/隔离PG验收。
3. 前端不得显示“一键确认全部”为正式事实。每条建议必须显示建议态、证据引用、质量/冲突标记；“接受”只能进入目标 Draft，后续仍需人工维护和Review。来源定位优先跳转已受权 Evidence Viewer 或 Document Version 页面，不复制整段正文到表格。

## 兼容、迁移与验证边界

本项仅核查与计划，不修改代码、Schema、API或依赖，不执行运行测试，也不产生客户数据外发。后续实现均沿用冻结 `/api/v1`；如发现冻结 DTO 无法表达安全定位或人工字段提示，必须先建 API Change Request，不静默增加宽泛正文或动态 URL。Windows Server 2025待独立验证；Debian 13按用户指令跳过验证但保留兼容目标。

Next：`AI-04-A07-P01` 冻结 AI Task List / Invocation List / Suggestion GET 的运行 DTO、稳定游标、证据定位和权限边界编码前核查。
