
---

# 0. 文档定位

本方案是当前项目进入正式开发之前的执行基线，用于直接指导：

**架构设计 → PoC验证 → 数据设计 → API设计 → 开发拆分 → 测试 → 打包 → 部署 → 验收。**

本方案不继续讨论产品方向，不重新设计已经确认的业务规则。

## 0.1 结论状态定义

### 【已验证】

指已经通过前期需求访谈，由产品负责人明确确认、锁定的业务规则或技术选型。

这里的“验证”表示：

**需求/决策层面已确认。**

不代表已经运行代码验证。

### 【合理推断】

基于现有要求，为保证系统可维护、可扩展而形成的架构设计。

必须在设计评审后冻结。

### 【待验证】

存在环境、第三方组件、算法或兼容性不确定性。

必须经过：

**PoC → 测试记录 → Pass/Fail → 架构决策**

才能进入正式开发。

---

# 第一部分：现状技术基线

## 1.1 软件总体架构

**状态：【合理推断】**

目标采用：

> **模块化单体 Modular Monolith + 独立AI/RAG能力层 + 子进程插件体系。**

第一版不采用微服务。

原因：

- 单套部署并发≤20人；
    
- 单服务器部署；
    
- 客户要求简单部署；
    
- Windows Server 2025第一版重点环境；
    
- Debian 13需要兼容；
    
- 微服务会显著增加部署、监控、网络和升级复杂度。
    

---

## 1.2 客户端技术栈

**状态：【已验证：技术选型】**

### Web客户端

- Vue 3
    
- TypeScript
    
- Vite
    

用途：

- PC浏览器；
    
- 手机浏览器；
    
- 响应式完整业务操作。
    

### 桌面业务客户端

**不建设。**

### 开发者工作台

Windows本地程序。

具体桌面GUI框架尚未冻结。

**状态：【待验证/待选型】**

---

## 1.3 服务端技术栈

**状态：【已验证：技术选型】**

- Python 3.13.x
    
- FastAPI
    
- Uvicorn
    

Python 3.13 为已确认主语言。

---

## 1.4 数据库

**状态：【已验证：选型；工程兼容待PoC】**

- PostgreSQL 18
    
- pgvector
    

截至当前，PostgreSQL 18仍为正式当前大版本，官方文档当前维护版本为18.6。

不单独部署：

- Milvus
    
- Qdrant
    
- Elasticsearch向量服务
    

第一版优先保持单服务器简单部署。

---

## 1.5 ORM与Migration

**状态：【已验证：选型】**

- SQLAlchemy 2.x
    
- Alembic
    

SQLAlchemy 2.0当前官方文档版本已到2.0.54。

---

## 1.6 文件存储

**状态：【合理推断】**

第一版：

> 本地文件系统 + PostgreSQL文件元数据。

不引入MinIO等独立对象存储服务。

逻辑目录：

```text
data/
├─ global/
├─ projects/
│  └─ {project_id}/
├─ generated/
├─ temp/
└─ plugin-data/
```

数据库负责：

- FileId
    
- ProjectId
    
- Version
    
- SHA-256
    
- MIME
    
- Size
    
- Uploader
    
- CreateTime
    
- StoragePath
    

文件不能通过静态目录直接访问，必须经过API权限检查。

---

## 1.7 API通信

**状态：【合理推断】**

业务API：

> REST + JSON

统一：

```text
/api/v1/
```

AI流式返回：

> SSE

第一版不依赖WebSocket。

---

## 1.8 配置

**状态：【合理推断】**

分三层：

```text
.env / yaml
        ↓
系统数据库配置
        ↓
加密Secret
```

建议：

- 非敏感运行配置：YAML；
    
- 系统业务配置：数据库；
    
- API Key / 私钥等：加密Secret Store。
    

---

## 1.9 日志

**状态：【合理推断】**

三类日志必须分开：

### Application Log

运行、异常、性能。

### Integration Log

AI、OCR、插件、文件转换。

### Audit Log

业务审计：

- 用户；
    
- 项目；
    
- 时间；
    
- 对象；
    
- 操作；
    
- 操作前/后关键状态。
    

Audit Log写数据库。

普通用户不能删除。

---

## 1.10 身份认证

**状态：【已验证：业务规则】**

仅：

> 内置用户名 + 密码。

第一版不做：

- LDAP；
    
- OAuth企业登录；
    
- 钉钉；
    
- 企业微信；
    
- AD/SSO。
    

---

## 1.11 权限体系

**状态：【已验证】**

部署级：

> DeploymentAdmin

项目级固定角色：

- ProjectManager
    
- ImplementationMember
    
- CustomerManager
    
- CustomerMember
    

约束：

- 普通用户只属于一个项目；
    
- 用户名在部署范围内唯一；
    
- 一个项目用户只有一个业务角色；
    
- 一个用户只有一个业务部门；
    
- DeploymentAdmin可管理全部项目。
    

---

## 1.12 插件机制

**状态：【已验证设计；IPC待PoC】**

第一版：

> 独立子进程 + JSON-RPC/stdin/stdout。

插件：

- 不能直接访问数据库；
    
- 通过Plugin API取得数据；
    
- 异常不得影响主进程；
    
- 独立版本；
    
- 可启用/禁用；
    
- 可独立升级；
    
- 客户不能安装第三方插件；
    
- 第一阶段不开放SDK。
    

第一版不做：

> 插件容器隔离。

