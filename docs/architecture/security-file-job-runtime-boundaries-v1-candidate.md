# 安全、文件、任务与运行边界 V1 候选

## 状态

`CANDIDATE / AF-03_COMPLETE / NOT_FROZEN`

本文件冻结 Architecture Candidate 中的信任边界、调用顺序和失败关闭原则。它不固定密码哈希库、ORM 字段、数据库表名、REST 端点、Cookie 名称或操作系统服务管理器；这些实现细节分别在基础工程、Data Model、Schema V1、API Contract V1 和 Release 设计中落实。

## 信任区与主体

|信任区|允许持有|禁止持有或直接访问|
|---|---|---|
|浏览器 / Vue 3|HttpOnly Session Cookie、页面级 CSRF 材料、已授权 DTO|持久化密码凭据、API Key、数据库连接、本地绝对路径、Plugin stdio|
|FastAPI 进程|请求上下文、Application Port、短生命周期解密结果|License 私钥、跨模块 Repository、向前端返回 Secret/traceback|
|Worker 进程|Job 租约、受控系统主体、Application Port|用户 Session Cookie、绕过授权的数据库写入、永久明文 Secret|
|PostgreSQL 18|业务状态、服务器端 Session、文件元数据、Job/Outbox、Audit、加密 Secret 密文|License 私钥、文件正文|
|本地文件存储|文件内容、生成制品、受控临时文件、插件执行工作区|用户可控物理路径、公开静态目录|
|Plugin 子进程|最小 OutputContext、单次执行目录、受控 Plugin API|数据库连接、AI Key、License 私钥、宿主完整环境变量、任意业务表|
|客户运行时 License 区|License 文档、公钥、可信时间状态|Ed25519 私钥|
|Developer Workbench|License/插件签名私钥、签发记录|客户运行数据库与客户项目资料|

Developer Workbench 与客户运行时必须物理分离。Plugin 独立进程提供故障隔离和凭据最小化，不等同于安全沙箱；第一版未采用容器或强制网络沙箱，不得对外宣称可安全运行任意第三方插件。

## 请求认证与授权链

### 固定顺序

```text
Request
  → Trace / 安全请求上下文
  → License Guard（仅对受许可业务操作）
  → Server Session 认证
  → CSRF 校验（Cookie 认证的状态改变请求）
  → Deployment / Project Role 校验
  → ProjectId + Resource Ownership 校验
  → Resource State / Review Lock / Expected Version 校验
  → Application Port
  → Audit
```

任何一层失败均停止后续业务操作。License 有效不代表用户已授权；`DeploymentAdmin` 的全局能力也不允许绕过 Session、License、对象状态、Review Lock 或 Audit。

### 认证边界

- 第一版只支持部署内唯一用户名 + 密码，不引入 LDAP、OAuth、AD/SSO、钉钉或企业微信登录。
- 密码只保存带独立盐的自适应单向哈希；不得保存明文、可逆密文或写入日志。具体算法与参数在基础工程安全实现中选定并形成可升级配置。
- Session 使用服务端不透明会话，状态由 `auth` 模块拥有并持久化；浏览器只持有 HttpOnly Cookie。生产环境 Cookie 必须启用 `Secure`，并显式设置 SameSite、Path 和生命周期。
- 登录成功、注销、账户停用、密码变更和管理员撤销必须使相关 Session 立即或在受控短窗口内失效；Session 标识必须轮换以阻止固定攻击。
- 不将长期 JWT、Session 标识或 Secret 保存到 `localStorage` / `sessionStorage`。
- 登录、恢复和其他高风险入口必须支持限速与失败审计；不引入 Redis，首版限速使用单实例进程内控制与数据库安全记录。多实例扩展不在 V1 Scope。

### CSRF 与外部错误

- 所有使用 Cookie 认证且会改变状态的请求必须同时通过 CSRF Token 校验；安全方法不得产生业务状态变化。
- 生产部署校验可信 Origin/Host，并拒绝不受信来源；具体 Token 传输名称留给 API Contract。
- 对普通用户，资源不存在与资源无权限返回相同外部语义，防止枚举；内部通过 `trace_id` 与 Audit 区分原因。
- Python traceback、SQL、物理路径、Session、Secret 和内部 Provider 响应不得返回前端。

