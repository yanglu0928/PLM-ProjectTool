# Architecture Freeze Candidate V1

## 基线标识

|字段|值|
|---|---|
|Architecture ID|`ARCH-CANDIDATE-V1`|
|状态|`CANDIDATE / AF-05_COMPLETE / NOT_GATE_2_FROZEN`|
|日期|2026-09-22|
|上游 Gate|Phase 0 Gate 1 `APPROVED`|
|正式编码|`BLOCKED_BY_GATE_2`|
|目标环境|Windows 11、Windows Server 2025、Debian 13；x86-64/AMD64|

本文件是 Architecture Freeze 的汇总候选，不替代实施方案 V2.1、各 ADR 或详细边界文档。Architecture、Core Data Model、Database Schema V1 和 API Contract V1 全部完成后，仍需用户在 Gate 2 正式确认；本候选不能单独授权业务编码。

## 输入与优先级

1. 用户最新明确变更与已批准 `EXC-P0-001`～`EXC-P0-007`。
2. 《PLM项目实施辅助工具软件开发实施方案 V2.1》。
3. 《AI开发总控指令与 Skill 规范 V1.1》。
4. Phase 0 总结与实际 PoC 证据。
5. ADR-001～ADR-009。
6. AF-01 模块边界、AF-02 Application Contract、AF-03 运行安全边界。

发生冲突时遵循：用户最新明确变更 > 正式锁定方案 > 已冻结 ADR/数据/API > 当前阶段设计 > AI 建议。合理推断和未验证事项不得描述为通过。

## 架构结论

- 第一版采用单服务器、模块化单体；一个 FastAPI 后端、独立 Worker、PostgreSQL 18/pgvector、本地文件存储和受控 Plugin 子进程。
- Vue 3 Web 只通过 REST/JSON 与 SSE 访问 API，不直连数据库、文件目录、AI Provider 或 Plugin 进程。
- 模块依赖固定为 `UI → API → Application Service → Domain → Repository / Gateway`。
- 跨模块只允许 Application Port、最小 Domain Event、TraceLink 和 DTO/Contract；禁止跨模块写表。
- AI、Retrieval、Plugin、Trace、Review、Project Authorization、Document/Evidence 各有唯一统一入口。
- AI 输出始终为建议；只有经业务规则、Evidence 和 ReviewService 人工确认后才能形成正式事实。
- 正式对象和文件保留历史版本，不允许覆盖；TraceLink 连接合同 → 调研 → 需求 → 原型 → 方案 → WBS。
- 客户运行时与 Developer Workbench 是不同信任区；License/插件签名私钥只存在开发者工作台。

## 系统上下文

```text
Project Users / DeploymentAdmin
              │ HTTPS deployment boundary
              ▼
        Vue 3 Web Frontend
              │ REST/JSON + SSE
              ▼
      FastAPI Modular Monolith
        │        │          │
        │        │          └─ ProviderAdapter ── External AI / Reranker
        │        └─ PostgreSQL Job/Outbox ← Worker Process
        │                                      │
        │                                      └─ PluginService → Python Plugin Process
        ├─ PostgreSQL 18 + pgvector
        └─ Local File Storage

Developer Workbench
  └─ signed License / signed Plugin / public key ──→ Customer Runtime
```

外部 AI/Reranker 只通过统一 Adapter 访问。客户资料外发仍按目的地、用途和最小载荷逐轮取得明确授权；历史授权不自动扩展到新批次或新目的地。

## 模块与数据所有权

### 客户运行模块