---

## 1.13 第三方组件

已确认：

- PyMuPDF
    
- pdfplumber
    
- PaddleOCR
    
- Tesseract
    
- OCRmyPDF
    
- python-docx
    
- python-pptx
    
- Aspose.Diagram / 模板驱动VSDX（P1）
    

PaddleOCR官方当前安装文档注明其核心包支持Python 3.8+，相关扩展依赖支持Python 3.9+；但Python 3.13及离线依赖组合仍必须在本项目环境中实际PoC。

---

## 1.14 外部系统

第一版必须集成：

### AI

首批实际验收：

> DeepSeek

架构需兼容：

- OpenAI-compatible
    
- Anthropic Messages
    
- Gemini Native
    
- 后续Provider Adapter
    

### Reranker

第一版：

> 可配置外部API。

不要求客户服务器本地运行AI模型。

---

## 1.15 部署结构

**状态：【已验证】**

第一版：

```text
一台服务器
├─ Web Frontend
├─ FastAPI
├─ Worker
├─ PostgreSQL
├─ pgvector
├─ File Storage
└─ Plugin Host
```

不要求数据库分离部署。

---

## 1.16 服务器环境

**状态：【已验证】**

第一版正式目标：

- Windows Server 2025
    
- Debian 13
    
- x86-64 / AMD64
    

Debian 13当前仍是Debian stable系列。

最低配置：

> 4C / 8GB / 100GB SSD

前提：

> 不运行本地大模型。

最低配置最终仍须性能PoC确认。

---

## 1.17 网络

支持：

- 内网；
    
- 公网。
    

公网网络、安全、域名、防火墙由实施团队负责。

AI外部接口是否可访问取决于客户网络。

---

## 1.18 License

**状态：【已验证设计；实现待PoC】**

签名：

> Ed25519

机器标识：

> 指定MAC地址 → 标准化 → SHA-256。

License Payload：

```text
license_id
customer
machine_fingerprint
valid_from
valid_to
issue_time
schema_version
```

开发者使用私钥签名。

客户程序只包含公钥。

---

## 1.19 升级

**状态：【已验证】**

- 完全离线；
    
- 管理员主动执行；
    
- 支持声明范围内跨版本升级；
    
- 升级前实施团队人工备份；
    
- 不提供自动回滚；
    
- 升级失败由实施团队恢复；
    
- Plugin支持单独升级。
    

---

## 1.20 核心业务模块

已经锁定：

```text
项目交接
→ 需求调研
→ 需求分析
→ 原型设计
→ 方案输出及评审
→ 计划制定
```

并存在公共：

- 用户；
    
- 项目；
    
- 阶段；
    
- 文件；
    
- 证据；
    
- 版本；
    
- Review；
    
- Trace；
    
- AI；
    
- RAG；
    
- Plugin；
    
- Audit；
    
- License。
    

---

# 第二部分：建设目标与Scope

## 2.1 总体建设目标

建立一套：

> **面向PLM实施全过程、私有化部署、AI辅助、结构化事实驱动的项目实施平台。**

核心数据链：

```text
合同/协议
↓
项目交接
↓
调研
↓
正式需求
↓
解决方案
↓
原型
↓
正式方案
↓
项目计划
```

所有正式成果必须可追溯。

---

# 2.2 第一阶段必须实现

P0 Scope：

1. 用户与权限；
    
2. 项目；
    
3. 六阶段Workflow；
    
4. 文件；
    
5. 版本；
    
6. Evidence；
    
7. Review；
    
8. Audit；
    
9. TraceLink；
    
10. Standard Capability；
    
11. AI Gateway；
    
12. RAG；
    
13. OCR；
    
14. 项目交接；
    
15. 调研问卷；
    
16. 需求分析；
    
17. 原型；
    
18. 方案；
    
19. Word；
    
20. PPT；
    
21. 流程图PNG/JPEG；
    
22. WBS；
    
23. License；
    
24. Plugin；
    
25. Windows离线安装；
    
26. Debian离线安装；
    
27. 离线升级；
    
28. 开发者工作台。
    

---

# 2.3 P1

- VSDX；
    
- Aspose.Diagram；
    
- 更多输出插件；
    
- 更丰富原型模板；
    
- 更多AI供应商实测；
    
- 插件SDK。
    

---

# 2.4 当前明确不做

- SaaS；
    
- 微服务；
    
- Redis集群；
    
- Kafka/RabbitMQ；
    
- 第三方插件市场；
    
- 客户插件开发；
    
- SSO；
    
- 手机App；
    
- 离线Web编辑；
    
- 项目计划资源负荷；
    
- 工时填报；
    
- 关键路径；
    
- 持续进度跟踪；
    
- AI原型执行沙箱；
    
- 自动代码提交；
    
- 本地LLM。
    

---

# 第三部分：目标架构

## 3.1 总体架构