### 权限主体与 PROJECT 隔离

- 部署级角色固定为 `DeploymentAdmin`；项目级角色固定为 `ProjectManager`、`ImplementationMember`、`CustomerManager`、`CustomerMember`。
- 普通用户只属于一个项目，一个项目用户只有一个业务角色和一个业务部门；用户名在部署范围唯一。
- PROJECT 请求的 `project_id` 必须由服务端根据目标资源和当前主体交叉验证，不能只信任 URL、表单或模型输出中的值。
- Worker 使用受控 `SystemActor` 执行，但必须继承原始 `actor_id`、`project_id`、`trace_id` 和授权目的；SystemActor 不能作为跨项目通配符。
- AI/RAG、文件、Evidence、Review、Trace、Plugin 和 Output 均重复执行对应 Project Authorization，不能依赖上游“已经检查”的口头假设。

### License 恢复面

- 未登录可访问的端点只允许最小存活检查和登录，不泄露版本、路径、用户或项目状态。
- License 无效时，已认证 `DeploymentAdmin` 仍可访问最小 License 查询/导入与诊断面；其余受许可业务操作失败关闭。
- License Guard 后仍必须执行 Auth、Role、Project、Resource State 与 Audit 链。

## 文件生命周期与访问边界

### 逻辑存储区

```text
data/
├─ global/                 # GLOBAL 标准能力与受控公共资料
├─ projects/{project_id}/  # PROJECT 文件内容
├─ generated/              # 已登记的生成制品
├─ temp/                   # 隔离上传、解析与转换临时区
└─ plugin-data/            # 按插件/执行隔离的工作区
```

物理路径由 Storage Adapter 根据不可猜测的内部标识生成。原始文件名只作为经过规范化的元数据保留，不参与路径拼接；绝对路径、`..`、设备名、符号链接/重解析点越界和大小写碰撞均失败关闭。

### 上传与持久化

```text
受控临时区接收
  → 大小 / 扩展名 / MIME / 文件特征校验
  → 流式 SHA-256 与重复策略判断
  → 创建 STAGED 元数据
  → 同文件系统原子提升到最终存储区
  → 提交不可变 DocumentVersion
  → 创建解析 Job
  → Parser / Evidence / RAG 通过 DocumentService 读取
```

- 上传大小和允许类型由部署配置与业务用途共同限制；扩展名、客户端 MIME 不能作为唯一依据。
- 文件写入先进入隔离临时区，校验失败不得进入正式目录或触发 Parser。
- 文件正文保存在本地文件系统；PostgreSQL 保存 `FileId`、`ProjectId`、Version、SHA-256、MIME、Size、Uploader、CreateTime 和受控 Storage Locator。
- 数据库失败、原子提升失败或 Hash 不一致时必须转入可恢复/可清理状态，不能留下可被业务引用的“半完成版本”。
- 正式 DocumentVersion 和 OutputArtifact 不物理覆盖；修订创建新版本，历史引用保持可解析。
- 临时文件仅由受控清理 Job 按状态和保留策略删除；活动 Job、审计证据和正式版本不得被临时清理命中。

### 文件读取与生成

- 文件不得挂载为公开静态目录；所有下载、预览、解析和证据定位先经过 Session、Project/Global 授权、资源状态与用途检查。
- 下游模块只保存 `document_id` / `document_version_id` / Evidence Locator，不保存或返回本地绝对路径。
- `DocumentService.open_authorized_content` 返回受控流或短生命周期句柄；调用结束后关闭，不把路径传给浏览器。
- Parser、OCR、转换器和 Plugin 只获得单次执行所需的最小输入副本/流及隔离输出目录；生成结果经校验、Hash 和 `document`/`output` 登记后才能成为可访问制品。
- GLOBAL 文件只能由明确的全局授权导入；PROJECT 文件必须落入对应项目范围。跨项目复制必须形成新的授权命令、文件版本与 Audit，不允许共享同一可写路径。

