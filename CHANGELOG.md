# 版本说明

本文件记录 PLM 项目实施辅助工具的可交付变更。正式版本发布时，应将 `Unreleased` 内容归入对应版本，并补充版本号、发布日期、兼容性、安装或升级要求、Migration、已知问题和验证结果。

## Unreleased

### 新增

- 2026-09-24：`0.1.0.dev0`/PLT-01-A02 增加内部配置版本创建/激活命令、SQLAlchemy 仓储、精确非敏感值白名单与同事务权限/Audit Port；Alembic `20260924_0003` 补齐冻结契约要求的 `schema_version`，旧版本默认 1。Windows 11/Python 3.13 后端 85/85、PostgreSQL 18.6 有数据 up/down/re-up、并发/回滚/ORM drift 与 wheel 检查 PASS。升级前备份并执行 `upgrade head`；非初始 Schema 版本阻止回退。无公开 API。已知问题：真实认证/License/CSRF/Audit、持久幂等、身份创建和默认策略未实现，Windows Server 2025/Debian 13 本任务未验证。
- 2026-09-24：`0.1.0.dev0`/PLT-01-A01 完成 SystemConfiguration 身份与不可变版本 ORM、Alembic `20260924_0002`。Windows 11/Python 3.13 后端 72/72 PASS；PostgreSQL 18.6 空库及已有数据升级、空表回退、ORM drift=0、约束负例和备份恢复 PASS。升级前备份并执行 `upgrade head`；有配置数据时 downgrade 失败关闭。无公开 API。已知问题：配置命令/权限/Audit/敏感值校验、Retention 子表和 SecretRecord 尚未完成；Windows Server 2025、Debian 13 本任务未验证。
- 2026-09-24：WBS 1.09 完成 Config/Secret 基础边界。新增受限 YAML + `PLM_` 环境启动配置、显式开发 `.env`、固定脱敏错误、SecretRef/受控消费方/必需 Audit/单次使用并清理缓冲区契约；backend 新增 pydantic-settings 2.15.0 与 PyYAML 6.0.3。Windows 11/Python 3.13 下后端 72/72 测试及 wheel 内容验证 PASS；无新增业务 API、表、Migration、真实密钥或客户数据外发。升级只需安装新增依赖；下一任务为 PLT-01-A01 SystemConfiguration ORM/Migration。已知未完成项：生产密文仓库、加密算法、外部 SecretKeyProvider、主材料恢复、PLT-01/02 API/审计尚未实现，不能宣称生产 Secret 可用；Server/Debian 未在本任务验证。
- 2026-09-24：WBS 1.08 完成纯 ASGI TraceId 中间件。对每个 HTTP 请求只复用单个规范 UUID，缺失、无效或重复头生成 UUIDv7；上下文在同步/异步、并发及流式响应间保持隔离，所有响应头、错误正文和安全 JSON 日志使用同一 TraceId。Windows 11/Python 3.13 下后端 57/57 测试 PASS；健康最小 body、公开路由范围、数据库与外部调用均未改变。无升级步骤；下一 WBS 为 1.09 Config/Secret。已知未完成项：正式业务成功 Envelope、Job/AI/Plugin/Audit 跨入口传播须在相应 WBS 实现；Server/Debian 未在本任务验证。
- 2026-09-24：WBS 1.07 完成平台 JSON 日志基础能力。Application 与 Integration 采用独立、可注入的 JSON 行输出流和事件/字段白名单；未分类 API 错误只记录安全码与响应 TraceId，原始异常、正文、Secret 和路径不进入日志。Windows 11/Python 3.13 下后端 48/48 测试 PASS；无业务 API、数据库变更或外部调用。无升级步骤；下一 WBS 为 1.08 TraceId。已知未完成项：请求级 Trace/耗时上下文、Audit 持久化及正式部署日志收集/保留策略仍由后续 WBS/Release 完成；Server/Debian 未在本任务验证。
- 2026-09-24：WBS 1.06 完成 FastAPI 统一错误边界。实现冻结通用错误码、固定安全提示、请求校验 400/422、未分类异常 500、普通权限 403 隐藏为 404、规范 UUIDv7 TraceId 与 `X-Trace-Id` 同步；新增兼容 405 码且不改冻结语义。Windows 11/Python 3.13 下后端测试 43/43 PASS；仅健康端点公开，业务表、业务 API、Migration 和外部调用均未增加。无升级步骤；下一 WBS 为 1.07 JSON log。已知未完成项：服务端脱敏日志与全生命周期 Trace 中间件分别在 1.07、1.08 实现，Server/Debian 发行兼容性未由本 WBS 验证。