|分组|模块|唯一职责摘要|
|---|---|---|
|Platform|platform|Composition Root、Config、UoW、异常、健康|
|Platform|auth|用户名密码、Server Session、CSRF、账户状态|
|Platform|project|项目、成员、角色、Project Authorization|
|Platform|workflow|阶段、Gate、Checklist、状态迁移|
|Platform|document|逻辑文件、不可变版本、文件元数据、解析状态|
|Platform|evidence|证据资格、定位和正式绑定|
|Platform|review|送审、处理人、锁定、退回、升版重审|
|Platform|trace|跨版本 TraceLink|
|Platform|audit|不可由普通用户删除的业务审计|
|Platform|jobs|PostgreSQL Job/Outbox、租约、重试、取消|
|AI/RAG|ai|AI Gateway、Provider/Model、Prompt、Task/Invocation|
|AI/RAG|rag|Chunk、Index、Embedding、Hybrid/Rerank/Context|
|Capability|capability|GLOBAL 标准能力基线和版本|
|Business|handover|交接分析、差异/缺失/风险与行动项|
|Business|survey|调研版本、轮次、问答与结论|
|Business|requirement|需求包、版本、来源、关系与验收标准|
|Business|prototype|原型包、版本、模板和需求映射|
|Business|solution|参考方案、章节版本和结构化专项|
|Business|plan|计划、WBS、FS 依赖、里程碑|
|Output|output|OutputContext、输出任务与制品编排|
|Extension|plugin|签名包、Manifest、兼容性和子进程生命周期|
|Security|license|License 导入、验签、机器绑定、有效期与状态|

独立信任区 `developer_workbench` 负责 License 签发、Plugin 签名和发行材料，不访问客户运行数据库或客户项目资料。

实体名是 Data Model 输入，不代表字段、表或外键已经冻结。

## 允许依赖矩阵

每行只能依赖“允许目标”列列出的公开 Application Port；未列出的模块依赖全部禁止。

|来源模块|允许目标|
|---|---|
|platform|无业务模块|
|audit|platform|
|auth|platform、audit|
|project|auth、audit|
|jobs|platform、audit|
|license|audit|
|document|project、jobs、audit|
|evidence|project、document、audit|
|review|project、audit|
|trace|project、audit|
|workflow|project、evidence、review、audit|
|ai|jobs、audit|
|rag|project、document、ai、jobs、audit|
|capability|document、review、trace、audit|
|handover|project、document、evidence、ai、rag、review、trace、audit|
|survey|project、document、evidence、ai、rag、review、trace、audit|
|requirement|project、evidence、ai、rag、review、trace、audit|
|prototype|project、requirement、document、review、trace、audit|
|solution|project、requirement、prototype、evidence、ai、rag、review、trace、audit|
|plan|project、solution、review、trace、audit|
|plugin|jobs、audit|
|output|project、document、solution、plan、plugin、trace、audit|
|developer_workbench|不依赖客户运行模块；只输出签名制品和公钥|

### 强制禁止

- UI → 数据库、文件系统、Provider、Plugin stdio。
- 业务模块 → 厂商 SDK/URL、pgvector SQL、subprocess。
- Plugin → 数据库、AI Key、License 私钥、Provider 直连。
- AI/RAG → 自动修改 Requirement、Solution、Plan 等正式对象。
- 下游模块 → 直接更新上游表或覆盖上游版本。
- 客户运行时 → Developer Workbench 私钥或任意第三方插件。

## 统一 Application Contract

|Port / Service|Owner|架构职责|
|---|---|---|
|ProjectAuthorizationService|project|默认拒绝，校验主体、项目、角色、资源归属和动作|
|AIService|ai|TaskSpec、Provider 路由、Prompt/Schema、建议态输出|
|RetrievalService|rag|GLOBAL/PROJECT 隔离、Hybrid/Rerank、Context 和 Index 生命周期|
|PluginService|plugin|签名/Manifest 校验、stdio 子进程、超时与错误隔离|
|TraceService|trace|跨版本关系，不复制正文|
|ReviewService|review|送审锁定、1～N 处理人、退回、升版重审|
|DocumentService|document|受权文件版本与内容流，不泄露绝对路径|
|EvidenceService|evidence|不可变版本定位、资格和正式绑定|