```text
┌─────────────────────────────┐
│ Vue 3 Web                   │
│ PC / Mobile                 │
└──────────────┬──────────────┘
               │ REST / SSE
               ▼
┌─────────────────────────────────────────────┐
│ FastAPI Application                         │
│                                             │
│ Platform Core                               │
│ ├─ Auth                                     │
│ ├─ Project                                  │
│ ├─ Workflow                                 │
│ ├─ Document                                 │
│ ├─ Evidence                                 │
│ ├─ Review                                   │
│ ├─ Trace                                    │
│ └─ Audit                                    │
│                                             │
│ Business Modules                            │
│ ├─ Capability                              │
│ ├─ Handover                                │
│ ├─ Survey                                  │
│ ├─ Requirement                             │
│ ├─ Prototype                               │
│ ├─ Solution                                │
│ └─ Plan                                    │
│                                             │
│ AI Platform                                 │
│ ├─ AI Gateway                              │
│ ├─ Provider Adapter                        │
│ ├─ Prompt Registry                         │
│ ├─ Embedding                               │
│ ├─ Retrieval                               │
│ └─ Reranker                                │
│                                             │
│ Job Engine                                  │
└──────┬─────────────────┬────────────────────┘
       │                 │
       ▼                 ▼
PostgreSQL           Plugin Manager
+ pgvector               │
                         ├─ Word process
File Storage             ├─ PPT process
                         └─ Flow process
```

---

# 3.2 模块依赖原则

业务模块禁止：

- 直接调用DeepSeek；
    
- 直接执行向量SQL；
    
- 直接调用插件进程；
    
- 直接访问其他模块内部表。
    

统一通过：

```text
AIService
RetrievalService
PluginService
TraceService
ReviewService
```

---

# 3.3 数据流

```text
Upload
↓
Document
↓
Parse
↓
OCR(if required)
↓
Structured Document
↓
Chunk
↓
Embedding
↓
pgvector
↓
Hybrid Retrieval
↓
Reranker
↓
LLM
↓
Structured Result
↓
Human Confirm
↓
Business Entity
```

---

# 3.4 文件流

```text
Upload
↓
Temp validation
↓
Hash
↓
Metadata
↓
Persistent storage
↓
Parser
↓
Business reference
↓
Version
```

---

# 3.5 权限校验

每次请求：

```text
Session
↓
License
↓
Account
↓
Project
↓
Role
↓
Resource ownership
↓
Artifact state
↓
Operation
```

---

# 3.6 异常处理

统一：

```text
DomainException
ValidationException
AuthenticationException
AuthorizationException
AIProviderException
RAGException
PluginException
FileException
LicenseException
SystemException
```

输出：

```json
{
  "code": "...",
  "message": "...",
  "trace_id": "..."
}
```

---

# 第四部分：正式技术选型

## 4.1 主语言

技术领域：语言  
推荐方案：Python  
版本：3.13.x  
状态：【已验证选型】  
选择原因：AI/RAG/OCR生态强；FastAPI成熟；文档生成生态丰富。  
风险：部分第三方二进制依赖对3.13支持需PoC。  
备选：Python 3.12，仅当P0-01失败才触发架构变更。

---

## 4.2 前端

推荐：

> Vue 3 + TypeScript + Vite

状态：【已验证选型】

---

## 4.3 后端

推荐：

> FastAPI + Uvicorn

状态：【已验证选型】

---

## 4.4 数据库

推荐：

> PostgreSQL 18

状态：

【已验证选型；离线安装待验证】

---

## 4.5 ORM

推荐：

> SQLAlchemy 2.x + Alembic

---

## 4.6 Vector

推荐：

> pgvector

原因：

不增加独立服务。

---

## 4.7 PDF

推荐：

> PyMuPDF主 + pdfplumber辅助。

PyMuPDF：

- 快速文本；
    
- 页坐标；
    
- 图片。
    

pdfplumber：

- 表格；
    
- 布局辅助。
    

---

## 4.8 OCR

推荐：

> PaddleOCR主 + Tesseract/OCRmyPDF辅助。

扫描PDF为第一版必须功能。

状态：【待PoC】

---

## 4.9 Word/PPT

推荐：

- python-docx
    
- python-pptx
    

状态：【待正式复杂文档PoC】

---

## 4.10 VSDX

P1：

- 模板驱动；
    
- Aspose.Diagram。
    

不自己实现完整Visio OOXML。

---

## 4.11 API

REST JSON。

版本：

```text
/api/v1
```

AI流：

SSE。

---

## 4.12 Authentication

建议：

> Server Session + HttpOnly Cookie。

状态：【合理推断】

不要将长期JWT保存localStorage。

---

## 4.13 Permission

固定Role + Resource Authorization。

---

## 4.14 Logging

推荐：

> structlog / Python logging JSON格式。

【待基础工程冻结】

业务Audit独立数据库表。

---

## 4.15 Config

建议：

> pydantic-settings + YAML/.env。

Secret单独加密。

---

## 4.16 Cache

第一版：

> 进程内Cache。

不引入Redis。

---

## 4.17 Job

第一版：

> PostgreSQL Job Table + Worker Process。

不引入Celery broker/RabbitMQ。

---

## 4.18 Plugin

> Python独立子进程 + JSON-RPC over stdio。

状态：【已确认设计，待PoC】

---

## 4.19 License

- Ed25519
    
- MAC
    
- SHA-256
    

---

# 第五部分：功能分解

## 5.1 子系统

```text
01 Platform
02 AI/RAG
03 Capability
04 Handover
05 Survey
06 Requirement
07 Prototype
08 Solution
09 Plan
10 Output
11 License
12 Developer Workbench
```

---

## 5.2 功能规格表

