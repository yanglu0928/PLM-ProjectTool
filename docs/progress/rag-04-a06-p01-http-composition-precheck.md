# RAG-04-A06-P01：Retrieval HTTP、取消与生产组合编码前核查

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_04_A06_P01_HTTP_COMPOSITION_PRECHECK_PASS`

## 编码前检查

|项|结论|
|---|---|
|当前阶段|Phase 2 Platform Core；Gate 2 已冻结，Gate 3 未通过|
|输入基线|ADR-004/007/009/013、DM-04、SC-01～04、API-01/API-03、CR-RAG-004、Schema0089|
|前置任务|A05-P02 已完成零外发 PROJECT FTS 的内部创建后执行、原子发布与 AI Context 读取|
|涉及 API|冻结 Create/Get/Result/Context/Cancel 五个 `/api/v1/projects/{project_id}/retrieval-runs...` Operation|
|涉及权限|Create 为 PM/IM/CM；Get/Result 为创建者或受权项目角色；Context 为创建者/受权调用链；Cancel 为创建者或 PM；普通用户越权统一 404|
|涉及实体|RetrievalRun、QueryContent、Candidate、ScorePart、ContextBundle/Item、Job/Lease/Attempt、Audit、Idempotency Receipt|
|依赖与外发|不新增依赖；首个策略固定本地 FTS、`egress=NOT_APPLICABLE`，不访问 Provider|
|验收标准|严格请求/响应 Envelope；正文与指纹最小投影；取消不拆分 Job/Run；生产 API 与固定 Worker 角色组合失败关闭；Windows 11/PostgreSQL 18 真实 HTTP/Worker/前端闭环|

## 核查发现

1. 冻结 API-03 已明确五个 Operation，但仓库只有内部 Create、Worker、终态和 AI Context Owner；没有 Retrieval 读取 Owner、HTTP Router、公开取消 Owner或前端消费面。
2. 冻结数据模型定义 `RetrievalRun = RUNNING / SUCCEEDED / FAILED / CANCELLED`，通用 Job 支持 `CANCEL_REQUESTED / CANCELLED`；Schema0089 却只允许 Run 从 RUNNING 转为 SUCCEEDED/FAILED，且终态 deferred validator 只认两种 Job 终态。直接复用通用 Job cancel 会造成 Job/Run 分裂，必须先以 Schema0090 追加取消边界。
3. 对 PENDING Job 可在取消 Owner 事务内直接把 Job/Run 同步置为 CANCELLED；对已认领 Job 先写 Job `CANCEL_REQUESTED`，由专属 Retrieval 取消 Reconciler 在同一事务关闭 Lease/Attempt/Job/Run并写 Audit。取消与成功发布依赖同一 Job 行锁顺序，先提交者决定结果；不得声称已发布结果被回滚。
4. Get/Result/Context 不能复用 AI Context 文本接口。HTTP 读取需要独立安全 DTO：Run 不返回 query/密文/fingerprint；Result 只返回候选最小来源、整数分数分解和受权 snippet；Context 返回有界 BundleView，不返回 Golden/人工答案、向量或其他项目存在性。所有读取每次重验 Session、License 和当前 Project 权限。
5. Create Router 只能从路径取 ProjectId，从 Session 取 Actor，严格解析 query/top_k/固定 metadata/policy/index refs；首版拒绝 GLOBAL、vector、rerank 与任意业务 filter，不把“已冻结但未实现”静默标为可用。
6. 固定 Windows SCM 只有 API、AUDIT_WORKER、PARSER_WORKER、AI_PROVIDER_WORKER 四个角色。为首个本地 FTS 新增第五角色会改变已冻结服务拓扑；A06 复用第四 Worker 的受控组合循环，但把 RAG claim/密钥/Owner与 Provider 链隔离，并采用公平有界调度。无 RAG 策略/专用内容密钥时不消费 Retrieval。
7. 现有生产 API 写组合的通用 Job cancel registry 尚未登记 `rag/RAG_RETRIEVAL`；A06 必须同时挂冻结 Retrieval `:cancel` 和通用 Job cancel 到同一 Owner，避免两条路径产生不同状态机或幂等证据。

## 实施拆分

- `RAG-04-A06-P02`：Schema0090，增加 Retrieval CANCELLED 终态、PENDING 直接取消和 RUNNING 协作取消的提交期原子约束。
- `RAG-04-A06-P03`：当前受权 Run/Result/Context 只读应用与 PostgreSQL Owner，固定最小 DTO。
- `RAG-04-A06-P04`：严格 Create/Get/Result/Context HTTP 合同与 opt-in Router，不默认挂载。
- `RAG-04-A06-P05`：Retrieval Cancel Owner、专属取消 Reconciler、冻结别名 Router及通用 Job cancel registry 接线。
- `RAG-04-A06-P06`：Windows 生产 API与既有第四 Worker角色组合；加入专用查询内容密钥来源和公平有界 Retrieval 循环。
- `RAG-04-A06-P07`：前端安全客户端/页面，仅显示状态、来源、分数与最小 Context，不显示query密文或内部指纹。
- `RAG-04-A06-P08`：Windows 11/PostgreSQL 18真实构建浏览器→HTTP→Worker→Result/Context/Cancel验收及资源清理。

## Compatibility / Risk / Rollback

保持冻结路径、角色和外部 DTO 语义，不引入新服务角色、依赖或外发。Schema0090 只追加冻结模型已有的 CANCELLED 状态，不复活或改写既有终态；有取消历史时物理降级拒绝并向前修复。生产组合可通过撤除 Router/策略和停止 Retrieval 调度关闭新流量，既有 Run/Job/Audit/收据历史保留。

主要风险是取消与发布竞态、Context 当前授权漂移、两个取消路径分叉、专用密钥缺失和多链 Worker 饥饿；分别以共享行锁/提交期约束、读取时重验、同一 Owner、启动失败关闭和公平有界调度处理。

## Verification / Result / Next

本项为静态核查，交叉确认冻结 API-03 五个 Operation、DM-04 CANCELLED、Schema0089 只认成功/失败、现有 Job cancel Owner registry 和四服务拓扑。未运行新增程序测试，不代表 HTTP、取消、生产组合、前端、正式 ACTIVE、业务质量、性能、Gate 3、UAT 或发行包通过。

结果：`PASS`。差异、风险、迁移/回滚和验证计划已记录；下一项 `RAG-04-A06-P02` 实施 Schema0090 Retrieval 取消原子边界。