- 2026-09-24：WBS 1.05 完成正式 Alembic migration 基线。新增 `plm` ORM Base、统一命名约定、随 wheel 交付的 Alembic 1.20 env/template 和不可变 revision `20260924_0001`，仅固定 PostgreSQL 18 + pgvector 0.8.6，不创建业务表。Windows 11/PostgreSQL 18.6 下后端 32/32、空库与有数据 up/down/re-upgrade、ORM drift=0、offline SQL、pg_dump/pg_restore 及 wheel 内容验证全部 PASS；下一 WBS 为 1.06 Error contract。
- 2026-09-24：WBS 1.04 完成 SQLAlchemy session。新增技术无关 UnitOfWork Contract、同步 SQLAlchemy 2.0.54 + psycopg 3.3.5 DatabaseRuntime、独立 Session/显式事务、默认与异常回滚、连接池健康检查及密码安全展示；Windows 11/Python 3.13.15/PostgreSQL 18.6 下后端测试 25/25、双连接实连和 wheel 构建 PASS。业务 ORM、数据库对象、Migration、业务 API 与客户数据外发均为 0；下一 WBS 为 1.05 Alembic migration。
- 2026-09-24：WBS 1.03 完成 Vue app shell。新增 Vue 3.5.43 + TypeScript 5.9.3 + Vite 8.3.0 响应式应用壳、最小 Router、same-origin 后端状态、安全错误边界和 404；Windows 11 下 Vitest 9/9、类型检查、生产构建、官方 npm 漏洞审计、机器验收及预览 HTTP smoke 2/2 全部 PASS。当前无登录/业务页面、数据库或客户数据外发；无 Migration，下一 WBS 为 1.04 SQLAlchemy session。
- 2026-09-24：WBS 1.02 完成 FastAPI app factory。新增 Python 3.13 后端包、无全局单例的 `create_app()`、隔离 lifespan、最小 `/health/live` 与 `/health/ready`、失败关闭 readiness 探针及 12 项 Unit/API/Permission/Integration 测试；Windows 11 使用 FastAPI 0.141.1、Uvicorn 0.53.0、HTTPX2 2.13.1 验证 PASS，wheel 构建及 Uvicorn factory 实际 HTTP smoke 2/2 PASS。Swagger/ReDoc/外部 OpenAPI 与全部业务 API 保持未暴露，数据库、Migration 和外部调用均为 0；下一 WBS 为 1.03 Vue app shell。
- 2026-09-23：WBS 1.01 完成模块目录规范 V1。建立 `apps/backend`、`apps/frontend` 和独立 `tools/developer-workbench` 顶层边界，冻结 `src/plm_assistant`、模块四层模板、测试镜像与 Windows 路径规则；新增机器目录和验证器，22/22 Runtime Module 与 API Owner、65/65 Root 及冻结依赖矩阵一致，6/6 测试 PASS。本任务未创建运行代码、API、Migration 或外部调用，下一 WBS 为 1.02 FastAPI app factory。
- 2026-09-23：用户正式批准 Gate 2；Architecture、Data Model、DB Schema V1 和 API Contract V1 按提交 `64cdf09` 冻结为正式开发基线，新增 Gate 2 冻结记录并解除正式开发阻塞，项目进入 Phase 1 `1.01 定义模块目录规范`。POC-03 继续阻塞 Gate 3/UAT，Server Office、Debian 13 与 Ghostscript 发行合规继续作为 Release 约束；SC-04 仍为验证性 Migration，本次没有外部调用或生产数据库变更。
- 2026-09-23：API-05 完成 `API-CONTRACT-CANDIDATE-V1` 与 Gate 2 确认包。新增确定性 Contract Lint 和机器目录，统一核对 22 个 Owner、65 个 Root、323 个唯一 Operation ID、363 个展开 Method/Path、150 个错误码、18 个 SSE event type、20 个 Schema Query 映射和 18 个核心枚举族；5/5 单元测试 PASS，5 个外发 Operation 精确受控，通用 DELETE 与实际外部调用均为 0。四份 Gate 2 候选已齐备但未自动批准，正式业务编码继续阻塞。
- 2026-09-23：API-04 完成实施业务主链 API Contract 候选。覆盖 Capability/Handover/Survey/Requirement/Prototype/Solution/Plan 7 个 Owner、28 个 Root，定义 158 个唯一 Operation ID、54 个唯一错误码、DTO、权限、Audit、SSE 和 Contract 测试矩阵；固化逻辑身份 + 不可变版本、Owner 编排统一 Review、实际调研记录优先于模板、AI Suggestion 只创建 Draft、需求四分类与能力匹配、原型范围决定、方案覆盖/Trace 一致以及最多六级且仅 FS 的 WBS。14/14 风险、14/14 验收通过，实际外部调用 0，未创建正式业务实现。
- 2026-09-23：API-03 完成 AI、RAG、Job、Plugin 与 Output API Contract 候选。覆盖 5 个 Owner、15 个 Root，定义 79 个唯一 Operation ID、51 个唯一错误码、DTO、权限、Audit、SSE 和 Contract 测试矩阵；固化逐次最小数据外发授权、AI 建议 `NOT_FORMAL_FACT`、Project RAG 隔离与换模型新建索引、Job/Outbox 内部控制、签名插件且无公共任意调用，以及输出二次校验与文档登记。12/12 风险、14/14 验收通过，实际外部调用 0，未创建 FastAPI/Pydantic/Worker 业务实现。
- 2026-09-23：API-02 完成平台、安全、文档与治理 API Contract 候选。覆盖 Platform/Auth/Project/Workflow/Review/Document/Evidence/Trace/Audit/License 10 个 Owner、22 个 Root，定义 86 个唯一 Operation ID、DTO、Role × Resource 权限、42 个唯一错误码、强制 Audit 和 Contract 测试矩阵；固化 Secret write-only、Session/CSRF、项目隔离、Review 锁、三步流式上传、9 类 Evidence Locator、固定版本 Viewer、逐节点 Trace 授权与最小 License 恢复面。14/14 验收通过，未创建 FastAPI/Pydantic/业务代码。
- 2026-09-23：API-01 完成 API Contract V1 执行计划与公共协议候选。定义 API-01～API-05 路径、`/api/v1` REST/JSON + multipart + SSE、成功/错误 Envelope、Session/CSRF、License/授权顺序、六类主体权限基线、ETag/If-Match、Idempotency-Key、keyset cursor、文件/Viewer、`202 + JobRef` 和 SSE 恢复规则；22 个 Owner/65 个 Root 全部分类为 DIRECT/NESTED/READ_ONLY/INTERNAL。13/13 验收通过，未创建 FastAPI 或正式业务代码。
- 2026-09-23：SC-05 完成 `DB-SCHEMA-CANDIDATE-V1`。以单一候选入口汇总 22 个 Owner、65 个 Root primary table/PK/Profile、PostgreSQL 类型与 Scope/Version/安全约束、29 个物理唯一键、20 个关键 Query ID、Migration/恢复契约、14 项统一开放风险和 14 条 API Contract 输入；静态一致性检查 65/65 Root、20/20 Query、14/14 风险、12/12 验收 PASS。候选仍待 Gate 2，SC-04 工作区继续标记为验证性而非生产 Migration。
- 2026-09-23：按用户最新明确指令取消 Codex/GPT 周额度自动检查和 20% 停止线；后续仅在用户明确要求时查询，额度重置或购买仍需逐次确认。
- 2026-09-23：SC-04 完成 Windows 11 PostgreSQL 18.6 Migration 与恢复验证。新增 `VALIDATION_ONLY` SQLAlchemy/Alembic 工作区，机器可读覆盖 65 个 Root/20 个 Query ID；空库及有数据 up/down、10 个直接 SQL 负例、Job/Audit/GIN/HNSW 计划、20 Worker `SKIP LOCKED`、Retention/Hold、敏感字段及 `pg_dump`/`pg_restore` 均 PASS。代表性 HNSW 1,001 条 Top-5 Recall 100%；强过滤小集合由 planner 选择 exact fallback，不作正式性能声明，也不把 Profile 最小表描述为生产 Schema。
- 2026-09-23：SC-03 完成 PostgreSQL 18 索引与关键查询候选。定义 B-tree/GIN/HNSW 索引 Profile、20 个关键 Query ID、28 组唯一语义到 29 个物理唯一键映射，以及 Project 授权/keyset、Job/Outbox `SKIP LOCKED`、Lease fencing、Audit/Trace/Evidence 双向反查、Retention、WBS/Requirement 图和 Hybrid Retrieval 查询计划。12/12 设计验收通过；POC-02/03 参数仅作为初值，DDL、执行计划与并发性能留待 SC-04 实测。
- 2026-09-23：SC-02 完成 PostgreSQL 18 字段、类型与约束候选。65 个 Root 全部获得 M/V/A/R/SEC Profile，采用 `uuidv7()`、UTC `timestamptz(6)`、text + named CHECK、显式 Scope/ProjectId 复合约束与默认 NO ACTION/NOT DEFERRABLE；登记 28 组唯一语义、多态白名单、版本不可变、乐观并发和敏感字段规则。12/12 验收通过；未创建 ORM、Migration、业务表或索引，进入 SC-03。
- 2026-09-23：SC-01 完成 PostgreSQL 18 逻辑到物理映射候选。采用单一客户数据库与 `plm` 应用 Schema，以 22 个模块短前缀维护 Owner；65 个 Aggregate Root 全部映射唯一 primary table，Developer Workbench 3 个 Root 保持独立数据库。明确 Root/Child/Inline/JSONB/File Ref、多态引用和默认 RESTRICT 边界，10/10 验收通过，未提前定义字段类型、约束、索引或 Migration。
- 2026-09-23：DM-06 完成 `DATA-MODEL-CANDIDATE-V1`。汇总 DM-01～DM-05 的 22 个客户运行模块、65 个 Aggregate Root 和 3 个隔离 Developer Workbench Root，统一 Scope、跨聚合关系、六类生命周期、正式化链、9 类候选保留期限、Legal Hold、物理清理前置、25 条完整性不变量、14 项风险和 Schema V1 交接清单。12/12 验收通过，项目进入 SC-01；Data Model 仍待 Gate 2 正式冻结。
- 2026-09-23：DM-05 完成实施业务域数据模型候选。细化 Capability、Handover、Survey、Requirement、Prototype、Solution 与 Plan 的逻辑身份、不可变版本、Evidence、Review 和 Trace 主链；固化实际调研记录优先、标准功能/非标功能/差异项/待确认项分类、友好待办输入提示、六级 WBS 与仅 FS 依赖。12/12 验收通过，历史 R1～R9 成果不自动正式化。
- 2026-09-23：DM-04 完成 AI / RAG / Job / Plugin / Output 数据模型候选。细化统一 Provider/Model/Prompt/AITask/Invocation、Chunk/EmbeddingIndex/RetrievalRun、PostgreSQL Job/Lease/Outbox、开发者签名 Plugin 与 OutputArtifact 的状态、引用、幂等、外发授权和失败关闭；校正 RetrievalRun 为 GLOBAL_OR_PROJECT。10/10 验收通过，未引入消息队列、独立向量库、本地模型或物理 Schema/API。
- 2026-09-23：DM-03 完成 Document / Evidence / Trace / 版本数据模型候选。分离 Document、不可变 DocumentVersion 与 FileObject，定义文件提交补偿恢复、ParseRecord 生命周期、9 类 EvidenceLocator、EvidenceBinding 与 TraceLink 边界；实际调研记录作为项目事实来源，调研业务表单仅为模板参考。8/8 验收通过，未定义物理 Schema、API 或 Migration。
- 2026-09-23：DM-02 完成平台与安全数据模型候选。细化 User/PasswordCredential/Session、ProjectMember/Role/Department、Workflow/Gate、Review/Round、SystemConfiguration/Secret、License/TrustedTime 和 Audit 的字段语义、基数、状态机、失败关闭与不变量；修正 Project 不复制 current stage、ReviewRound 绑定不可变主题版本两项所有权边界。8/8 验收通过，未定义物理 Schema、API 或 Migration。
- 2026-09-22：DM-01 完成核心实体与聚合目录候选。22 个客户运行模块映射为 65 个 Aggregate Root，另有 3 个物理隔离的 Developer Workbench 聚合；每项均声明 Owner、Scope、事实语义和核心不变量。固定逻辑对象/不可变 Version 分离，以及 `AI Suggestion → 人工显式接受 → Domain Draft Version → Review → 正式版本` 链，未定义物理表、列、索引或 Migration。
- 2026-09-22：AF-05 完成 `ARCH-CANDIDATE-V1`。汇总 22 个客户运行模块与独立 Developer Workbench、显式允许依赖矩阵、统一 Application Contract、五类关键运行视图、单服务器三平台部署、质量属性、七项 Phase 0 例外和五项持续风险；8/8 架构候选验收通过。新增 Data Model Freeze 计划并进入 DM-01；Architecture 仍须与 Data Model、Schema V1、API Contract V1 在 Gate 2 一并正式确认。
- 2026-09-22：AF-04 完成关键 ADR。新增 ADR-003～009，分别固化模块化单体、统一 AI/RAG、Plugin 独立进程、License/可信时间、PostgreSQL Job/Outbox、本地文件元数据化存储和 POC-03 质量替代控制；每项均包含 Context、Decision、Consequences、Rejected Alternatives 与 Rollback/Change Rule，并明确仍等待 Gate 2 完整冻结。
- 2026-09-22：AF-03 完成安全、文件、任务与运行边界候选。固定 Server Session → CSRF → Role → Project/Resource → Review Lock 的默认拒绝链；文件采用隔离临时区、流式 Hash、原子提升和不可变版本；Secret 只以引用进入业务/Job/日志；长任务采用 PostgreSQL Job/Outbox、租约、至少一次与幂等执行；Application/Integration/Audit 三类记录分离，并明确 API、Worker、Plugin、客户 License 区与 Developer Workbench 信任边界。未引入 Redis、消息队列、容器化插件或新的正式业务代码。
- 2026-09-22：启动 Architecture Freeze。AF-01 形成 22 个客户运行模块与独立 Developer Workbench 的边界候选，单列 Output 编排且保持 Plugin 进程边界；AF-02 形成 ProjectAuthorizationService、AIService、RetrievalService、PluginService、TraceService、ReviewService 等技术无关 Application Contract 及 18 个最小 Domain Event，长任务继续使用 PostgreSQL Job/Outbox，不引入消息队列。以上均为候选，未冻结实体字段、表或 `/api/v1`。
- 2026-09-22：用户批准 `EXC-P0-006/007` 并正式确认 Phase 0 Gate 1。POC-03 保留 Top-5 98.00% PASS、分类 48.00% FAIL、引用 74.00% FAIL，以 R11 + 强制人工确认作为批准替代控制；POC-06 以 Windows 11 Office 全链、Server OOXML/Hash 和 Server Office 实开豁免收口。新增 Phase 0 总结，项目进入 Architecture Freeze；正式业务编码继续由 Gate 2 阻塞。
- 2026-09-21：用户批准 `EXC-P0-005`，暂缓 POC-06、POC-08、POC-09 的 Debian 13 验证。POC-08、POC-09 以 `PASS_WITH_EXCEPTION` 收口；POC-06 仅解除 Debian 缺口，Windows Server 2025 未安装 Microsoft Office 的阻塞不变。Debian 13 仍是正式兼容目标，未形成兼容性结论。
- 2026-09-21：启动 POC-09 License，实现“显式选择 MAC → 规范化 → SHA-256 → 确定性 Payload → Ed25519”验证链。Windows 11 与 Windows Server 2025 均通过 26/26 单元测试和 10/10 验收场景；MAC 变化、过期、Payload/签名篡改、错公钥、异常系统时间、回拨及畸形文档 8/8 全部拒绝，核心源码覆盖率 91%～94%，测试私钥与原始 MAC 均未落盘。Debian 13 保持未验证。
- 2026-09-21：启动 POC-08 Plugin Host，实现 Phase 0 验证性 `PluginService → Python 独立子进程 → JSON-RPC 2.0 over stdio` 链路。Windows 11 与 Windows Server 2025 均通过 13/13 单元/集成测试、10/10 验收场景及 20/20 并发调用；crash、timeout、invalid JSON 均失败关闭且 FastAPI 继续健康，不兼容版本/篡改/禁用在启动前拒绝，v1.0.0→v1.1.0 独立升级 PASS，插件可见敏感环境变量数 0。Debian 13 保持未验证。
- 2026-09-21：启动 POC-06，生成恰好 100 页的中文 DOCX 与 50 页的中文 PPTX，覆盖三级章节、表格、图片、原生流程和可编辑数据图。Windows 11 上 OOXML 完整性、Microsoft Word/PowerPoint 实开、PDF 导出及 150 页全量视觉检查 PASS；Windows Server 2025 包结构与 Hash PASS，但因虚拟机未安装 Office 保持 `PARTIAL_PASS_OFFICE_BLOCKED`；Debian 13 未验证。
- 2026-09-21：POC-05 完成真实扫描件分层语义准确率审计。5 份匿名文档固定抽取 15 页，先从原页视觉抄录 75 个检查点再比较 OCR；PaddleOCR 主链 75/75、关键错误 0，Tesseract 辅助基线 70/75、关键错误 2，后者不得作为关键字段唯一来源。登记 `EXC-P0-004`，Windows 11 物理断网复跑与 Debian 13 暂缓，POC-05 以 `PASS_WITH_EXCEPTION` 收口；客户原文、文件名、渲染页和逐项真值未提交。
- 2026-09-21：用户同意 R10 修复方向并要求不重复真实复验后，完成 POC-03 R11 离线修复合同。新增 Prompt v3，显式区分文档事实与能力适配，能力适配强制装配需求/约定与标准能力双来源证据；新增 Evidence Selector，使直接支持证据可超过第 1 名泛化候选，并保持 ProjectId、来源角色和 Golden 字段防泄漏失败关闭。新增 10 项合成单元测试，本轮外部调用 0，历史 50 条与 98.00% / 48.00% / 74.00% 不重跑、不改写。
- 2026-09-21：完成 POC-03 独立留出集 R10 本地失败分层诊断。新增可重复诊断工具与 3 项单元测试；确认 17 条合同/调研/技术协议样本虽检索命中 16 条但分类仅命中 1 条，能力适配任务缺少跨来源标准能力对照；模型 46/50 次引用第 1 名，正确证据位于第 2～5 名时引用仅命中 2/12；13 条严格引用失例中 8 条引用包含全部人工答案术语。冻结原结果，不事后补标，推荐在独立开发集实施双来源证据、Prompt v3 结构化判定与 Evidence Selector。
- 2026-09-21：用户明确授权后完成 50 条独立留出集真实质量复验。2,106 个唯一向量、50/50 条百炼 `qwen3-rerank` 和 50/50 条 DeepSeek Prompt v2 预测完成；Top-5 49/50（98.00%）PASS，分类 24/50（48.00%）与引用 37/50（74.00%）FAIL，缺失预测和越界引用均为 0。新增完全一致 Chunk 去重与冲突重复失败关闭，管理层汇报更新为 R9；本留出集冻结为已见测试集，修复后必须使用全新独立留出集。
- 2026-09-21：新增实施 WBS 草案 R7。基于 R6 内部交付包生成 5 个项目、60 项任务，其中 40 项需求交付任务保留 Requirement/Solution/Delivery/Evidence 追溯，20 项覆盖基线、联调、验收和交接控制；Excel 5/5 页签视觉检查、40 个证据链接和公式错误扫描 PASS。草案不填写实名、日期或承诺工期，状态保持 `NOT_FORMAL_WBS`。
- 2026-09-21：新增管理层汇报 R8.1。8 页完整呈现范围、专项、W0-W4 路线、校准集质量 FAIL、风险和下一步；PowerPoint 最终化、逐页渲染及可编辑原生图表检查通过。50 条独立留出集明确标记为尚未真实复验，不把待验证事项描述成通过。
- 2026-09-21：真实留出集质量入口新增 `poc-03.holdout.v1` 恰好 50 条的失败关闭校验，普通 Golden Dataset 继续保持 100~200 条限制；组合语料 2,078 个 Chunk、预期证据缺失 0，PostgreSQL 18.6/pgvector 0.8.6 前置检查 PASS。安全审查要求单独明确百炼 Embedding/Reranker 的数据外发授权，拦截前本轮外部调用为 0。
- 2026-09-21：新增第一批项目需求与解决方案交付包 R6。整合 5 个项目、40 条需求—方案、21 项接口/迁移/权限专项、10 条工作基线正式化待办和 30 个推荐调研主题，并按 W0-W4 形成实施路线；工作簿 6/6 页签视觉与回读通过、71 个证据链接完整、公式错误 0，POC-03 183/183 测试 PASS。全部对象保持内部草案，本轮外部调用 0，正式 Phase 0 与 Review Gate 不变。
- 2026-09-21：新增第一批内部解决方案草案 R5。40 条需求评审稿全部形成唯一方案 Trace，覆盖 10 条标准配置、10 条非标实现、10 条差异处理和 10 条工作基线专项，并生成 11 条接口、7 条迁移、3 条权限专项设计；工作簿 4/4 页签视觉与回读通过、61 个证据链接完整、公式错误 0，POC-03 176/176 测试 PASS。所有方案保持 `NOT_FORMAL_SOLUTION`，本轮外部调用 0，正式 Phase 0 Gate 不变。
- 2026-09-21：新增 AI 代决策需求评审 R4。按证据优先、保守默认、最小影响和可回滚原则，为第一批 5 个项目的 10 条前置假设形成工作基线，并将 40 条候选收敛为内部需求评审稿（P0 30、P1 10、高风险 6）；工作簿 4/4 页签视觉与回读通过、50 个证据链接完整、公式错误 0，POC-03 170/170 测试 PASS。所有条目继续标记为非正式 Requirement，本轮外部调用 0，正式 Phase 0 Gate 不变。
- 2026-09-21：第一批 5 个项目在无法安排现场调研时转为本地桌面调研，新增证据分级、局限声明、前置假设和需求候选生成器；形成 25 条调研结论、40 条需求候选（29 条可评审、1 条带假设、10 条待前置决策），工作簿 5/5 页签渲染、回读、公式与交互验证 PASS，POC-03 165/165 测试 PASS。本轮不调用外部模型，不把资料推断升级为客户确认事实，也不改变 Phase 0 Gate。
- 纳入《AI自主执行与最小人工确认规则 V1.0》：新增 `.ai/SKILL.md`、根目录 `STATUS.md` 和 `docs/decisions/decision-log.md`，后续采用 L1 自主执行、L2 记录、L3/Gate 确认模式。
- 新增 Codex/GPT 周额度保护：自动执行开始、WBS 切换前和长任务结束后检查周窗口，剩余低于 20% 时保存检查点并停止新任务；额度重置仍须用户逐次明确确认。
- 用户授权在当前 Scope 和正确分支内使用已绑定 GitHub 身份自动 fetch、commit、push，同时保留禁止 force push、直接提交 main、覆盖未知远端改动和上传敏感数据的约束。
- 建立仓库级 AI 开发约束入口。
- 建立项目开发 Skill，以及架构、技术、开发、测试、PoC 和发行规则。
- 将 GitHub 私有仓库设为唯一代码和版本说明同步目标。
- 启动 Phase 0，建立 PoC 工作区、执行登记表和三平台环境矩阵。
- 建立 POC-01 Python 3.13 依赖分组、环境采集、最小功能验证及三平台在线/离线验证脚本。
- 完成 Windows 11 / Python 3.13.15 Python 包在线与 wheelhouse 离线验证：109 个制品、15/15 项检查通过。
- 基线升版至实施方案 V2.1 / 总控规范 V1.1，新增 Windows 11，与 Windows Server 2025、Debian 13 并列支持。
- 增加 Windows 11 中文扫描 PDF 的 OCRmyPDF/Tesseract 端到端验证脚本，并记录 Ghostscript 安装与许可证风险。
- Windows 11 中文 searchable PDF 主链验证通过：Tesseract 5.4 + OCRmyPDF 17.12.1 + `tessdata_best`，5/5 术语命中。
- 完成 Ghostscript 10.08.0 项目内 portable 安装脚本及 SHA-256 校验，Windows 11 PDF/A-2b 验证通过。
- 修复 OCRmyPDF deskew 在中文 Windows 错误输出上的编码兼容问题，补充 UTF-8/本地编码回退单元测试。
- 新增 ADR-002，采用 Ghostscript AGPL 源码公开策略；仓库公开、项目许可证和第三方声明仍为发行 Gate。
- 完成 Windows Server 2025 Datacenter 10.0.26100 实机验证：Python 3.13.15 官方嵌入式运行时、完整离线依赖、15/15 项检查、Tesseract/OCRmyPDF/Ghostscript PDF/A-2b 与 deskew 中文主链全部通过。
- 增加 Windows Server 2025 非管理员部署脚本；当系统策略拒绝 Python EXE 安装器时，回退到校验过的官方嵌入式包。
- 根据用户决定登记 `EXC-P0-001`，暂缓 Debian 13 的 POC-01 验证；POC-01 以 `PASS_WITH_EXCEPTION` 收口，不形成 Debian 兼容性结论。
- 启动 POC-02，新增 PostgreSQL 18 + pgvector 工作区、三平台验收矩阵和 Windows 可用性检查脚本。
- 完成 Windows 11 首轮可用性检查：PostgreSQL 18.6 官方 Windows x64 安装器/二进制 ZIP 与 pgvector 0.8.6 源码可用；MSVC x64/`nmake` 工具链尚未安装。
- 完成 Windows 11 PostgreSQL 18.6 便携式初始化、启动、SQL 和停止验证；发现含中文字符的数据库运行路径会触发编码失败，当前约束为使用纯 ASCII 路径。
- 安装并验证 Visual Studio Build Tools 2022 17.14.41 / MSVC 14.44 x64，按 pgvector 官方流程构建并加载 pgvector 0.8.6。
- 新增 POC-02 SQLAlchemy/Alembic 验证脚手架；空库 up/down 与有数据升级/回退均通过。
- 完成 Windows 11 100,000 条 32 维向量 HNSW 验证：20 组 Top-5 平均及最低 Recall 均为 100%，并完成 `pg_dump` / `pg_restore` 与重启健康检查。
- 完成 Windows Server 2025 完全断网验证：PostgreSQL 18.6、pgvector 0.8.6、SQLAlchemy/Alembic、100,000 条向量 HNSW、备份恢复及重启全部通过。
- 新增 Windows Server 2025 最小离线包生成与来宾验收脚本；运行包和证据均记录 SHA-256，虚拟网卡在验证结束后恢复。
- 修复 Windows PowerShell 5.1 将 `psql` 普通 stderr/NOTICE 误判为终止错误的问题，并兼容嵌入式 Python 的 Alembic 本地模块路径。
- 根据用户决定登记 `EXC-P0-002`，暂缓 POC-02 的 Windows 11 完全断网重放与 Debian 13 验证；POC-02 以 `PASS_WITH_EXCEPTION` 收口，未验证范围不形成兼容性结论。
- 启动 POC-05，新增 Document + OCR 工作区、六类输入三平台验收矩阵、PoC 统一 ParsedDocument JSON Schema 与验证性解析脚手架。
- 完成 POC-05 Windows 11 六类输入统一解析：DOCX、PPTX、XLSX、CSV、文本 PDF 和扫描 PDF 均输出 PoC ParsedDocument，Schema 与来源定位断言通过。
- 完成 PP-OCRv5 mobile PaddleOCR 主链及 Tesseract/OCRmyPDF 辅助链验证；固定退化扫描样本在 Windows 11 三条链均达到 5/5 术语召回，PDF/A-2b 与中文 `--deskew` 通过。
- 修复 PaddlePaddle 3.3.1 Windows CPU oneDNN 未实现错误，验证性解析器固定 `enable_mkldnn=False`；该约束保留到后续上游版本回归。
- 完成 Windows Server 2025 完全断网 POC-05 复跑：本地 PaddleOCR 模型、离线 JSON Schema wheel、六类输入和三条 OCR 链共 8/8 PASS。
- 修复 Windows PowerShell 5.1 对 Python 无 BOM UTF-8 JSON 的本地代码页误读，Server 驱动显式使用 UTF-8 回读证据。
- 新增 POC-05 真实方案库只读批量验证器：对 18 个、365,328,831 字节的本地方案文件执行隐私隔离、OOXML 完整性、统一解析、Schema 和输入不变性检查。
- 完成 Windows 11 真实方案库复跑：17/17 个受支持的 DOCX、PPTX 和文本 PDF 通过，18/18 原件未改变；1 个旧版 `.doc` 明确记录为 `UNSUPPORTED`。
- 修复 DOCX 无名称段落样式触发的空值异常，并优化文本 PDF 分类，避免仅少量低文本页时错误地对整本启动 OCR。
- 启动 POC-04，新增统一 AIService、ModelRouter、ProviderAdapter 与 DeepSeek Chat Completions 验证实现，不在业务入口硬编码厂商 URL 或 SDK。
- 完成 Windows 11 POC-04 11/11 确定性场景及 11/11 单元测试，覆盖文本、SSE、JSON Schema、timeout、401、429、503、流式中断与厂商隔离。
- 完成 DeepSeek 官方端点真实验证：401 错误映射、文本、SSE 流式和结构化 JSON 全部通过，密钥和响应正文均未写入证据。
- 修复真实 JSON Output 首次返回不可解析内容时不重试的问题；JSON/Schema failure 现纳入最多 3 次受控重试，首次失败证据保留。
- 完成 Windows Server 2025 POC-04 实机验证：11/11 单元测试、11/11 确定性场景及 DeepSeek 真实 401、文本、SSE 流式和结构化 JSON 全部通过。
- 新增 POC-04 Windows Server 2025 验证包生成与来宾机执行脚本；临时密钥执行后删除，提交证据不记录 Secret 或响应正文。
- 根据用户决定登记 `EXC-P0-003`，暂缓 POC-04 的 Debian 13 验证；POC-04 以 `PASS_WITH_EXCEPTION` 收口，不形成 Debian 兼容性结论。
- 启动 POC-03，新增 Golden Dataset JSON Schema、三平台验收矩阵、确定性 Chunk 和候选评审生成器。
- 将本地历史方案与技术协议/合同作为只读 POC-03 输入：26 个受支持文件生成 60,430 个块、655 个 PROJECT Chunk 和 120 条候选评审记录；候选正文不进入 Git。
- 修复 POC-05 Tesseract 页面图片句柄未及时关闭导致的 Windows 临时目录清理失败，并增加句柄关闭回归测试。
- POC-05 真实资料验证新增 4 个 DOCX 和 5 个扫描 PDF，9/9 个受支持文件通过；过滤 macOS `._` 旁车文件，9 个旧版 `.doc` 明确记录为不支持。
- POC-03 新增本地 Golden Dataset 人工评审工作簿：120 条候选、2 张工作表、3 组受控下拉、完备性公式、筛选表和冻结窗格；含客户资料的工作簿继续由 Git 忽略。
- POC-03 新增评审表严格导入器：复核来源字段、人工必填项和引用边界，只允许 100~200 条人工批准记录按锁定 Schema 导出正式 Golden Dataset。
- POC-03 新增 R5 Golden 标签轻量确认包：从 R4 中确定性保留 62 条已明确人工结论，将剩余 58 条冲突归并为 7 组批量规则，并支持单条例外覆盖与证据跳转。
- POC-03 新增 R5 严格导入器：全局批量确认前禁止导出，单条分类优先于分组规则，查询、来源、分类组合和分组等只读字段被修改时失败关闭；脱敏报告不提交查询、审核人或数据集正文。
- POC-03 R5 工作簿四张表完成公式扫描与视觉检查，公式错误 0；全量回归测试由 91 项增至 96 项且全部通过。当前工作簿仍为未确认状态，不形成新 Golden Dataset。
- POC-03 R5 全局人工确认完成严格导入：120/120 条、0 个问题，Schema 与覆盖审计 PASS；最终标签收敛为五类业务结论，`HUMAN_CONFIRMATION_REQUIRED` 仅保留为工作流态。
- POC-03 新增分层检索诊断、72 组候选参数扫描、相邻 Chunk 扩展与可恢复真实 Reranker 验证；百炼 `qwen3-rerank` 120/120 实时调用将精确 Top-5 从 60.00% 提升到 74.17%，仍如实判定未达标。
- 修复逐字换行中文 OCR 文本在检索前未合并字间空白的问题，并新增确定性词法 IDF 审计；R5 Top-5 Recall 达到 114/120（95.00%）。剩余引用上限与 98% 门槛冲突已升级为 L3，不自动修改 Golden 真值。
- 用户批准方案 A；新增 R6 六项问题与引用复核包。范围锁定为 6 条低区分度样本，其余 114 条及全部 R5 分类保持不变；支持一次批量确认、单条例外、Top-5 对照和原文证据跳转。
- 新增 R6 严格导入器与回归测试：未确认时保持 6 条 PENDING 且不生成数据集；确认后只更新获批问题/引用，来源字段、范围或未展示引用被修改时失败关闭。三张工作表已完成渲染、回读和公式错误扫描。
- R6 人工确认后严格导入 120/120、问题 0，覆盖审计 PASS；本地 OCR 规范化检索 Top-5 提升为 116/120（96.67%）。完整百炼/DeepSeek 质量复验在发送数据前被安全审查停止，等待本轮显式外部数据处理授权。
- 用户明确授权后完成 R6 真实端到端质量复验：百炼重排 120/120、DeepSeek 预测 120/120；Top-5 Recall 60.00%、分类准确率 47.50%、来源引用准确率 51.67%，三项均 FAIL。分层诊断确认本地确定性检索策略尚未接入正式 Hybrid/Reranker 路径，下一版本先对齐检索链，不改变模型、门槛或 Golden 标签。
- P03-A11-R4 将来源类型过滤、OCR 中文空白规范化和确定性词法 IDF Top-20 接入正式候选链，保留 Vector/Full Text 0.6/0.4；检索缓存新增 pipeline version 防止误用旧排名。无外部调用的 120 条 PostgreSQL 回放候选池覆盖 119/120（99.17%），并新增不调用 DeepSeek 的 `--retrieval-only` 真实 Reranker 验收模式。
- 用户明确授权后完成 P03-A11-R4 的 120/120 条百炼 `qwen3-rerank` 真实复验，纯语义 Top-5 为 91/120（75.83%）；新增瞬时网络错误/429/5xx 有限重试与指数退避，已有逐条缓存可在超时后断点恢复。
- P03-A11-R5 新增无标签保护性融合：保留百炼重排第 1 名和 OCR 规范化词法前 4 名；复用 120 条真实重排缓存后精确 Top-5 达到 114/120（95.00%）、同文档 118/120（98.33%），P03-A11 PASS。结果来自同一 Golden Dataset 的探索调优且没有门槛余量，正式生产声明仍要求独立留出集。
- P03-A12-R1 新增 Prompt v2：正式输出只允许五类业务标签，按“匹配性 → 充分性 → 满足程度”顺序判断，禁止把资料缺失推断为非标准，使用 OCR 空白规范化后的完整 Chunk，并将预测缓存绑定 `PromptId + PromptVersion`。
- 新增 `--prediction-only` 失败关闭模式：要求完整本地 Embedding 与 R5 检索缓存，只允许执行 DeepSeek 预测，不调用百炼 Embedding/Reranker。120/120 条本地 payload 离线审计 PASS，来源越界、正文截断和 Golden 字段泄漏均为 0；分类准确率仍等待真实复验。
- 用户明确授权后完成 P03-A12-R2 Prompt v2 的 120/120 条 DeepSeek 真实复验；本轮 Embedding/Reranker 外部调用均为 0，两个瞬时空/非约束响应通过逐条缓存断点续跑恢复。分类 51/120（42.50%）、引用 62/120（51.67%），均如实判定 FAIL，并登记 R6 问题/标签/唯一引用的可判定性风险。
- 用户批准重新评审后新增 R7 全量语义、分类与引用确认包：覆盖 120 条样本、836 条证据候选和 120/120 原文定位，AI 建议变更分类 73 条、引用 58 条；合同、技术协议和调研材料缺少标准能力交叉证据时保守建议为资料不足。支持一次全局确认与单条例外，未确认时严格失败关闭且不生成数据集。
- 新增 R7 严格导入器和 5 项回归测试：锁定 120 条范围与 AI 建议字段，人工分类只允许五类正式结论，人工引用只允许已展示证据；工作簿 4/4 表已渲染、公式错误 0，POC-03 全量 129/129 测试 PASS。R7 明确标记为 AI 辅助校准集，同集复测不得替代独立留出集或降低 90%/98% 门槛。
- POC-03 新增独立留出集来源接入与锁定：49 份实际客户调研记录本地解析、Schema 和双 Hash 去重通过；50 条候选按 33/7/8/2 配额锁定。调研表单被明确限定为参考资料，13 个表单块不计入配额，调研 2/2 均来自新的实际记录；141/141 测试 PASS，客户资料未提交。
- POC-03 独立留出集 R1 完成 DeepSeek AI 预填和友好确认包：50/50 条建议、50/50 唯一问题、五类分类全覆盖，原文件定位 50/50；主表支持一次批量确认、单条修改/退回和证据跳转，不填充大段正文。三表渲染、公式错误与交互回归通过，POC-03 146/146 测试 PASS。
- 用户完成独立留出集 R1 确认后，新增独立 `poc-03.holdout.v1` Schema、严格导入器和 5 项失败关闭回归；实际导入 50/50 APPROVED、0 问题，12/12 覆盖与隔离检查 PASS，POC-03 151/151 测试 PASS。完整留出集与人工信息不提交，真实外部质量复验仍需当轮授权。
- 新增本地项目级分析确认包 R1：通用生成器按项目形成标准功能、非标功能、差异项、待确认项和推荐调研大纲，工作簿提供项目级快速结论、逐条黄色维护区与本地证据定位；8/8 页签渲染、回读、公式扫描和输入交互回归通过，POC-03 全量 155/155 测试 PASS。本轮覆盖统计、客户名称、原文、摘录和工作簿仅保存在 Git 忽略的本地目录，未调用外部模型。旧版 `.doc` 仅通过本机 Word 转换副本补齐本轮分析，不形成跨平台直接解析结论。
- 2026-09-21：用户确认项目分析 R1 后，新增本地调研执行包 R2。通用生成器将 12 个项目按资料成熟度分为 4 批，生成 60 条调研任务、39 条 P0 任务和 24 条决策记录；工作簿提供项目看板、黄色人工维护区、状态联动和本地证据跳转。客户数据与成品继续由 Git 忽略，本轮外部模型调用 0。
- POC-04 适配 DeepSeek V4 默认思考模式：`AIRequest` 新增显式 `thinking` 控制并由统一 Adapter 映射；结构化短任务使用非思考模式，避免推理预算导致空正文。POC-04 12/12 测试 PASS。
- POC-03 评审导入器兼容人工“确认全部建议定位”和 `YYYY.M.D`/`YYYY/M/D` 本地日期；修正后实际评审表为 109 条 APPROVED、11 条 PENDING、0 个导入问题。
- POC-03 启动 P03-A04，新增不可变索引—Embedding 模型绑定与向量维度保护；同一索引禁止原地更换模型或维度。
- POC-03 新增 OpenAI-compatible Embedding 安全探测入口；API Key 仅从环境变量读取，报告不保存输入文本、向量值或厂商响应正文。
- POC-03 修复 Windows 隔离运行时缺少 `tzdata` 时探测报告无法生成的问题，改用操作系统本地时区时间戳。
- POC-03 P03-A04 实际调用百炼 `qwen3.7-text-embedding`，请求与返回均为 1024 维；索引 `v1` 单模型绑定 PASS。
- POC-03 将 109 条人工 APPROVED 记录完成 Schema 合法导出；覆盖审计发现仅 1 个唯一查询、1 种来源类型和 1 种分类，故质量 Gate 保持未通过。
- POC-03 新增可重复执行的脱敏 Gold Set 覆盖审计，校验查询唯一性、四类来源和六类分类，不保存查询或客户内容。
- POC-03 新增完全本地的评审建议生成器和 R2 工作簿：生成 120 条不同查询及配套建议，全部重置为 PENDING；45 条 CONTRACT 可映射，75 条 SOLUTION 不伪造来源类型并留待人工确认，客户正文未上传外部 AI 服务。
- POC-03 复核用户填写后的 R2：120 行均标记为 APPROVED，45 行满足全部必填 Gate，75 行仍缺来源类型；人工状态值不能绕过正式数据校验。
- POC-03 新增 R3 人工确认待办交互原型：主表不再填充大段原文，提供 120 个本地证据定位链接、逐项维护提示、人工处理下拉和状态提示，并完整保留 R2 技术评审页。
- 新增交接分析 UX 设计边界：AI 发现与正式 ActionItem 分离，经人工确认后才可生成待办；正式产品应使用 Evidence Viewer 按文档版本与来源定位自动跳转和高亮。
- POC-03 新增来源资格审计：确定性识别 20 条合同和 25 条技术协议，发现 25 条需纠正来源类型；75 条历史解决方案不自动伪造为标准能力或调研。当前缺少 55 条合格记录以及两类真实语料，P03-A02 转为 BLOCKED。
- POC-03 P03-A05 完成真实换模重建验证：旧 `qwen3.7-text-embedding` 1024/v1 原地换模被拒绝；新建 `text-embedding-v4` 768/v2，120 条固定非客户文本通过 12 批完成 120/120 重建，旧向量复用 0；v2 保持未激活。
- POC-03 P03-A06 完成 PostgreSQL 18.6/pgvector ProjectId 隔离验证：两个项目、40 条合成记录执行 6 组 Vector/FTS/Hybrid Top-5，30 行结果跨项目泄漏 0；缺失 ProjectId 拒绝，参数注入结果 0。
- POC-03 P03-A07 完成 PostgreSQL Full Text 验证：`simple` 配置结合上游中文术语空格规范化，4 场景/40 条合成记录 Top-5 平均与最低 Recall 100%，表达式 GIN 索引命中；未宣称数据库原生中文分词。
- POC-03 P03-A08 完成 pgvector HNSW Top-5 验证：1,000 条合成三维向量、4 组已知近邻的平均与最低 Recall 100%，执行计划命中 HNSW；不替代真实 Golden Dataset 指标。
- POC-03 P03-A09 完成 Hybrid Retrieval 验证：Vector 0.6 + Full Text 0.4、每通道 4 倍 Top-K 候选池，HNSW `m=32`/`ef_construction=200`/`ef_search=200`；1,000 条合成记录、4 场景 Top-5 平均与最低 Recall 100%，GIN/HNSW 均命中。
- POC-03 P03-A10 完成外部可配置 Reranker：百炼华北 2 `qwen3-rerank` 真实 5→3 重排通过；新增响应完整性校验，以及 HTTP 429、超时、无效响应 fail-open 降级和脱敏记录。
- POC-03 P03-A14 完成 Context Builder → AIService 验证：新增相关度排序、字符预算、Chunk/来源引用、Prompt/Project Trace，并通过 POC-04 `AIService → ModelRouter → ProviderAdapter` 完成结构化输出校验。
- POC-03 P03-A15 完成异常与空结果验证：DB 不可用停止、空/低可靠度禁止 AI、Reranker fail-open、AI 错误脱敏与正常链路共 6 场景通过。
- POC-05 新增 DOCX 无效内部关系兼容：遇到指向 `word/NULL` 的关系时只修复临时副本，原文件保持不变，并增加回归测试。
- 接入用户指定的本地 `标准能力库/`：20 个 DOCX 全部解析通过，确定性分区为 19 份标准能力文档和 1 份调研表单；原件、文件名和解析正文不进入 Git。
- POC-03 以 4 份合同、5 份技术协议、19 份标准能力文档和 1 份调研表单重建候选集：29 份文档生成 1,695 个 Chunk 和 120 条候选，覆盖 29/29 文档。
- POC-03 新增四类来源 R4 人工确认包：主表只展示问题、AI 建议和人工输入，120 个链接可打开本地证据并定位原文件；新候选全部保持待确认，不继承旧工作簿批准状态。
- POC-03 完成 R4 待办清单严格导入：只有“同意 AI 建议”或带实质性“人工复核/结论”的“修改后确认”可转为批准；“暂不处理”保持 PENDING。明确的信息不足和无可靠匹配结论按确定性短语映射到锁定枚举。
- POC-03 新增 Windows 11 真实 Golden Dataset 质量验证器：复用 1,815 个百炼真实向量、PostgreSQL 18.6/pgvector Hybrid 检索、120/120 次 `qwen3-rerank` 和统一 DeepSeek AIService；加入可恢复缓存、严格引用约束及脱敏聚合诊断。
- POC-03 P03-A11~A13 首轮真实指标完成并判定 FAIL：Top-5 Recall 60.00%、分类准确率 14.17%、来源引用准确率 50.83%；保留门槛和本轮失败证据，登记 Golden 标签一致性风险及建议修复顺序。