|ID|功能|输入|处理|输出|权限|异常|验收|
|---|---|---|---|---|---|---|---|
|SYS-001|登录|用户名密码|Hash验证|Session|全员|错误/锁定|正确鉴权|
|SYS-002|项目创建|ProjectDTO|创建Project|Project|Admin|Code重复|创建成功|
|SYS-003|项目用户|UserDTO|唯一性+Project绑定|User|Admin|Username重复|不能跨项目|
|SYS-004|部门|Department|CRUD|Department|Admin|被引用|单用户单部门|
|SYS-005|阶段|Checklist|Gate Check|Stage|PM|条件不足|禁止推进|
|DOC-001|上传|File|校验/Hash|Document|Project|损坏|可追溯|
|DOC-002|正式证据|Attachment|Formalize|Evidence|PM|无文件|版本化|
|AI-001|Provider|配置|注册Adapter|Provider|Admin|Key错误|DeepSeek通过|
|AI-002|Prompt|Prompt|Version|Template|Admin|Schema错误|可回滚版本|
|RAG-001|Index|Document|Chunk/Embed|Index|System|Embed失败|可检索|
|HAN-001|能力基线|标准文档|AI提取|Capability|PM|AI失败|人工确认|
|HAN-002|差异分析|合同等|RAG+AI|Gap|PM/member|无匹配|有证据|
|HAN-003|待办闭环|Gap|补充/复核|Closed|PM|阻塞|阶段门槛|
|SUR-001|部门识别|Handover|AI|Candidates|PM|错识别|人工确认|
|SUR-002|问卷生成|Scope|AI|Questionnaire|PM/member|AI失败|PM分发|
|SUR-003|答卷|Answers|Validate|Response|Assignee|重复提交|原记录保留|
|SUR-004|AI复核|Response|Analyze|Followup|PM/member|AI失败|不自动分发|
|SUR-005|部门结论|Responses|AI+人工|Conclusion|PM|冲突|客户确认|
|REQ-001|Candidate|Survey|AI提取|Candidate|PM/member|重复|Trace存在|
|REQ-002|正式需求|Candidates|合并拆分|Requirement|PM|冲突|PM确认|
|REQ-003|能力匹配|Requirement|RAG|Match|PM|低置信|人工确认|
|REQ-004|解决方案|Requirement|AI建议+人工|Solution|PM/member|无结论|每需求必有|
|REQ-005|客户确认|Version|Review|Confirmed|PM|退回|全确认|
|PRO-001|原型范围|Requirement|Decide|Scope|PM|-|可不做|
|PRO-002|原型描述|Spec|Validate|Spec|PM/member|缺字段|完整|
|PRO-003|原型生成|Spec+Template|AI|Prototype|PM/member|AI失败|可预览|
|SOL-001|参考方案|Files|Parse|Structure|PM/member|Parse失败|6级|
|SOL-002|目录融合|Reference+Facts|AI|Outline|PM/member|冲突|PM确认|
|SOL-003|章节映射|Facts|RAG|Mapping|PM/member|无来源|Trace|
|SOL-004|章节生成|Mapping|AI|Draft|PM/member|AI失败|人工确认|
|SOL-005|流程|Process|Node/Edge|Process|PM/member|无效图|可输出|
|PLAN-001|参考计划|Excel/CSV|Parse|WBS Ref|PM/member|格式错误|导入|
|PLAN-002|AI WBS|Solution|AI|WBS|PM/member|超6级|可修改|
|PLAN-003|计划|WBS|工期/FS/负责人|Plan|PM/member|循环依赖|可导出|
|OUT-001|Word|Context|Plugin|DOCX|Authorized|Plugin失败|Office打开|
|OUT-002|PPT|Context|Plugin|PPTX|Authorized|Plugin失败|Office打开|
|OUT-003|Flow|Process|Plugin|PNG/JPEG|Authorized|Render失败|正确|
|LIC-001|Request|MAC|SHA|Request|Admin|无MAC|文件生成|
|LIC-002|License|Request|Ed25519|License|Developer|私钥错误|验签|
|PLG-001|Plugin|Package|Verify|Installed|Admin|不兼容|主服务不受影响|

---

# 第六部分：数据模型

## 6.1 Platform

### Project

PK：

UUID

字段：

- code
    
- name
    
- status
    
- current_stage
    

生命周期：

Active → Archived。

---

### User

字段：

- id
    
- username
    
- password_hash
    
- project_id
    
- department_id
    
- role
    
- enabled
    

Admin可以不绑定具体项目。

---

## 6.2 Documents

### Document

逻辑文件。

### DocumentVersion

实际版本。

### Evidence

正式证据引用。

关系：

```text
Document
1:N
DocumentVersion

Evidence
N:M
StageChecklist
```

---

## 6.3 AI

### AIProvider

### AIModel

### PromptTemplate

### AITask

### AIInvocation

记录：

- provider；
    
- model；
    
- prompt_version；
    
- input_hash；
    
- output；
    
- tokens；
    
- latency；
    
- error。
    

---

## 6.4 RAG

### DocumentChunk

- document_version_id
    
- project_id/global
    
- text
    
- metadata
    
- page
    
- section
    

### EmbeddingIndex

记录：

- embedding_model_id
    
- dimension
    
- version
    

规则：

> 一个Index绑定一个Embedding Model。

更换模型：

> 建新Index，重新Embedding。

---

## 6.5 Capability

```text
CapabilityBaseline
→ BaselineVersion
→ CapabilityItem
```

Scope：

GLOBAL。

项目引用具体Version。

---

## 6.6 Handover

```text
HandoverAnalysis
→ AnalysisItem
→ ActionItem
```