### 跨平台文件规则

- 代码使用平台路径抽象，不硬编码 `\`、`/`、盘符或大小写行为；保存到数据库的是 Storage Locator，不是客户端路径。
- 内部文本、JSON、日志与进程协议统一使用 UTF-8；调用外部工具时显式处理 stdout/stderr 编码，不依赖中文 Windows 当前代码页。
- Windows 默认部署根为 `C:\PLMTool\`；在 POC-02 的中文路径限制解除前，PostgreSQL 运行与数据路径必须使用纯 ASCII 路径。用户文件名可包含中文，但物理存储名使用内部标识。
- Linux 默认根为 `/opt/plmtool/`；目录权限按最小运行身份配置。不得把 Windows ACL、重解析点或大小写假设直接外推到 Debian。

## 配置与 Secret 边界

|类别|存储位置|示例|访问规则|
|---|---|---|---|
|Bootstrap / 非敏感运行配置|YAML、部署环境|监听地址、目录、日志级别|启动时读取；可进入受控发行模板|
|系统业务配置|PostgreSQL|Provider 策略、限额、功能开关|经 ConfigPort、权限和 Audit 修改|
|Secret|加密 Secret Store|AI/Reranker API Key、集成凭据|业务与 Job 只持 `secret_ref`；仅 Provider/Integration Adapter 在调用瞬间解密|
|签名私钥|Developer Workbench|Ed25519 License/插件签名私钥|绝不进入客户服务器、Git、日志、备份或发行包|

- Secret 密文与加密主材料必须分离。主材料由部署外部的 `SecretKeyProvider` 提供，不与数据库密文、普通 YAML 或源代码一起保存；具体 Windows/Linux 保护实现进入 Release 安全设计。
- `.env` 只允许开发或安装引导使用，不作为生产 Secret 的可交付明文仓库；真实 `.env`、API Key、密码和私钥不得提交 Git。
- API、Domain Event、Job Payload、Outbox、Audit、Application/Integration Log 和 Plugin Context 只传 `secret_ref` 或脱敏标识，不传明文。
- 解密结果限制在单次外部调用的内存作用域，不缓存到进程内通用 Cache，不写临时文件；错误消息只记录 Provider、配置版本和脱敏凭据标识。
- Secret 创建、替换、启停和访问失败必须审计；查询界面永不回显完整值。轮换产生新 Secret 版本，旧版本按受控策略停用，不原地改写审计历史。

## Job、Outbox 与 Worker 边界

### 交付语义

- 第一版固定使用 PostgreSQL Job Table + 独立 Worker Process，不引入 Celery Broker、Redis、RabbitMQ、Kafka 或自定义 TCP。
- Job/Outbox 采用至少一次交付；精确一次不作为承诺。所有可重试写操作必须有 `idempotency_key`，消费者以 Job/Event 标识和业务版本共同去重。
- API 只在短事务中提交业务状态、Job/Outbox 和 Audit，不在请求事务内执行 OCR、Embedding、模型调用、文件转换或插件长任务。
- Worker 通过数据库原子领取租约；租约包含所有权、过期与心跳语义。进程崩溃后过期租约可回收，但同一有效租约不能被两个 Worker 同时完成。

### Job 生命周期

候选语义为：`PENDING → RUNNING → SUCCEEDED / FAILED / CANCELLED`，并支持 `RETRY_WAIT`、`CANCEL_REQUESTED` 和达到策略上限后的终止失败。状态字段和表名留待 Data Model/Schema 冻结。

- RetryPolicy 区分可重试和不可重试错误，采用有上限的次数、退避和抖动；认证失败、Schema 错误、越权、签名错误等不得盲目重试。
- 取消为协作式：停止新的外部调用，在安全检查点退出；已提交的正式版本、Audit 和不可逆外部结果不得伪装为已回滚。
- Job Payload 只保存对象引用、版本、策略版本和最小参数，不保存文件正文、Prompt 全文、Secret、Cookie 或客户资料副本。
- 长任务按阶段提交检查点；每个阶段输出先进入暂存区，完整校验后再原子发布，失败结果不可被正式业务引用。
- Worker 只能调用公开 Application Port / Gateway Port，不直接写其他模块表；Job Owner 负责结果状态，目标业务 Owner 负责正式状态迁移。
- 部署进入维护模式时停止接收新 Job，等待或安全取消活动任务、停止 Worker，再执行备份和 Migration。

## 日志、审计与隐私

### 三类记录

|类型|用途|最小内容|禁止内容|
|---|---|---|---|
|Application Log|运行、异常、性能、健康|时间、级别、组件、trace_id、安全错误码、耗时|密码、Cookie、Token、文件正文、Prompt/响应正文、客户字段、traceback 对外输出|
|Integration Log|AI、OCR、Plugin、文件转换|集成类型、Provider/模型或工具版本、trace_id、Job/Invocation ID、耗时、重试、脱敏结果|API Key、完整请求/响应、Plugin stdio 原文、绝对路径|
|Audit Log|业务与安全审计|actor、project、时间、对象/版本、动作、结果、关键前后状态、trace_id|Secret 明文、密码哈希、Session 标识、文件正文|

AIInvocation、解析结果和正式业务对象是受权业务数据，不因“不得写日志”而丢失；它们按所属模块的数据权限和保留规则保存，不能复制到普通日志。

### Audit 强制点

- 登录成功/失败、注销、账户/角色/项目成员变更。
- License 导入、验签结果、机器/时间拒绝和状态变化。
- 文件上传、版本创建、下载/预览授权拒绝、生成制品发布。
- Secret 创建、轮换、停用和访问失败；不记录明文值。
- AI/RAG 调用、索引激活、Review/Gate、正式化、跨项目拒绝。
- Plugin 安装、签名/兼容检查、启停、调用失败。
- Job 创建、取消、终止失败和管理员重试。

Audit 写 PostgreSQL，由 `audit` 模块唯一拥有；普通用户无删除能力，其他模块不得直接更新 Audit 表。更正通过追加事件表达。保留期、归档与受权导出在 Data/Release 设计中明确，但不得提供物理覆盖历史的普通业务接口。

## 运行单元与部署边界

```text
Browser
  → Web Frontend
  → FastAPI modular monolith
       ↔ PostgreSQL 18 + pgvector
       ↔ Local File Storage
       → External AI / Reranker via approved adapters
       → PostgreSQL Job/Outbox
             ← Worker Process
                  → Plugin Host → one or more isolated Plugin subprocesses