### 兼容性

- 正式目标环境为 Windows 11、Windows Server 2025、Debian 13，均为 x86-64/AMD64。
- 当前仍处于 Phase 0 技术验证执行期，尚无可发布程序版本。

### Migration

- 无正式产品 Migration；POC-02 包含两版验证性 Alembic migration，用于验证空库和有数据 up/down，不进入正式数据模型基线。

### 验证结果

- 项目 Skill 结构校验通过。
- POC-01 本轮要求覆盖 2/2：Windows 11、Windows Server 2025 PASS；Debian 13 为 `DEFERRED_BY_USER`。
- POC-02 Windows 11 除“完全断网”外的功能验收项 PASS。
- POC-02 Windows Server 2025 全部验收项 PASS；20 组 Top-5 平均及最低 Recall 100%，备份恢复条数与 ID 校验和一致。
- POC-02 当前要求覆盖按例外处理完成：Windows 11 功能链 PASS、Windows Server 2025 完全断网功能链 PASS；Windows 11 断网重放与 Debian 13 为 `DEFERRED_BY_USER`。
- POC-03 Windows 11 P03-A11~A13 已执行：基础链路完整、越界引用 0，但三项真实质量门槛均 FAIL；POC-03 保持 `BLOCKED_QUALITY_GATE`，不进入下一 WBS。
- POC-05 Windows 11 功能链 PASS；Windows Server 2025 完全断网 8/8 PASS；扫描 PDF 三条 OCR 链在两端均为 5/5 术语召回。
- POC-05 Windows 11 真实方案库批次为 `PARTIAL_PASS`：当前支持格式 17/17 PASS，旧版 `.doc` 1 个不支持；该批次没有真实扫描 PDF，不形成真实扫描件准确率结论。
- POC-04 当前要求覆盖按例外处理完成：Windows 11、Windows Server 2025 功能链 PASS，两端确定性场景均为 11/11，真实 DeepSeek 文本/流式/结构化/401 全部通过；Debian 13 为 `DEFERRED_BY_USER`。
- POC-03 P0.09 候选准备 PASS：120 条候选覆盖 26/26 个可解析文档，全部保持 `PENDING_HUMAN_REVIEW`；正式 Golden Dataset 和三项质量指标尚未执行。
- POC-05 Windows 11 真实技术协议/合同批次为 `PARTIAL_PASS`：当前支持格式 9/9 PASS，含 5 个扫描 PDF、105 页和 45,145 个 OCR 行；9 个旧版 `.doc` 不支持。
- POC-03 人工评审工作簿生成验证通过：两张工作表均完成渲染检查，导出后回读成功，公式错误为 0；初始 120 条全部为 `PENDING`，尚未形成正式 Golden Dataset。
- POC-03 R2 初始生成验证为 25/25 单元测试通过、120 行全部 PENDING、0 个来源一致性问题、明细公式错误扫描为 0；P03-A04 真实 Embedding 探测与索引绑定 PASS。
- POC-03 R3 确认交互原型验证通过：30/30 单元测试通过，R2 技术页逐单元格差异为 0，主表含 120 个相对证据链接，本地定位器含 120 个候选锚点和 120 个原文件入口；状态为 `PASS_FOR_UX_REVIEW`，不代表 P03-A02 或正式交接模块通过。
- POC-03 当前 49/49 单元测试通过；P03-A08 HNSW 与 P03-A09 Hybrid 的 4 组 Top-5 平均/最低 Recall 均为 100%。
- POC-03 P03-A10 完成后 56/56 单元测试通过；Reranker 真实请求与三类降级场景均 PASS。
- POC-03 P03-A14 完成后 62/62 单元测试通过；统一 AIService 调用链和禁止 RAG 直连厂商的边界检查 PASS。
- POC-03 P03-A15 完成后 68/68 单元测试通过；除 P03-A02 及其阻塞的 P03-A11~A13 外，可独立执行的 Windows 11 验收项均已完成。
- POC-03 四类来源接入后 75/75 单元测试通过；R4 工作簿两张表均完成渲染检查，导出回读成功，公式错误为 0，120/120 证据链接和原文件入口已解析。
- POC-05 标准能力库批次 20/20 DOCX 解析 PASS、0 个 Schema 错误、20/20 原件不变；无效 `word/NULL` 关系回归用例通过。
- POC-03 更新后的 R4 含 120 条带实质性复核结论的“修改后确认”；严格导入为 120 条 APPROVED、0 个问题，正式 Golden Dataset 本地导出成功。覆盖审计包含 120 个唯一问题、29 份文档、四类来源和六类结果，82/82 单元测试与覆盖审计 PASS。
- 项目分析 R1 确认记录与包指纹一致；R2 调研执行工作簿 4/4 页签完成渲染和回读，公式错误 0，任务状态与决策状态交互回归 PASS；POC-03 全量 160/160 单元测试 PASS。