类型：

- Gap
    
- Missing
    
- Conflict
    
- Risk
    
- Scope
    
- NeedConfirm
    

---

## 6.7 Survey

```text
Survey
→ SurveyVersion
→ Round
→ Question
→ Assignment
→ Response
→ Answer
```

结论：

```text
DepartmentConclusion
ModuleConclusion
```

---

## 6.8 Requirement

```text
RequirementPackage
→ Requirement
→ RequirementVersion
```

关联：

- RequirementSource
    
- RequirementRelation
    
- AcceptanceCriterion
    
- RequirementSolution
    

---

## 6.9 Prototype

```text
PrototypePackage
Prototype
PrototypeVersion
PrototypeTemplate
RequirementPrototypeLink
```

---

## 6.10 Solution

```text
ReferenceSolution
SolutionOutline
SolutionOutlineVersion
SolutionSection
SolutionSectionVersion
```

结构化专项：

- ProcessModel
    
- InterfaceSpec
    
- MigrationSpec
    
- PermissionDesign
    

---

## 6.11 Plan

```text
Plan
WbsItem
WbsDependency
Milestone
ReferencePlan
```

WbsItem：

- level <= 6
    
- planned_start
    
- planned_finish
    
- actual_start
    
- actual_finish
    
- owner_id
    
- duration
    
- status
    

依赖：

仅FS。

---

## 6.12 Trace

统一：

```text
TraceLink
```

字段：

```text
source_type
source_id
target_type
target_id
relation_type
```

这是核心公共模型。

---

# 第七部分：接口设计

## 7.1 API规则

```text
/api/v1/{resource}
```

统一返回：

```json
{
  "data": {},
  "trace_id": "..."
}
```

错误：

```json
{
  "error": {
    "code": "REQ_001",
    "message": "..."
  },
  "trace_id": "..."
}
```

---

## 7.2 核心接口

|API|Method|URL|调用方|权限|
|---|---|---|---|---|
|Login|POST|`/auth/login`|UI|public|
|Me|GET|`/auth/me`|UI|login|
|Projects|POST|`/projects`|UI|Admin|
|Users|POST|`/projects/{id}/users`|UI|Admin|
|Upload|POST|`/projects/{id}/documents`|UI|Project|
|Parse|POST|`/documents/{id}/parse`|UI|PM/member|
|Capability Parse|POST|`/capability-baselines/{id}/parse`|UI|PM/member|
|Handover|POST|`/projects/{id}/handover/analyze`|UI|PM/member|
|Survey Generate|POST|`/surveys/generate`|UI|PM/member|
|Survey Assign|POST|`/surveys/{id}/assign`|UI|PM|
|Survey Submit|POST|`/assignments/{id}/submit`|UI|assignee|
|Requirement Analyze|POST|`/requirements/analyze`|UI|PM/member|
|Requirement Match|POST|`/requirements/{id}/match`|UI|PM/member|
|Prototype Generate|POST|`/prototypes/generate`|UI|PM/member|
|Solution Parse|POST|`/solution-references/parse`|UI|PM/member|
|Solution Generate|POST|`/solution-sections/{id}/generate`|UI|PM/member|
|WBS Generate|POST|`/plans/generate`|UI|PM/member|
|Output|POST|`/outputs`|UI|authorized|
|Review|POST|`/reviews`|UI|PM|
|Review Decision|POST|`/reviews/{id}/decision`|UI|reviewer|
|Trace|GET|`/trace/{type}/{id}`|UI|Project|
|Plugins|GET|`/admin/plugins`|UI|Admin|
|License|POST|`/admin/license/import`|UI|Admin|

---

## 7.3 AI外部接口

通过：

```text
IAIProvider
```

第一版实测：

> DeepSeek

不得在业务模块写：

```python
deepseek_client...
```

---

## 7.4 Plugin IPC

【待PoC】

协议：

> JSON-RPC over stdio。

调用：

```text
FastAPI
↓
Plugin Manager
↓
subprocess
↓
JSON request
↓
Plugin
↓
JSON response
```

---

## 7.5 不使用接口

第一版无：

- FTP；
    
- COM；
    
- ActiveX；
    
- CAD SDK；
    
- 消息队列；
    
- WebSocket；
    
- 自定义TCP。
    

---

# 第八部分：Phase 0 PoC

## POC-01 Python 3.13依赖矩阵

目标：

证明全部核心库可在目标OS离线部署。

环境：

- Windows Server 2025
    
- Debian 13
    

验证：

- FastAPI
    
- Uvicorn
    
- SQLAlchemy
    
- psycopg
    
- PyMuPDF
    
- pdfplumber
    
- PaddleOCR
    
- Tesseract
    
- OCRmyPDF
    
- python-docx
    
- python-pptx
    
- pgvector客户端
    

成功：

全部安装、import、最小功能运行。

失败：

单库替代；

只有在核心库无兼容方案时才评估Python降至3.12。

---

## POC-02 PostgreSQL18 + pgvector

验证：

- 两OS；
    
- 完全离线；
    
- init；
    
- Alembic；
    
- pgvector；
    
- HNSW；
    
- 备份恢复。
    

成功：

10万级测试向量稳定检索。

---

## POC-03 PLM RAG

Golden Dataset：

100~200条。

输入：

- 标准能力；
    
- 合同；
    
- 技术协议；
    
- 调研。
    

链：