改变状态的 Application Command 必须携带 `trace_id`、`actor_id`、PROJECT 场景的 `project_id`、可重试操作的 `idempotency_key`，以及版本化对象修改时的 `expected_version`。具体语言签名与 REST 端点留待 API Contract V1。

## 关键运行视图

### 受权请求

```text
Request
 → Trace Context
 → License Guard（受许可业务）
 → Server Session
 → CSRF（Cookie 状态改变请求）
 → Deployment / Project Role
 → ProjectId + Resource Ownership
 → Resource State / Review Lock / Expected Version
 → Application Port
 → Audit
```

任一层失败即停止。License 有效、DeploymentAdmin 或 Worker SystemActor 均不能绕过其余授权与审计。

### 文件进入知识与证据链

```text
Isolated Upload
 → size/type/signature validation
 → streaming SHA-256
 → STAGED metadata
 → atomic promote
 → immutable DocumentVersion
 → Parse Job
 → Chunk / Evidence Locator
 → Project-authorized RAG Index
```

文件不作为静态目录公开，业务模块不保存物理路径。解析、OCR 和转换使用受控临时区，完整校验后才发布结果。

### AI 建议正式化

```text
Authorized Business Input
 → RetrievalService
 → Context Bundle + Evidence
 → AIService / PromptVersion / OutputSchema
 → SUGGESTION / NOT_FORMAL_FACT
 → Human Review
 → Domain Owner creates new formal version
 → Trace + Audit
```

POC-03 的分类 48.00% 和引用 74.00% 仍为 FAIL；人工确认是强制风险控制，不替代 Gate 3/UAT 的新独立留出集质量验证。

### 长任务与恢复

```text
API short transaction
 → Domain state + Job/Outbox + Audit
 → Worker atomic lease / heartbeat
 → Application/Gateway Port
 → staged result + validation
 → atomic publish
 → Domain Event / Audit
```

交付语义为至少一次，所有消费者必须幂等。Job Payload 只存引用和策略版本，不存文件正文、Prompt 全文、Cookie 或 Secret 明文。

### 输出与 Plugin

```text
Approved Solution / Plan
 → OutputService builds minimal OutputContext
 → PluginService verifies signature/manifest/OS/API version
 → JSON-RPC over stdio child process
 → isolated artifact staging
 → validation + hash
 → Document/OutputArtifact registration
 → Trace + Audit
```

独立进程是故障和凭据隔离，不是任意第三方代码的强安全沙箱。

## 数据与版本原则

- PostgreSQL 18 是事务、Session、Job/Outbox、Audit、配置、Secret 密文、业务元数据和 pgvector 的唯一数据库。
- 文件正文保存在本地文件系统；数据库保存元数据与受控 Storage Locator。
- PROJECT 数据必须包含并校验 ProjectId；GLOBAL 仅用于明确授权的标准能力等公共基线。
- 一个激活 Embedding Index 只绑定一个 Provider、Model、Dimension 和 IndexVersion；换模新建索引并全量重建。
- 正式 Document、Evidence、Requirement、Prototype、Solution、Plan 和附件保留历史版本；修订创建新版本。
- TraceLink 只保存稳定对象/版本引用和关系，不复制业务正文。
- Audit 由 audit 模块唯一拥有；普通用户无物理删除能力，更正通过追加事件。
- Secret 密文与主材料分离；业务、Job、Event、Log 和 Plugin Context 只传 `secret_ref`。

## 部署视图

### V1 单服务器

```text
One x86-64 Server
├─ Web Frontend
├─ FastAPI Modular Monolith
├─ Worker Process
├─ PostgreSQL 18 + pgvector
├─ Local File Storage
├─ Plugin Host / signed child processes
├─ Config + encrypted Secret Store
└─ License + trusted-time state
```