Developer Workbench ── signed artifacts/public keys only ──→ Customer Runtime
```

### 进程职责

|运行单元|职责|约束|
|---|---|---|
|Web Frontend|静态 UI、REST/JSON 与 SSE 客户端|不直连数据库、文件目录或外部 AI|
|FastAPI|认证授权、同步 Application Port、SSE、提交 Job|不执行不可控长任务，不启动任意插件入口|
|Worker|领取 Job，执行 Parser/OCR/AI/RAG/Output 编排|与 API 分进程；使用相同 Contract、授权上下文和 Audit|
|PostgreSQL/pgvector|事务数据、Session、Job/Outbox、Audit、向量|只向受控本机/内网运行身份开放，不直接暴露互联网|
|Local File Storage|不可变文件版本、临时区、生成物|API/Worker 运行身份最小权限；浏览器不可直访|
|Plugin Host / Process|验证开发者签名与 Manifest，stdio 调用|最小环境、超时/终止、单次工作区；故障不得拖垮 API|

- 单服务器是 V1 正式拓扑；API 与 Worker 是同一产品的不同进程，不拆分为微服务。
- Plugin 子进程继承经白名单构造的环境，执行目录限制在单次工作区；主机在 timeout/crash 后回收整个进程树并清理可清理暂存物。
- Plugin 若声明外部依赖，必须在 Manifest、安装验收和管理员配置中明确。由于 V1 不承诺强安全沙箱，插件仍只允许安装开发者签名包，不开放第三方插件市场或客户自开发 SDK。
- Office 不是服务器运行依赖；DOCX/PPTX 由标准 OOXML 生成。Windows Server 2025 未完成 Office 实开，不能据 Windows 11 结果宣称 Server Office 兼容。
- Debian 13 仍是正式目标，但 Phase 0 实机验证已批准暂缓；当前设计必须保持路径、权限、进程和 UTF-8 可移植，不能写成“Debian 已验证”。

## License 与可信时间状态

- 客户侧只保存 License、公钥和受限可信时间状态；MAC 由显式选择后规范化并 SHA-256，License 以 Ed25519 公钥验签。
- 可信时间状态通过 `TrustedTimeStatePort` 原子保存最近成功时间和必要完整性信息，文件/记录权限仅授予运行身份；系统时间明显回拨时失败关闭并审计。
- License 私钥和插件签名私钥只存在 Developer Workbench。客户备份、诊断包、日志和数据库导出不得包含私钥。
- License、MAC 或可信时间拒绝只返回分类型安全错误，不回显完整机器指纹、签名材料或内部状态路径。

## 安装、备份与升级边界

- Windows 默认目录为 `C:\PLMTool\{app,runtime,plugins,config,data,logs,license}`；Debian 默认目录为 `/opt/plmtool/{app,runtime,plugins,config,data,logs,license}`。实际路径可配置，但必须通过根目录约束和权限检查。
- 生产进程使用专用、非交互、最小权限运行身份；`config`、`data`、`license` 与 Secret 主材料不得赋予普通用户写权限。
- 基线备份集包含 PostgreSQL、`data`、`config` 和 `license`。Secret 主材料必须通过独立受保护流程纳入灾备，否则即使数据库恢复也不能解密 Secret；不得把主材料放入普通源码/日志归档。
- V1 不提供自动备份。实施团队执行备份并验证可恢复性。
- 升级顺序固定为：人工备份 → 维护模式 → 停止新任务并收敛 Worker → 离线升级 → Migration → 启动 → 健康检查；失败由实施团队按备份人工恢复。
- 备份、诊断和支持包默认排除 Secret 明文、Session、客户正文、普通运行日志和 Developer Workbench 私钥；如业务上必须包含客户数据，必须走明确授权和受控传输。

## 失败关闭与非目标

以下情况必须拒绝或隔离，不能降级为绕过安全控制：

- Session 缺失/过期、CSRF 失败、ProjectId 不一致、资源归属未知。
- License 无效、签名失败、机器不匹配或可信时间回拨。
- 文件越界、类型/大小不符、Hash 不一致或元数据/内容未完整提交。
- Secret 无法解密、Job 授权上下文不完整、Plugin 签名/协议/版本不合法。
- Audit 必填上下文缺失且操作属于强制审计点。

AF-03 不引入 WAF、SSO、集中式 SIEM、对象存储、Redis、消息队列、容器化插件、强制网络沙箱、多节点调度或自动备份。这些均不属于 V1 已批准 Scope。

## AF-03 验收

- Server Session、CSRF、License、Role、Project/Resource 与 Review Lock 的检查顺序明确，默认拒绝：PASS。
- 文件上传、不可变版本、受权读取、临时区和跨平台路径边界明确：PASS。
- 三层配置与 Secret 引用/解密/日志隔离明确，客户侧不含签名私钥：PASS。
- PostgreSQL Job/Outbox、租约、至少一次、幂等、取消和维护模式边界明确，未引入消息队列：PASS。
- Application、Integration、Audit 三类记录分离，Audit 由唯一模块拥有且普通用户不能删除：PASS。
- API、Worker、PostgreSQL、文件存储、Plugin 和 Developer Workbench 信任区明确：PASS。
- Windows 11、Windows Server 2025、Debian 13 保持正式目标；未把未验证平台或 Server Office 描述为通过：PASS。
- 未冻结 ORM、表名、REST 端点或具体操作系统服务管理器，未提前进入正式业务编码：PASS。

## 下一步

AF-04：将模块化单体、AI/RAG、Plugin、License/可信时间、PostgreSQL Job、文件存储和 POC-03 质量替代控制固化为关键 ADR。