```text
Parser
→ Chunk
→ FTS
→ Vector
→ Reranker
→ DeepSeek
```

目标初值：

- Top5 Recall ≥95%
    
- 分类准确率≥90%
    
- 来源引用准确率≥98%
    

指标最终以真实数据PoC修订。

---

## POC-04 AI Gateway

实测：

> DeepSeek。

同时实现协议Adapter框架。

验证：

- text；
    
- streaming；
    
- structured JSON；
    
- timeout；
    
- retry；
    
- invalid key；
    
- 429；
    
- Schema failure。
    

成功：

业务代码无DeepSeek依赖。

---

## POC-05 Document + OCR

覆盖：

- DOCX；
    
- PPTX；
    
- XLSX；
    
- CSV；
    
- 文本PDF；
    
- 扫描PDF。
    

成功：

输出统一ParsedDocument，并保留页码/章节/表格来源。

---

## POC-06 Word/PPT

测试：

- 100页Word；
    
- 50页PPT；
    
- 中文；
    
- 表格；
    
- 图片；
    
- 流程；
    
- 多级章节。
    

验收：

Microsoft Office正常打开，无损坏。

---

## POC-07 VSDX

已降P1。

不阻塞正式开发。

---

## POC-08 Plugin Host

验证：

- crash；
    
- timeout；
    
- invalid JSON；
    
- incompatible version；
    
- independent update。
    

成功：

FastAPI不崩溃。

---

## POC-09 License

链：

```text
MAC
→ normalization
→ SHA-256
→ License Payload
→ Ed25519
```

验证：

- 正常机器；
    
- MAC变化；
    
- 过期；
    
- 篡改License；
    
- 错公钥；
    
- 系统时间。
    

成功：

非法授权全部拒绝。

---

# 第九部分：开发实施阶段

## Phase 0 技术验证

前置：

技术基线确认。

产出：

- 8项P0 PoC；
    
- P1 VSDX记录；
    
- PoC报告；
    
- ADR。
    

验收：

所有阻塞PoC Pass或明确替代方案。

---

## Phase 1 架构冻结与基础工程

任务：

- Repo；
    
- Python monorepo；
    
- Vue；
    
- FastAPI；
    
- SQLAlchemy；
    
- Alembic；
    
- logging；
    
- config；
    
- API contract；
    
- module convention。
    

交付：

可运行空壳系统。

---

## Phase 2 Platform Core

任务：

- Auth；
    
- Project；
    
- User；
    
- Department；
    
- Document；
    
- Evidence；
    
- Workflow；
    
- Review；
    
- Trace；
    
- Audit；
    
- License。
    

验收：

完整模拟项目可以走通权限与阶段。

---

## Phase 3 AI/RAG Platform

任务：

- Provider；
    
- DeepSeek；
    
- Prompt；
    
- Job；
    
- Parser；
    
- OCR；
    
- Chunk；
    
- pgvector；
    
- Hybrid；
    
- Rerank。
    

验收：

任意业务模块均可通过统一接口进行RAG/AI。

---

## Phase 4 项目交接

实现完整交接闭环。

---

## Phase 5 需求调研

实现部门、问卷、Round、AI补充、结论。

---

## Phase 6 需求分析

实现需求包、需求、匹配、解决方案、确认。

---

## Phase 7 原型

实现本地模板→AI生成→预览→评审。

---

## Phase 8 方案

实现参考方案→目录→章节→流程→正式方案。

---

## Phase 9 Output Plugin

实现：

- Word；
    
- PPT；
    
- PNG/JPEG。
    

---

## Phase 10 Plan

实现：

- Excel/CSV参考；
    
- AI WBS；
    
- 6级；
    
- FS；
    
- 负责人；
    
- 里程碑；
    
- 甘特图；
    
- Excel导出。
    

---

## Phase 11 Integration & QA

跨阶段Trace、权限、异常、AI、插件、性能。

---

## Phase 12 Packaging

- Windows离线包；
    
- Debian离线包；
    
- Upgrade；
    
- Plugin Update；
    
- Developer Workbench。
    

---

# 第十部分：开发WBS

## 10.1 Phase 0

|WBS|任务|前置|输入|输出|验收|风险|
|---|---|---|---|---|---|---|
|P0.01|创建Python3.13 Windows测试环境|无|Server2025|venv|Python正常|中|
|P0.02|创建Python3.13 Debian环境|无|Debian13|venv|Python正常|中|
|P0.03|构建离线wheel仓库|P0.01|requirements|wheelhouse|断网安装|高|
|P0.04|PaddleOCR兼容测试|P0.03|扫描PDF|OCR结果|中文准确|高|
|P0.05|PostgreSQL18 Windows安装|无|installer|DB|offline|高|
|P0.06|pgvector Windows|P0.05|extension|vector|SQL通过|高|
|P0.07|PostgreSQL Debian|无|deb bundle|DB|offline|中|
|P0.08|pgvector Debian|P0.07|package|vector|SQL通过|中|
|P0.09|创建RAG Gold Set|无|PLM资料|dataset|100+|高|
|P0.10|实现Hybrid retrieval|P0.06|GoldSet|metrics|Recall|高|
|P0.11|DeepSeek Adapter|无|API|adapter|Schema|高|
|P0.12|OCR→RAG链|P0.04/10|PDF|Result|端到端|高|
|P0.13|Plugin subprocess|无|protocol|host|crash隔离|高|
|P0.14|MAC读取|无|NIC|fingerprint|稳定|中|
|P0.15|Ed25519签名|P0.14|payload|license|验签|中|
|P0.16|DOCX生成|无|sample|docx|Office|中|
|P0.17|PPTX生成|无|sample|pptx|Office|中|