### 已知问题

- Phase 0 阻塞 PoC 尚未全部通过，禁止进入大规模正式业务开发。
- Debian 13 尚无可用验收环境，兼容性保持未验证；恢复 Debian 验证或发行时必须重新开启相关 Gate。
- POC-02 Windows 11 完全断网与 Debian 13 尚未验证；虽已按批准例外收口，仍不能宣称三平台全部 PASS。
- PostgreSQL 18.6 在 Windows 中文运行路径存在 `initdb` 编码失败；当前部署路径必须为纯 ASCII。
- POC-05 Windows 11 物理断网与 Debian 13 依据 `EXC-P0-004` 暂缓；真实扫描仅完成 15/105 页分层检查点审计，不等同于逐字符全量标注。当前状态为 `PASS_WITH_EXCEPTION`。
- 当前工作区依赖未提供打包 LibreOffice，POC-05 DOCX 样本未完成 DOCX 转 PNG 视觉检查；OOXML 结构解析已通过，Office 打开性留在 POC-06。
- POC-03 P03-A13 在现行 Top-5 Context 与唯一目标 Chunk 口径下的可达上限为 95.00%，低于 98%；需要人工决定修订低区分度问题/可接受引用集合或调整验收口径。
- POC-05 当前不支持旧版二进制 `.doc`；真实方案库中的 1 个文件未转换、未解析，是否纳入 P0 需单独确认。
- POC-04 Debian 13 尚未验证；虽已依据 `EXC-P0-003` 收口，仍不得声明 Debian 兼容或通过 Debian Release Gate。
- POC-03 旧 R1 的 109 条批准记录覆盖审计失败；当前 R2 虽有 120 条不同查询且用户已全部标记 APPROVED，但 75 条 SOLUTION 来源无锁定枚举映射，在通过完整 Gate 前不得运行或宣称 Top-5 Recall、分类准确率和引用准确率。
- POC-03 旧 R2/R3 仍作为历史证据保留；新 R4 四类候选不继承旧批准状态，120 条均须重新进行业务确认后才能进入 Golden Dataset。
- 两个本地资料库共 10 个旧版二进制 `.doc` 不受当前统一解析器支持，未自动转换或改写。
- R2 调研执行工作簿是 Phase 0 本地辅助成果，不是正式 Handover/Survey 业务模块；当前独立留出集真实质量复验的数据外发 Gate 保持不变。