- 最低基线：4 Core / 8 GB RAM / 100 GB SSD；不运行本地模型。最终容量仍由性能与文档量验证。
- Windows 默认根：`C:\PLMTool\`；POC-02 中文路径限制解除前，PostgreSQL 运行与数据路径使用纯 ASCII。
- Debian 默认根：`/opt/plmtool/`；权限和服务管理必须使用 Linux 原生最小权限模型。
- 内部文本、JSON、日志和 stdio 协议统一 UTF-8；外部工具显式处理 Windows 代码页差异。
- Office 不是服务器依赖；DOCX/PPTX 使用标准 OOXML 生成。
- PostgreSQL 不直接暴露互联网；浏览器不能直接访问 data/plugins/license 目录。

### 安装、备份与升级

- 基线备份：PostgreSQL、data、config、license；Secret 主材料通过独立受保护流程纳入灾备。
- V1 不提供自动备份，实施团队执行并验证恢复。
- 升级：人工备份 → 维护模式 → 停止新任务/收敛 Worker → 离线升级 → Migration → 启动 → 健康检查。
- 失败由实施团队按备份人工恢复，不允许未验证的强制前滚。

## 质量属性与控制

|属性|主要控制|后续验证 Gate|
|---|---|---|
|安全|Server Session、HttpOnly/Secure Cookie、CSRF、默认拒绝 Project Authorization、SecretRef、签名包|Gate 2 / Security / UAT|
|数据隔离|PROJECT 强制 ProjectId；GLOBAL 显式授权；RAG/文件/Trace 重复校验|Gate 2 / Gate 3|
|一致性|单模块事务、Outbox、幂等、乐观版本、文件原子发布|Schema/API Freeze / Integration|
|可恢复性|持久化 Job 租约、阶段检查点、人工备份恢复|Integration / Release|
|可追溯性|Evidence Locator、TraceLink、Prompt/Index/Input 版本、Audit|Gate 3～Gate 7|
|可移植性|路径抽象、UTF-8、Adapter、三平台发行矩阵|Release Gate|
|可维护性|模块 Owner、公开 Port、ADR、禁止跨表写入|Gate 2 / Code Review|
|AI 质量|建议态、双来源 Context、Evidence Selector、强制 Review、新留出集|Gate 3 / UAT|
|合规|Ghostscript AGPL 公开源码与许可证 Gate、客户数据外发授权|Release / 每次外发|

## 风险与批准例外

|ID|事实/风险|当前控制|关闭条件|
|---|---|---|---|
|EXC-P0-001|POC-01 Debian 13 未验证|不得外推 Windows 结果|Debian 发行前恢复依赖/OCR/PDF 验证|
|EXC-P0-002|Windows 11 物理断网、POC-02 Debian 未验证|保留 Server 断网证据和平台边界|对应 Release Gate 前恢复验证|
|EXC-P0-003|POC-04 Debian AI Gateway 未验证|Provider Adapter 与平台无关 Contract|Debian Release 前实机验证|
|EXC-P0-004|Windows 11 物理断网和 Debian OCR 未验证；真实扫描只抽样 75 点|PaddleOCR 主链、Tesseract 仅辅助、关键字段人工确认|Release/UAT 扩展实际样本|
|EXC-P0-005|POC-06/08/09 Debian 未验证|保持路径/stdio/MAC 抽象，不声明通过|Debian Release 前恢复验证|
|EXC-P0-006|POC-03 分类 48%、引用 74% FAIL|R11、建议态、Evidence、强制 Review|Gate 3/UAT 新独立留出集达到 90%/98%|
|EXC-P0-007|Server 2025 未执行 Office 实开|Office 非服务器依赖；Windows 11 实开 + Server OOXML/Hash|客户端 Office 回归；若服务器装 Office 则重开评审|
|R-AF-001|Ghostscript AGPL 发行合规尚未完成|ADR-002，当前只允许私有开发验证|公开完整对应源码、兼容许可证和第三方声明|
|R-AF-002|Plugin 不是强恶意代码沙箱|只允许开发者签名包、最小环境和单次工作区|若开放第三方插件，需 L3 与强隔离新 PoC|
|R-AF-003|SecretKeyProvider 的 Windows/Linux 实现未选定|密文/主材料分离 Contract|Release 安全设计与恢复验证|
|R-AF-004|V1 为手工备份|维护模式、固定备份集、恢复校验|Release 演练通过；不承诺自动备份|
|R-AF-005|Windows PostgreSQL 中文运行路径失败|安装/数据目录使用纯 ASCII|上游/本项目重新验证后才能解除|

以上均已有 Owner 或后续 Gate，不存在未登记且会阻塞 Data Model Freeze 的架构分歧。

## 明确非目标

V1 不引入：微服务、Redis、Kafka、RabbitMQ、独立向量库、本地大模型、SSO、手机 App、第三方插件市场、客户插件 SDK、AI 原型执行沙箱、WebSocket、FTP、COM、ActiveX、自定义 TCP、对象存储或自动备份。

未经 Change Request，不得以“将来可能需要”为由预埋上述运行依赖。

## 延后但不阻塞 Architecture Candidate 的细节

|事项|归属后续阶段|
|---|---|
|实体字段、聚合、关系、生命周期与不变量|Core Entity / Data Model Freeze|
|物理表名、类型、外键、唯一约束、索引和 Migration|Database Schema V1|
|REST 路径、DTO 字段、分页、错误码和 SSE 事件|API Contract V1|
|密码哈希库/参数、Cookie/CSRF 名称|基础工程安全设计，需满足本候选 Contract|
|Windows Service / Linux systemd 包装|Release/Installation 设计|
|SecretKeyProvider 平台实现和密钥恢复|Release 安全设计|
|Audit 保留期、归档与受权导出|Data/Release 设计|
|Job 租约时长、批量大小、退避参数|基础工程与性能验证|

这些是实现或下游冻结细节，不构成选择另一总体架构的理由。

## Traceability

|候选结论|详细来源|
|---|---|
|模块、Owner、允许/禁止依赖|`module-boundaries-v1-candidate.md`、ADR-003|
|Application Port、Event、错误语义|`application-contracts-v1-candidate.md`|
|认证、文件、Secret、Job、日志、部署|`security-file-job-runtime-boundaries-v1-candidate.md`|
|AI/RAG|ADR-004、POC-03、POC-04|
|Plugin|ADR-005、POC-08|
|License|ADR-006、POC-09|
|Job/Outbox|ADR-007|
|文件存储|ADR-008、POC-05/06|
|质量替代控制|ADR-009、EXC-P0-006|
|三平台与合规|ADR-001、ADR-002、Phase 0 例外|

## AF-05 验收

- 架构形态、22 个客户运行模块和独立 Developer Workbench 信任区完整：PASS。
- 依赖矩阵为显式允许列表，跨模块写表、厂商直连和越权路径明确禁止：PASS。
- 同步请求、文件、AI 正式化、Job、Output/Plugin 五类关键运行视图完整：PASS。
- 单服务器三平台部署、备份、升级、Secret 与 License 边界完整：PASS。
- 七项 Phase 0 例外和五项持续风险均有控制与关闭 Gate：PASS。
- ADR-001～009、AF-01～AF-03 和 Phase 0 证据可反向追溯：PASS。
- 未提前冻结实体字段、Schema 或 REST API，未开始正式业务编码：PASS。
- 没有未登记、不可裁决且会阻塞 Data Model Freeze 的架构分歧：PASS。

## 结论与下一步

`ARCH-CANDIDATE-V1` 满足 Architecture Freeze 候选条件，AF-01～AF-05 完成。项目进入 Core Entity / Data Model Freeze；Architecture 仍等待 Gate 2 与 Data Model、Database Schema V1、API Contract V1 一并正式确认。