---

## 10.2 Platform

|WBS|任务|前置|输出|
|---|---|---|---|
|1.01|定义模块目录规范|Phase0|architecture|
|1.02|FastAPI app factory|1.01|backend|
|1.03|Vue app shell|1.01|frontend|
|1.04|SQLAlchemy session|1.02|persistence|
|1.05|Alembic migration|1.04|migration|
|1.06|Error contract|1.02|error model|
|1.07|JSON log|1.02|logging|
|1.08|TraceId middleware|1.06|tracing|
|1.09|Config/Secret|1.02|config|

后续业务模块按照前述功能ID逐一转成Story和Task，不允许以“开发需求模块”等宽任务进入Sprint。

---

# 第十一部分：测试

## 11.1 Unit

目标：

核心Domain规则≥80%覆盖。

权限、Review、Stage Gate、License：

≥90%。

---

## 11.2 API

覆盖：

- happy path；
    
- validation；
    
- duplicate；
    
- lock；
    
- project isolation；
    
- expired license。
    

---

## 11.3 Functional

按照六阶段建立完整UAT Scenario。

至少一条：

```text
创建项目
→交接
→调研
→需求
→原型
→方案
→计划
```

完整跑通。

---

## 11.4 Integration

重点：

- OCR→RAG；
    
- RAG→DeepSeek；
    
- Requirement→Prototype；
    
- Requirement→Solution；
    
- Solution→WBS；
    
- Solution→Plugin。
    

---

## 11.5 Exception

必须模拟：

- AI不可用；
    
- Reranker不可用；
    
- DB断开；
    
- 文件损坏；
    
- Plugin crash；
    
- License过期；
    
- 磁盘不足。
    

---

## 11.6 Permission

建立：

> Role × API × Project关系矩阵。

跨项目访问：

**0容忍。**

---

## 11.7 Performance

目标：

20并发。

初始验收目标：

- 非AI GET P95 ≤500ms；
    
- 普通写接口 P95 ≤1s；
    
- 长AI任务提交≤1s返回JobId。
    

---

## 11.8 Installation

要求：

断网环境。

Windows和Debian各执行：

- clean install；
    
- restart；
    
- license；
    
- create project；
    
- AI配置；
    
- OCR；
    
- output。
    

---

## 11.9 Upgrade

测试：

- 受支持旧版本；
    
- 不支持版本；
    
- migration error；
    
- plugin update。
    

---

# 第十二部分：部署

## 12.1 开发环境

推荐：

Windows 11 x64。

工具：

- Python 3.13；
    
- Node；
    
- PostgreSQL；
    
- Git；
    
- VS Code / PyCharm。
    

---

## 12.2 测试

必须至少：

### Windows

Windows Server 2025。

### Linux

Debian 13。

---

## 12.3 Production

最低：

- 4 Core
    
- 8GB
    
- 100GB SSD
    
- x86-64
    

建议：

- 8C
    
- 16GB
    
- SSD
    

文档量大：

建议32GB。

---

## 12.4 Windows目录

```text
C:\PLMTool\
├─ app
├─ runtime
├─ plugins
├─ config
├─ data
├─ logs
└─ license
```

---

## 12.5 Linux目录

```text
/opt/plmtool/
├─ app
├─ runtime
├─ plugins
├─ config
├─ data
├─ logs
└─ license
```

---

## 12.6 Backup

由实施团队负责：

- PostgreSQL；
    
- data；
    
- config；
    
- license。
    

不提供自动备份。

---

## 12.7 Upgrade

```text
人工备份
↓
维护模式
↓
离线升级
↓
Migration
↓
启动
↓
健康检查
```

失败：

由实施团队人工恢复。

---

# 第十三部分：风险

|ID|风险|条件|影响|概率|等级|预防|处理|
|---|---|---|---|---|---|---|---|
|R01|Python3.13库不兼容|OCR等无wheel|阻塞安装|中|P0|PoC|替代版本/库|
|R02|Windows pgvector困难|extension构建问题|RAG阻塞|中|P0|PoC|替代安装方式|
|R03|RAG误匹配|专业语义接近|错方案|高|P0|Hybrid+Rerank|人工确认|
|R04|OCR准确率低|扫描差|数据错误|中|高|Paddle+辅助OCR|人工校验|
|R05|DeepSeek不可达|客户网络|AI不可用|中|高|Provider config|提示/重试|
|R06|Plugin崩溃|输出异常|输出失败|中|中|subprocess|kill/restart|
|R07|Word/PPT版式不足|python库限制|交付质量|中|高|PoC模板|定制plugin|
|R08|License MAC漂移|网卡变化|无法使用|中|高|明确选MAC|新授权|
|R09|磁盘增长|大量文档|服务故障|中|中|容量说明|扩容|
|R10|项目越权|API缺Project校验|数据泄露|低|极高|Resource auth|测试阻断|
|R11|Prompt升级导致结果漂移|Prompt变化|结果不同|高|中|Prompt版本|回归测试|
|R12|Embedding更换|Vector不兼容|搜索失效|中|中|新Index|全量重建|
|R13|AI输出Schema失败|模型不稳定|Job失败|中|中|schema/retry|人工重试|
|R14|双平台离线包依赖复杂|native dependency|安装失败|高|高|wheel/deb bundle|PoC|
|R15|参考方案内容污染新项目|直接复用|错承诺|中|高|AI+人工校验|Trace检查|

---

# 第十四部分：正式开发前待确认问题

目前不存在尚未确认的P0业务问题。

剩余P0全部转换为：

> **技术验证项。**

## P0

### P0-T01

Python3.13全部依赖能否双平台离线安装。

验证：

POC-01。

### P0-T02

PostgreSQL18+pgvector Windows/Debian。

POC-02。

### P0-T03

RAG是否达到质量门槛。

POC-03。

### P0-T04

DeepSeek AI Gateway。

POC-04。

### P0-T05

扫描PDF OCR。

POC-05。

### P0-T06

Plugin subprocess IPC。

POC-08。

### P0-T07

MAC+Ed25519 License。

POC-09。

### P0-T08

正式Word/PPT质量。

POC-06。

---

## P1

开发对应模块前确认：

1. Word Plugin第一版正式模板；
    
2. PPT Plugin第一版正式模板；
    
3. 原型模板第一版页面规范；
    
4. Flow Plugin视觉规范；
    
5. 六阶段核心Checklist具体初始化数据；
    
6. 最大上传文件大小；
    
7. Excel WBS字段规范；
    
8. VSDX是否启动开发；
    
9. Aspose许可证采购。
    

---

## P2

开发过程中确认：

- 页面细节；
    
- 默认排序；
    
- 按钮文案；
    
- 非核心报表；
    
- Dashboard指标；
    
- 主题视觉。
    

---

# 第十五部分：最终执行路线图

## 第一天

第一天不开发业务页面。

执行：

```text
1 创建GitHub Private Repository
2 创建develop/main分支
3 建立docs/architecture
4 建立docs/poc
5 创建Python 3.13环境
6 创建Windows Server 2025测试VM
7 创建Debian 13测试VM
8 建requirements-poc
9 开始POC-01依赖矩阵
10 建PoC验证登记表
```

当天产物：

```text
Repository
Architecture目录
PoC目录
Windows VM
Debian VM
Dependency Matrix V0.1
```

---

## 第一阶段

只做：

> Phase 0。

顺序：

```text
Python依赖
↓
PostgreSQL/pgvector
↓
Document/OCR
↓
DeepSeek Gateway
↓
RAG
↓
Plugin
↓
License
↓
Word/PPT
```

VSDX延后。

---

# 可以并行

### Track A

```text
Python依赖
PostgreSQL
pgvector
```

### Track B

```text
DeepSeek Adapter
AI Gateway
```

### Track C

```text
OCR
Document Parser
```

### Track D

```text
Plugin IPC
License
```

### Track E

```text
Word/PPT
```

RAG需要A+B+C后进入最终端到端验证。

---

# Phase 0完成标准

必须：

1. Windows依赖PASS；
    
2. Debian依赖PASS；
    
3. PostgreSQL/pgvector PASS；
    
4. OCR PASS；
    
5. DeepSeek Gateway PASS；
    
6. RAG达到验收指标；
    
7. Plugin Crash隔离PASS；
    
8. License PASS；
    
9. Word/PPT交付级样例PASS。
    

全部满足以后：

> **Phase 0 = Complete**

---

# 什么时候可以正式编码

准确说：

可以在Phase 0期间写：

> PoC代码。

但不能正式大规模实现业务模块。

只有Phase 0通过之后执行：

```text
Architecture Freeze
↓
Core Entity Freeze
↓
Database Schema V1
↓
API Contract V1
```

完成设计评审之后：

> **正式进入Phase 1编码。**

---

# 正式开发真实顺序

```text
Phase 0
技术PoC
        ↓
Architecture Freeze
        ↓
Data Model Freeze
        ↓
API Contract Freeze
        ↓
Phase 1
基础工程
        ↓
Phase 2
Platform Core
        ↓
Phase 3
AI/RAG
        ↓
Phase 4
项目交接
        ↓
Phase 5
需求调研
        ↓
Phase 6
需求分析
        ↓
Phase 7
原型
        ↓
Phase 8
正式方案
        ↓
Phase 9
输出Plugin
        ↓
Phase 10
WBS
        ↓
Phase 11
系统集成测试
        ↓
Phase 12
双平台离线发行
        ↓
UAT
        ↓
Release Build
        ↓
License
        ↓
客户部署
```

---

# 最终交付物

正式交付必须至少包含：

```text
Windows Server 2025离线发行包
Debian 13离线发行包
数据库初始化包
数据库升级脚本
Plugin包
License Request Tool
License文件
安装工具
升级工具
配置模板
管理员手册
安装手册
升级手册
用户手册
Release Notes
Third Party License清单
验收测试报告
PoC报告
```

源码：

**不交付客户。**

源码保存在：

> 本地Git + GitHub Private Repository。

---

# 最终决策结论

当前项目已经满足：

**业务范围冻结条件。**

当前项目已经满足：

**技术选型冻结条件。**

当前项目还没有满足：

**正式开发启动条件。**

剩余唯一前置工作是：

> **执行Phase 0技术PoC。**

Phase 0通过以后，不再继续扩大技术讨论，直接执行：

> **架构冻结 → 数据模型冻结 → API冻结 → 正式编码。**