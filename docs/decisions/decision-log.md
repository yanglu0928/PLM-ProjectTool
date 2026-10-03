# 自主决策记录

## DEC-20261002-673 — 模型安全状态只挂 Windows 显式写平台

- Date/WBS：2026-10-02 / `AI-02-A08-P04`；依据 P03 可选路由与现有 `--platform-write` 信任组合。
- Decision：仅显式 Windows 写模式注入 Model `:set-state`，登录模式404、读平台 POST405；沿用同账户数据库/License/Session/Audit/收据，AVAILABLE 在 HTTP 与内部命令双层关闭。
- Reason：安全停止/退役属于受控管理写操作，不能扩展只读模式或被误解为生产模型可调用。
- Impact/Rollback：仅 Windows 组合根增加路由，无 Schema/依赖/冻结 API 或出站变化；撤装配可回退，历史状态/审计保留。
- Verification：Win11 隔离 PG18 登录404/读模式405/写模式200、先暂停后退役及原响应重放/GET、AVAILABLE422、权限/License/缺模型游标钥关闭通过；后端2052运行/3跳过及开发wheel通过。正式目标账户及发行仍待。

## DEC-20261002-672 — Model `:set-state` 请求显式目标态且只开放安全转移

- Date/WBS：2026-10-02 / `AI-02-A08-P03`；依据冻结 API-03、P02 内部命令与通用强 If-Match 合同。
- Decision：可选 POST 严格接收 `{"state":"SUSPENDED"}` 或 `{"state":"RETIRED"}`，映射内部 SUSPEND/RETIRE；强 If-Match、Origin/CSRF、幂等键必填，正文有界且禁止额外/重复字段。AVAILABLE 返回受控验证错误，默认/生产组合不挂载。
- Reason：冻结路径承载目标态，但当前真实 Provider/质量前置不足，不允许把已定义的 AVAILABLE 当成当前可执行能力。
- Impact/Rollback：只增 AI 可选 HTTP 和 `create_app` 注入，无 Schema/依赖/出站或 Breaking API 变化；撤注入可回退，历史结果保留。
- Verification：合同3项、Win11 隔离 PG18 真实200/历史重放/版本/权限/许可/审计与 AVAILABLE 拒绝、后端2052运行/3跳过、开发wheel通过；正式 Windows 装配由 P04 验证。

## DEC-20261002-671 — Model 安全状态命令按操作分离幂等域

- Date/WBS：2026-10-02 / `AI-02-A08-P02`；依据 CR-AI-004/005、Schema0058、现有 Provider 激活与通用收据模式。
- Decision：仅内部 SUSPEND/RETIRE，分别使用 `V1_AI_MODEL_SUSPEND`/`V1_AI_MODEL_RETIRE` 收据域，锁定 Model 并核对强版本/允许前态；状态行、不可变结果、Audit 与收据同事务。重放必须验证原结果及 Audit 归属，保持原状态/ETag，不从当前 Model 行重建。
- Reason：禁止跨操作 Key 互用和并发双写；终态退休不能被重放误读成当前许可。
- Impact/Rollback：仅内部 AI Application/Repository，无 Schema/API/依赖/外发变化；未挂生产入口可撤，有历史时保留并向前修复。
- Verification：Win11 隔离 PG18 真实管理员/CSRF/License/强版本/同 Key 双并发/跨操作域/历史重放/Audit 回滚与撤权通过；单元2项、后端2049运行/3跳过及开发wheel通过。

## DEC-20261002-670 — Model 状态结果只保存首次非 AVAILABLE 转移

- Date/WBS：2026-10-02 / `AI-02-A08-P01`；依据 CR-AI-005、冻结 API-03、当前通用收据与 Provider 激活结果模式。
- Decision：AI 自有不可变状态结果表只允许 `SUSPEND`/`RETIRE`，固定转移 `AVAILABLE→SUSPENDED`、`AVAILABLE/SUSPENDED→RETIRED`；保存 before/result、expected/result lock_version、actor、trace、Audit，留存首次响应证据。当前不开放 AVAILABLE，后续须单独证明 Provider/质量前置。
- Reason：限制状态表本身的可表达范围，防止通过插入“AVAILABLE 结果”绕过上层验收；保障历史重放与审计一致。
- Impact/Rollback：普通增量0058/ORM，原0057与冻结提交不变；空结果可降级，有历史必须向前修复。
- Verification：Win11 隔离 PG18 空/有数据升级、空表 down/re-up、状态/版本 `23514`、历史保护、非空降级拒绝、ORM drift=0；后端2047运行/3跳过及开发wheel通过。正式生产迁移未执行。

## DEC-20261002-669 — 模型创建只装配显式 Windows 写模式

- Date/WBS：2026-10-02 / `AI-02-A06`；依据 A05 可选 POST 与现有 `--platform-write` 信任组合。
- Decision：模型 POST 仅在显式写平台组合挂载，复用同账户 PG/License/Session/Audit/收据；登录专用及只读平台均不开放创建。初态仍 SUSPENDED，装配不赋予模型可路由/外发资格。
- Reason：将管理写操作限制在已有受控写组合，不扩大只读模式权限；模型登记与质量/Provider 可用相互独立。
- Impact/Rollback：仅 Windows 组合根增加路由，无 Schema/依赖/冻结 API 或数据外发变化；撤写路由组合可回退，历史模型与审计保留。
- Verification：Win11 隔离 PG18 三模式404/405/201与同 Key重放/GET、权限/License、缺模型游标钥关闭通过；后端2047运行/3跳过及开发wheel通过。正式目标账户与发行仍待。

## DEC-20261002-668 — AIModel 创建首次响应固定为初态投影

- Date/WBS：2026-10-02 / `AI-02-A05`；依据冻结 `AI_MODEL_CREATE` 201 ModelView、A02 持久幂等收据与 A03 安全投影。
- Decision：可选 HTTP 创建复用 A02 受权事务，返回模型不可变语义及初态 `SUSPENDED`/`"v0"`、空质量引用；同 Key 历史重放保持原 201 投影，不以当前模型状态/后来质量引用冒充首次响应。严格 JSON、Origin、Session/CSRF、Key，默认路由关闭。
- Reason：避免重放因后续模型状态变化产生非确定 201，也不把未核实质量写成已评估。
- Impact/Rollback：增 AI 创建服务初态投影与可选 HTTP；无 Schema/依赖/外发或冻结 API Breaking Change。撤可选路由可回退，历史模型/收据/Audit 保留。
- Verification：定向合同3项、Win11 隔离 PG18 首次201/状态及质量引用变化后历史重放/权限/License/Audit、后端2047运行/3跳过及开发wheel通过。未额外重复并发证明，A02 内部命令同 Key 并发已验；生产组合、真实质量和发行仍待。

## DEC-20261002-667 — 模型只读平台组合使用独立当前账户 Vault 游标密钥

- Date/WBS：2026-10-02 / `AI-02-A04`；依据 A03 可选只读路由、既有 Provider 游标正式来源及 Windows 平台显式读组合。
- Decision：固定 `ai-model-list-cursor-v1` 独立 KeyRef，只读当前进程账户 Vault；缺失/非32字节/异常时显式平台组合启动失败关闭，登录专用模式仍不挂模型路由。密钥不自动生成、不复用 Provider/Secret/其他游标。当前仅合成测试账户密钥，正式目标账户材料仍待供给。
- Reason：若直接复用 Provider key，会破坏资源隔离及恢复边界；若静默生成，则重启后游标失效且无法审计恢复。
- Impact/Rollback：仅增加 Windows AI 模型只读组合，不改 Schema/冻结 API/依赖或模型调用；停用显式路由并保留历史 Model/Audit 可回退。
- Verification：当前账户临时引用丢失/备份恢复、平台合同双显式模式挂载及缺钥关闭、A03 隔离 PG18 独立服务读取、后端2044运行/3跳过及开发wheel通过。A04 尚未做平台组合+PG端到端；正式目标账户/Server2025/Debian/Gate 仍未验证。

## DEC-20261002-666 — AIModel 只读投影独立分页游标并显式标注质量未评估

- Date/WBS：2026-10-02 / `AI-02-A03`；依据冻结 API-03 模型 LIST/GET、DM-04 模型可用与质量不等价、Schema 0057、现有 Provider 管理只读入口。
- Decision：模型分页使用独立 32 字节 HMAC key/`ai-model-metadata` family，绑定当前 Session 和 page_size，以 `(created_at, model_id)` keyset 排序；不复用 Provider 游标。只读 DTO 仅含模型语义、受控能力、状态/ETag、质量引用及固定 `NOT_EVALUATED` 质量语义，不输出 Key/Secret/厂商异常；可选路由不默认或生产挂载。
- Reason：防止跨资源/Session 游标混用与分页漂移，防止 SUSPENDED/AVAILABLE 或任意质量引用被误表述为 POC 质量通过。
- Impact/Rollback：只增 AI 内部读取、游标和可选 `/api/v1/admin/ai/models` GET 合同；冻结 API 无 Breaking Change，无 Schema/依赖/外发。未挂载时可撤入口；历史 Model/Audit 保留。
- Verification：定向单元/合同6项、Win11 隔离 PG18 管理员/普通用户/许可/分页/撤权/安全投影与默认404通过；后端2041运行/3跳过，开发wheel构建通过。正式游标密钥供给和发行仍待。

## DEC-20261002-665 — 模型首次登记复用管理员受权收据，质量引用先拒绝未证明值

- Date/WBS：2026-10-02 / `AI-02-A02`；依据冻结 DM-04/API-03、Schema 0057、现有 AIProvider 创建链。
- Decision：内部模型创建在当前部署管理员 Session/CSRF 与 License 检查后，以 actor-scoped 收据、Provider 当前配置/能力证明、模型/能力行、Audit 同一 PostgreSQL 事务提交；初态固定 SUSPENDED。相同 Key/载荷重放原 ModelId，换载荷冲突；重复语义由数据库唯一键拒绝。质量引用虽然 Schema 可保存，本项在无独立质量 Owner 证明适配器前拒绝非空输入，不伪造质量通过；后续独立受权关联命令再处理。
- Reason：避免未验证质量字符串直接影响模型路由；Provider 的名称和配置存在不等于外发/质量可用。保留历史幂等结果，Provider 后续退休不抹去原登记。
- Impact/Rollback：新增 AI 模块内部 Domain/Application/Repository，不开 API/Worker/模型调用，无 Schema/依赖变化；未生产调用可撤内部入口，有历史模型时保留 Model/Audit/收据并向前修复。
- Verification：Windows11 定向单元3项、隔离 PG18.6 真实 Session/CSRF/Provider 能力/License/重放/并发/审计回滚、后端2035运行/3跳过、开发 wheel PASS。真实质量证明、模型可用/外发和 Gate3 仍待。

## DEC-20261002-664 — AIModel 语义身份与能力声明分离且不可原地改写

- Date/WBS：2026-10-02 / `AI-02-A01`；依据冻结 DM-04、SC-01 `ai_models`/两个子表、API-03 模型语义身份与 RAG 重建规则。
- Decision：模型主表固定 Provider、受控 key、kind、revision、Embedding dimension，初态 `SUSPENDED`；能力声明与质量证明引用分别放 `ai_model_capabilities`、`ai_quality_profile_refs`，均为只增不可改历史。主表只允许后续任务受权改变 state/lock，语义字段不可原地更新；当前不开放 API/模型调用。
- Reason：避免 Embedding 维度或模型修订原地变化后复用既有向量；Provider 可用或配置存在均不证明模型质量与外发授权。初态暂停防止未测试模型被路由。
- Impact/Rollback：普通增量 Schema/ORM/Migration，复用既有 PostgreSQL 18/SQLAlchemy/Alembic，无公开 API/依赖变更；空表可降级，有模型历史时拒绝物理降级。版本/能力变化创建新模型身份并由后续受权命令处理；不可复制旧质量证明。
- Verification：隔离 PostgreSQL 18.6 空库 up/down/re-up、有 Provider 历史升级、非法维度/重复语义/跨 Provider/历史修改拒绝、ORM 漂移 0 已通过；后端全量结果见本项进度记录。Gate 3/真实模型调用仍未验证。

## DEC-20261002-663 — 第四服务命令只在受控策略有效时列入计划

- Date/WBS：2026-10-02 / `AI-01-A05-P05-A03-P04-P02-A03-P03-A02`；依据 CR-AI-003、ADR-013、现有三角色 `PLAN_ONLY` 合同。
- Decision：`SERVICE_NAMES` 固定列出第四角色供 SCM/只读盘点识别；旧 Bootstrap 无 AI 探针策略时服务命令计划只保留原三角色，明确安装/对账 AI 角色失败关闭。有合法受控策略时才列出第四命令；宿主先校验数据库就绪和维护准入，再报告 RUNNING，STOP 协作排空后释放数据库。
- Reason：无策略旧部署仍需查看/安装原三服务；无可运行 Worker 时不能生成看似可安装的 AI 命令。只读盘点必须能发现第四角色是否存在，包括不应存在的安装。
- Impact/Rollback：增加固定服务名和诊断范围；原三角色命令不变，无 Schema/API/新依赖。撤未投产第四角色可回退，已投产需先停机与 Job 对账，不能自动删除 SCM/审计。
- Verification：Windows11 定向模拟、后端2032项/3跳过、开发 wheel 与原生只读盘点通过；本机四服务均未安装。真实 SCM/目标账户/外发/Gate 仍待。

## DEC-20261002-662 — AI Provider Worker 必须独立于现有三种 Windows 服务

- Date/WBS：2026-10-02 / `AI-01-A05-P05-A03-P04-P02-A03-P03`；依据 CR-AI-003、ADR-007/012/013、现有固定三角色 SCM 清单。
- Decision：选择第四个固定 `AI_PROVIDER_WORKER`，原三角色不改变；先 A01 装配可信 Worker+维护循环，再 A02 同步宿主/身份/服务命令与只读盘点，A03 真实目标账户验收。只完成前序时不得输出第四个可安装命令或挂公开 Test。
- Reason：复用 Audit/Parser 角色会混合 Vault/网络权限和停写证据；只增加名称则会生成不可运行命令。
- Impact/Rollback：ADR-013 增量、运维清单扩展；无 DB/API/依赖变化。未投产可撤新增角色，已投产须先停新任务/服务并保留历史 Job/Audit，不自动删除 SCM。
- Verification：A01 定向9、隔离 PG18 持锁的真实合成 Job/Secret/TLS/结果、后端2025运行/3跳过及 wheel PASS；A02/A03、真实外发/目标账户/SCM 实机/Gate 开放。

## DEC-20261002-661 — Provider 探针绝对时限与租约预算

- Date/WBS：2026-10-02 / `AI-01-A05-P05-A03-P04-P02-A03-P02`；依据 CR-AI-002、ADR-007、当前 `PinnedHttpsProbeTransport` 与 Worker 60 秒租约。
- Decision：受控域名 DNS 在只运行固定标准库代码的短命隔离解释器中解析，3 秒超时并终止子进程；网络建立到固定响应读取使用单一 20 秒绝对截止时间，拒绝分块/无长度/超限/滴流响应；Job 租约调整为 120 秒，保留现有 fencing 与发布前当前事实重验。仅内部 Provider Test，不扩展通用网络栈。
- Reason：`getaddrinfo` 无调用时限；`http.client` 的逐次 socket 超时可被滴流续命。60 秒租约不足以覆盖领取、三次预检、独立 Secret 审计和结果发布的最坏数据库事务预算。后台超时线程会残留未知工作，不选；从请求线程强行终止不安全。
- Impact/Rollback：无 Schema/API/依赖变化；失败重试等待可能从 60 增至 120 秒。回滚可停用未挂载 Worker/路由并恢复原传输代码，已存在 Job/审计不删除。新 DNS 子进程不接收 Secret、客户正文或 Provider Key。
- Verification：Win11 定向16项（含真实隔离 DNS 子进程超时）、本机合成 TLS、隔离 PG18 Job→结果/审计、后端2023运行/3跳过与开发 wheel PASS。子进程创建期的 OS 级阻塞、真实厂商外发、SCM 及 Gate 保持开放。

## DEC-20261002-660 — Provider Worker 生命周期分步进入正式组合

- Date/WBS：2026-10-02 / `AI-01-A05-P05-A03-P04-P02-A03-P01`；依据 CR-AI-002、ADR-007/012/013、现有三角色 SCM 与单次 Provider Worker。
- Decision：P02-A03 先拆 P01 为单线程、协作停止、持 PostgreSQL 维护共享锁覆盖整个 `run_once` 的 Worker Loop；P02 独立处理系统 DNS 时限/租约窗口，P03 再通过 Change Request 扩展第四个固定 SCM 角色和只读运维证据，P04 才在同源策略/服务就绪条件下挂 Test 路由。P01 不注册进程、不运行网络或开放路由。
- Reason：把单次工厂直接当成常驻服务，会在维护转换/停止期间继续领取任务；把 AI 角色塞进现有 Audit/Parser 服务会混淆进程身份与出站权限。无界 DNS 解析也使停止完成时间不可证明。
- Impact/Rollback：仅内部应用编排增量；无 Schema/API/依赖变更。撤未装配 Loop 可回退，历史 Job/Audit 保留。SCM 固定角色变动先登记独立 CR，再实施；真实外发仍须逐次范围授权。
- Verification：P01 定向4、隔离 PG18 维护锁/状态转移、后端2018运行/3跳过、开发 wheel PASS；A03/P04/Gate 保持开放。

## DEC-20261002-659 — Windows 探针 Worker 构建时锁定策略与审计信任源

- Date/WBS：2026-10-02 / `AI-01-A05-P05-A03-P04-P02-A02-P02`；依据 CR-AI-002、A02-P01 Secret 审计、现有单次 Worker 与 Windows 受控信任链。
- Decision：Runner 在首次预检后以同一快照绑定 Secret 审计作用域及 trace，再进行发送前后重验；Windows 专用工厂从 Bootstrap 读取受控策略，从当前账户取得 DB/License、SYSTEM Actor 与固定 Vault 主钥，并注入 PostgreSQL SecretStore、AES-GCM、持久审计、专属 Job 组件及生产默认的钉 IP HTTPS Transport。缺一依赖固定失败并释放新建数据库连接。工厂只构建，不注册服务、不自动领取任务。
- Reason：跨进程策略/身份/主钥若用合成或请求输入，容易让 Job 指纹与 Worker 出站地址分叉；SecretResolver 必须在明文交付前持久审计。
- Impact/Rollback：内部 Runner 与 Windows 组合层增量，无 Schema/公开 API/新依赖；撤未挂载工厂即可回退，历史 Job/审计不删除。正式服务生命周期/维护模式和真实外发仍由后续验收。
- Verification：Win11 定向 8 项、隔离 PG18/本机 TLS 两个终态的持久 Secret 审计、后端 2014 项运行/3 跳过、开发 wheel PASS。不以工厂存在宣称生产 Worker/Gate 通过。

## DEC-20261002-658 — Provider 探针密钥访问以受权快照绑定独立审计事务

- Date/WBS：2026-10-02 / `AI-01-A05-P05-A03-P04-P02-A02-P01`；输入 CR-AI-002、`SecretResolver` 审计 Port、ADR-007 SystemActor/原 actor/trace 继承及 Audit 事件约束。
- Decision：新增仅供探针 Worker 的上下文绑定 Secret 访问审计适配器。调用方须用已重验的 `ProviderTestPreflightSnapshot` 限定 Job/SecretRef/SecretVersion/原用户/trace；`record_access` 严格匹配当前作用域和 `AI_PROVIDER_ADAPTER`，在独立短事务写 `SYSTEM`、原用户、Secret 版本目标的 append-only Audit 并提交，成功返回后才允许 `SecretResolver` 交付明文。缺上下文/身份/数据库/审计均拒绝；不使用 no-op 或猜测主体。
- Reason：SecretResolver 现有 Port 不携带 Job 身份，直接写无主体事件会丢失因果关系。作用域快照是已有受权事实，ContextVar 仅在同步 Worker 调用栈内绑定并复位，不能从请求或全局默认值构造。
- Impact/Rollback：增加内部适配器与测试，不改 Schema/公开 API/技术栈或默认 Worker 装配；撤未装配适配器即可回退，已写 Audit 保留。调用方在正式 Worker 装配任务中接入作用域并重新验收。
- Verification：Win11 定向3项、隔离 PG18 SYSTEM/原用户/SecretVersion/trace 审计落库、故障清零拒绝 PASS；后端2009运行/3跳过、开发 wheel 通过。不以适配器存在宣称真实外发或 Worker/Gate 通过。

## DEC-20261002-657 — Provider Test API/Worker 同源装配分三步验收

- Date/WBS：2026-10-02 / `AI-01-A05-P05-A03-P04-P02`；输入 CR-AI-002、P04-P01 部署策略、已有单次 Worker 与 Windows 服务计划。
- Decision：先建不公开的受控策略 Test 提交 Router 工厂（A01），再建同策略的 Windows 单次 Worker 组合及受控执行边界（A02），最后在两者就绪时验证并开放显式写模式的 Test 路由/生命周期（A03）；原激活 P04 在这之前仍关闭。
- Reason：当前正式服务计划没有 Provider Test Worker；若先公开 Test，异步 Job 无消费者。两进程必须使用同一受控策略摘要，不能采用不同合成注入。
- Impact/Rollback：仅执行顺序/组合层拆分，冻结 API/Schema/技术栈不变；撤工厂/路由即可回退，已有 Job/结果历史不删除。无真实外发授权。
- Verification：A01 Win11 隔离 ASGI/PG18 缺策略失败、202 Job/Outbox/Audit与重放通过；后端2006运行/3跳过、开发 wheel PASS。A02/A03 未实施，本决策不判 P02/P04/Gate PASS。

## DEC-20261002-656 — 部署 Bootstrap 显式提供非秘密探针策略快照

- Date/WBS：2026-10-02 / `AI-01-A05-P05-A03-P04-P01`；依据 CR-AI-002 和现有 `EndpointProbePolicy/Registry`。
- Decision：在受控 Bootstrap YAML 新增可选 `ai_probe_policies`，只接受有界、六字段、引用唯一的非秘密策略。独立部署工厂将配置严格转换为不可变 Registry；缺失或无效配置固定消息失败关闭，不回显 URL。策略在进程启动时形成快照，变更须受控重启；Provider API 仍只能写符号引用。
- Reason：Test/Worker/Activate 必须使用同一受控策略指纹，不能硬编码外发地址或复用合成测试 registry。复用已有 Bootstrap 可信配置入口，不增加独立文件/环境 Secret 来源。
- Impact/Rollback：增量非秘密部署配置字段与独立工厂，无 Schema、API、依赖、真实外发或生产路由开放。移除配置字段/工厂即可回退，既有 Provider/Test 历史保留。正式目标账户配置 ACL、三平台与实际出站另验。
- Verification：Win11 定向5项与后端2006运行/3跳过，开发 wheel 通过；无真实外发。目标账户配置 ACL、同源组合和 Gate 未验。

## DEC-20261002-654 — Provider 激活在单事务写状态、Audit、快照与收据

- Date/WBS：2026-10-02 / `AI-01-A05-P05-A03-P02`；输入冻结 API-03、CR-AI-002、P05-A02 当前证明、Schema 0056。前置满足；本项仅内部命令，公开 HTTP/正式 Worker 另验。
- Decision：先验当前管理员 Session/CSRF，再验 License；写事务内再次验管理员，按 actor/操作/Key 原子预留通用幂等收据。已有收据仅经原 actor/Provider/期望版本和 Audit 绑定的不可变快照重放，不更新当前行。新命令锁定当前配置/Secret/最新成功探针，要求 CONFIGURED 或 SUSPENDED 且锁版本精确匹配，条件更新为 ACTIVE，再同事务写 USER Audit、首次响应快照和收据；提交前重验 License。任一步失败整笔回滚。不同 Key 不允许对已 ACTIVE 的 Provider 隐式再激活。
- Reason/Impact/Rollback：防止撤权、配置/Secret 变化、旧证明、并发或后续暂停导致的错误激活/重放。无新 Schema/API/依赖；撤内部命令入口可回退，已提交 Provider/Audit/快照历史保留，不物理删除。Windows 11 隔离 PG18 验证真实权限、幂等、并发/版本、证明失效和回滚。

## DEC-20261002-653 — Provider 激活先存不可变首次响应，再执行命令

- Date/WBS：2026-10-02 / `AI-01-A05-P05-A03-P01`；输入冻结 API-03 的 200 ACTIVE/幂等要求、CR-AI-002、P05-A02 当前证明与平台通用收据。核查发现通用收据仅有 `ref_type/ref_id/status`，不保留原始 Provider lock_version；若激活后再暂停，重放时从当前行生成响应会变成错误版本或错误状态。
- Decision：把 A03 拆为 P01 不可变激活首次响应快照与 P02 同事务受权命令。P01 新增增量表，记录 Provider/config/探针证明、actor/Audit/trace、请求和结果版本及固定 ACTIVE 状态；通用收据引用此快照。数据库 FK/约束/不可变触发器保护归属与重放唯一性；不保存 Secret、端点、响应正文。先验证空/有数据迁移及拒绝非空降级，再接命令。
- Reason/Impact/Rollback：旧成功状态的当前行不代表首次 200 结果。原冻结 `64cdf09` 保留，此为 CR-AI-002 可追溯增量 Schema；空表可 down，有历史结果禁止物理删除并通过向前修复回滚应用入口。无 Breaking API、技术栈或额外依赖；P01 不会激活 Provider。

## DEC-20261002-652 — 激活资格只认当前事务内最新终态探针证明

- Date/WBS：2026-10-02 / `AI-01-A05-P05-A02`；输入冻结 DM-04/API-03、CR-AI-002、P05-A01 历史结果读取与 P04 当前事实预检。此项为内部证明，不执行激活或真实网络外发。
- Decision：提供供后续激活命令在同一 PostgreSQL 事务内调用的证明服务：先重验 License、锁定当前 Provider/config 与当前 ACTIVE SecretVersion、重新计算受控策略摘要，再读取该 Provider 最新终态结果（按 observed_at、结果 ID 降序），核对 Job/Outbox 原始绑定、SUCCEEDED 及配置/SecretVersion/策略。任何较新的失败证明、配置升版、Secret 轮换/停用或策略变更都拒绝，不能回退挑选旧成功。结果仅作为待激活的内部资格快照；调用者还需同事务授权、版本检查、状态更新、Audit/收据与最终 License 重验。
- Reason/Impact/Rollback：历史成功引用不足以证明当前环境，也不得因新的失败结果忽略风险。无 Schema/API/依赖变化；撤内部服务调用即可回滚，append-only 历史保留。隔离 PG18 验证成功、失效和事务只读行为，后续激活状态机独立验收。

## DEC-20261002-651 — Provider Test Job 结果仅作同事务受权历史投影

- Date/WBS：2026-10-02 / `AI-01-A05-P05-A01`；输入冻结 API-03 JobView、CR-AI-002、已验的 Job/Outbox 与不可变探针结果。前置满足；不变更冻结响应、Schema 或权限。
- Decision：将 `('ai','AI_PROVIDER_TEST')` 接入既有部署管理员 Job 读取 Owner registry。Owner 在同一只读事务核对 Job 原始 actor/scope、严格 Job/Outbox 快照、结果的 Job/Provider/配置/SecretVersion/策略/attempt/fencing 绑定；仅 SUCCEEDED 且唯一成功结果时返回 `AI_PROVIDER_TEST` 资源引用。失败结果只作一致性证明，不公开错误详情；未完成/取消不公开结果。此历史引用不代表配置仍为当前或允许激活；当前激活资格另列 P05-A02。
- Risk/Rollback：畸形或缺失绑定失败关闭，不传 payload、Key、URL、Lease 或探针正文。撤 Owner 注册可回退，Job/结果历史保留；无需数据库迁移。按既有 JobDetail 权限与结果引用合同验证。

## DEC-20261002-650 — Provider Test 先接单次受控 Worker，不挂生产循环

- Date/WBS：2026-10-02 / `AI-01-A05-P04-A05`；输入 CR-AI-002、P04-A01～A04 的领取/预检/探针/发布。现有这些组件彼此独立，没有一条完整的 Job 到结果链。
- Decision：新增纯 Application 单次 `run_once`：只领取一个 AI Provider Test Job，按 claim 的 JobId/fencing/worker/trace 运行固定探针，校验返回观察值与 claim 一致，再调用成功原子发布；受限异常或发布冲突交给失败/重试发布。无 Job 返回 IDLE，不循环、不注入厂商 Key/端点、不挂 Windows 生产组合。验证使用隔离 PG18、真实 Secret 只读 Store 与本机临时 CA TLS，测试专用解密器/端点覆盖只留 validation。
- Reason/Impact/Rollback：只验证零到一个 Job 的状态转换，避免默认应用或未获外发授权的生产 Worker 隐式启动。无 Schema/API/依赖变化；撤单次 Worker 内部入口即可回退，已形成的 Job/结果/Audit 历史保留。真实厂商 Key/数据外发与进程守护、部署装配另行按 P05/Release 验收。

## DEC-20261002-649 — Provider 探针失败按安全码有限重试，终态才写不可变结果

- Date/WBS：2026-10-02 / `AI-01-A05-P04-A04-P02`；输入 CR-AI-002、DEC-20261002-648、Job 最多 3 次与结果表 `job_id` 唯一约束。
- Decision：对受信内部探针异常只接收固定安全错误码；网络/DNS 暂不可用可在第 1/2 次以 5/15 秒重试，第 3 次或非重试类立即终止。每次仅在当前 AI Job/fencing/worker 的短事务内更新 Job/Lease/Attempt 并写 SYSTEM Audit；重试不写最终 ProbeResult；终态 FAILED 才从原不可变配置读取 SecretRef，写绑定原 Job/配置/SecretVersion 的不可变失败结果及 Audit。原始异常、响应、Key 不落库。成功路径同时补同事务 Audit；缺受控 SYSTEM 身份或 Audit 失败，整笔回滚。旧租约不得补写失败。
- Reason/Impact/Rollback：结果表每 Job 只能一个终态，重试记录留在 Attempt；成功/失败审计必须与终态一致。无 Schema/API/依赖变更；撤内部 Worker 调用可回退，已提交 Job/Attempt/Audit/结果历史不删除。仍不启用生产 Worker 或真实外发；逐次许可/配置变动不因失败处理被放宽。

## DEC-20261002-648 — 探针成功证明与 Job 终态在同一事务发布

- Date/WBS：2026-10-02 / `AI-01-A05-P04-A04-P01`；输入 CR-AI-002、`20261002_0055` 不可变结果表、P04-A03 的一次性成功观察值。
- Decision：先完成成功分支的原子发布，失败/重试作为 P02。发布事务依次对当前 AI Job/fencing、Provider 配置、策略摘要及 ACTIVE SecretVersion 做行锁重验；只接受匹配当前 Job/Token 的成功观察值；插入不含响应正文的不可变结果后以既有 Job lease `finish` 改为成功并提交。任一检查/插入/终态失败整笔回滚，不补发历史成功。现有预检逻辑抽取同事务入口，避免两套事实判定漂移；生产 Worker 仍关闭。
- Reason/Impact/Rollback：独立事务预检与结果插入之间存在竞态；共用锁和提交原子性防止过期租约或换配置产生激活证明。无新 Schema/API/依赖或真实外发；撤内部发布调用可回退，既有不可变证明/Job 历史不删除。成功观测本身仍是可信内部 Worker 输入，不是公开授权；失败状态与审计另由 P02 实施。

## DEC-20261002-647 — Provider Test 用固定 HTTPS 目标与测试专用合成入口

- Date/WBS：2026-10-02 / `AI-01-A05-P04-A03-P02`；输入 CR-AI-002、固定无客户探针、P04-A02 当前事实预检、P04-A03-P01 精确 SecretVersionId。生产依赖未包含 HTTP 客户端。
- Decision：使用 Python 3.13 标准库建立单次 HTTPS 探针：受控策略的完整 URL 仅允许 HTTPS/FQDN/固定路径；生产 DNS 所有候选地址须为 global IP，连接钉住所选 IP，TLS SNI/证书仍验证原域名。无代理、无重定向、固定 POST/极小 JSON 探针、短超时与有界响应；发送前再做 License/配置/SecretVersion/fencing 预检，通过 SecretResolver 的精确版本读取合成 Key，发送后再次检查租约。测试专用子类仅在 validation 使用回环地址/临时 CA，不挂生产组合。只返回安全结果码，不保存响应正文或原始异常。
- Reason/Impact/Rollback：避免新依赖与普通 HTTP 客户端对代理、重定向和 DNS 重绑定的隐式行为；本机 TLS 合成验证可不触及真实厂商。无 Schema/API/依赖变化；撤内部 Adapter 调用可回退，既有 Job/Secret/Audit 历史保留。执行与发布仍分开，任何真实外发须独立范围授权与发行审查。

## DEC-20261002-646 — SecretResolver 增加可选精确版本约束

- Date/WBS：2026-10-02 / `AI-01-A05-P04-A03-P01`；输入 DEC-20261002-645、SecretResolver 当前信封缺 SecretVersionId。
- Decision：在内部 `SecretEnvelope` 增加不可暴露的 `secret_version_id` 元数据，由 PostgreSQL Store 读取当前 ACTIVE 版本填充；`SecretResolver.use` 增加可选 `expected_version_id`，指定时必须在解密前与当前信封精确一致，缺失/错配失败关闭并记 DENIED。未指定时保持现有消费者行为。这里只建版本绑定能力，不实施 AI 网络发送。
- Reason/Impact/Rollback：版本号不能唯一绑定 Job 记录的 SecretVersion UUID。该变化无 Schema/API/依赖改动，旧调用兼容；可撤新参数调用回退，但已写入历史仍保留。需单位、真实 PG 轮换与全量回归，不将该能力当作外发授权。

## DEC-20261002-645 — Provider Test 预检不是外发许可

- Date/WBS：2026-10-02 / `AI-01-A05-P04-A02`；输入 CR-AI-002、P04-A01 专属领取、现有 SecretResolver 信封未携带 SecretVersionId 的事实。
- Decision：执行前先以当前 License Guard、Jobs fencing checkpoint、Provider 当前配置行锁、受控策略摘要与 ACTIVE SecretVersionId 完整比对首次 Job 快照；返回仅内存的预检计划，不解密 Secret、不联网、不改变 Job 状态。将策略摘要算法收敛为 AI 统一函数，避免提交与执行计算漂移。预检不是可跨事务复用的外发凭证；A03 需设计版本绑定的 Secret 使用和发送前重验，不凭本项打开 Worker 循环。
- Reason/Impact/Rollback：仅有 SecretVersion 号无法防止轮换后错用新密文；配置或策略变化后旧 Job 不能继续执行。无 Schema/API/依赖变化，撤内部预检调用可回退；已存在 Job/Lease 保留，失败状态处理在 A04。

## DEC-20261002-644 — Provider Test Worker 先建立专属领取与 fencing

- Date/WBS：2026-10-02 / `AI-01-A05-P04-A01`；输入 CR-AI-002、P03 原子队列、现有 Job Lease/Attempt 规则。
- Decision：P04 拆为 A01 专属 Job 领取、A02 执行前配置/许可/Secret/策略重验、A03 受限合成网络 Adapter、A04 不可变结果与终态发布。A01 只领取 `owner_module=ai`、`job_type=AI_PROVIDER_TEST`、DEPLOYMENT、引用载荷形状正确且未耗尽的 Job；使用 PostgreSQL `FOR UPDATE SKIP LOCKED`，过期租约先关闭旧 Attempt，再递增 fencing token 建立新 Attempt/Lease。A01 不启动循环、不调用网络/Secret，也不将 Job RUNNING 视为测试成功。
- Reason/Impact/Rollback：通用 `claim_next` 可领取其他 Owner，不适合作为 AI Worker 入口。专属领取避免越权并为后续发布建立 fencing；无 Schema/API/依赖变化。撤内部调用可回退，已创建的 Job/Attempt/Lease 历史不删除；耗尽/取消/终态由后续专属流程处理，不在 A01 静默改写。

## DEC-20261002-643 — Provider Test 202 HTTP 保持显式注入且无请求正文

- Date/WBS：2026-10-02 / `AI-01-A05-P03-A03`；输入冻结 API-03 与内部 A02 原子提交。
- Decision：新增可选 `POST /api/v1/admin/ai/providers/{provider_id}:test`，执行可信 Origin、Session/CSRF、必填 Idempotency-Key、强 If-Match 和空正文检查，委托 A02 返回 202 `job_id`；只将路由加入显式应用参数，不挂入 Windows 平台组合，直到 Worker/结果/信任与外发安全完成。错误返回公共安全码，不返回端点/Secret/探针细节。
- Reason/Impact/Rollback：符合冻结异步合同，阻止意外公开尚不可执行的 Job；无 Schema/Breaking API/依赖变化。撤可选注入可回退，既有 Job/审计/收据历史保留。

## DEC-20261002-642 — Provider Test 提交以原始命令收据固定 JobRef

- Date/WBS：2026-10-02 / `AI-01-A05-P03-A02`；输入冻结 202 JobRef、CR-AI-002、P03-A01 队列。
- Decision：只在管理员 Session/CSRF、运行许可、If-Match、当前 Provider 配置、受控探针策略及 ACTIVE SecretVersion 全部满足时，同一事务写入 Job/Outbox、Audit 与持久幂等收据。收据指向 JobId；重放先核对原命令指纹及 Job/Outbox 归属，返回首次 JobRef，不以变化后的配置/Secret 重新排队。只允许 CONFIGURED、SUSPENDED、ACTIVE 测试，RETIRED 拒绝；本任务不开放 HTTP、不解密 Secret、不联网。
- Reason/Impact/Rollback：避免同 Key 重放因当前配置漂移产生新探针，也不把首次成功误当成当前连通证明。无 Schema、公开 API、新依赖或现有数据迁移；撤内部调用可回退，已有队列/审计/收据历史不删除。真实外发与 Worker 仍关闭。

## DEC-20261002-641 — Provider Test 异步提交先建立受信 Job/Outbox 对

- Date/WBS：2026-10-02 / `AI-01-A05-P03-A01`；输入冻结 AI_PROVIDER_TEST `202 JobRef`、DM-04 Job/Outbox 至少一次与 CR-AI-002。
- Decision：将 P03 拆为 Job/Outbox 原子队列 A01、管理员授权/同事务收据与 Audit A02、可选 202 HTTP A03。A01 的 Job payload 仅含 Provider/配置/Secret版本引用、固定 probe id 与策略摘要，不存 URL、Key、客户正文；使用独立 submission UUID 将同一 Job/Outbox 对绑定，重复查验全部固定字段，异常只报告安全错误。队列不自行授权、提交事务或启动 Worker。
- Reason/Impact/Rollback：受信队列与业务权限分层，不把仅有 Job 行或 Outbox 行误报为已受理请求。无 Schema/公开 API/新依赖，已验证队列可由后续受权服务组合；撤调用即回滚，已有 Job/Outbox 历史保留。

## DEC-20261002-640 — Provider Test 结果只记录不可变版本证明

- Date/WBS：2026-10-02 / `AI-01-A05-P02`；输入 CR-AI-002、冻结 DM-04 的当前配置连通证明及 0054 Provider/Secret/Job 关系。
- Decision：新增 append-only 的 AI Provider 探针结果表，绑定 Provider 与配置版本的复合键、SecretRecord 与 SecretVersion 的复合键、唯一 JobId，以及 Job Attempt/Lease 的复合键、固定探针标识、策略 SHA-256、成功或安全失败码、观察时间。只在 Worker 完成时插入结果，不把待执行/运行中状态伪装为证明；不存 URL、Key、响应正文或原始异常。成功结果仅是可供后续激活重验的候选，不自行改变 Provider 状态。
- Reason/Impact/Rollback：Job 可变且至少一次，不能单独作为当前配置及 Secret 版本的稳定证明。Schema 从 0054 增量升级，空表可降；有结果记录时拒绝降级并向前修复。公开 API/技术栈不变；空/有数据迁移、复合归属、历史不可变和回滚均需隔离 PG 验证。

## DEC-20261002-639 — Provider Test 探针计划由受控策略精确解析

- Date/WBS：2026-10-02 / `AI-01-A05-P01`；输入冻结固定无客户探针、CR-AI-002 和现有符号化 EndpointPolicyRef。
- Decision：AI 内部仅接受预注入的不可变端点策略 registry，以配置中的精确引用查找；策略固定 Provider Kind、区域、外发类别、HTTPS URL 与探针模型标识。P01 只返回离线、无 Key/客户正文的固定探针计划；未知/错配/非 HTTPS、URL 注入均失败关闭。生产策略来源、DNS/IP 出站检查和实际适配器留后项，不把本合同当成网络安全完成。
- Reason/Impact/Rollback：阻止直接从 Provider 配置的符号化引用拼接任意目标，同时保持后续受限 Adapter 可扩展。无 DB/API/依赖变化；撤内部纯合同即可回滚，未发生外发或数据迁移。

## DEC-20261002-638 — Provider Test 按冻结异步合同拆分安全前置

- Date/WBS：2026-10-02 / `AI-01-A05`；冻结 API-03 为 202 JobRef、固定无客户探针，DM-04 要求可绑定当前配置的连通证明；当前实现缺端点策略解析、TestRun、AI Job Owner 和 Adapter。
- Decision：先登记 CR-AI-002，不开放同步 HTTP 或任意 URL；依次完成受控策略/探针、持久证明、同事务 Job/Outbox、受限 Worker、受权结果与组合。真实外发保持关闭，先用本机合成端点验证。
- Reason/Impact/Rollback：防止 URL 注入、Secret 错发或旧配置测试结果误用于激活。当前决策仅改变实施顺序和增量设计，无代码/API/Schema 变更；后续各项分别验证、可撤未开放入口，历史证明不得物理清除。

## DEC-20261002-637 — Provider PATCH 仅装入 Windows 显式写平台

- Date/WBS：2026-10-02 / `AI-01-A03-P04-A02-P03`；输入冻结 Provider PATCH 与已验可选路由、`--platform-write` 组合。
- Decision：仅在 `include_secret_write` 分支构造配置追加服务并挂入 PATCH；复用已在该分支使用的 Session、License Guard、PostgreSQL UoW、Secret 证明、幂等收据及 Audit。默认/登录模式保持 404，只读平台仅有同路径 GET，PATCH 返回 405。写依赖初始化失败则整体启动失败并释放运行时。
- Reason/Impact/Rollback：保持写面显式开启，不把合成验证推定为正式信任源就绪。无 Schema、依赖、冻结 API 或权限变化；撤组合注入可回滚代码，已有配置版本、收据和审计保留。验证隔离 PostgreSQL/ASGI 双平台边界、权限、许可、重放及启动失败关闭。

## DEC-20261002-636 — Provider PATCH HTTP 保持冻结If-Match且幂等键可选

- Date/WBS：2026-10-02 / `AI-01-A03-P04-A02-P02`；输入冻结 API-01 PATCH部分DTO/If-Match、API-03 PATCH控制S,L,C,M,A（未列I），内部P01要求事务收据键。
- Decision：新增显式可选PATCH Router，强If-Match必需，正文只接受六种受控非空变更字段且至少一种，Kind不可变；客户端Idempotency-Key非必需，缺省时服务器生成只用于该事务的随机键，有合法Header时支持稳定同Key重放。响应固定200配置版本+强ETag；默认与现有Windows平台组合暂不挂载。无Key的重复请求按If-Match并发规则冲突，不承诺原响应重放。
- Reason/Impact/Rollback：不把内部持久收据要求误转为冻结合同之外的强制客户端Header，同时保留自愿重放能力。无Schema/依赖/Breaking变更；撤可选Router即可代码回滚，历史版本/审计/收据保留。

## DEC-20261002-635 — Provider PATCH 部分字段在锁内合并且按原始变更集幂等

- Date/WBS：2026-10-02 / `AI-01-A03-P04-A02-P01`；输入冻结 API-01 PATCH缺失字段不修改/If-Match及API-03 Provider PATCH，现有追加服务只接受完整配置。
- Decision：新增内部受控部分更新命令，仅允许显示名、EndpointPolicyRef、SecretRef、地区、外发类别、能力声明的非空子集；Kind不可变。对原始规范化变更集、ProviderId和If-Match版本生成幂等指纹；授权/License后先预约收据，历史同Key重放直接返回原始不可变版本结果。新写入在同一事务锁定Provider，读取当前完整配置并合并、校验、证明Secret、追加版本/Audit/收据。旧完整追加入口保留。
- Reason/Impact/Rollback：避免路由层预读导致并发丢失或同Key在后续当前态变化后产生不同指纹。无Schema/公开API/依赖变化；撤新入口可代码回退，已追加版本及收据保留。后续可选HTTP独立验证。

## DEC-20261002-634 — Provider PATCH 原始版本结果与既有收据兼容

- Date/WBS：2026-10-02 / `AI-01-A03-P04-A01`；输入冻结 PATCH `200 config version + ETag`、API-01 同Key原结果、现有内部追加 UUID 与 `201` 版本创建收据。
- Decision：保留旧 `append()` UUID 入口及其已有收据形状/状态，增加内部 `append_result()` 返回原始不可变配置版本号与当次写入后的强ETag；重放以收据配置ID查询不可变版本，并用已纳入请求指纹的原 `expected_lock_version + 1` 还原原始 ETag，不读取当前配置指针。公开PATCH下一任务统一返回冻结200，内部201仅代表历史配置版本创建收据，不作为HTTP状态。
- Reason/Impact/Rollback：避免破坏历史收据或因后续升版/状态改变使同Key返回漂移。无Schema/API/依赖变化；撤新入口可回退，已有配置版本/收据不删除。需隔离PG验证原始结果、后续变化、失权、并发及回滚。

## DEC-20261002-633 — Provider 创建仅 Windows 显式写平台装配

- Date/WBS：2026-10-02 / `AI-01-A03-P03-A03`；输入已验证可选 Provider POST、当前 Windows `--platform-write` 的 Secret/License 信任组合。
- Decision：仅在 `include_secret_write` 分支创建 `AIProviderCreateService` 并挂入 POST Router，复用该分支既有 Session、License Guard、PG UoW、Secret证明、收据、Audit；只读平台模式不构造写服务，默认/登录模式不挂载。任一创建依赖失败则写平台整体启动失败并释放运行时，不静默丢失写路由。
- Reason/Impact/Rollback：维持显式最小暴露，未验证正式信任源不作为生产就绪；无 Schema/公开API/依赖变化。撤组合注入即可代码回滚，已提交的Provider历史不删除。只读模式同一路径已有GET，未挂载POST时由框架返回405而非404；需在验证与版本说明明确。

## DEC-20261002-632 — Provider 创建 HTTP 仅可选注入

- Date/WBS：2026-10-02 / `AI-01-A03-P03-A02`；输入冻结 API-01/API-03 与 A01 原始 ProviderView。
- Decision：新增严格 JSON 的可选 `AI_PROVIDER_CREATE` POST Router；请求仅包含受控配置字段及 SecretRef UUID，不接收 URL/API Key/密文。复用当前 Origin/Session/CSRF/管理员/License、同事务收据与 Audit，返回固定脱敏首版视图、强 ETag、Location/no-store；默认及现有 Windows 平台组合均不自动挂载写 Router。License 失效映射冻结403，Secret 不可用对外统一安全503。
- Reason/Impact/Rollback：保证只在显式安全组合验证后开放写面，且公开201与幂等重放保持首版响应。无 Schema/依赖/Breaking 变化；撤可选 Router 注入即可回退，已创建的 Provider/审计/收据仍保留。

## DEC-20261002-631 — Provider 创建返回原始不可变配置快照

- Date/WBS：2026-10-02 / `AI-01-A03-P03-A01`；输入冻结 `AI_PROVIDER_CREATE` 201 ProviderView 与原内部创建仅返回 ID 的差异。
- Decision：保留现有 `create()` 内部 UUID 入口兼容性，另提供面向冻结 HTTP 的创建结果入口；在同一创建/幂等事务中从首版不可变配置构造固定 `CONFIGURED/v0` 安全视图。同 Key 重放返回该原始视图，不读取可能已变更的当前配置或 Secret 正文；不增 Schema/公开 API。
- Reason/Impact/Rollback：满足创建结果和幂等原语义，避免提交后另一次当前态读取改变首次响应或受后续配置变化影响。仅 AI 内部 Application/Repository 与测试增量；撤掉新入口可回滚，已存 Provider/收据不变。正式 HTTP、目标账户信任和生产迁移仍另验。

## DEC-20261002-630 — Provider 只读路由挂入 Windows 显式平台模式

- Date/WBS：2026-10-02 / `AI-01-A04-P05`；输入冻结 Provider GET/LIST、P01～P04 安全投影/游标/可选HTTP及现有 Windows `--platform`/`--platform-write` 组合。
- Decision：两种显式平台模式共用当前 Session、DeploymentAdmin 与 License Guard，加载专用 Provider 游标 Vault KeyRef 后才注入只读路由；普通默认应用和 `--login` 不挂载。缺钥或任一构造失败，整个显式平台模式启动失败并清理运行时，不降级为无签名游标。
- Reason/Impact/Rollback：保持既有平台管理读面一致且失败关闭。无 Schema/API/依赖变化；不选择显式平台模式或撤路由注入即可代码回退，Provider 数据不变。合成装配证据不替代正式账户密钥/License 信任源。

## DEC-20261002-629 — Provider GET/LIST 仅显式可选装配

- Date/WBS：2026-10-02 / `AI-01-A04-P04`；输入冻结 API-01/API-03、P01～P03 安全投影/分页/签名钥。
- Decision：新增一个可选 Provider 只读 Router，由 `create_app` 显式注入；默认应用及现有 Windows 平台组合均不自动挂载。GET/列表只输出固定安全字段，可信 Host/Session 与内部管理员/License 双重检查；无效游标统一 `REQUEST_MALFORMED` 400，详情附强 ETag，列表用内部签名游标。
- Reason/Impact/Rollback：保留正式信任材料未供给时的失败关闭和冻结请求/错误合同。无 Schema/依赖/Breaking API 变化；撤路由注入可回滚，不影响 Provider 历史。

## DEC-20261002-628 — Provider 列表游标使用独立 Windows Vault KeyRef

- Date/WBS：2026-10-02 / `AI-01-A04-P03`；输入 P02 独立签名游标与现有 Windows 当前账户 Credential Manager 恢复机制。
- Decision：固定 Provider 专用 `ai-provider-list-cursor-v1` KeyRef，只读解析严格 32 字节；无钥/错长/异常失败关闭。仅用随机测试 KeyRef 在本机证明失密、加密备份和旧游标恢复；不自动生成或供给正式 KeyRef。
- Reason/Impact/Rollback：避免跨资源共用签名钥和在服务启动时静默变钥。无 Schema/API/依赖变化，撤入口装配即可回退；正式目标账户、Server 2025/Debian 来源仍另验。

## DEC-20261002-627 — Provider 列表使用专用签名游标

- Date/WBS：2026-10-02 / `AI-01-A04-P02`；输入冻结 API-01 列表游标规则、API-03 `AI_PROVIDER_LIST`、DM-04 与 P01 安全投影。
- Decision：内部列表按不可变 `(created_at, provider_id)` 降序 keyset，最大页长 200；游标使用独立 32 字节密钥签名，绑定家族、当前 Session 摘要、页长与位置，每页重验当前管理员/License。复用 P01 显式安全列投影，不 SELECT Secret 密文；正式目标账户密钥供给与 HTTP 装配分别验收。
- Reason/Impact/Rollback：避免 offset 漂移、跨会话/跨资源游标误用及共享签名密钥。无 Schema/API/依赖变化；不装配列表入口即可回退，既有 Provider 历史不变。

## DEC-20261002-626 — Provider 安全读取拆分详情与列表

- Date/WBS：2026-10-02 / `AI-01-A04-P01`；输入冻结 API-03 `AI_PROVIDER_GET/LIST`、DM-04、现有0054与管理员只读 Session Port。
- Decision：先实现内部详情的显式列投影和 SecretRef 遮罩，当前管理员/License 前后重验并提供资源强版本；列表的有界 keyset/cursor、HTTP 和生产组合独立验收，不以无界内部查询冒充完整列表。
- Reason/Impact/Rollback：冻结列表需安全分页且签名游标有独立密钥生命周期；详情不依赖游标，可先建立可复用的最小安全视图。无 Schema/API/依赖变更；撤内部读取入口即可回滚，历史配置不变。

## DEC-20261002-625 — Provider 配置追加不直接变更 ACTIVE

- Date/WBS：2026-10-02 / `AI-01-A03-P02`；输入冻结 DM-04/API-03、CR-AI-001 和 A03-P01 创建链。
- Decision：内部追加仅允许 CONFIGURED/SUSPENDED，锁 Provider 根并核强预期版本及不变 Kind；ACTIVE/RETIRED 拒绝。当前管理员/License 每次调用重验；同 Key 历史回放保留首次配置 ID，但不意味着现行 Secret 可用或允许外发。
- Reason/Impact/Rollback：活动配置直接切换会使正在执行的调用缺少独立暂停与路由切换证明。无 Schema/API/依赖变化；可撤内部入口回滚代码，已提交的配置历史保留且只能通过新的受权版本纠正。验证见 `docs/progress/ai-01-a03-p02-provider-config-append.md`。

## DEC-20261002-599 — Checklist Record 缺业务 Owner 时保持写入口关闭

- Date/WBS：2026-10-02 / `WFL-01-A07-P01`；输入冻结 `WORKFLOW_CHECKLIST_RECORD`、CR-WFL-004、`EVIDENCE_FIXED_PROJECT_V1`/Review/Exception Owner 约束。
- Decision：不把现有 UUID/静态快照或 AI 推断当正式 Evidence/Review/受权例外事实，不开放 PASS/WAIVED 写接口；优先补齐真实 Owner 验证，转向独立 Workflow 前端可读/启动任务。理由、备选与迁移/回滚/验证见进度记录。本项标前置阻塞，不标 Gate 或 A07 完成。

## DEC-20261002-598 — Workflow START 重放保留首次固定结果语义

- Date/WBS：2026-10-02 / `WFL-01-A06-P02`；输入 API-01 同 Key 原结果要求、固定六阶段定义 V1、Schema 0030 与通用持久收据。
- Decision：启动首次只允许 NOT_STARTED/v0→ACTIVE/HANDOVER/v1，收据保存 actor/project/operation/key 与原请求版本指纹、WorkflowId。重放先重新验证当前 Session/PM/License 和根身份/定义/已启动事实，再由**固定 V1 初态定义**重构首次 WorkflowView(v1)；不返回可能已推进的当前 Workflow，不增可变快照列。若来源无法证明，失败关闭。
- Reason/Impact/Rollback：固定 V1 起点在本版本内是确定的，可保原结果而不复制全量当前状态；后续定义变更须用新 operation 版本/CR，不得重解释旧收据。无新 Schema/API/依赖；撤内部命令保留既有收据/Audit 历史，不修改冻结基线或伪称正式Gate已批准。

## DEC-20261002-597 — Workflow 启动先做受权事务内的原子状态写

- Date/WBS：2026-10-02 / `WFL-01-A06-P01`；输入冻结 DM-02/API-02、六阶段 V1、Schema 0030 与已验证的实例初始化/GET。
- Decision：Workflow 自有 Repository 仅在调用方已持当前权限的事务中锁定根、核完整初态与 `expected_version=0`，把首阶段 HANDOVER 与根状态/版本同事务更新；不在此层模拟 Gate、客户审批、幂等回执或公开请求。版本不匹配、已启动及不完整快照分别拒绝，不做隐式初始化。
- Reason/Impact/Rollback：先建立可由后续受权命令复用的原子事实边界，避免前端或 API 直接改状态；无 Schema/API/依赖变化。未装配公开入口，可撤 Repository 调用回滚代码；已真实启动的历史不得由代码回滚重置。

## DEC-20261002-596 — Evidence 原集成矩阵复用但锁定随包运行来源

- Date/WBS：2026-10-02 / `PLT-PKG-01-A09-P48-A05`；输入当前候选/暂存 SHA 和既有 `EVD-01-A04-P03-A05` 临时PG/ASGI矩阵。
- Decision：保留原验证脚本默认PoC模式，仅新增可选随包PG路径；该模式须核被导入的 `plm_assistant` 位于随包 Python packages，包装器先验候选/暂存并后验临时目录与ZIP未变。
- Reason/Impact/Rollback：用原有完整矩阵检验当前包实际字节，同时避免复制测试逻辑/误用开发源码；仅测试工具，弃用可选入口即可回退，正式环境/Gate不据此放行。

## DEC-20261002-595 — Alembic env 不作为独立可导入业务模块

- Date/WBS：2026-10-02 / `PLT-PKG-01-A09-P48-A04`；输入包内586模块枚举、首次普通导入 `migrations.env` 的 `context.config` 异常，以及 P47-A04 随包真实迁移通过。
- Decision：依赖匹配与585普通模块导入均须无错误；仅精确排除 `plm_assistant.migrations.env` 的普通导入，仍要求其在 Alembic 实际升级/降级链中验收，不泛化跳过其他模块。
- Reason/Impact/Rollback：Alembic env 需运行上下文，直接 import 不是正确入口；仅审计边界调整，无产品行为变化，可弃用审计工具回退，不改变迁移证据或 Gate。

## DEC-20261002-594 — 新应用包复用旧第三方审阅输入但不复用法律结论

- Date/WBS：2026-10-02 / `PLT-PKG-01-A09-P48-A02`；输入 P45/P47 固定 SHA、第三方库存及原有 P43/P45 审阅材料。
- Decision：对两个完整 ZIP 固定身份后，比较所有非应用载荷及库存清单哈希，并核对自有后端依赖声明和原生 OCR 映射；仅发布新的审阅差异稿，不改历史草案或生成最终产品 LICENSE/NOTICE。
- Reason/Impact/Rollback：应用迭代不应让旧第三方材料失去来源绑定，也不能让材料继承冒充法律批准。仅新增只读审计/文档，无产品或发行包变化；弃用差异稿即可回退，法律标志仍 false。

## DEC-20261002-593 — 技术候选通过不提升发行 Gate

- Date/WBS：2026-10-02 / `PLT-PKG-01-A09-P48-A01`；输入当前候选 SHA、P47-A03～A05 实际证据与 P46-A01 旧候选发行阻断清单。
- Decision：将新候选的技术合成链记为已验证，但产品级 LICENSE/NOTICE、正式信任、目标平台、浏览器/UAT、AI质量和安装升级仍独立保持 OPEN；不修改 ZIP 的 `release_eligible=false` 或关闭 CR-PKG-008/Gate。
- Reason/Impact/Rollback：避免以新 ZIP 字节完整和合成登录替代正式发行证据；仅审计记录，无运行行为，撤销本判断需新证据而非删除历史。

## DEC-20261002-592 — 隔离 HTTPS 演练暂存迁至 D 盘

- Date/WBS：2026-10-02 / `PLT-PKG-01-A09-P47-A05`；输入 C 盘 Temp 复制 `Errno 28`、D 盘约 448 GB 空闲、新候选 SHA 固定。
- Decision：首次失败未启动服务/数据库；改为进程级 TEMP/TMP 指向明确的 `D:\PLMTemp`，重新清洁解包并全量校验后，在 D 盘两份全新隔离布局运行原有合成 HTTPS/License 测试。C 盘先前清洁暂存删除命令被环境策略拒绝，保留并登记，不改用绕过方式。
- Reason/Impact/Rollback：规避系统盘容量而不降验证强度；只影响一次性测试位置，无 API/Schema/原候选变化。停止使用 D 盘暂存或弃用测试脚本即可回退，Gate 不因此放行。

## DEC-20261002-591 — 随包迁移只在一次性双库集群验收

- Date/WBS：2026-10-02 / `PLT-PKG-01-A09-P47-A04`；输入 CR-PKG-008、P47-A03 哈希校验暂存和原随包PG烟测模式。
- Decision：先完整复核暂存清单，再用包内 Python/PG18 初始化一次性回环集群；在有一条非客户配置记录库验证0051→0052→0051→0052，在另一空库直升0052，并验证 pgvector；停服后仅删除已核验的唯一 Temp 数据目录。
- Reason/Impact/Rollback：将包内迁移与开发环境迁移区分，同时验证已有数据不丢失；不接触正式库/服务，失败时保留异常运行集群供审计而不误报通过；HTTPS独立后续执行。

## DEC-20261002-590 — 当前应用真实候选仍按非发行边界逐件验真

- Date/WBS：2026-10-02 / `PLT-PKG-01-A09-P47-A03`；输入 CR-PKG-008、干净提交 `6d731177`、固定 P45 父候选及新 wheel/dist。
- Decision：新唯一 ZIP 与历史父包分离；先核验源 ZIP SHA/安全路径/清单，再解包到全新直接 ASCII Temp 子目录、逐件哈希与全集读回；只用候选包内 Python 导入新 API/迁移，不把此检查扩展为正式安装或发行放行。
- Reason/Impact/Rollback：避免同版号旧应用误交付；不触碰既有正式服务、数据库或原候选，弃用新 ZIP 即可回退；随包数据库/HTTPS另列 P47-A04。

## DEC-20261002-589 — 派生候选仅替换受控应用归属路径

- Date/WBS：2026-10-02 / `PLT-PKG-01-A09-P47-A02`；输入 CR-PKG-008 与 P45 固定父包/哈希清单。
- Decision：父包第三方/运行时/OCR/PG/Caddy 载荷只读逐件验证并原样传递；完整替换 wheel 的 `plm_assistant` 与对应 dist-info，以及前端 dist，输出新唯一非发行 ZIP/全量哈希/来源字段。CLI 要求干净 HEAD；不修改父包。
- Reason/Impact/Rollback：避免同版号旧文件残留与第三方来源漂移；仅开发工具/候选，弃用派生 ZIP 即可回退，Gate 不据此放行。

## DEC-20261002-588 — 旧固定 ZIP 不代表当前源码交付物

- Date/WBS：2026-10-02 / `PLT-PKG-01-A09-P47-A01`；输入 P45 SHA 固定 ZIP 与当前已提交应用源码。
- Decision：旧 ZIP 继续作为不可变第三方基底和历史证据，不直接安装宣称当前功能；先按 CR-PKG-008 构建有唯一来源/哈希的新非发行应用派生候选。
- Reason/Impact/Rollback：包内缺 Evidence 回查与 Migration 0052，前端资产也不同；只读核查无运行时影响，放弃派生候选即可回滚，不修改原包。

## DEC-20261002-587 — GLOBAL 操作恢复需历史与当前双证据

- Date/WBS：2026-10-02 / `EVD-01-A04-P03-A08-P19`；输入 CR-EVD-004 与 P18 保存的原操作号。
- Decision：仅原操作者当前 DeploymentAdmin 可用原 Key 回查；完成收据后再 GET 当前 GLOBAL Evidence/强 ETag。未知或读取失败不清除锁，完成且当前读取成功后也由用户显式点击清除。
- Reason/Impact/Rollback：历史已提交并不代表当前资格未发生变化；仅前端页面状态增量，停用入口即可回退，收据历史保留。

## DEC-20261002-586 — GLOBAL 人工资格提交前保存最小原操作号

- Date/WBS：2026-10-02 / `EVD-01-A04-P03-A08-P18`；输入 P16 受权页面、P17 GLOBAL 命令和 CR-EVD-004 的不确定回执边界。
- Decision：在请求前将当前 actor、GLOBAL EvidenceId、原操作 Key 存入同源 sessionStorage 并读回；存储失败不发送，未知结果保留并阻新裁定。理由/正文不存入浏览器会话；完成回执不当当前状态。
- Reason/Impact/Rollback：断线后防止换 Key 重复裁定；仅 UI 状态增量，无后端/API/Schema 变更，停用表单即可回退，历史记录不删除。

## DEC-20261001-585 — GLOBAL 写入复用严格首次回执但隔离 Viewer Scope

- Date/WBS：2026-10-01 / `EVD-01-A04-P03-A08-P17`；输入冻结 GLOBAL 资格 POST、项目客户端与 P16 管理员只读页。
- Decision：在独立管理员 Session 传输中复用现有资格命令校验/回执解析，写前额外核对 Viewer 内容 URL 与 GLOBAL 固定 DocumentVersion；项目命令也维持项目 URL 绑定。页面未保存原 Key 前不开放写按钮。
- Reason/Impact/Rollback：避免跨 Scope 来源混用或断线后换 Key；无 API/Schema 变化，停用新调用即可回退。

## DEC-20261001-584 — GLOBAL Evidence 页面先完成受权只读定位

- Date/WBS：2026-10-01 / `EVD-01-A04-P03-A08-P16`；输入冻结 GLOBAL List/Get/Viewer 与 P14/P15 客户端。
- Decision：将原计划的全局页面拆成只读浏览定位、人工资格写入、原操作号恢复三个可分别验收的 WBS；本项只发布 DeploymentAdmin 只读入口。Viewer 固定来源与当前 GET 版本一致前不展示内容 URL。
- Reason/Impact/Rollback：没有由页面发起的原操作号时提供恢复按钮会误导用户输入不明 Key；分项不变更合同或权限，移除路由即可回退 UI。

## DEC-20261001-583 — GLOBAL 历史回查须另取当前强 ETag

- Date/WBS：2026-10-01 / `EVD-01-A04-P03-A08-P15`；输入冻结 GLOBAL EVIDENCE_GET、P14 原操作收据客户端。
- Decision：扩展现有 Evidence 资格客户端的 GLOBAL 当前 GET，必须是 DeploymentAdmin 会话，匹配 EvidenceId 和响应强 ETag；项目身份不借全局路径。复用当前状态解析，不根据历史收据推断状态。
- Reason/Impact/Rollback：历史收据与当前资格可能不同；方法独立且未接 UI，无数据库/API 差异，停用调用即可回退。

## DEC-20261001-582 — GLOBAL 回查客户端不得借项目角色

- Date/WBS：2026-10-01 / `EVD-01-A04-P03-A08-P14`；输入 CR-EVD-004 双 Scope 与 P12 项目客户端。
- Decision：GLOBAL 客户端仅 DeploymentAdmin 当前会话，单独全局路径；项目 PM/CustomerManager 仍仅项目路径。共用最小回执解析，但不混同两套权限或当前状态。
- Reason/Impact/Rollback：与后端 Scope 隔离一致；只新增未接 UI 的前端方法，停用调用即可回退，无数据迁移。

## DEC-20261001-581 — 历史收据完成后人工确认清除待核对记录

- Date/WBS：2026-10-01 / `EVD-01-A04-P03-A08-P13`；输入 CR-EVD-004、P12 前端回查客户端及现有会话操作号锁。
- Decision：`UNCONFIRMED` 继续保留记录；`COMPLETED` 必须再 GET 当前 Evidence，页面分开展示历史与当前，只有原操作者点击“已核对当前资格”才清除本地提醒。GET/存储失败不解锁，不自动重发资格命令。
- Reason/Impact/Rollback：当前状态可能已由后来事件改变；用户可自行核对而不被历史回执误导。仅 UI 变化，回滚隐藏入口并保留记录及服务端收据。

## DEC-20261001-580 — 回查客户端不代替当前 Evidence GET

- Date/WBS：2026-10-01 / `EVD-01-A04-P03-A08-P12`；输入 CR-EVD-004 和 Windows 显式组合已验合同。
- Decision：项目 PM/CustomerManager 客户端只发原 Key Body 和当前 CSRF；`COMPLETED`/`UNCONFIRMED` 均标记 `is_current_state_proof: false`，不自动重发或换 Key。页面单独做 GET/Viewer 恢复。
- Reason/Impact/Rollback：历史收据只能证明原操作提交，不能证明当前资格或授权未变化；独立客户端无既有页面行为变更，停用调用即可回退。

## DEC-20261001-579 — 资格回查只进入显式平台写组合

- Date/WBS：2026-10-01 / `EVD-01-A04-P03-A08-P11`；输入 CR-EVD-004、P10 可选 HTTP、现有 Windows 平台组合。
- Decision：在 `--platform-write` 内复用当前授权/收据/UOW 服务并挂载只读回查 POST；默认应用、登录专用和只读组合保持关闭。虽为无业务写入的 POST，仍以现有资格写模式为首版明确入口，避免扩大部署 Scope。
- Reason/Impact/Rollback：合成真实 PG 验证正常回查及授权拒绝，未改 DB/API 冻结原版；停用可选注入即可回滚，历史收据不删除。前端/浏览器和正式信任仍独立验收。

## DEC-20261001-578 — Evidence 候选创建的证明与写事务顺序

- Date/WBS：2026-10-01 / `EVD-01-A03-P03-A01`；输入冻结 EVIDENCE_CREATE、现有创建权限 Port、Document `get_version_for_trace` 与两种来源证明 Port。
- Decision：先在 Document 受权固定结果链证明 Locator；在 Evidence 创建同一 UOW 中重新检查当前 Session/CSRF/角色和 Document 固定可用版本（复用 `get_version_for_trace`），然后同事务完成幂等收据、CANDIDATE 记录与强制 Audit。读取 Proof 不持久化用户输入正文；失效/撤权时整个写事务失败关闭。
- Reason/Impact/Rollback：证明完成与写入之间有时间窗，单独凭旧证明无法保证当前可用；现有 Document 公共 Application Port 已可提供调用方 UOW 内锁定复核，无需 Evidence 直查 Document 表。此次只读核查不变 API/Schema；后续分内部写服务、隔离PG、可选HTTP与平台组合逐项验收。

## DEC-20261001-577 — DOCX V1/V2 固定结果共存隔离复验

- Date/WBS：2026-10-01 / `EVD-01-A03-P02-A02-P03-P04-A05`；输入 `CR-EVD-001`、Document 受权固定结果 Port 及 V2 SECTION 证明。
- Decision：在单次临时 PostgreSQL 18 与私有结果目录中，为同一合成 DOCX DocumentVersion 建立分开的 V1/V2 Job、成功 ParseRecord 和 ResultRef，按两版本分别受权读回并证明段落/章节；跨项目、撤权和私有结果篡改必须失败。只用已验的受控快照替身，不伪称生产 Session。
- Reason/Impact/Rollback：验证文本版本列/唯一约束和不改写历史的真实共存；仅验证脚本及报告，无生产代码/API/Schema/依赖变更，临时库停止后清理。旧运行作业升级排空留独立验收，避免用数据库共存代替运行时兼容。

## DEC-20261001-576 — Evidence SECTION 仅认固定 DOCX V2 标题节点

- Date/WBS：2026-10-01 / `EVD-01-A03-P02-A02-P03-P04-A04`；输入 `CR-EVD-001` 和已验证的 DOCX Parser V2 `DOCX_SECTION` 节点。
- Decision：沿现有 Document 受权固定 ParseResult Port 证明 SECTION；仅接受 DOCX Version 2 的 `DOCX_SECTION`、规范 `word/heading/<level>/<paragraph_index>` 路径及一致节点ID，单一匹配才通过。DOCUMENT 仍走原全文证明；旧 V1、普通段落和其他格式 SECTION 失败关闭。
- Reason/Impact/Rollback：避免空泛 SECTION 标签获得业务证据地位；无公开 API/Schema/权限/依赖变更。停用新分支即可回退，V2 已存结果保留不可改；定向/负例、落盘回查、后端全量和wheel验收。

## DEC-20261001-575 — DOCX V2 标题节点与独立解析版本

- Date/WBS：2026-10-01 / `EVD-01-A03-P02-A02-P03-P04-A03`；输入 `CR-EVD-001`、Parser V1 profile/result 及 DOCX 抽取器。
- Decision：仅 DOCX 的新计划使用 Parser Version 2；V1 DOCX 结果继续可构造/读取，但不新增标题节点。V2 为非空内置 Heading 1～9 段落在原段落节点之外追加 `DOCX_SECTION`，section_path 按样式级别和正文段落序号编码为 `word/heading/<level>/<paragraph_index>`，重复标题也唯一。普通/自定义/空标题不推断。
- Reason/Impact/Rollback：内容版本变化必须与旧结果区分；节点保留原段落位置且无 API/Schema 变化。部署时先使旧 Parser Worker 静止，待 RUNNING 的 V1 尝试收尾或按原恢复流程显式处理后启用 V2；不能把运行中的旧尝试悄悄改版。回滚关闭 V2 新作业并保留已发布字节；旧代码不会消费 V2 新作业，故需先静止/排空再回滚。以单元、真实DOCX回放、全后端与wheel验收。

## DEC-20261001-574 — 多页 PDF 中文扫描页定位验证

- Date/WBS：2026-10-01 / `EVD-01-A03-P02-A02-P03-P04-A01`；输入原生文本 PDF P01 和真实离线 OCR P02 合成验收、冻结 Evidence PAGE/TEXT_RANGE 契约。
- Decision：用临时合成 PDF 的一页原生文字与一页中文扫描图验证逐页分流、中文 OCR 与 PAGE 坐标；使用现有离线模型临时 ASCII 副本，不下载、不触碰客户材料。SECTION 是缺乏来源节点的独立问题，另列后续任务。
- Reason/Impact/Rollback：防止单页英文 OCR 结果被外推到常见中文多页文档。只增验证脚本与记录，无生产 API/Schema/权限/依赖变更；删临时文件即可回退，识别失败则登记实际结果并调整测试覆盖，不虚报质量。

## DEC-20261001-573 — 离线 OCR 合成来源定位验证

- Date/WBS：2026-10-01 / `EVD-01-A03-P02-A02-P03-P03-P02`；输入既有 PP-OCRv5 离线适配器、Parser OCR 节点、Evidence 固定结果证明和原生 PDF P01 PASS。
- Decision：使用仓库已有的本地模型字节复制到临时 ASCII 路径，禁止下载；仅用新建合成 PNG/扫描 PDF 实际调用模型，回查归一化 PAGE bbox 与已知绘字/嵌图区域，再做 Evidence 节点证明。模型、字体、输入路径由参数显式传入，不写客户材料。
- Reason/Impact/Rollback：区分真实 OCR 与假 Engine 契约测试，且避开已知中文模型路径限制。仅新增验证脚本/记录，无生产 API/Schema/权限/依赖变化；移除临时副本即可回退，脚本结果以实际运行决定，不把合成质量推广到客户文档。

## DEC-20261001-572 — PDF 原生文本定位与 OCR 边界分项验收

- Date/WBS：2026-10-01 / `EVD-01-A03-P02-A02-P03-P03-P01`；输入 Parser PDF 原生文本节点、Evidence 固定结果证明及前一项 Office 合成定位验证。
- Decision：仅以临时落盘的合成 PDF 检查原生文本页码、规范字符区间和 Evidence 节点证明；空白页必须返回 OCR_REQUIRED，另列扫描 PDF/图片 OCR 验收，不把本项算作 OCR 质量或实际模型验证。
- Reason/Impact/Rollback：防止文本型 PDF 的定位证据被扩展解释成扫描件可用。仅新增验证脚本和进度记录，不改 API/Schema/权限/依赖；可停止使用该脚本回退，历史验证记录保留。先完成脚本真实运行及原单元回归，失败如实登记。

## DEC-20261001-571 — 新候选安装映射与独立Web服务边界

- Date/WBS：2026-10-01 / `PLT-PKG-01-A09-P24`；输入P22/P23固定候选、ADR-013、`CR-PKG-005`。
- Decision：对21,110项载荷和三项清单建立确定性目标映射；Caddy安置于`runtime/caddy`，其对应源码置于`app/third-party-sources`，既有目录映射不改。`PLMProjectToolWeb`仅作独立Web边界候选，ADR-013三项应用服务保持原名原数；无目标账户/证书/ACL/NOTICE时只输出计划，禁止正式安装与SCM操作。
- Reason/Impact/Rollback：确保离线新候选可审计且不把合成HTTPS当生产信任源。无API/Schema/数据迁移/正式服务变更；停用新计划脚本即可回退，P15/P22保留。真实全包映射、大小写冲突与只读门禁验证后仍仅记非发行PASS。

## DEC-20260930-520 — Parser 异步现时授权口

- Date/WBS：2026-09-30 / Phase2 `PAR-01-A05-P01-P05-A02-P01`；输入 ADR-007/011 与 CR-PAR-003，原冻结权限和上传角色保持。
- Decision：新增 Project 内部 `DOCUMENT_PARSE_PROCESS` 操作并沿现有上传角色；Parser 准备及最终发布通过 Auth/Project/License 公共 Application Port 复核原用户，不靠 SYSTEM 身份提权。取消/失败清理不因用户撤权禁止。
- Reason/Impact/Rollback：只验旧上传来源不足以防长任务期间撤权。无公开 API/Schema/依赖变更；停未装配 Worker 可撤入口，已提交历史保留。真实拒绝/回滚和正常链验证后才记内部 PASS。

## DEC-20260930-519 — Parser 进程须动态复核 SystemActor

- Date/WBS：2026-09-30 / Phase2 `PAR-01-A05-P01-P05`；输入 ADR-007/011、既有 Parser Worker Step 和 Windows 受控 SystemActor。前置功能链内部 PASS，正式进程尚未装配。
- Decision：不把构造时读取的 UUID 当成持续有效身份。Parser 关键状态提交前重验同一受控 Vault 身份；进程入口显式装配 WorkerDatabase/License/Project/Storage/Identity，失败关闭，不复用 HTTP Session 或隐式 Secret 环境变量。先验证正式组合，再标进程 PASS。
- Reason/Impact/Rollback：长解析期间 Vault 材料可能失效或改变，启动时唯一检查不足。此为 ADR-011 的实现补齐，不改变安全机制、Schema/API/技术栈；停独立入口可回退，已写审计保留。需 Windows11 真实运行、故障注入、全量与 wheel 证据；Server2025/Debian 仍另验。

## DEC-20260930-518 — Parser 过期取消扫描与恢复分离

- Date/WBS：2026-09-30 / Phase2 `PAR-01-A05-P01-P04-P03-P04`；输入 ADR-007/011 和 P03 已验原子恢复。前置满足，Gate3 不变。
- Decision：Jobs 只按数据库时间返回当前过期取消的只读候选与稳定游标；Parser 单步调度持有同一受控 SystemActor，遇竞争后依原 `RecoverExpiredParserCancel` 的当前代/来源检查或只读终态证明。候选仅为 hint，不给扫描者写权限；独立进程组合另项验收。
- Impact/Rollback：不改 Schema/API/权限/依赖；小批有界轮询防坏来源永远占据队首。停用调度即可回退应用，已提交取消历史不变。真实 PG/HTTP、竞争及故障测试后才标内部 PASS。

## DEC-20260930-517 — Parser 取消过期恢复与只读确认

- Date/WBS：2026-09-30 / Phase2 `PAR-01-A05-P01-P04-P03-P03`；输入 ADR-007、CR-PAR-001/002、P04-P02 活租约协作取消与 P03-P02 用户申请。前置满足，Gate3不变。
- Decision：`CANCEL_REQUESTED` 不属于普通 Parser 领取候选，不能等待通用 `claim_next_parse` 自行恢复。新增 Jobs-owned 当前代真实到期 Port，Parser 编排在同 UOW 内核 USER 首申请、Document 当前记录、SYSTEM Audit 与 Job/Lease/Attempt；恢复候选只是 hint，执行时重新锁定来源和数据库时间。确认丢失只读核验终态及唯一审计，不复做转换或猜测提交结果。
- Impact/Rollback：无 Schema/API/权限/依赖扩张。合成身份仅测试内部能力；正式 SystemActor/独立进程及其他环境仍待。撤未装配恢复入口可回退，已提交取消历史必须保留；真实过期、旧代、零写拒绝、故障回滚和全量/wheel通过才关闭本项。

## DEC-20260930-516 — Parser 项目取消 Owner 接入顺序

- Date/WBS：2026-09-30 / Phase2 `PAR-01-A05-P01-P04-P03-P02`。输入 API-03 项目取消、CR-PAR-002 版本快照、Document 实际上传来源与已有 Worker 协作取消；前置满足。涉及 Project/Document/Jobs/Audit/Platform 的应用 Port，不改冻结 API 或新依赖。
- Decision：现有 Job 通用路由只作 Owner dispatch hint。Parser Owner 事务内重新查当前 Session/License/项目角色和原上传创建者、Document 版本/Audit 上传来源，再按 Job/Outbox 实际绑定加锁；Jobs 自有取消变更，Audit 自有首 USER 事件，0050 记录首次版本，Platform 收据同事务完成。先验来源再锁 Job，减小与上传提交相反锁序风险；deadlock 仅幂等重试完整事务，不从部分状态猜成功。
- Impact/Rollback：仅新增 Parser Owner 与 Project 授权操作，不扩项目 Admin 旁路；已提交取消事实不可删除。卸载 Owner 保留表/事件/收据可回退应用；真实 PG/HTTP 权限、幂等、故障回滚后才宣称 P02 PASS。Gate3/包不变。

## DEC-20260930-515 — PAR-01-A05-P01-P04-P03-P01 Parser 取消首响应版本表

- Date/WBS：2026-09-30 / Phase2 `PAR-01-A05-P01-P04-P03-P01`。输入冻结 API-03、CR-PAR-001、已有 P04-P01/P02 Worker 协作取消与 CR-PAR-002；前置 PASS。涉及 Jobs ORM/Schema 与 Audit 事件来源，不变更 `/api/v1`、用户权限、License 或依赖。
- 差异/方案：通用幂等收据只有结果引用，Audit 事件无 `lock_version`；Worker 后续终结会改变当前版本。不能用当前 Job 版本构造首次重放，也不能混用 Audit Export 专属表。新增独立 `job_parse_cancel_versions`，只存事件 ID 与首版本；0050 限制项目 Parser USER 取消事件来源并保护不可变历史，含历史 downgrade 拒绝。原冻结基线不追写。
- 验收/回滚：空库及已有 Job 升降级、来源/不可变/非空降级拒绝，PG18 PASS；后端1632（3跳过）/开发 wheel PASS。未装配 Owner，可回退应用入口并保留表；正式生产升级/历史恢复另验。P02 再接实际当前授权与同事务幂等响应，P03 处理过期/崩溃；Gate3不变。

## DEC-20260930-514 — PAR-01-A05-P01-P04 Parser 协作取消分层

- Date/WBS：2026-09-30 / Phase2 `PAR-01-A05-P01-P04`，先 `P04-P01` Jobs 当前租约取消识别/确认，再 `P04-P02` Document/Audit 同事务与 Worker 检查点。输入 ADR-007 的协作取消、冻结 Job `CANCEL_REQUESTED`、现有 Audit Owner 取消状态机和 P02/P03 Parser Worker；Gate2及前置满足。涉及 Jobs/Parser/Document/Audit 内部 Port，不增公开 API/权限、Schema/Migration、依赖或外发。
- 冲突/方案：现有通用 `heartbeat` 仅允许 RUNNING，若请求方将 Job 改成 CANCEL_REQUESTED，Parser 后台线程会误报心跳不可用并停止，而无 Job/ParseRecord 取消终结。不能让 Parser 直写 Jobs 表，也不能把取消按失败重试。选择 Jobs 自有 `pulse_parse`：RUNNING 续租，CANCEL_REQUESTED 只回报并停止续租，保留有限原租约供 Worker 在下一个安全检查点确认；已过期则留给独立恢复，不因线程仍活着续租无限期。Jobs `acknowledge_parse_cancel` 仅在当前 token/Worker/活租约、原请求三字段、正确 Owner/JobType 下关闭 Job/Lease/Attempt，供后续 Parser 同 UOW 调用。
- 验收/回滚：P01 在真实 PG18 证明 RUNNING 续租、CANCEL_REQUESTED 不续租、当前代可确认、旧 token/其他 Owner/过期拒写及 Audit 常规心跳不变；P02 再验证 Document/Audit/Jobs 同事务与 Worker 安全点。原取消请求授权 Owner 尚只为 Audit Export，Parser 用户请求入口另列后续，不能将 P01/P02 称为端到端用户取消。撤销未装配新 Port 可回滚；已确认终态历史不可回退，Gate3不变。
- P01 Executed：Jobs Service/Repository 新增 Parser 专用 `pulse_parse` 和仅供 Caller UOW 的当前租约确认；不改通用 heartbeat/Audit 语义。定向 Jobs Lease5、Python3.13 后端全量1628（3既有跳过）、Windows11 隔离 PG18 RUNNING 续租、请求取消后不续租、当前确认/旧或过期拒绝/其他 Owner 不可用、wheel PASS；随机库清理/PoC PG恢复停止。仅 Jobs 内部能力，P04整体未完成，Parser Worker 还未调用新 Port。
- P02 编码前补充：当前 Phase2，前置 P01/P03 已通过；只接 Parser Worker 的协作取消安全点和 Document/Audit/Jobs 原子确认，不改客户可调用取消 Owner。若启动写的提交回执不确定，Document 自有 Repository 按当前 Job/代数/固定版本查找现有 RUNNING 记录并取消，不以本地 `started is None` 推断数据库不存在；缺记录时只取消 Job/Audit，不伪造解析历史。心跳读到请求立即停止续租并标记，长同步操作返回后才收口；取消后结果文件可能成为不可见孤儿，留清理任务。确认必须在租约未过期且当前 token/Worker、原绑定有效时；并发发布以 Job 行锁序判唯一终态。验收含真实 PG 与文件、取消前/处理中/发布竞争、旧代/到期/审计及末端失败回滚、全量/wheel。
- P02 Executed：`ParserWorkerStep` 改用 Parser 专用 pulse，在抽取与发布安全点识别取消并停止续租；Document 自有当前 Job/代数 ParseRecord 核对 `RUNNING→CANCELLED`，即使 Start 回执不确定也不漏已提交记录，缺记录不伪造。Parser 编排 Document/Audit/Jobs 在同一短事务确认。Worker定向12、Python3.13 后端全量1631（3既有跳过）、Windows11隔离 PG18/真实文件抽取中取消无新结果、独立 PG18 启动回执不确定核对/未启动/审计与末端 Job 失败回滚、wheel PASS；随机库清理/PoC PG恢复停止。用户请求 Owner/正式 API、过期取消恢复和独立进程仍未接线；P04整体/Gate3不关闭。

## DEC-20260930-513 — PAR-01-A05-P01-P03 Parser Worker 失败分类与事务收口

- Date/WBS：2026-09-30 / Phase2 `PAR-01-A05-P01-P03`。前置 A05-P01-P02 单步成功与续租 PASS；输入为 ADR-007 至少一次/有界重试、DM-03 ParseRecord 历史和现有 Jobs `retry_or_fail`。涉及 Parser Application、Document 自有 ParseRecord 失败 Port、Jobs 当前租约与 Audit；无公开 API/权限/ORM/Migration/依赖或外发。
- 编码前检查：目标是对本 Worker 已持有的当前 `DOCUMENT_PARSE` 租约，按固定安全错误类别执行有限重试或最终失败；若 ParseRecord 已 RUNNING，Document `RUNNING→FAILED`、Audit 和 Jobs `RETRY_WAIT/FAILED` 在同一短事务提交，任一失败整体回滚。准备输入/启动之前尚无 ParseRecord 的失败只关闭当前 Job attempt 并追加 Audit，不伪造已启动 Document 事实，后续代的既有对账会补记未启动代。旧/过期 lease 与来源不符必须拒写。
- 选择/影响：已知格式/数据/配置错误不可重试；受控 IO/瞬时服务错误可重试，采用小范围有界退避，最大代数由现有 Job 执行。心跳失败、未知提交结果、租约失效或审计/数据库不可用不二次推断为可安全关闭，停止本 Worker 等待租约恢复；异常内容不得入 Audit。先 Document 行锁与安全错误码、后同 UOW Audit 和 Jobs 状态，沿用原先 Jobs 锁序。无 Schema 升级；可回滚尚未装配的内部服务，但历史失败记录不可删除。验证定向/PG18真实事务和回滚/后端全量/wheel；Gate3不变，取消/崩溃恢复和独立进程另列后续。
- Executed：Document 自有 `RUNNING→FAILED` Repository、Parser 固定错误分类与同事务 Document/Audit/Jobs 失败 Port 已接单步 Worker；可重试退避 5/15 秒且仅 Jobs 原有最大代数决定终态，未启动无 ParseRecord 的错误只结束 Job Attempt 并审计。心跳/Start 或结果发布不确定状态不推测失败、Worker 实例毒化。定向 Worker 9、Python3.13 后端全量1626（3既有跳过）、Windows11隔离 PG18 真实文件 Worker 成功+错误编码失败、独立 PG18 致命/可重试/未启动/旧租约拒绝/Audit 与末端 Job 失败回滚、wheel PASS；随机数据库清理、PoC PG恢复停止。无运行时独立进程/取消/崩溃恢复；终态前无 ParseRecord 的用户状态呈现需后续收口，Gate3不变。

## DEC-20260930-512 — PAR-01-A05-P01-P02 Parser Worker 单步成功链与续租

- Date/WBS：2026-09-30 / Phase2 依赖前置 PAR-01-A05-P01-P02。输入 CR-PAR-001 时序调整、Jobs 专用领取 P01、受控输入快照 A02、九类格式候选解析 A03、Document ParseRecord 启动/结果原子发布 A04；Gate2 已通过。涉及 Parser Application 的单步执行/格式分派和 Jobs 现有短事务心跳 Port，不增加 API、权限、ORM/Migration、依赖或外发。
- 编码前检查/目标：只处理受限 `DOCUMENT_PARSE` Job 的一个成功执行步骤：领取→当前租约输入快照→第1/2/3代启动→真实格式抽取→私有结果写一次→最终续租→fenced 同事务发布；长格式处理时后台定时心跳，心跳异常后禁止发布并停止当前 Worker 再领取。输入快照始终关闭，绝不持数据库事务跨文件/OCR 操作；重入同一 Worker 实例拒绝。图片/混合 PDF 需要显式离线 OCR Engine，未供给时失败关闭；纯文本 PDF 可走原生文本链。
- 方案/风险/回滚：组合已验服务，不让 Worker 绕过 Document/Jobs Port；与本实例同一 WorkerRef 的心跳线程只用独立短事务，退出须停线并校验，再同步续租后发布。解析/IO/DB异常暂保留 RUNNING Job 等待租约过期，且本实例停止再次领取；显式失败分类/重试/取消、崩溃确认对账与守护进程另列子项，不能把本项称为完整 Worker。实测合成短/长运行、真实 PG/文件/Audit/当前租约及异常拒发布、后端全量/wheel；仅内部服务，撤销未装配 Worker 可回滚，孤儿文件不可见，Gate3不变。
- Executed：`ParserWorkerStep` 接入 Parse 定向领取、当前 lease 快照、第1/2/3代启动、九类 profile 分派、私有结果一次写及 fenced 原子发布；后台短事务心跳与同步最终续租，失败毒化本 Worker 实例。定向4、Python3.13 后端全量1621（3既有跳过）、Windows11隔离 PostgreSQL18/真实本地文件合成长解析心跳、ResultRef/ParseRecord/Job/Audit 成功及空队列、wheel PASS；验证脚本初轮两处错误断言已修正后完整重跑，随机库清理并恢复 PoC PG 停止。真实 PG 夹具的 Queue/Document 源为内部桩，不声称浏览器上传来源已在此验证；未装配独立进程/失败关闭/取消/崩溃恢复，Gate3 不变。

## DEC-20260930-511 — PAR-01-A05-P01-P01 Parser Worker 定向 Job 领取

- Date/WBS：2026-09-30 / Phase2 依赖前置 PAR-01-A05-P01-P01。输入为冻结模块化单体/Jobs Owner、现有通用 Job Lease、Document ParseJob 入队及 CR-PAR-001 解析前置时序；Gate2与前置均满足。涉及 Jobs Application/Repository 内部领取，不涉及 Parser 内容、Document 表、公开 API/权限、ORM/Migration、依赖或数据外发。
- 编码前检查/目标：当前通用 `JobLeaseService.claim_next` 会领取任何 Job 类型，Parser Worker 不可调用它。新增 Jobs-owned `claim_next_parse`，仅在相同事务/行锁/fencing 下选择 `owner_module=document` 且 `job_type=DOCUMENT_PARSE`，过期接管/达到最大尝试的既有逻辑不变。验收为混合队列中只领取 Parse、非 Parse 行与 Lease/Attempt 全不变、过期接管和空队列行为、后端全量与 wheel。
- 方案比较/决策：不在 Parser 领取后再筛类型（会消耗其他 Owner 的 Job）；复用原 Jobs Repository 核心领取实现并在 SQL 候选查询加 Owner 过滤，保留通用领取语义不变。服务新增显式方法而不扩公开 API。可撤新方法回滚，未装配 Worker；未知混合队列数据一律不跨 Owner 修正。P01整体、正式 Worker/心跳/失败/取消、Gate3均未完成。
- Executed：Jobs Service/Repository 新增定向 `claim_next_parse`，保留通用领取实现与过期接管逻辑。定向3、Python3.13 后端全量1617（3既有跳过）、Windows11隔离 PG18 高优先级 Audit+Parse 混合队列、Parse 过期接管、Audit 行/Lease/Attempt 不变与通用领取回归、wheel PASS；随机库清理/PoC PG 恢复停止。正式 Worker 仍未接线，P01整体与 Gate3不关闭。

## DEC-20260930-510 — PAR-01-A04-P02-P03-P03 第2/3代当前租约原子成功发布

- Date/WBS：2026-09-30 / Phase2 依赖前置 PAR-01-A04-P02-P03-P03。输入冻结 DOC-04 ResultRef/ParseRecord/Job 时间与身份约束、P02-P02 首代真实原子发布、P03-P02 同一 Job 第2/3代启动均已验证。涉及 Parser 发布 Application 合同及 Document 自有内部请求验证；无 ORM/Migration、公开 API、权限、依赖或外发变化。
- 编码前检查/目标：将当前硬编码首代的成功发布条件扩为当前第1～3代，并强制 `prepared`、`started`、Jobs 当前 Claim、Document ParseRecord 的 attempt_no 完全相等。私有文件实读/Hash、Outbox/固定 Version/模型证明、ResultRef→ParseRecord→Audit→Job 完成顺序保持不变；旧 fencing、旧 ParseRecord、改变来源及审计/最终 Job 失败仍全部拒绝或回滚。
- 方案/风险/回滚：复用已有原子事务与冻结触发器，不开第二条“重试快速成功”路径。真实隔离 PG18 分别验证第2和第3代结果发布、旧代拒绝、唯一成功引用/时间顺序，单元/后端全量/wheel；不重新解释跨 Job 用户主动重试。撤销本次内部代数扩展即可回退到首代；已成功结果历史不可删。正式 Worker/崩溃恢复与 Gate3 仍待。
- Executed：`StoredParseResult`/`ParseSuccessRequest` 与 `PublishParserResult` 仅放宽第1～3代，同时强制 prepared/started/current Claim/Document 行同代。定向5、Python3.13 后端全量1616（3既有跳过）、Windows11 隔离 PG18 第2与第3代真实文件→ResultRef/ParseRecord/真实 Audit/Job 成功、旧第2代在第三代下拒绝、时间顺序和唯一结果引用、wheel PASS；扩大原 P03-P02 隔离验证脚本作联合回归，随机库清理/PG恢复停止。跨 Job 用户主动重试、正式 Worker/崩溃恢复、Gate3仍待。

## DEC-20260930-509 — PAR-01-A04-P02-P03-P02 同一 Job 旧 ParseRecord 对账与新尝试启动

- Date/WBS：2026-09-30 / Phase2 依赖前置 PAR-01-A04-P02-P03-P02。输入为冻结 DOC-04 连续 ParseRecord 尝试序号、P03-P01 Jobs 旧代证明、P02-P01 首次启动及真实 PG 触发器；Gate2 已通过。涉及 Parser Application、Document 自有 ParseRecord DTO/Repository、Jobs 只读证明及 Audit 追加；不涉及公开 API/权限、ORM/Migration、依赖或客户数据外发。
- 编码前检查/目标：只处理同一 DOCUMENT_PARSE Job 的第2/3代后台租约；重核当前租约/Outbox/固定 Document 来源，按旧代证明将遗留 RUNNING 变 FAILED、未启动代补记 PENDING→CANCELLED，然后 PENDING→RUNNING 启动当前代；全流程一笔短事务，审计每个被对账的旧记录。已有终态只能逐字段吻合，不得覆盖成功或其他 Job 的历史。现有 `StartedParseAttempt` 内部合同需允许 1..3，不变更冻结公开 Contract。
- 方案比较/决策：不把旧 RUNNING 直接复用为新代，也不跳过缺失旧代（均违反冻结保留/连续性）；采用 Jobs 证明驱动 Document 对账，Document 不直接查 Jobs 表。当前仅同一 Job 原有代数，另一个 Job 的用户主动重试存在全局 ParseRecord 序号与新 Job attempt_no 起点不同的问题，另立任务分析，不能冒称已支持。
- 验收/风险/回滚：隔离 PG18 真实触发器验证旧 RUNNING、未启动、第三代、同代幂等、旧代/跨 Job/来源异常与 Audit 失败回滚；定向/后端全量/wheel。旧记录的 FAILED 完成时间采用 Jobs 原代完成事实；未启动代 CANCELLED 完成时间为补记时间并保留原 Job 尝试证明，不能伪称当时生成了 ParseRecord。可撤未装配新服务/Repository；历史不可删、Gate3不变。成功发布第2/3代、正式 Worker 和用户主动重试仍待后续任务。
- Executed：新增内部 `StartRetryParseAttempt` 与 Document `start_retry`；同一 Job 当前 lease/Outbox/Document 来源及旧 Jobs 证明重核后，旧 RUNNING→FAILED 或未启动 PENDING→CANCELLED、当前 PENDING→RUNNING 与每条旧历史真实 Audit 同一短事务。定向3、Python3.13 后端全量1614（3既有跳过）、Windows11 隔离 PG18 旧 RUNNING、未启动、第三代、幂等、旧代拒绝及 Audit失败回滚、wheel PASS；随机库清理、PoC PG 恢复停止。跨 Job 主动重试与第2/3代成功发布未验，不关闭 P03/Gate3。

## DEC-20260930-508 — PAR-01-A04-P02-P03-P01 旧 JobAttempt 事实证明

- Date/WBS：2026-09-30 / Phase 2 依赖前置 PAR-01-A04-P02-P03-P01。输入为 Gate2 冻结的 DOC-04 ParseRecord 连续尝试序号、现有 Job lease/fencing 状态机、P02-P02 首次原子成功发布；前置均满足。涉及 Jobs Application DTO 与已有 Lease Repository 的只读证明，不写 Document 表；无 API、权限、ORM/Migration、依赖或外发变化。
- 编码前检查：当前 Phase2；目标仅证明当前 DOCUMENT_PARSE 活租约之前每代 JobAttempt 均已终结、顺序连续、Lease 与 Attempt 身份/时间一致。验收为真实 PostgreSQL18 第一次过期→第二次领取后证明；当前租约错代/过期、历史行缺失/篡改必须失败关闭，单元及后端全量、wheel 均通过。
- Decision/Reason：Jobs Owner 在当前 Job 行锁和 lease 检查下返回最小化不可变 `ClosedJobAttempt` 元组，按 attempt_no 严格 1..N-1 排列；Document 后续凭该证明终结旧 ParseRecord 或补记未启动尝试。不能由 Document 直接读 Jobs 私有表，也不能从最新 attempt_no 猜测历史。此子任务只建立证明，不把重试启动标 PASS。
- Impact/Rollback：不修改冻结 schema/公开 Contract；撤销未装配内部证明即可回滚。风险为旧 Lease/Attempt 数据异常导致新解析被拒绝，优先保留历史等待修复而不伪造。P03 整体、Worker 和 Gate3 仍 INCOMPLETE。
- Executed：Jobs 自有 `ClosedJobAttempt` 不可变证明及当前行锁下的逐代连续性、旧 Lease/Attempt 身份和时间检查已实现。定向2、Python3.13 后端全量1611（3既有跳过）、Windows11 隔离 PostgreSQL18 第1→2→3次过期接管/旧代拒绝/篡改拒绝、wheel PASS；随机库清理且 PoC PG 恢复停止。仅证明历史，尚不写旧 ParseRecord 或启动重试。

## DEC-20260930-507 — PAR-01-A04-P02-P02 当前租约 ParseResult 原子成功发布

- Date/WBS：2026-09-30 / Phase 2 依赖前置 PAR-01-A04-P02-P02；A04-P01 受控结果字节、P02-P01 首次 RUNNING ParseRecord 均已通过。输入冻结 DOC-04 Schema、Job Lease 和 `DocumentParseJobResults` 的时间顺序约束。
- 编码前检查：涉及 Parser Application 协调、Document 自有 ParseResultRef/ParseRecord Repository、Jobs 现有当前租约/完成 Port 和 Audit 同事务追加；无新 ORM/Migration、公开 API、权限或 AI 外发。验收为字节/模型/源版本/Job/Outbox/租约完全绑定，Hash/大小实读，结果引用先于 ParseRecord/Job 完成，陈旧代、篡改、Audit失败一律回滚 DB 成功。
- 决策：不使用 `JobLeaseService.finish(publish callback)`（它先设置 Job 完成时间，若回调再建 ResultRef 会违反结果时间 ≤ Job 完成时间的已冻结读取不变量）。改为单短事务中先 `check_current` 锁当前 Job，复核 Outbox 和 Document 来源，Document 插入不可变 ResultRef→升 RUNNING ParseRecord 为 SUCCEEDED→追加 Audit，最后调用同一 Jobs Repository 的 `finish` 再核租约并设置更晚的 Job 完成时间，然后一次提交。任何错误回滚全部 DB 状态；事先写盘的孤儿保留私有，不自动发布或删除。
- 风险/回滚：当前仅首次 Attempt；过期/取消/重试历史对账仍需独立实现。文件与 DB 非单一事务，正式 Worker 恢复必须验证孤儿/损坏；发布后 Evidence 授权读取仍未实现。仅新增未装配端口/服务可回滚，不删历史，不关闭 Gate3。
- Executed：Document 所有的结果证明/Repository 与 Parser 发布协调已实现；私有字节实读复验、当前 lease/Outbox/Document 固定来源重核、ResultRef→ParseRecord→真实 Audit→Job 完成均在一笔短事务中。定向3、Python3.13 后端全量1609（3既有跳过）、Windows11 隔离 PostgreSQL18 真实触发器/审计及两处晚期失败回滚、wheel PASS。PoC 端口55432被本机代理占用，验证改用55434，不改生产端口。仅首次 Attempt，尚未组合正式 Worker，Gate3不变。

## DEC-20260930-506 — PAR-01-A04-P02-P01 首次解析 Attempt 的 PENDING→RUNNING

- Date/WBS：2026-09-30 / Phase 2 依赖前置 PAR-01-A04-P02-P01；A03 候选解析和 A04-P01 私有结果文件已通过，冻结 DB Schema V1 的 ParseRecord 触发器要求 INSERT PENDING、随后 RUNNING，且同版本/profile/parser_version 的 attempt 序号连续。
- 编码前检查：只实现当前首次 DOCUMENT_PARSE Job 租约对应的 Document ParseRecord 启动；涉及 Job lease/Outbox Application Port、Document 来源 Port 与 ParseRecord Repository，当前无公开 API/权限、Schema/Migration、结果发布或正式 Evidence。验收为来源/lease/fencing 绑定、PostgreSQL 真实触发器状态转换、重复同租约幂等、错误租约/跨版本拒绝及后端回归。
- Decision：首次 Attempt 必须先取得 A02 已验证输入快照，后以短事务重核当前 Job/Outbox/Document 固定来源；Document Repository 对固定 Version 加锁，只允许 `attempt_no=1` 和无同 profile/version 历史，插入 PENDING 并在同事务升为 RUNNING/lock_version1。重复当前同一 Job 的 RUNNING 返回原记录，不改历史。不得把此分项视作重试支持；第二/第三次尝试与上一条运行记录的失败对账单独实现，再允许 Worker 启动解析。
- 风险/回滚：文件快照与记录启动间仍有时间窗，后续 Worker 必须心跳/取消检查，成功发布再 fencing；真实 DB 测试不能代替完整 Worker/崩溃恢复。可撤未装配服务/Repository 回滚，历史 ParseRecord 不得删除。Gate3 不变。
- Executed：新增 Parser 短事务协调与 Document 自有 DTO/Repository，固定来源/租约/Outbox 重核后按冻结触发器插入 PENDING→RUNNING；仅 `attempt_no=1`，同 Job 同代幂等，其他 Job/过期租约/变更来源失败关闭。定向3、Python3.13后端全量1606（3既有跳过）、真实隔离PostgreSQL18触发器/1行/幂等/冲突验证、wheel包含PASS；随机数据库清理，PoC PG恢复停止。尚无重试历史对账、结果引用/Job成功同事务发布，故 P02 整体未完成。

## DEC-20260930-505 — PAR-01-A04-P01 ParseResult 私有一次性存储

- Date/WBS：2026-09-30 / Phase 2 依赖前置 PAR-01-A04-P01；A03 已生成版本化 canonical JSON 候选；冻结 DB Schema V1 已有 `doc_parse_result_refs` 的相对 locator、Hash、大小和 Schema 版本，尚无正式结果物理写入器。Gate 3 未通过。
- 编码前检查：只涉及 Document 拥有的结果物理存储适配器及验证测试，不更改 ORM/Migration、公开 API、角色权限或 Job/ParseRecord 状态。输入必须是 Parser 内部候选规范字节、预分配结果 UUID、Scope/Project 坐标；调用者仍须完成当前租约/Document 来源复核并在数据库事务发布。
- Decision：在 Document 私有 data_root 的专用 `results` 命名空间，以作用域/项目/结果 UUID 生成不可客户端指定的相对 locator；受控同卷 staging 写入、flush/fsync、hash/size 后无覆盖提升，最终文件按 Hash/size 重开验证。数据库发布失败后未引用文件保留为不可见孤儿，后续独立恢复/清理，不在本项做危险删除。绝不返回绝对路径给 HTTP/外部调用。
- 风险/回滚/验证：文件系统提升与数据库提交非单一事务，后续 P02 必须先写盘再在短事务中核 fencing/来源并发布；崩溃孤儿不得自动当成功。撤未装配适配器可回滚，不删历史结果。测试跨 Scope 相对定位、真实字节/重开/不可覆盖、坏摘要与路径污染、源目录符号链接/重解析拒绝、写入失败可恢复；性能/目标账户 ACL/Server2025/Debian 尚待。
- Executed：新增 Document 私有 `results` 命名空间的唯一 UUID、同卷无覆盖提升、文件 flush/fsync、SHA/大小复验与作用域绑定重开。定向4（目录符号链接因本机账户权限跳过1，普通文件伪目录拒绝通过）、Python3.13 后端全量1603（3跳过）、wheel PASS。首轮 GLOBAL 自身被测试误判跨 Scope 导致1失败，修正夹具后完整重跑。未写 `doc_parse_result_refs`、未接 Job/ParseRecord，失败时孤儿仍私有且保留；目标账户 ACL/电源故障恢复未验。

## DEC-20260930-504 — PAR-01-A03-P04-P02 扫描 PDF/图片 OCR 候选位置

- Date/WBS：2026-09-30 / Phase 2 依赖前置 PAR-01-A03-P04-P02；A02-P02 受控固定版本快照、P03 原生 PDF、P04-P01 离线主链已通过，Gate 3 仍未通过。
- 编码前检查：只涉及 Parser Application 的 PDF/PNG/JPEG/TIFF 分页扫描、候选节点和页内 bbox/模型身份；不改 ORM/Migration、公开 API、权限或正式 Evidence。OCR 结果须经当前 Worker fencing 再发布，此项不接 Worker。
- Decision：图片经 Pillow 验格式/尺寸/方向后转 RGB 内存数组；多帧 TIFF 逐页处理。PDF 用 PyMuPDF 按固定倍率仅渲染无原生文本页，其余页保留 P03 原生字符范围；任何页 OCR 无文本/异常/超限都使整个候选结果失败。OCR 区域按 PAGE+归一化 bbox、置信度与显式模型复合 SHA-256 固定；无源文件路径、模型目录或临时图片进入结果。源摘要和大小在读取时重核。原生/识别文字都仅为候选，不自动形成 Evidence 或已确认业务事实。
- 风险/回滚/验证：bbox 是 OCR 区域不是逐字高亮；EXIF 非默认方向暂失败，避免 Viewer 坐标歧义。真正空白 PDF 页会要求 OCR 并可能失败。大图/页数/累计像素与输出节点有限额，超限不截断成功。撤新增应用模块和 DTO 增量即可回滚，无数据迁移。单元覆盖图片/多页混合/篡改/无文本/格式与定位，真实本机离线模型合成扫描文件与全量回归；客户资料/生产 Worker/Gate3 不在本项结论内。
- Executed：PNG/双页 TIFF、原生文字+扫描页混合 PDF 候选节点及 PAGE bbox/置信度/模型 Hash，错误 MIME、EXIF 方向、篡改/无 OCR 行失败关闭；定向4、Python3.13 后端全量1599（2既有跳过）、wheel PASS。`verify_parser_ocr_synthetic.py` 在本机 Windows11 PoC 离线运行时用真实模型复跑合成 PNG 1 条和混合 PDF 原生1/OCR1 条，exit0；全部内存生成、无客户文件/外发。无现有客户扫描件质量复验、Worker/持久发布/Viewer、发行许可或 Gate3 结论。

## DEC-20260930-503 — PAR-01-A03-P04-P01 离线 PaddleOCR 主链适配器

- Date/WBS：2026-09-30 / Phase 2 依赖前置 PAR-01-A03-P04-P01。PAR-01-A03-P03 已将无文本 PDF 明确标记 OCR_REQUIRED；本项只建真实离线 OCR 主链适配器及图像区域 DTO，不发布 ParseRecord。
- 编码前检查：输入为本机 POC-05 Windows11 已验证 PaddleOCR/PaddlePaddle CPU 运行时与 PP-OCRv5 mobile det/rec 模型；涉及 Parser 基础设施层的模型加载、OCR 候选文本/归一化像素框，无数据库/API/权限、客户数据或外发。验收为显式本地模型加载、合成图片真实识别与 bbox、畸形/缺模型拒绝和后端回归。
- Decision：沿用 POC-01 固定版本 PaddleOCR3.7.0/PaddlePaddle3.3.1/Numpy2.3.5/Pillow12.3.0；启用 CPU `enable_mkldnn=False`，仅接受操作员指定的两个本地模型目录，读取关键模型文件 Hash 形成非路径指纹。直接传内存 RGB ndarray，不创建源图片临时文件；OCR 返回行文本/置信度/归一化 bbox。运行环境须显式禁止模型源在线检查；不得把无识别行当成功。Tesseract 仍只作后续辅助链，不替代主模型。
- 风险/回滚：Paddle 依赖和模型较大，正式发行须校验模型 Hash、许可及目标账户的离线恢复；模型目录本身不入 Git/包。撤适配器与依赖即可回滚，无 Migration。此项真实合成图片识别不等于扫描 PDF/OCR 质量 Golden Dataset 或正式 Evidence。
- Executed：本机 Windows11 PoC 离线环境用显式本地 PP-OCRv5 mobile det/rec 模型真实识别合成 `PROJECT SCOPE APPROVED`，返回一条归一化区域框；模型复合 SHA-256 为 `511580fe3e72fe1759ce18ac05d5454eee88865303603631be644a4978889cf4`（不含模型文件/路径）。首次 WindowsPath 精确类型判断误拒绝，改为 Path 子类检查并完整重跑。补强预期指纹匹配、离线开关、文件完整性、图像/输出边界；定向4、Python3.13 后端全量1595（2既有跳过）、wheel模块与依赖元数据 PASS。未物理断网/实际扫描PDF、未接 Worker/结果发布、目标账户/发行许可证仍待。

## DEC-20260930-502 — PAR-01-A03-P03 PDF 原生正文页内定位

- Date/WBS：2026-09-30 / Phase 2 依赖前置 PAR-01-A03-P03；固定版本快照及结构化候选结果前置通过，Gate 3 不变。
- 编码前检查：仅 Parser 内部 PDF 抽取、页内 TEXT_RANGE 位置、生产 PyMuPDF 依赖与测试；无 Schema/Migration、公开 API、权限或正式 Evidence。输入为当前租约已验证的私有字节快照；结果仍需 Worker 重新 fencing 才能发布。
- Decision：沿用 POC-01 Windows/Python3.13 已验证 `PyMuPDF==1.28.2`。逐页 `get_text("text")` 的 NFC/LF 规范化文本按非空行记 page_no、字符区间与 SHA-256 指纹；不猜自动标题/表格或物理视觉框。空 PDF、加密、损坏、超限失败关闭；任一无文本页返回 `PARSER_OCR_REQUIRED`，不把混合扫描 PDF 部分标成功。下一分项接 OCR 后再调整组合策略。
- 风险/回滚/验证：页内字符范围可用相同 parser_version 重放，但不是高亮坐标；后续受权 resolver/Viewer 要做页跳转和原文定位实测。撤新模块与依赖即可回滚。测试合成 PDF 双页重放、无文本页、损坏/Hash/格式拒绝，全量回归与 wheel；PoC/正式发布的 PyMuPDF 授权义务仍须纳入发行合规复核，不能以单元 PASS 代替。
- Executed：双页合成原生文本 PDF 逐行页内位置及指纹重放、混合空/无文本页 OCR_REQUIRED、损坏 PDF/篡改快照拒绝定向3；Python3.13 后端全量1591（2既有跳过）、开发wheel构建 PASS。当前任何无文本页均需OCR，包含真正空白页；尚未实现 bbox 高亮、表格、OCR、Worker/发布，发行许可未审结。

## DEC-20260930-501 — PAR-01-A03-P02 Office 来源位置与依赖

- Date/WBS：2026-09-30 / Phase 2 依赖前置 PAR-01-A03-P02；PAR-01-A03-P01 结构化结果、CR-PAR-001 和固定版本输入已通过，Gate 3 不变。
- 编码前检查：只修改 Parser 内部 Office 抽取、结果位置变体、生产依赖和测试；输入固定 DocumentVersion 的当前租约已验证私有快照；涉及 DOCX/PPTX/XLSX 候选节点，不改数据库、公开 API、权限、AI Provider 或正式 Evidence。验收为合成 Office 文件的正文与可重放源坐标、恶意/损坏 ZIP 拒绝、版本/摘要一致、全量回归和 wheel。
- Decision：沿用 POC-01 Windows/Python3.13 已验证的 `python-docx==1.2.0`、`python-pptx==1.0.2`、`openpyxl==3.1.5` 纳入正式后端；DOCX 正文按 XML body 顺序用 PARAGRAPH，表格逐格用 TABLE_CELL；PPTX 文字形状用 SLIDE_SHAPE、表格单元格用带 slide/shape 的 TABLE_CELL anchor；XLSX 公式原文/单元格用 SHEET_RANGE，禁止执行公式或外部链接。物理页码不猜测。ZIP 预检限制数量、展开总量、恶意路径及加密项，解析节点/文本输出超限显式失败。
- 风险/回滚：单元格合并、PPTX 表格与可视层次、自动分页/渲染并非本项证明；后续受权 resolver 必须重读固定版本才能对位置作 Evidence 断言。撤新增模块和三项依赖即可回滚，无迁移。Windows Server/Debian、真实客户 Office、结果发布与点击定位未验。
- Executed：三种 Office 合成真文件正文/位置、DOCX 合并单元格左上去重、XLSX 稀疏大范围先拒绝、ZIP 损坏/恶意路径及摘要失配均通过；定向 6、Python3.13 后端全量 1588（2 既有跳过）、开发 wheel 包含模块与三项依赖元数据、diff 检查 PASS。仅证明固定合成文件与定位形状，不声称 Office 自动分页/真实客户文件/受权 Evidence Viewer。

## DEC-20260930-500 — PAR-01-A03-P01 文本与 CSV 可重放结构化定位

- Date/WBS：2026-09-30 / Phase 2 依赖前置 PAR-01-A03-P01；输入为 CR-PAR-001、PAR-01-A01 profile 和 A02-P02 当前租约下受控字节快照。Gate 3 未通过。
- 编码前检查：只涉及 Parser Application 内部 ParsedResult/Node 与纯文本、CSV 抽取；实体为固定 DocumentVersion、受控输入快照和候选解析节点；不改 ORM/Migration、公开 API、角色权限或依赖。节点绝不自动成为 Evidence/正式业务事实。
- Decision：纯文本按 UTF-8-SIG、统一 CRLF/CR 为 LF，在固定版本的规范化全文中使用非空行字符区间及 SHA-256 指纹定位；CSV 按标准逗号方言逐单元格产出逻辑 `CSV` sheet 的 A1 坐标，保留引号内换行。结构化结果采用版本化、确定性序列化，源摘要和大小重新核对；编码错误、CSV 错误、超出安全上限或不匹配 profile 一律失败，不产出部分成功。后续 Office/PDF/OCR 可扩展位置变体，但不在本项混入。
- 风险/回滚/验证：CSV 的 `CSV` 是固定逻辑 sheet 标识，后续受权 Evidence resolver 必须重读同一 DocumentVersion 才能把坐标确认为实际证据；文本偏移基于规范化文本而非原字节，需同版本/同 parser_version 重放。可撤新增 Parser 内部模块回滚，无数据迁移。测试 BOM/中文/CRLF、引号内换行/单元格位置、摘要/类型/编码/输出上限拒绝、稳定序列化及全量回归；尚不声称 Worker 心跳、结果发布或 Evidence 点击定位通过。
- Executed：新增结构化候选结果和 TEXT_RANGE/SHEET_RANGE 类型化位置、严格 UTF-8-SIG 文本/逗号 CSV 真实抽取。定向 4、Python3.13 后端全量 1582 项（2 既有跳过）、开发 wheel 构建/包含、diff 检查 PASS；冻结 EvidenceLocator 格式校验仅证明形状兼容，不证明 DocumentVersion 内容或用户权限。安全上限为规范化前 3200 万字符及 10 万节点，超限显式失败，不截断成功；尚无 Worker/ParseRecord 发布、Office/PDF/OCR 与受权定位体验。

## DEC-20260930-499 — PAR-01-A02-P02 当前租约下的受控文件快照

- Date/WBS：2026-09-30 / Phase 2 依赖前置 PAR-01-A02-P02；CR-PAR-001、A01 profile 合同和 A02-P01 Document 来源元数据 Port 已完成，Gate 3 不因此提前通过。
- Decision/Reason：Worker 输入只接受当前 Job fencing token/worker_ref，短事务中依次核 Job Lease、DOCUMENT_PARSE Job/Outbox 绑定与 Document 原上传/Audit/固定文件元数据；事务外由既有 LocalFileStorage 完整复制并核 Hash/大小，之后第二短事务复核相同三方事实。仅向 Parser 返回已验证私有字节流与 profile，不返回 locator。失配关闭并记录独立完整性 Audit；长解析期间由未来 Worker 心跳，结果发布仍须再做 fencing。
- Impact/rollback/validation：不新增 API/Schema/Migration/权限/依赖；撤新 Parser 服务与验证接线可回滚。定向验证伪造/过期租约、Outbox/Document 漂移、Hash 失配关闭并审计、快照关闭，真实 PG/文件正常链与租约失败链、全量回归和 wheel。不得把“可取得解析输入”写为 OCR/Worker 已运行或 Evidence 定位成功。
- Executed：新增 `PrepareParserInput` 两次短事务核租约/队列/来源、事务外受控快照及完整性 Audit；定向 6、后端全量 1578（2 既有跳过）、真实隔离 PG/文件正常字节、错误 fencing token、篡改拒绝与 Audit、wheel 包含均 PASS。仅手动领取合成 Job 验证输入，未启动正式 Worker、心跳或发布 ParseRecord。

## DEC-20260930-498 — PAR-01-A02-P01 Document 拥有的 Parser 输入元数据 Port

- Date/WBS：2026-09-30 / Phase 2 依赖前置 PAR-01-A02-P01；`CR-PAR-001` 已记录时序调整，PAR-01-A01 格式策略合同通过。
- Decision/Reason：复用 Document `CommittedParseDocumentSource` 的上传提交与 Audit 原始证明，在同一调用方事务内增加内部 `read_input`，仅向受控 Parser Worker 的下一层提供固定 DocumentVersion 对应 FileObject 的哈希、大小、检测 MIME 和私有相对 locator；不通过用户 Cookie，也不公开至 HTTP。后续 Worker 必须先核当前 Job lease/Outbox 并在文件读取后复核，单独 DTO 不是授权凭据。
- Impact/rollback/validation：只改 Document Application/Repository 内部读取与测试，不改 Schema/Migration、冻结 API 或角色。回滚可撤方法/DTO；验证严格来源绑定、错误脱敏、畸形/路径拒绝及正确 Python3.13 全量回归，真实 PG/物理快照留下一子项，不能将元数据视为已验证文件字节。
- 实施中偏差：首轮真实上传后的读取被旧 `purpose_code='SOURCE_UPLOAD'` 检查拒绝，而上传 API 将用户声明用途（如 `PROJECT_RECORD`）保存为 `purpose_code`；该码不是来源类型。选择保留 COMMITTED Intent、固定 Version/File、`source_metadata/source_ref='UPLOAD'` 和 Audit 的检查，移除错误的单值用途限制；重跑 PostgreSQL 验证正常与伪造主体拒绝，不改变冻结字段/公开合同。
- Executed：Document 内部新增 `DocumentParseInputSource` 与 `read_input`、SQLAlchemy 同事务固定 File/Version 元数据复核，并修正用途码误判。定向 7、Python3.13 后端全量 1572（2 既有跳过）、真实隔离 PG 上传后来源元数据/Audit/伪造 actor 拒绝、wheel 构建 PASS；首轮 PG 失败已记录并修复重跑。真实文件快照/租约双检与 Parser Worker 未实现，P01 仅内部元数据 Port PASS。

## DEC-20260930-497 — PAR-01-A01 生产 Parser 输入与策略合同

- Date/WBS：2026-09-30 / Phase 2 依赖前置 PAR-01-A01；依据 `CR-PAR-001`，不调整 Gate 3 结论。
- Decision/Reason：在 Parser 自有 Application 合同中对不可变 DocumentVersion ID、SHA-256、大小和检测 MIME 建立严格输入描述与固定版本 profile 选择；PDF 保留正文优先/OCR 按需，扫描/图片由 PaddleOCR 主链、辅助链待真实执行验证。此项不读取文件、不执行 OCR、不创建 SUCCEEDED ParseRecord。
- Impact/rollback/validation：无数据库/API/权限/新依赖；独立模块可撤。校验支持格式、畸形/伪造输入和不变性，后端回归与 wheel；后续 Worker 必须经 Document 授权快照复核摘要和 Job fencing，不能用本合同推断真实解析或 Evidence 精确定位。
- Executed：新增 Parser 自有固定版本输入与九种已接受 MIME 的版本化策略选择、失败关闭测试；定向 3、Python 3.13 后端全量 1569 项（2 项既有跳过）、隔离 wheel 构建与模块打包检查通过。默认 Python 3.14 缺项目导入/依赖、虚拟环境无 `setuptools` 的非隔离构建失败均在正确环境/隔离构建重跑，不冒称 Worker 已运行。

## DEC-20260930-496 — DOC-05-A06-P03 隔离浏览器 ParseRecord 只读验收

- Date/WBS：2026-09-30 / Phase2 DOC-05-A06-P03。前置 A06-P01/P02 前端合同、DOC-04-A05 Windows Parse 列表组合、A04-P03 真文件下载夹具均已验证；P08-A02 的文件 UI 上传确认仍待，本项只读且不进行文件选择/上传。
- Decision/Reason：复用随机库/角色/Vault/临时文件根夹具的真实文件支撑 DocumentVersion，在该固定版本下仅插入合成 PENDING ParseRecord/Job 元数据；独立 API-only 和 IAB 页面两份证据，浏览器由项目详情→文档历史→详情→版本→解析状态，验证按需状态、固定版本和安全投影。PENDING 不冒充 Worker 消费/解析成功，文件实际下载也不在本项重复验收。
- Impact/rollback/validation：只扩验证夹具、进度/版本说明，不改生产 API/Schema/Migration/权限/依赖；撤新增模式可回滚。随机资源/真实文件精确清理、匿名/跨项目拒绝、游标页与浏览器 UI/SQL 核对；失败留真实记录，不能由 API-only 外推浏览器 PASS。正式信任/Server2025/Debian/性能/Gate3/可用包不在本项关闭。
- Executed：API-only 首轮被 DB Job 载荷约束拒绝，补齐固定 Document/Version refs；第二轮仅会话计数断言误设为 1，修为实际 Admin+Member 两会话后重跑 exit0。实际 IAB 合成成员经项目→文档→可用版本打开面板，看到同一固定版本三次 PENDING 尝试，刷新仍为三条；SQL/文件及随机库、角色、Vault 清理 exit0。未执行浏览器文件上传或 Worker 消费。

## DEC-20260930-495 — DOC-05-A06-P02 项目版本解析状态界面

- Date/WBS：2026-09-30 / Phase2 DOC-05-A06-P02。P01 固定版本 ParseRecord 安全只读客户端已验证并同步；项目 Document 详情/版本历史已有受权入口。P08-A02 浏览器上传仍待确认，但只读状态面板可独立实施。
- Decision/Reason：在当前文档的每个可用版本行增加按需解析状态面板，一次只显示一个版本的受权 ParseRecord；切版本、切项目/文档、刷新与失败要清旧结果/阻断迟到响应。提供 50 条续页与显式刷新，不自动轮询或暗示解析 Job 已完成。仅显示服务器安全投影的状态/尝试/Job、结果引用和时间，不显示解析正文、物理路径或无权错误细节。
- Impact/rollback/validation：只修改项目文档详情 Vue 与定向测试，无新路由、后端 API、Schema/Migration、权限或依赖变化；可撤面板回滚。测试入口按需、双版本切换/迟到、刷新、空态/续页、拒绝清旧/401、路由变化/会话失效、没有原始内容泄漏；全量前端测试/typecheck/build。实际 Windows 浏览器/PG 与 Worker 处理另验，不能外推 Gate3 或 UAT。
- Executed：新增单版本按需解析面板、续页/刷新及切换代际保护，401/404 清旧；定向 6 与全量 1012 项/typecheck/build PASS。未运行实际浏览器/PG，不宣称 Worker/Locator/Gate 通过。

## DEC-20260930-494 — DOC-05-A06-P01 固定版本 ParseRecord 只读客户端

- Date/WBS：2026-09-30 / Phase2 DOC-05-A06-P01。P08-A02 浏览器文件操作待确认，但后端 `DOC-04-A05` 已在 Windows 显式组合实现冻结 `DOCUMENT_PARSE_LIST`；现有前端 DocumentReadClient 具固定 Scope/Document/Version 路径与安全 GET。此独立只读项不依赖浏览器上传或 Phase3 Worker。
- Decision/Reason：在 DocumentReadClient 中增加 PROJECT/GLOBAL 固定版本 ParseRecord 分页读取与严格安全投影，仅显示状态/尝试/Job 引用和必要时间、错误码，不返回物理路径或原始解析结果。验证 Session 受权仍由后端承担，客户端只做输入及响应防御；入队/`PENDING` 不能写成解析成功。
- Impact/rollback/validation：仅前端 Document API/测试与进度，不改冻结 API、Schema/Migration、权限、技术栈或依赖；撤新增方法可回滚。测试非法 Scope/ID/cursor 不发网、双 Scope 固定路径、最多 50 条/游标、状态时间形状/重复/脱敏、401/403/404/非预期错误及超时，前端全量/typecheck/build；页面与真实浏览器/PG 另验。正式 Parse Worker、精确 Evidence Locator、Gate3/可用包不因本项通过。
- Executed：新增固定版本 ParseRecord 安全客户端和独立测试。首轮 1006 项测试通过但新测试夹具 TypeScript 返回类型报错，标注后 typecheck/build/全量 1006 项均 exit0；未运行真实浏览器/PG 或 Worker，不升级 Gate。

## DEC-20260930-493 — DOC-05-A05-P08-A02 Windows 11 实际浏览器上传

- Date/WBS：2026-09-30 / Phase2 DOC-05-A05-P08-A02。前置 P08-A01 网络/PG/文件 exit0 与 P07 页面合同；冻结 `/api/v1`/DB0049 不变。涉及 Document UploadIntent、FileObject、Version、Parse Job/Audit，仅在每轮随机隔离库和临时文件根验收。
- Decision/Reason：在既有本机浏览器夹具增加独立 `--document-upload-browser` 模式，用两份仓库内非客户合成 PDF 经真实页面新建/升版，核页面状态、浏览器实际内容请求与受权文档读取；退出时 SQL/物理文件/Job/Audit 与随机资源清理断言。P08-A01 的 HTTPX 不能替代浏览器；Worker 解析完成、100MB 峰值内存/性能和正式信任另验。
- Risk/rollback/validation：浏览器文件选择属 UI 上传动作，先取得本次明确授权再执行；无客户文件/外网。只改验证夹具和进度，撤模式及两份合成夹具可回滚；保留失败和修复过程，不能把未执行的浏览器结论标 PASS。无生产 API/Schema/Migration/权限/依赖或升级变化。

## DEC-20260930-492 — DOC-05-A05-P08-A01 隔离网络 API/PG/真实文件验收拆分

- Date/WBS：2026-09-30 / Phase2 DOC-05-A05-P08-A01。P01～P07 客户端/页面合同与既有 Windows 写组合 `validation/doc-03-a04-a04-upload-finalize-platform/verify.py` 满足前置；该既有脚本使用 TestClient，不证明真实网络浏览器长度头。
- Decision/Reason：先扩展已验证的随机库/角色/Vault/临时文件根网络夹具，以真实 HTTP 与 PostgreSQL/LocalFileStorage 核验 PROJECT 新建/升版的 Create→Content→Commit、短时 token、Content-Length/Hash、下载字节、Parse Job 入队、Audit/幂等/跨项目拒绝及清理；实际浏览器在 P08-A02 单独核验，不能将 A01 外推为浏览器 PASS。Parser Worker 的实际处理亦另列，不把入队视为解析完成。
- Impact/rollback/validation plan：仅隔离 `validation/` 夹具和进度，无生产 API/Schema/Migration/权限/依赖变化，撤新增模式可回滚。验证随机资源精确清理与原 PoC PG 状态恢复；任一失败保留日志，不伪称 PASS。正式信任源/其他 OS/性能/Gate3 不在本项结论中。

## DEC-20260930-491 — DOC-05-A05-P07 项目文档新建/升版上传页面

- Date/WBS：2026-09-30 / Phase2 DOC-05-A05-P07。冻结上传四步协议、Windows 显式路由、P01～P06 客户端及项目 Document 历史/详情页前置具备。
- Decision/Reason：独立页面覆盖新建和升版两模式，入口分别来自项目文档历史与受权详情；升版先独立 GET ACTIVE 文档与原强 ETag/最新版本引用。用户明确选择文件/目的/类别并确认后，同一次操作按 Create→Content→Commit 连续执行；各阶段保留原文件与原 Key，未知结果停住，仅在用户核对后显式复用原阶段，不生成新 Key；确定性内容/Commit 拒绝进入显式 Abort。Commit 首次回执只展示为本次结果，要求独立重读当前文档。
- Impact/rollback/validation plan：只增 Document 页面、路由、历史/详情入口与页面测试；不改变后端 API/Schema/Migration/权限/依赖，撤页面/路由即可回滚。测试无会话/无项目写角色、模式/输入、阶段调用顺序、未知恢复原键、Abort、跨项目迟到结果清除与首次回执非当前状态。实际浏览器/PG/真实文件/Parser Worker 后续单独验收；不把页面合同视为发行可用。

## DEC-20260930-490 — DOC-05-A05-P06 上传 Commit/Abort 安全业务回执

- Date/WBS：2026-09-30 / Phase2 DOC-05-A05-P06。冻结 `DOCUMENT_UPLOAD_COMMIT/ABORT`、后端 201/200 合同、P05 空体私有传输及 P04 已收内容回执满足前置。
- Decision/Reason：新建与既有 Document 升版显式区分；Commit 仅在可信的内容回执结构/ID 与目标匹配时提交，升版携带父 Document 原强 ETag，201 要绑定 Upload ID、Document/Version/Parse Job UUID、正整数版本号及精确 Location。Abort 仅返回 ABORTED/cleanup_pending 安全状态；两者回执都是首次命令结果而非当前资源证明，页面须另行 GET。确定性拒绝按 HTTP 状态/错误码映射；断线、503、畸形或伪成功为未知，保留原 Key、不自动重试。
- Impact/rollback/validation plan：仅新增 Document 前端业务客户端及测试，无 API/Schema/Migration/权限/依赖变化；撤新增文件可回滚。验证输入、首次/重放结果绑定、权限/License/版本/内容故障、错误结构、Location/no-store 与未知行为；定向/全量/typecheck/build。真实 PG/浏览器/Parse、正式信任与发行另验。

## DEC-20260929-489 — DOC-05-A05-P05 项目上传终结命令私有传输

- Date/WBS：2026-09-29 / Phase2 DOC-05-A05-P05。P01～P04 与后端可选 `DOCUMENT_UPLOAD_COMMIT/ABORT`、冻结项目路径/Session/CSRF/幂等合同满足前置。
- Decision/Reason：Commit 和 Abort 共用空体私有传输，但公开为两个固定动作；项目/上传 UUID、原幂等键、Commit 可选强 If-Match 在发网前校验。Abort 禁止携带 If-Match，Commit 升版调用方后续必须传父文档原 ETag；不在传输层猜测新建/升版。超时、连接断开、401 分别保留原键、不自动重发、清本地写证明。
- Impact/rollback/validation plan：仅 SessionClient/定向测试、无 API/Schema/Migration/权限/依赖变化；撤新增方法即可回滚。覆盖固定路径/头/空体、坏 ID/Key/ETag、未登录/401、互斥/超时，再跑前端全量/typecheck/build。业务回执、UI/真实文件与解析另验。

## DEC-20260929-488 — DOC-05-A05-P04 内容 SHA-256 与 200 回执安全客户端

- Date/WBS：2026-09-29 / Phase2 DOC-05-A05-P04。冻结 `DOCUMENT_UPLOAD_CONTENT`、P02 短时意图结果与 P03 私有 PUT 前置满足。
- Decision/Reason：用浏览器 Web Crypto 对同一不可变 Blob 计算 SHA-256，摘要成功且令牌仍未过期才调用 P03；严核 200 的项目 Upload ID、大小、摘要、detected MIME、trace/no-store，仅返回安全白名单。已知 4xx 拒绝与网络/伪 200 未知结果区分，不自动重传。无 Web Crypto/Hash 失败在网络前明确失败。首版最多 100 MB 摘要需 `arrayBuffer()`，记录峰值内存风险，实际浏览器另验。
- Impact/rollback/validation plan：仅 Document 前端业务客户端/测试；无 API/Schema/Migration/权限/依赖变化，撤新增实现即可回滚。定向测试 SHA/原 Blob、到期/异常/权限/伪响应/不重传，前端全量/typecheck/build；真实网络 `Content-Length`、文件字节、解析和内存性能另验。

## DEC-20260929-487 — DOC-05-A05-P03 项目上传内容私有 PUT 传输

- Date/WBS：2026-09-29 / Phase2 DOC-05-A05-P03。P01/P02 与后端 `DOCUMENT_UPLOAD_CONTENT` 可选 Router 均已具备；冻结内容流协议要求项目/上传 ID、Cookie/CSRF、短时 token、Content SHA-256 和长度限额。
- Decision/Reason：只为 PROJECT Scope 增加 SessionClient 私有 PUT 通道。调用方提供已计算的 SHA-256 与有明确长度的 Blob；前端先校验 ID/token/hash/大小，固定同源路径、`application/octet-stream`、私有 CSRF、`X-Upload-Token` 和 `X-Content-SHA256`，单次请求且可中止，401 清写证明。浏览器 Fetch API 禁止脚本设置 `Content-Length`，Fetch 标准会为已知长度请求体生成该头；不伪造手动设置或改写冻结后端合同（https://fetch.spec.whatwg.org/）。
- Impact/rollback/validation plan：无 API/Schema/Migration/权限/依赖变更；撤新方法即可回滚。单元合同覆盖固定路径/头、Blob 大小、非法值、失去写证明、401、互斥、超时；全量前端/typecheck/build。实际浏览器/HTTP `Content-Length`、文件 Hash、Commit/解析链另行验证，当前不得宣称上传可用。

## DEC-20260929-486 — DOC-05-A05-P02 项目 UploadIntent 安全业务客户端

- Date/WBS：2026-09-29 / Phase2 DOC-05-A05-P02。P01 固定私有 Session/CSRF/Key 传输与冻结 `DOCUMENT_UPLOAD_CREATE`、后端 PROJECT UploadIntent 201 合同已具备。
- Decision/Reason：新建 Document 与既有 Document 升版用显式互斥输入类型；业务客户端先规范字段/Key，再按固定 Project ID 调用 P01，严格校验 JSON/trace、201 的 UUID/token/未过期 UTC/Location/no-store，只返回白名单短时结果。确定性拒绝按状态/错误码映射；断线、伪成功或未知回执一律标“结果未知”，不自动换 Key 重试。
- Impact/rollback/validation plan：仅新建 Document 前端业务客户端与测试；无冻结 API、Schema、Migration、权限或依赖变更，撤新增文件可回滚。测试覆盖输入、成功、拒绝、伪响应、超时及令牌不落存储；前端全量/typecheck/build。Token 在后续内容 PUT 使用，当前不做 UI/文件/解析验收。

## DEC-20260929-485 — DOC-05-A05-P01 项目上传意图的前端私有会话桥接

- Date/WBS：2026-09-29 / Phase2 DOC-05-A05-P01。输入为冻结 `DOCUMENT_UPLOAD_CREATE`、已实现的可选项目上传意图 HTTP、现有 SessionClient 私有 CSRF/互斥/幂等命令通道；Gate 2 与前置满足。
- Decision/Reason：只新增固定 PROJECT Scope 的 UploadIntent POST 传输入口，调用方提供原请求体与原幂等键；复用私有 CSRF、同源 Cookie、超时一次和 401 清本地写证明。GLOBAL、文件内容 PUT、Commit/Abort 和页面拆成后续独立任务，避免把传输桥接误报为可用上传。
- Impact/rollback/validation plan：无冻结 API、Schema、Migration、权限或依赖变化；撤新增方法即可回滚。验证项目 ID/Key/体积拒绝、只发固定路径、Session 缺证明、401、超时与互斥；定向及全量前端测试、typecheck/build。正式信任源和真实文件/解析链另行验证。

## DEC-20260929-484 — DOC-05-A04-P03 真实隔离文件浏览器/PG 下载验收

- Date/WBS：2026-09-29 / Phase2 DOC-05-A04-P03。冻结下载 GET、后端已实现 verified snapshot/流式响应及 P01/P02 前端地址与入口满足前置。
- Decision/Reason：在现有随机库/临时 data root 夹具中通过受控 LocalFileStorage 写入非客户合成文本文件，记录真实 SHA-256/大小及 AVAILABLE FileObject/Version；先做 HTTP 字节/附件头/拒绝，再从实际浏览器版本行触发下载。原合成版本元数据无真实文件，不能复用其可见性作为下载证据。
- Impact/rollback/validation plan：仅验证夹具/进度，不改生产 API/Schema/Migration/权限/依赖；撤模式即可回滚。要求每轮随机库/角色/Vault/临时文件清理及原 PoC PG 状态恢复。浏览器若无法可靠获得下载字节，必须将该层证据界定为“触发成功”而非字节校验 PASS；正式信任/三平台另验。
- Deviation before repair：首轮浏览器点击 `target=_blank` 的下载链接只在 IAB 建立未归属当前 session 的新标签，原标签的下载事件等待 15 秒超时；不能据此宣称下载成功。为完成实际可验证下载，在本 WBS 中改为同标签原生附件链接，重跑前端及浏览器；取舍是受权失败时浏览器可能显示服务端错误页，保留回退到文档详情的能力并列入已知问题。原 P02 记录保留，不追写已推送提交。
- Executed：隔离 LocalFileStorage 写入 50 字节合成文本，真实 FileObject/Version、HTTP 下载字节与 SHA-256、附件头、匿名 401/外项目 404/Range 400、随机库/角色/Vault/临时文件根清理完整 exit0。改同标签后前端 841 项/typecheck/build PASS，Windows 11 IAB 从受权项目版本行触发下载事件，浏览器保存文件 SHA-256 为 `72e5df2e4b099d1736bd7031192212402f3b74f56db444a99040f608dc1201d1`，与夹具原文一致；同页保持。事后读 Downloads 发现首轮新标签也保存了同摘要文件，故首轮是“事件不可观测”而非下载失败。两份仅含合成内容的测试下载已移到回收站，可恢复；IAB 临时标签最终关闭操作被中断，不能宣称浏览器标签已清理。PoC PostgreSQL fast stop 还原。正式信任/三平台/文内定位仍未验。

## DEC-20260929-483 — DOC-05-A04-P02 版本行原生附件下载入口

- Date/WBS：2026-09-29 / Phase2 DOC-05-A04-P02。P01 固定同源下载地址与 P03 实际版本历史 UI、冻结 `DOCUMENT_VERSION_DOWNLOAD` 及后端受权流式接口满足前置。
- Decision/Reason：仅在服务端返回的 AVAILABLE 版本行展示原生附件链接，由浏览器对固定 GET 发起请求、服务端重新核 Session/Project/License/完整性；新标签保留当前详情页处理过期或拒绝错误。不在前端缓存最多 100MB 内容，也不把下载称为文内定位/预览。
- Impact/rollback/validation plan：只改 Document 详情视图/测试，无 API/Schema/Migration/权限/依赖变化；撤链接即可回滚。验证安全同源 href、未加载/空态无链接及无内容型 fetch；定向/全量前端测试与构建。真实文件浏览器下载须在后续隔离任务单独证明。
- Executed：受权版本行显示“下载版本 N”同源附件链接，`target=_blank`/`noopener noreferrer` 保留当前页面；未加载或空版本不生成内容链接，元数据页不请求文件正文。视图定向 10、前端全量 841 项/typecheck/build PASS；真实文件点击未验。

## DEC-20260929-482 — DOC-05-A04-P01 受权版本下载固定地址合同

- Date/WBS：2026-09-29 / Phase2 DOC-05-A04-P01。冻结 `DOCUMENT_VERSION_DOWNLOAD`、后端 Windows 11 合成流式 GET、版本客户端和历史 UI 已有前置。
- Decision/Reason：提供只生成 PROJECT/GLOBAL 固定同源 `/content` 地址的前端方法；不携带 token、文件路径或查询参数，也不把 100MB 流式响应在前端整包转 Blob。后续 UI 以浏览器原生附件请求调用，服务端继续负责 Session/Project/License/完整性校验。
- Impact/rollback/validation plan：仅 Document 前端 API/测试，无后端 API/Schema/Migration/权限/依赖变化；撤方法即可回滚。验证合法路径、恶意/不合法 scope 和 ID 在网络前拒绝、无请求副作用；全量前端回归。真实文件浏览器下载另验，不能用合成元数据替代。
- Executed：`DocumentReadClient.contentUrl` 只返回固定同源受权流式 GET 地址，PROJECT/GLOBAL 严格分开；非法 Scope/Document/Version ID 本地失败，不含凭据或查询。定向 69、前端全量 841 项/typecheck/build PASS。尚无 UI 入口、真实文件/浏览器下载证据。

## DEC-20260929-481 — DOC-05-A03-P03 版本历史隔离浏览器/PG 验收

- Date/WBS：2026-09-29 / Phase2 DOC-05-A03-P03。P01/P02 前端合同、冻结版本读 API 与 Windows 11 合成后端版本读链前置满足。
- Decision/Reason：扩展既有每轮随机库浏览器夹具，给首条合成项目 Document 构造一条文件元数据匹配、状态 AVAILABLE 的不可变版本；通过受权项目页面按需展示该版本，不创建或外发客户文件。将 API/SQL 归属及拒绝、UI 显示和临时资源清理作为同一验收闭环。
- Impact/rollback/validation plan：仅验收夹具/进度，无生产 API/Schema/Migration/权限/依赖变更；移除模式即可回滚。先运行独立 API/PG，再实际浏览器，要求完整 exit0 和随机库/角色/Vault 清理。合成信任不代表正式目标账户或三平台 PASS。
- Executed：首轮因合成 SHA-256 按 64 字符而非 32 字节入库违反 DB check；改为 `bytes.fromhex`。第二轮 API/PG 成功但会话数预期沿用旧模式而断言失败；收紧为本模式 1 Session。第三轮 API/PG 完整 exit0：匿名 401/跨项目 404、版本列表/详情 AVAILABLE 安全投影、51 个版本与文件元数据匹配、库/角色/Vault 清理。第四轮 Windows 11 实际 IAB：合成成员从项目→文档历史→详情按需加载版本 1/MIME/大小/哈希，详情刷新清旧、再次读取成功，最终完整夹具 exit0；PoC PG fast stop 还原。仅合成元数据，未创建真实文件内容，不支持以此证明下载。

## DEC-20260929-480 — DOC-05-A03-P02 项目 Document 版本历史界面

- Date/WBS：2026-09-29 / Phase2 DOC-05-A03-P02。输入为 P01 安全版本客户端、P02 Document 详情及冻结 `DOCUMENT_VERSION_LIST`；Gate 2/后端受权读链满足。
- Decision/Reason：在受权项目 Document 详情页增加按需加载的 AVAILABLE 版本历史、续页和明确空态；不提供尚未验收的下载/正文入口。详情刷新、路由切换及身份不匹配时清旧数据并废弃迟到结果，保留固定项目范围。
- Impact/rollback/validation plan：只改 Document 前端视图/测试；无 API/Schema/Migration/权限/依赖变化。可撤回版本历史 panel；定向视图测试、前端全量/typecheck/build。实际浏览器/PG 另做独立验收，不把 UI 合同记为正式信任通过。
- Executed：文档详情增加按需版本历史、50 条续页、空态与元数据说明，刷新/跨路由废弃旧数据和迟到结果；不提供正文/下载。视图定向 10、前端全量 839 项及 typecheck/build PASS。浏览器/PG 对该 UI 未验。

## DEC-20260929-479 — DOC-05-A03-P01 DocumentVersion 前端只读客户端

- Date/WBS：2026-09-29 / Phase2 DOC-05-A03-P01。输入为冻结 `DOCUMENT_VERSION_LIST/GET`、后端受权只返回 AVAILABLE 版本的读合同、现有 Document 元数据客户端；Gate 2 与前置读链满足。
- Decision/Reason：在既有 `DocumentReadClient` 增加明确项目/GLOBAL 路径的版本列表及详情读取；只投影签名哈希、大小、MIME、可用状态、前驱与时间等安全元数据，不包含本地路径、正文或下载 URL。沿用固定每页 50 与受控游标，不自行推断内容已能下载。
- Impact/rollback/validation plan：仅前端 Document API 与测试，不改冻结 `/api/v1`、后端、权限、Schema/Migration/依赖。回滚客户端方法即可；定向单测及全量前端测试/typecheck/build，并确认错误信息不泄漏响应正文。正式浏览器/PG、发行信任与三平台另验。
- Executed：新增固定 PROJECT/GLOBAL 版本列表与详情调用、AVAILABLE 安全投影、50 条签名游标分页、版本降序/标识/数值/哈希/时间校验；异常统一关闭。定向 67、前端全量 835 项、typecheck/build PASS。仅客户端合同，实际浏览器/PG 与正式信任仍待。

## DEC-20260929-478 — DOC-05-A02-P02 文档详情实际浏览器验收

- Date/WBS：2026-09-29 / Phase2 DOC-05-A02-P02。P01 前端合同、P03-A01/A02 列表 API/浏览器 PG 合成验收及后端详情 GET 前置满足。
- Decision/Reason：复用每轮随机库中的合成 Document 元数据，新增互斥 detail-browser 验收模式；浏览器从受权项目列表进入文档详情，刷新后仍读取服务端。只校验元数据、强 ETag 与权限边界，不引入文件内容或客户资料。
- Impact/rollback/validation plan：仅测试夹具/进度，不改生产 API/Schema/Migration/权限/依赖；撤模式可回滚。浏览器 UI 与临时库 SQL/角色/Vault 清理均须通过；如进程中断，精确核残留并重跑，不把局部 UI 观察当完整 exit0。正式信任、其他平台、质量/性能 Gate 另验。
- Executed：Windows 11 合成成员从项目列表→文档历史→首条详情，显示服务端元数据与 `"v0"`；页面刷新后仍显示且无错误。独立隔离夹具 exit0，SQL 51 ACTIVE+1 RESTRICTED/FOREIGN1、随机库/角色/Vault 清理；PoC PG 恢复原停止。无生产 API/Schema/Migration/权限/依赖变化，不关闭正式信任/其他平台/性能质量/Gate3。

## DEC-20260929-477 — DOC-05-A02-P01 项目 Document 元数据详情页

- Date/WBS：2026-09-29 / Phase2 DOC-05-A02-P01。冻结 `DOCUMENT_GET`、后端受权详情/强 ETag、前端 P01 安全客户端及 P02 项目列表前置满足。
- Decision/Reason：从项目 Document 历史行进入独立只读详情；直达路由也只以服务器 GET 为授权来源，不因 URL 或列表缓存获得权限。仅展示已校验的安全元数据，不提供文件正文、下载、版本历史或 GLOBAL 管理入口。刷新清旧详情，项目/Document 路由变化丢弃迟到响应。
- Impact/rollback/validation plan：仅前端路由/视图/列表入口和测试，无后端 API、Schema/Migration、权限或依赖变化；回滚撤新路由/视图/入口，P01/P02 保留。风险是跨项目旧资料误显，以代际与 ID/Scope/ETag 校验控制。验收页面单测、全量前端/typecheck/build；实际浏览器/PG 另列任务，正式信任和 Gate3 不借本项放行。
- Executed：项目文档行新增详情入口，直达详情页只使用当前服务端 GET 投影；刷新先清旧、拒绝/ETag 错配失败关闭、跨项目及文档迟到结果丢弃。定向 12/12、前端全量 814/814、typecheck/build PASS；实际浏览器/PG 下一分项。无后端 API/Schema/Migration/权限/依赖变更。

## DEC-20260929-476 — DOC-05-A01-P03-A02 浏览器完整复验与异常清理

- Date/WBS：2026-09-29 / Phase2 DOC-05-A01-P03-A02。P01/P02/A01 与 Windows 隔离夹具前置满足。
- Decision/Reason：增加独立 `--document-history-browser` 模式，浏览器仅用临时合成项目资料，校验从受权项目入口到 50+1 分页及刷新。首次真实 UI 已可见，但会话切换中断导致夹具未完成且 PoC PG 异常停止，不能据此标 PASS；先精确回收残留随机库/角色/唯一 Test 凭据，再用新随机库完整重跑。停机根因不推断。
- Impact/rollback/validation：仅验收夹具/记录，不改正式 API/Schema/Migration/权限/依赖；撤 browser 模式可回滚。第二轮 UI 50→51→50、受限/外项目不可见，夹具 SQL/清理 exit0，PoC PG 正常恢复停止。首轮 crash recovery 与停机根因保留为已知问题；正式信任、其他平台、性能质量/Gate3 未验。

## DEC-20260929-475 — DOC-05-A01-P03-A01 独立 API/PG 验收

- Date/WBS：2026-09-29 / Phase2 DOC-05-A01-P03-A01。Document 前端 P01/P02 与后端 Windows 显式读取组合、现有随机库/角色/Vault 隔离夹具前置满足；P03 原拟 API/PG + 实际浏览器整体验收。
- Decision/Reason：浏览器工具无法可靠确认 Chrome URL 而按安全策略终止，不能把 API/PG 证据扩展成浏览器 PASS。将已独立完成的真实 Session、临时 PostgreSQL、50+1 签名游标与权限隔离验收登记为 A01；浏览器另列 A02，未验证不放行。只保留 `--document-history-api-only` 正式夹具模式，未测试的 browser flag 不纳入提交。
- Impact/rollback/validation：仅合成验收夹具与记录，无冻结 API/Schema/Migration/权限/依赖变化；撤新 API-only 模式可回滚。Python 语法、完整 API/PG 夹具 exit0，临时库/角色/Vault 清理通过，PoC PG 恢复原停止。风险为正式信任和浏览器行为尚未验证，A02/Gate3 维持未完成。

## DEC-20260929-474 — DOC-05-A01-P02 项目 Document 历史只读页面

- Date/WBS：2026-09-29 / Phase2 DOC-05-A01-P02。P01 安全客户端及冻结 `DOCUMENT_LIST`、Windows 显式读取组合前置满足。
- Decision：先给已受权项目接入元数据历史路由/入口/列表，只显示服务端投影的元数据；不把会话项目摘要当读取权限证明，最终由每次 Document API 裁决。不在本项加入 GLOBAL 管理入口、文档详情、上传或下载。失败/权限丧失清旧列表，项目切换/卸载丢弃迟到响应，跨页重复拒绝整页。
- Impact/rollback/validation：仅新增 Document 页面/测试并修改前端路由、项目详情入口，无后端/DB/API/权限/依赖变化；撤路由/入口/页面可回滚。页面定向 6/6，前端全量 808/808、typecheck/build PASS。风险为旧项目资料误显，以清旧和代际检查控制；实际浏览器/PG、目标账户正式信任和 Gate 3 未验，P03 单列。

## DEC-20260929-473 — DOC-05-A01-P01 Document 元数据只读客户端

- Date/WBS：2026-09-29 / Phase2 DOC-05-A01-P01。冻结 API-02 `DOCUMENT_LIST/GET`，后端 DOC-01-A02/A03-P01～P04 已有授权读取及 Windows 显式组合；Review/Workflow 写链真实 Owner 与 Phase3 解析证据前置未满足，选择独立可交付的 Document 前端读取任务。
- Decision：先实现固定 PROJECT/GLOBAL 双 Scope 元数据列表与详情的安全客户端，不增加用户可控路径或内容读取。服务端仍为唯一权限源；客户端限制同源 GET、响应字段、Scope/ID/强 ETag、游标与错误投影。页面与浏览器/PG 验收另列任务，避免把单元合同误称端到端。
- Impact/rollback/validation：仅新增前端 Document API 客户端/测试，无冻结 API/Schema/Migration/后端权限/依赖变化，删除新增文件可回滚。风险为跨项目或异常响应展示，以失败关闭校验和后续页面迟到结果防护控制。实现后 46 定向、802 全量测试、typecheck/build PASS；首轮 UUID 正则及 TS scope 类型问题均已修复并全量重跑。正式浏览器/PG、目标账户信任、其他平台与 Gate 3 未验。

## DEC-20260929-472 — PRJ-05-A15-P04 Windows 11 项目名称更新端到端

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A15-P04。P01～P03、后端 PRJ-04-A07 与现有隔离浏览器/PG 夹具前置满足。
- Decision：增加互斥项目名称 PATCH API-only/browser 合成验收模式，只修改每轮随机库的 OWNED 项目。HTTP 检查匿名/非负责人/CSRF/跨项目/缺版本、v0→v1/旧版冲突/同名仍 v2 与独立 GET；浏览器从当前项目详情确认新名称，先看本次回执，再独立刷新当前详情。SQL 核 OWNED 名称/版本、FOREIGN 未变、每次实际提交的 Audit 数及 PATCH 无幂等收据；随机库/角色/Vault 精确清理。PoC PG 原启停状态另行核查。
- Impact/rollback/validation：只改自有合成验收夹具与记录，无生产 API/Schema/权限/依赖变化；回滚撤新模式。风险是非目标数据被修改或 PG 异常停机，以随机库/固定合成 ID、最终存在性和启停检查控制。正式信任/其他平台/性能/Gate 独立验收。
- Executed：Windows 11 API-only 与实际 IAB 两轮随机库均 exit0。HTTP 匿名/非负责人/缺 CSRF/跨项目/缺 If-Match/非法 Body 拒绝，首次改名 `v1`、旧版冲突、同名再写 `v2`、独立 GET 通过；浏览器先见本次回执，再独立刷新见新名称。SQL 核 API-only OWNED `ACTIVE/v2`、2 Audit，浏览器 OWNED `ACTIVE/v1`、1 Audit，FOREIGN 未变、无 PATCH 收据；两轮临时库/角色/Vault 清理通过。PoC PG 测试前停止，启动成功，验收后已无进程；日志末尾无本轮正常关闭记录，停机原因未证实，不把关闭过程标 PASS。无生产 API/Schema/权限/依赖变更，不关闭正式信任/其他平台/性能质量/Gate3。

## DEC-20260929-471 — PRJ-05-A15-P03 项目名称更新显式确认页面

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A15-P03。冻结 `PROJECT_PATCH`、P01/P02、ProjectReadClient 与现有项目详情前置满足。
- Decision：项目详情只给当前 ProjectManager 的 ACTIVE 项目显示名称修改入口；展示原项目编号/版本，输入名称后要求显式勾选，提交仅使用原项目详情和原版本。PATCH 无幂等 Key，成功或未知均清旧详情、禁止直接重试，显示回执只作本次结果且独立 GET 后才恢复当前展示。归档与名称修改编辑/提交互斥；路由切换/卸载丢弃迟到结果，不跨项目显示。
- Impact/rollback/validation：仅 Project 前端视图/测试，无后端 API、Schema、Migration、权限、依赖变更；回滚可撤名称编辑 UI，保留 P01/P02。风险是写成功但浏览器断线或响应不明，对此不自动重发，提示先重读并核对审计；已知拒绝也清旧详情。验收负责人/非负责人、确认门槛、同名/目标名、first/current 分离、失败/未知与跨项目迟到结果，全量前端/typecheck/build；浏览器/PG 另项。
- Executed：ProjectDetailView 增加负责人 ACTIVE 项目名称修改显式确认，归档与改名互斥；提交后清旧详情，成功回执标非独立当前状态，已知拒绝/未知均要求重新读取，跨项目迟到结果丢弃。前端 756/756、typecheck、build PASS；首轮测试全过但测试样本 TypeScript `state` 推断过宽，修正测试类型后完整重跑。无生产 API/Schema/Migration/权限/依赖变化，浏览器/PG 下一分项。

## DEC-20260929-470 — PRJ-05-A15-P02 项目名称更新安全业务客户端

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A15-P02。P01、冻结 `PROJECT_PATCH`、后端 PRJ-04-A06/A07 与 ProjectReadClient 前置满足。
- Decision：仅接受单字段名称输入，经 NFKC/trim、1～255 字符且无控制字符后提交。原 ACTIVE Project ID/编号/创建时间/强版本与 200 项目回执绑定；后端即使同名 PATCH 也固定版本 +1，因此不可复用部门同值不增版规则。响应只保留安全 ProjectView，响应头 ETag 必须完全一致。已知拒绝按状态+码映射；伪成功、错码/状态、断线和未知服务器错误全部不确定，须独立 GET 核对，禁止自动重试。
- Impact/rollback/validation：只加 Project 业务客户端/测试，不改冻结 API、DB、权限、依赖；回滚撤客户端与测试，P01 保留。验证输入/身份/字段/版本绑定、已知拒绝和未知、首尾数据分离，前端全量/typecheck/build；实际浏览器/PG 下一分项。
- Executed：新增 ProjectPatchClient 与 27 项业务客户端测试；前端 751/751、typecheck、build PASS。后端同名亦版本 +1 的实际合同已覆盖；无 Schema/Migration/后端 API/权限/依赖变化。页面和实际浏览器/PG 下一分项。

## DEC-20260929-469 — PRJ-05-A15-P01 项目名称更新固定前端传输

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A15-P01。冻结 `PROJECT_PATCH`、后端 PRJ-04-A06/A07、现有 SessionClient 前置满足；只处理一个无幂等 Key 的项目名称 PATCH 通道。
- Decision：只加私有 `PATCH /api/v1/projects/{project_id}` 传输，规范 UUID、强且安全整数版本、非空有界 JSON body、同源 Cookie/私有 CSRF、无自动重试；401 清本地会话证明，失败或超时返回不确定，后续业务客户端必须先独立 GET 核对。本项不解析成功载荷或增加页面，不允许修改 ProjectCode。
- Impact/rollback/validation：无 DB/后端 API/权限/依赖变化；回滚撤该前端方法和测试。风险为无 Key 写后断线误判未提交，以单次请求、不自动重试及后续 GET 恢复控制。验收单测验证固定路径/头、非法输入、401/503 与超时互斥，并跑前端全量/typecheck/build；正式浏览器/PG 留后续分项。
- Executed：新增 SessionClient 单次项目 PATCH 与 4 项传输合同；前端 724/724、typecheck、build PASS。只校验传输输入与原始 Response，不解析名称业务结果；无 Migration/后端 API/权限/依赖变化，实际浏览器/PG 留后续分项。

## DEC-20260929-468 — PRJ-05-A14-P04 Windows 11 项目归档端到端

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A14-P04。P01～P03、后端 PRJ-04-A08-P03 与现有隔离浏览器/PG 夹具前置满足。
- Decision：增加互斥 archive API-only/browser 合成验收模式；仅归档每轮随机库中的 OWNED 项目，验证匿名/非负责人/CSRF/外项目/缺版本拒绝、首次 200/同 Key 重放/Key 冲突及独立 GET。浏览器从我的项目进入授权详情，核明确单向影响与勾选，确认后仅显示首次回执，再独立刷新读取 ARCHIVED 且无再归档入口。SQL 核 OWNED ARCHIVED/v1、FOREIGN ACTIVE/v0、单 Audit/完成收据、原成员不被误删；随机库/角色/Vault 精确清理。原 PoC PostgreSQL 启停状态另行核查，异常不虚报正常关闭。
- Impact/rollback/validation：只改自有隔离验收夹具/进度，不改生产 API/Schema/权限/依赖。风险为误碰非临时项目或本机 PG 异常中止，以唯一临时库、固定合成项目和最终存在性检查控制；回滚撤新 fixture 模式。正式信任/其他平台/性能/Gate 独立验收。
- Executed：Windows 11 API-only 与实际 IAB 浏览器两轮独立随机库均 exit0。HTTP 匿名/非负责人/缺 CSRF/跨项目/缺 If-Match 拒绝、首次 200 与同 Key 重放、异版本同 Key 冲突及独立详情 GET 通过；浏览器显式确认后先见首次回执，再刷新见 ARCHIVED 且无归档入口。SQL 两轮均核 OWNED ARCHIVED/v1、FOREIGN ACTIVE/v0、负责人保留及恰一 Audit/收据；临时数据库/角色/Vault 精确清理。PoC PG 启动前处于停止，验收后确认运行并正常 fast stop 恢复停止；启动时有可能残留旧 PID 提示，原因未证实。无生产 API/Schema/权限/依赖变更，不据此关闭正式信任、其他平台、性能质量、Gate3 或程序包验收。

## DEC-20260929-467 — PRJ-05-A14-P03 项目归档显式确认界面

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A14-P03。P01/P02、安全项目详情 GET 与冻结归档合同前置满足；只能从服务器详情读取 ACTIVE 项目与强版本，不使用路由参数当实体证明。
- Decision：仅当前 ProjectManager 可写会话展示单向归档入口，明确提示将禁止新写/Job 且首版无普通反归档，需勾选核对目标及影响。首次提交固定 Project/Actor/原 ProjectView/ETag/Key；成功或未知均清旧详情并要求独立 GET。未知结果仅在成功重读显示原项目仍 ACTIVE 且原字段/版本相同后允许再次明确勾选并复用原 Key；若历史变化或拒绝读取，保持锁写并提示审计核对。同 Key 冲突锁本页；成功回执不作当前状态证明；切项目/卸载丢弃迟到结果。
- Impact/rollback/validation：仅 Project 详情前端/测试，不改 API/Schema/权限/依赖。风险为归档单向影响、未知结果误用新 Key、刷新后旧按钮复现，使用明确确认/内存原记录/成功 GET 锁与服务器裁决；回滚撤入口，P01/P02 保留。前端测试/typecheck/build，浏览器/PG 另项。
- Executed：2026-09-29，仅 ACTIVE 项目负责人可见单向归档确认；成功或未知均清旧详情，首次回执与独立 GET 分离。未知原 Key 恢复必须重读原 ACTIVE/同版本，冲突锁本页，切项目迟到回执丢弃。定向测试一处“新项目应报错”错误预期修正后，前端 720 项/typecheck/build PASS；实际浏览器/PG 另项。

## DEC-20260929-466 — PRJ-05-A14-P02 项目归档首次回执安全客户端

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A14-P02。P01 固定传输、冻结 PROJECT_ARCHIVE、后端 PRJ-04-A08 与 Project 只读投影前置满足。
- Decision：仅接受原项目 ACTIVE 安全投影、强版本及原幂等 Key；200 必须绑定原 Project ID/编号/名称/创建时间、ARCHIVED、版本 +1 与响应强 ETag。业务返回显式 `is_current_state_proof:false`，同 Key 重放仅作首次操作回执；已知 HTTP/错误码一致映射，伪成功、坏信封、断线与未知状态不得自动重发或更换 Key。
- Impact/rollback/validation：只增前端业务客户端/测试，不改 API/Schema/权限/依赖。风险为单向归档回执误当实时状态或未知结果用新 Key 再次提交，使用原项目字段/版本绑定、首次语义和失败关闭控制；回滚撤客户端，P01 传输保留。前端测试/typecheck/build；确认页面和浏览器/PG 另项。
- Executed：2026-09-29，原 ACTIVE/强版/原 Key、归档 ID/编号/名称/创建时间/ARCHIVED/v+1 与响应 ETag 绑定；同 Key 重放标记非当前证明，已知拒绝/伪成功/断线分离。前端 715 项/typecheck/build PASS；页面与实际浏览器/PG 另项。

## DEC-20260929-465 — PRJ-05-A14-P01 项目归档固定前端传输

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A14-P01。冻结 PROJECT_ARCHIVE、后端 PRJ-04-A08-P03、ProjectReadClient 及现有 SessionClient 前置满足。
- Decision：仅新增私有 `POST /api/v1/projects/{project_id}:archive` 固定传输，规范 Project UUID、强且安全整数 If-Match、16～128 可打印原幂等 Key、空 Body/无 Content-Type、同源 Cookie/CSRF、单次发送。401 清本地会话证明；断线/超时结果未知，业务层必须保留原 Key/If-Match，不自动生成新 Key。本项不解析业务回执、不提供归档按钮。
- Impact/rollback/validation：仅 Auth transport 与单元测试，无 API/Schema/权限/依赖变化。风险为提交已成功但连接断开；回滚撤方法/测试。前端测试/typecheck/build，回执/页面/实际浏览器 PG 另项。
- Executed：2026-09-29，固定 Project UUID/强 If-Match/原 Key/空正文、私有 CSRF/同源单次提交、401 清证明与超时互斥验证通过；前端 687 项/typecheck/build PASS。业务回执、确认页及实际浏览器/PG 另项。

## DEC-20260929-464 — PRJ-05-A13-P04 Windows 11 部门停用端到端

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A13-P04。P01～P03、后端 PRJ-04-A16-P03 与既有隔离浏览器/PG 夹具前置满足。
- Decision：新增互斥 department-deactivate API-only/browser 验收模式，合成负责人所用部门验证在用 409，另建无成员 ACTIVE 部门验证匿名/非负责人/CSRF/外项目/缺版本、首次 200/同 Key 重放/Key 冲突、独立历史读取；浏览器从已授权部门历史选择无成员 ACTIVE 条目，明确勾选后停用并独立刷新。SQL 核目标 INACTIVE/v1、单 Audit、不可变结果和完成收据，随机数据库/角色/Vault 精确清理，恢复原 PostgreSQL 状态；失败不标 PASS。
- Impact/rollback/validation：仅隔离验收夹具及进度，不改生产 API/Schema/权限/依赖。风险为误停用负责人所用部门或中断留下测试资源，以独立无成员部门、随机资源名和最终清理控制；回滚移除新 fixture 模式。正式信任/其他平台/性能/Gate 独立验收。
- Executed：2026-09-29，API-only 经首轮测试断言误用部门 ID 作收据结果 ID，按既有结果快照外键修正后完整重跑 exit0；匿名/权限/CSRF/版本/在用409、首次/重放/冲突/历史及 SQL 一审计/结果/收据通过。实际 IAB 从历史选 FREE/v0、明确勾选、首回执后独立刷新见 INACTIVE，browser fixture exit0；两轮自有库/角色/Vault 均清理。原 PG 开始前停止，结束检查亦停止；尝试正常 stop 时已无进程，日志末尾未解释停机原因，不能将关闭路径标为已验证。

## DEC-20260929-463 — PRJ-05-A13-P03 部门停用确认界面

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A13-P03。P01/P02、部门历史页和冻结停用合同前置满足；从服务器授权历史取得当前ACTIVE条目及强版本，不使用任意路由快照。
- Decision：项目负责人可写会话下才为ACTIVE部门提供停用入口，需明确勾选。首次提交固定Project/Actor/Department/ETag/Key；未知结果保留原记录并清旧列表，成功重读历史后若原部门仍ACTIVE且同版本，才允许再次明确勾选并仅以原Key/版本恢复。若已变更或不在已读历史，保持锁写并提示核对审计；同Key冲突锁本页。成功回执只标首次结果，独立历史重读才是当前状态；切项目/卸载丢弃迟到回执。
- Impact/rollback/validation：仅项目部门历史前端/测试，不改API/Schema/权限/依赖。风险为未知结果误用新Key、分页未定位或在用部门失败，使用内存原记录、原版本比较与服务器最终裁决；回滚撤停用入口，保留P01/P02。前端测试/typecheck/build，浏览器/PG另项。
- Executed：2026-09-29，ACTIVE负责人显式确认、固定原目标/版本/Key、未知后成功历史重读且原行未变方可同Key恢复、冲突锁页及迟到结果丢弃。幂等冲突刷新后保留醒目锁定提示；前端683项/typecheck/build PASS。实际浏览器/PG另项。

## DEC-20260929-462 — PRJ-05-A13-P02 部门停用首次回执安全客户端

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A13-P02。P01传输、冻结停用合同、CR-PRJ-005及部门历史安全投影前置满足。
- Decision：只允许ACTIVE原部门、强安全版本和原幂等Key；200响应必须绑定原部门ID/编码/名称/创建时间、INACTIVE及v+1强ETag。返回显式`is_current_state_proof:false`，同Key重放只能是不可变首次回执。明确错误仅按HTTP/码一致映射（含在用409），未知与断线保留原Key/ETag，不生成新请求。
- Impact/rollback/validation：仅前端业务客户端/测试，无API/Schema/权限/依赖变化。风险为误认重放为当前状态或伪成功，严格投影与原输入/版本绑定；回滚撤客户端。前端测试/typecheck/build，页面和真实浏览器/PG另项。
- Executed：2026-09-29，ACTIVE原值/强版本/原Key、INACTIVE/v1强ETag与ID/编号/名称/创建时间绑定、同Key重放仍非当前证明、在用部门409、伪回执/未知/断线边界验证通过；前端679项/typecheck/build PASS。页面/实际浏览器PG另项。

## DEC-20260929-461 — PRJ-05-A13-P01 部门停用固定前端传输

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A13-P01。冻结PROJECT_DEPARTMENT_DEACTIVATE、后端PRJ-04-A16-P03、既有SessionClient和CR-PRJ-005前置满足。
- Decision：仅加私有 `POST /api/v1/projects/{project_id}/departments/{department_id}:deactivate` 传输；双规范UUID、强且安全整数If-Match、16～128可打印ASCII原幂等Key、无Body/无Content-Type、同源Cookie/私有CSRF、单次发送。401清本地会话证明；断线/超时结果未知，业务层须保留原Key/If-Match，不生成新Key重试。本项不解析业务响应或增加页面。
- Impact/rollback/validation：仅Auth transport和单元测试，无API/Schema/权限/依赖变化。风险为提交已成功但连接断开；回滚移除方法/测试。前端测试/typecheck/build，真实浏览器/PG另项。
- Executed：2026-09-29，固定双ID/强ETag/原Key/空Body、私有CSRF/同源/单次发送、401清证明与超时互斥验证通过；前端652项/typecheck/build PASS。业务响应/页面和实际浏览器/PG另项。

## DEC-20260929-460 — PRJ-05-A12-P04 Windows 11 部门更新端到端

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A12-P04。P01～P03、后端PRJ-04-A15-P02前置满足，复用自有随机PG/Vault/浏览器夹具与合成信任源。
- Decision：独立department-patch API-only和browser模式；HTTP核匿名/非负责人/CSRF/外项目、强版本、真实变更v1、旧版冲突、无变化不增版本。浏览器从已授权部门历史选择ACTIVE条目、改字段后明确确认、核本次回执并独立刷新；SQL核目标编号/名称/v1、单Audit、无幂等收据。关闭自有服务并精确清理随机库/角色/Vault，恢复原PG停止状态；失败不标PASS。
- Impact/rollback/validation：只改验收脚本/进度，无生产API/Schema/权限/依赖变化。风险为本机PG启动及中断残留，用唯一资源名和精确清理；回滚移除新fixture模式。正式信任/其他平台/性能/Gate独立验收。
- Executed：2026-09-29，API-only隔离HTTP/PG及实际IAB浏览器/PG均PASS。浏览器从历史选择ACTIVE部门、改编号/名称、勾选确认，获得v1回执后独立刷新读到新值；SQL目标NEW/v1、一条PATCH Audit、无PATCH收据。两轮随机库/角色/Vault清理exit0，原PoC PostgreSQL恢复停止。正式信任/其他平台/Gate未验。

## DEC-20260929-459 — PRJ-05-A12-P03 部门历史内显式更新

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A12-P03。P01/P02、部门历史页、冻结PATCH合同前置满足。后端没有单部门GET，页面从授权历史GET取得当前条目与强ETag，不使用可伪造路由状态。
- Decision：仅当前项目负责人且当前会话可写时，为ACTIVE部门展示行内修改；编辑前保留历史快照、修改编号/名称后重新显式勾选，固定原Project/Actor/Department/ETag/输入单次PATCH。成功只展示本次回执并清旧列表，需重新读取历史；未知或版本冲突锁写且清旧列表，只有成功重新读取可解除。项目/身份变化或卸载丢弃迟到结果。
- Impact/rollback/validation：仅项目部门历史前端/测试，不改API、Schema、权限规则或依赖。风险是分页旧条目、断线后重复写与跨项目结果；以原强版本、禁自动重试、重读解锁和服务器裁决处理。回滚撤行内编辑，保留P01/P02。验证前端测试/typecheck/build，实际浏览器/PG另项。
- Executed：2026-09-29，ACTIVE负责人行内编辑、改字段撤确认、单次原快照提交、成功回执与当前历史分离、未知后清旧/失败重读不解锁/成功重读解锁、跨项目迟到回执丢弃测试通过。首轮夹具复用已消费Response导致一项测试失败，修正夹具后完整前端648项/typecheck/build PASS；实际浏览器/PG另项。

## DEC-20260929-458 — PRJ-05-A12-P02 部门更新安全业务客户端

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A12-P02。P01传输、冻结PATCH合同、后端PRJ-04-A15与部门历史安全投影前置满足。
- Decision：一次更新只允许 code/name 中至少一项并按服务端 NFKC/trim 有界规范化；只接受 ACTIVE 原部门与强版本。200 必须绑定原部门 ID/创建时间/ACTIVE、目标字段、未改字段、响应强ETag与预期版本增量（无变化保持）；明确错误仅按已知 HTTP/码匹配，其他及断线均视未知，须重读历史，不自动重试。
- Impact/rollback/validation：仅前端业务客户端/测试，无API/Schema/权限/依赖变化。风险为伪成功误确认或未知重试；回滚移除客户端。前端测试/typecheck/build；实际页面和浏览器/PG另项。
- Executed：2026-09-29，原部门/ACTIVE/强版本、NFKC字段、无变化v0与变更v1、伪ID/创建时间/状态/字段/ETag、明确拒绝与未知边界测试通过；前端644项/typecheck/build PASS。页面/真实PG另项。

## DEC-20260929-457 — PRJ-05-A12-P01 部门更新固定前端传输

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A12-P01。冻结 PROJECT_DEPARTMENT_PATCH、后端 PRJ-04-A15-P02 与现有 SessionClient 为输入；Gate2 与前置写/只读链已满足。
- Decision：仅加私有 `PATCH /api/v1/projects/{project_id}/departments/{department_id}` 传输，双规范 UUID、强且安全整数版本、非空有界 JSON body、同源 Cookie/私有 CSRF、无自动重试/无幂等 Key；401 清会话证明，失败或超时返回不确定，由后续业务客户端先 GET 复核。当前任务不解析业务响应或新增页面。
- Impact/rollback/validation：仅 Auth transport 和单元测试，未改冻结 API、Schema、权限或依赖。风险为超时已提交却误重发，调用层明确不得重试；回滚移除方法/测试。验证前端测试、typecheck/build；实际浏览器/PG 另项。
- Executed：2026-09-29，固定双 ID/强版本/8192 字节上限、CSRF/同源/不重试/401 清证明和超时 busy 互斥验证通过；前端 617 项、typecheck、build PASS。业务响应和实际浏览器/PG 另项。

## DEC-20260929-456 — PRJ-05-A11-P04 Windows 11 部门创建端到端

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A11-P04；P01～P03与后端PRJ-04-A14-P03前置满足，复用自有随机PG/Vault/浏览器夹具，仅合成信任源。
- Decision：独立department-create API-only和browser模式，HTTP核匿名/非负责人/CSRF/外项目及201/原Key重放/异载荷冲突；浏览器从部门历史入口明确确认创建，再重读历史。SQL验仅一新部门、单Audit与完成收据，清理自有进程/库/角色/Vault并恢复原PG停止状态；失败不标PASS。
- Impact/rollback/validation：只改验收脚本/进度，无生产API/Schema/权限/依赖。风险为本机PG服务启动及中断残留，使用唯一资源名和精确清理；回滚撤新fixture模式。正式信任/三平台/性能/Gate仍独立验收。
- Executed：2026-09-29，API-only隔离HTTP/PG和实际IAB浏览器/PG均PASS。浏览器由部门历史进入创建、勾选确认，获得NEW/v0首次回执，再返回历史独立读到NEW；SQL仅一条新增ACTIVE/v0、单Audit及完成收据。两轮随机测试库/角色/Vault清理exit0，原PoC PostgreSQL恢复停止。未验证正式信任/其他平台/Gate。

## DEC-20260929-455 — PRJ-05-A11-P03 部门创建确认页面

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A11-P03；P01/P02客户端、部门历史页与后端冻结创建合同前置满足。
- Decision：仅当前ProjectManager且有内存写证明时显示创建入口；编码/名称变化撤确认。显式勾选后固定原输入+Project+Actor+一次Key提交；未知结果保留原输入/Key并要求再次明确确认原操作，不允许新建Key；幂等冲突锁写，确定拒绝重置。首次回执标注不是当前状态，历史需重新读取；切项目/身份变化/卸载丢弃迟到结果。
- Impact/rollback/validation：仅Project前端页面/路由/测试，无后端API/Schema/权限/依赖变化。风险是未知结果误重建或跨项目旧结果显示；原记录内存锁与服务器最终裁决。回滚撤入口/页面，P01/P02保留；验证全前端测试/typecheck/build，浏览器PG另项。
- Executed：2026-09-29，首轮切项目时忙碌标记遮住拒绝提示，修正后页面/入口权限、显式确认、未知原Key恢复、冲突锁页、迟到结果测试通过。前端613项/typecheck PASS；合并构建首次Windows进程异常退出，单独完整build重跑PASS。实际浏览器/PG另项。

## DEC-20260929-454 — PRJ-05-A11-P02 部门创建首次结果安全客户端

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A11-P02；P01传输与冻结Department201响应及P01只读安全投影前置满足。
- Decision：NFKC规范编码/名称并固定仅二字段Body；仅201且trace/Department安全投影、原输入一致、ACTIVE/`"v0"`、ETag/Location精确一致时接收首次结果，明确标记不是当前状态证明。同Key重放仍为首次结果；已知拒绝与网络/坏响应未知分离，未知时调用者保留原输入/Key，不自动重发。
- Impact/rollback/validation：仅前端业务客户端/测试，无API/Schema/权限/依赖变化；撤新增客户端可回滚，P01传输保留。验证坏输入零网络、成功/重放/伪造响应、已知状态码、未知/超时以及全前端测试/typecheck/build；页面与浏览器/PG另项。
- Executed：2026-09-29，正常/同Key首次回执、坏输入零网络、伪201、已知拒绝/未知及无写证明测试通过；前端604项、typecheck、build PASS。页面与实际浏览器/PG未验。

## DEC-20260929-453 — PRJ-05-A11-P01 部门创建私有前端传输

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A11-P01；冻结 Department POST、PRJ-04-A14-P03 Windows 显式组合、前端私有 SessionClient 均已具备。
- Decision：只在 SessionClient 增加规范 Project UUID 的固定部门 POST 路径，使用既有同源 Cookie/私有 CSRF/原调用方 Idempotency-Key、8192字节 JSON Body 上限与单次超时。401 清写证明；网络未知不自动重发或换 Key。DTO、首次结果和页面另 WBS。
- Impact/rollback/validation：无后端 API/Schema/Migration/权限/依赖改变；撤新增方法及测试即可回滚。验证固定路径/头、坏 ID/Body/Key 零网络、只读会话/401/503、互斥和超时，并跑全前端测试/typecheck/build。
- Executed：2026-09-29，固定路径/头、坏输入/无写证明零网络、401/503、互斥和超时用例通过；前端575项、typecheck、build PASS。业务响应和实际浏览器/PG待后续独立任务。

## DEC-20260929-452 — PRJ-05-A10-P03 Windows 11 部门历史端到端

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A10-P03；P01/P02与PRJ-04-A13-P04前置满足。自有浏览器/PG随机隔离 fixture，仅合成信任源。
- Decision：独立 department-history 模式种入52条部门含末页INACTIVE，API-only核匿名/外项目/非成员拒绝及50+2分页，浏览器从项目详情进入部门页并加载更多；SQL核最终数据不变，清理随机库/角色/Vault与自有服务，恢复PoC PG原停止状态。不把合成验收外推到正式信任/Gate3。
- Impact/rollback/validation：仅验证脚本及进度，无生产程序/API/Schema/权限/依赖变化；中断风险用唯一资源名和精确清理控制。失败不标PASS；回滚撤独立 fixture 模式。
- Executed：2026-09-29，首轮 API-only 审计列名错误、首轮浏览器旧Session数量断言错误分别修复并重跑；最终 HTTP/PG 50+2/一条停用与浏览器续页均通过，SQL 52/1/零部门写，随机资源清理 exit0，PoC PG恢复原停止。正式信任/其他平台/性能/质量/Gate未验。

## DEC-20260929-451 — PRJ-05-A10-P02 部门历史只读页面

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A10-P02；P01安全客户端、Project详情路由与冻结 Department GET 前置已满足。
- Decision：增加项目详情到部门历史入口和独立只读页；首次/刷新固定50条，续页仅使用当前服务器游标，跨页重复 ID 或读取失败清旧，路由变化/卸载丢弃迟到结果。展示 ACTIVE/INACTIVE、编码/名称/创建时间，不声称客户端可授予权限或提供写操作。
- Impact/rollback/validation：仅 Project 前端页面、路由、测试与进度；无 API/Schema/权限/依赖改变。风险是分页后事实变化或跨项目旧数据显示；服务器当前授权为准，切换清旧。回滚撤入口和页面，P01保留。前端测试/typecheck/build，实际浏览器/PG另项。
- Executed：2026-09-29，入口、历史展示、续页/刷新、无身份/改密、拒绝清旧、跨页重复与跨项目迟到结果测试通过；前端563项、typecheck、build PASS。实际浏览器/PG另项未验。

## DEC-20260929-450 — PRJ-05-A10-P01 部门历史只读客户端

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A10-P01；冻结 Department 列表合同、PRJ-04-A13-P04 Windows 显式装配与现有前端项目读取前置满足。
- Decision：独立于成员选择用的 ACTIVE 部门列表，新增固定50条 Department 历史页读取客户端，保留 INACTIVE、强 ETag/UTC时间与安全字段；项目/游标校验、同源 Cookie、单次超时、错误合同及分页异常均失败关闭。此项不创建 UI 或写命令，权限由服务器实时裁决。
- Impact/rollback/validation：仅 Project 前端客户端/测试与进度，无 API/Schema/权限/依赖变化。历史可能跨页变化，客户端不声称快照一致；回滚撤新增读取客户端。全量前端测试/typecheck/build验证，实际浏览器/PG另项。
- Executed：2026-09-29，固定50条安全投影、INACTIVE历史、游标/错误/超时/异常测试通过；前端557项、typecheck、build PASS。实际浏览器/PG与正式信任未验。

## DEC-20260929-449 — PRJ-05-A09-P04 Windows 11 成员三状态端到端

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A09-P04；P01～P03 与后端 PRJ-04-A12-P03 前置已满足。复用自有浏览器/PG fixture，仅合成信任源。
- Decision：独立 member-state 模式建立随机 PostgreSQL 库/角色、Vault测试凭据、一个负责人和一个目标成员；API-only 验匿名、CSRF、非负责人/跨项目、原 Key重放与异输入冲突；浏览器按暂停→恢复→移除操作，核对每次首次回执和重读当前历史、最终移除仍有历史。SQL 验 v3、三条状态 Audit、三份完成收据；清理自有资源并恢复原 PG 服务状态。不同模式测试不同随机资源，不将合成证据当生产信任/Gate3。
- Impact/rollback/validation：只修改验证脚本及进度，无实体/Schema/API/权限/依赖变更。风险是本机服务原停止、会话中断造成残留、浏览器会话丢失；先记原状态，使用唯一命名、结束精确清理。失败不标 PASS；回滚撤 fixture 模式。
- Executed：2026-09-29，API-only HTTP/PG exit 0；真实浏览器暂停→恢复→移除，各次 first receipt 与当前历史分开显示，最终 SQL REMOVED/v3、三条 Audit、三份完成收据，资源清理 exit 0。PoC PG 恢复原停止状态；正式信任、其他平台、性能/质量与 Gate 未验。

## DEC-20260929-448 — PRJ-05-A09-P03 成员状态确认页面

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A09-P03；P01/P02、成员历史列表与后端冻结三状态命令均已具备。无单成员 GET，继续从已读取历史选择目标。
- Decision：项目负责人针对当前非移除成员选择合法暂停/恢复/移除操作，展示目标用户、状态/角色/部门与强版本，明确勾选后生成一次 Key 并单次提交。未知结果在本页保留原目标/动作/版本/Key，只允许再次明确确认后按原记录恢复；同时重读历史但不把其当首次结果证明。成功回执与服务器当前历史分开；已知拒绝清原操作重读，幂等冲突锁页；路由/身份变化丢弃迟到回执并销毁内存 Key。移除属于保留历史的状态终结，页面不提供直接恢复。
- Impact/rollback/validation：仅现有 Project 成员页与测试，不改后端 API/权限/Schema/依赖。风险是首次回执非当前状态、离页后 Key 丢失或误操作最后负责人；服务端为最终裁决，页面告知风险。测试权限/动作/确认/原 Key 恢复/冲突与迟到回执，运行全前端测试/typecheck/build。回滚撤新增页面入口，P01/P02保留。

## DEC-20260929-447 — PRJ-05-A09-P02 成员状态首次回执客户端

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A09-P02；P01 传输及冻结三状态后端首次快照/幂等合同已具备。
- Decision：使用已读取成员安全快照加动作/原幂等 Key 校验请求；仅合规 200、同一成员/User、角色/部门/生效时间保持、目标状态及 vN→vN+1/响应 ETag 一致时返回明确命名的 first receipt。REMOVED 要有 ended_at，其他状态无 ended_at；回执不宣称当前状态。401/权限/版本/状态/幂等冲突等已知拒绝单独分类；超时、503、坏 JSON/投影等为未知，调用方保留原动作/Key/版本，不能直接新建请求。
- Impact/rollback/validation：不改冻结 API/Schema/权限/依赖。测试输入零网络、三动作、重放首次回执、已知拒绝/未知结果与伪造响应；全前端测试/typecheck/build。风险是回执后其他管理员再次变更，P03 页面必须另行重读当前历史；回滚撤本客户端和测试，P01 传输保留。

## DEC-20260929-446 — PRJ-05-A09-P01 成员状态命令私有传输

- Date/WBS：2026-09-29 / Phase2 PRJ-05-A09-P01；冻结 `PROJECT_MEMBER_SUSPEND/RESUME/REMOVE`、PRJ-04-A12-P03 Windows 显式组合和现有 SessionClient 前置满足。
- Decision：只在内存 SessionClient 增精确三种成员状态 POST 路径，两个规范 UUID、强 If-Match、原调用方幂等键、私有 CSRF、同源 Cookie、空 Body、单次发送；401 清提交证明，其他网络未知不自动重试/换 Key。业务 DTO、首次回执与当前状态分离及页面留后续 WBS。
- Reason/impact/rollback/validation：防路径注入、CSRF/Key 泄漏、状态写重复和客户端越权。新增固定路径/头/无Body、坏输入零网络、401/503、互斥与超时一次测试及全前端构建。无 Schema/Migration/后端 API/权限/依赖变化；回滚撤本方法和测试。

## DEC-20260928-445 — PRJ-05-A08-P04 Windows 11 成员 PATCH 端到端验证

- Date/WBS：2026-09-28 / Phase2 PRJ-05-A08-P04；P01～P03 合同与 Windows 显式写组合前置已通过。使用现有自有 Windows 浏览器/PG fixture；正式发行信任源和其他平台不在本项范围。
- Decision：扩展 fixture 独立 member-patch 模式，在随机 PostgreSQL 库/角色、临时 Vault 凭据、合成负责人/目标用户/两个 ACTIVE 部门下，由真实浏览器通过成员历史页提交角色/部门变更；另用真实 HTTP 对版本冲突、权限/CSRF/跨项目和 no-op 核对，SQL 查单成员版本及 Audit。只对自有随机资源清理。失败不得标 PASS 或外推 Gate3。
- Impact/rollback/validation：验证脚本和可能发现的前端缺陷限本模块处理；无基线/Migration/API/依赖变化。预期风险是本机 PG 原停止、浏览器环境与 fixture 登录路径，先记录原状态，启动测试服务后恢复。验收前端测试/typecheck/build、HTTP/浏览器/SQL、资源清理，回滚撤验证模式。
- Executed：2026-09-29，API-only HTTP/PG exit0；首轮浏览器 v1 与列表成功但旧Session断言失败，修正后重跑。中断遗留的精确随机测试库/角色/Vault凭据经核验后清理；最终浏览器/SQL/清理 exit0，PoC PG 原停止状态恢复。正式信任/其他平台/性能/Gate未验。

## DEC-20260928-444 — PRJ-05-A08-P03 成员角色/部门修改页面

- Date/WBS：2026-09-28 / Phase2 PRJ-05-A08-P03；前置 P01/P02、成员历史列表及 ACTIVE 部门客户端 PASS，冻结 PATCH 无单独成员 GET。
- Decision：在已授权成员历史列表内选定精确成员快照编辑，避免凭路由 ID 跨多页盲查或捏造 GET；仅当前项目负责人可见提交，候选部门必须为当前 ACTIVE。展示目标用户、当前角色/部门/状态及强版本，明确勾选后一次 PATCH。已知拒绝清编辑并要求重读；未知结果锁住本页后续写入，重读列表仅供对账，不能当作本次操作的唯一证明或自动重试。导航/身份变化丢弃迟到回执。
- Impact/rollback/validation：仅 Project 前端页面/路由范围内修改，不改后端 API/Schema/权限/依赖。风险是列表快照过期或 PATCH 提交后状态并发变化，服务端 If-Match 为最终裁决；测试授权、显式确认、版本冲突、未知结果和迟到回执，运行全前端测试/typecheck/build。回滚撤列表编辑入口，保留 P01/P02。

## DEC-20260928-443 — PRJ-05-A08-P02 成员 PATCH 业务响应客户端

- Date/WBS：2026-09-28 / Phase2 PRJ-05-A08-P02；前置 P01 私有传输及 PRJ-04-A11 后端合同 PASS。
- Decision：客户端以已读取成员安全快照（含强 ETag）加部分角色/部门期望输入构造严格 JSON；只有 200 固定信封、同一成员/User、未改状态/生效历史、期望角色/部门及 ETag 为原值或加一时才确认。无变化可返回原版本；版本/权限等已知拒绝单独分类。网络超时、未知状态、坏 JSON/投影或不匹配的成功回执均为结果不确定，后续 UI 必须重新读取成员历史而非用旧版本重试。原冻结 API 不变，不加幂等 Key。
- Reason/impact/rollback/validation：防止页面把别人成员或后端异常回执显示为成功。单元覆盖输入零网络、确定拒绝、不可判定结果和安全投影；全前端测试/typecheck/build 验收。无 Schema/Migration/依赖变；回滚撤本客户端与测试，P01 传输保留。

## DEC-20260928-442 — PRJ-05-A08-P01 成员 PATCH 私有会话传输

- Date/WBS：2026-09-28 / Phase2 PRJ-05-A08-P01；输入 Gate2 冻结 `PROJECT_MEMBER_PATCH`、PRJ-04-A11-P01/P02 Windows 显式组合及 PRJ-05-A07 已验项目成员入口。
- Decision：仅给内存 SessionClient 增加固定成员 PATCH 路径的受控单次传输，严格验证两个 UUID、强 `"vN"` If-Match 与非空有界 JSON 字符串，使用同源 Cookie、私有 CSRF、no-store 和禁重定向；401 清本地提交证明，其他未知网络结果不自动重试。该 PATCH 无冻结幂等 Key，结果不确定时后续业务客户端须先从服务器重读成员历史再决定，不凭旧版本再次提交。
- Reason/impact/rollback/validation：保持冻结 API 与服务器实时权限不变。风险是路径注入、CSRF 泄漏、超时后重复变更或会话并发；以请求头/目标、非法输入零网络、401/503、互斥和超时单次测试及全前端构建验证。无 Schema/Migration/依赖变化；回滚撤该 SessionClient 方法和测试。

## DEC-20260928-441 — PRJ-05-A07-P03-A05 独立浏览器/PG 成员写链

- Date/WBS：2026-09-28 / Phase2 PRJ-05-A07-P03-A05；A01～A04 已通过各自合同，A05 不以单元测试代替浏览器和数据库事实。
- Decision：复用本项目自有浏览器 fixture 的随机数据库/角色/Windows Vault 测试凭据与本机代理，仅增独立成员创建模式：合成负责人和未分配启用目标用户、一个 ACTIVE/一个 INACTIVE 部门；在实际浏览器操作候选、部门/角色确认和创建后核对成员、Audit 与幂等收据各一条。另以真实 HTTP/PG 复核安全拒绝和重放；完成后清理自有进程/库/角色/Vault。许可和游标密钥仅测试注入，不冒充正式信任锚。
- Impact/rollback/validation：只改验证脚本及证据，不改生产 API/Schema/权限。风险是本机既有 PG 服务未运行、浏览器会话残留和测试资源未清理；先检查/恢复测试服务，执行后以 SQL 和自有资源不存在为证。回滚撤验证脚本模式，无数据迁移。

## DEC-20260928-440 — PRJ-05-A07-P03-A04 项目成员创建页面

- Date/WBS：2026-09-28 / Phase2 PRJ-05-A07-P03-A04；CR-PRJ-006 A01～A03 PASS，沿用原 `PROJECT_MEMBER_CREATE` 写合同。
- Decision：仅当前 Session 摘要显示为本项目负责人且具有私有 CSRF 时展示创建流程，实际权限始终由服务端重核。部门从现有客户端仅选 ACTIVE，目标用户必须先用精确用户名解析；输入变化即清除旧候选，角色/部门显式选择并确认。未知提交结果保留原输入与幂等 Key 于当前页面内存，须明确勾选后原样重试；会话/项目变化或幂等冲突阻止重试。成功只显示服务端已确认的成员安全投影。
- Impact/rollback/validation：不改后端/Schema/权限。风险为旧候选、重复提交、会话切换及误将查询命中视为成员成功；以页面权限、候选失效、原 Key 重放与失败分支测试后才标 PASS。回滚撤页面/路由/入口，保留后端与客户端。

## DEC-20260928-439 — PRJ-05-A07-P03-A03 前端候选与部门安全选择

- Date/WBS：2026-09-28 / Phase2 PRJ-05-A07-P03-A03；前置 CR-PRJ-006 A01/A02 已在 Windows 11 隔离 PG 通过。只处理前端客户端，不提前声明页面或浏览器验收。
- Decision：候选 POST 必须经 SessionClient 私有 CSRF、同源单次传输，不用 URL 查询、不自动重试、不带幂等 Key；响应只接受单个最小候选或统一空值。部门沿既有 GET 固定 50 条分页，游标逐页读取且有上限，仅返回 ACTIVE 选项，不从成员历史或管理目录推断部门。候选与部门数据只用于页面选择，成员创建 POST 仍实时复核。
- Impact/rollback/validation：无后端/Schema/权限变更；风险是过期/跨项目候选、异常分页、响应夹带私有字段与 CSRF 暴露。以前端传输/投影/权限错误/分页/失效测试、全量 typecheck/build 验收；回滚撤本次前端读取客户端和 SessionClient 专用传输方法。

## DEC-20260928-438 — PRJ-05-A07-P03-A02 Windows 显式平台候选装配

- Date/WBS：2026-09-28 / Phase2 PRJ-05-A07-P03-A02，沿用 CR-PRJ-006 和 A01 已验证增量合同。
- Decision：只在 Windows `--platform` 与 `--platform-write` 已具备完整可信来源的组合根注入精确成员候选 Router，复用当前真实 PostgreSQL Session、License Guard、Project 创建授权、Auth-owned User 读取、Project-owned 成员归属读取及持久摘要限流。默认应用和 `--login` 不挂载；任何现有生产信任源失败则整个显式组合关闭，不降级为候选单独开放。
- Impact/rollback/validation：不改变 Gate2 冻结接口、Schema、Migration、依赖或角色权限。风险是误挂载、跳过 Session/License 或信任源失败后部分路由仍发布；以两种显式模式的隔离 PostgreSQL 真实会话/权限/许可/限流、默认与 login 404、缺钥启动失败验证。回滚撤组合根传参及本任务测试，不删除 A01 的独立可选 API。

## DEC-20260928-437 — PRJ-05-A07-P03-A01 精确成员候选合同实施前

- Date/WBS：2026-09-28 / Phase2 PRJ-05-A07-P03-A01，关联CR-PRJ-006。原`AUTH_USER_LIST`保持DeploymentAdmin专用；原`PROJECT_MEMBER_CREATE`仍须服务端实时核验。
- Decision：新增可选`POST /api/v1/projects/{project_id}/member-candidates:resolve`，固定JSON`{"username":"..."}`与私有CSRF；仅当前ACTIVE项目负责人经真实Session、License和`PROJECT_MEMBER_CREATE`同等授权后，在同一短事务内以Auth-owned Port精确读取ENABLED User，Project-owned Port检查无非REMOVED成员。无匹配/停用/已分配统一`200 data:{candidate:null}`，命中只给UserId/显示名，不公开他项目。读前通过现有PostgreSQL计数桶持久保留按负责人+项目30/5分钟、按负责人+项目+规范用户名10/5分钟容量；即使候选缺失也计数，429固定错误。`Cache-Control:no-store`。最初拟GET查询串，实施前安全复核发现用户名易进入URL历史/代理日志且跨站可消耗额度，故同一CR内收敛为带Origin/CSRF的POST；不表示写入成员，也不要求幂等Key。
- Reason/impact/rollback/validation：用户名猜测风险以精确查询、当前负责人门禁、最小投影、统一未命中及跨进程限流约束；候选后身份/成员变化仍由原创建POST复核。非破坏性新增合同，不改原冻结文件、Schema/Migration或依赖；回滚撤可选路由/服务/适配器/增量合同。Unit、HTTP权限/异常及隔离PostgreSQL当前事实和限流测试后才标记A01 PASS；正式Windows组合装配另验。

## DEC-20260928-436 — PRJ-05-A07-P03 页面前置与 CR-PRJ-006

- Date/WBS：2026-09-28 / Phase2 PRJ-05-A07-P03。冻结成员POST需目标User UUID，而项目负责人不能调用仅DeploymentAdmin可用的`AUTH_USER_LIST`。项目部门GET可供当前项目成员使用，前端尚无客户端。
- Decision：页面不要求非技术用户手填UUID，也不扩大管理目录权限。按用户持续授权登记CR-PRJ-006，先实现当前有效ProjectManager精确用户名候选解析的非破坏性增量API与安全限流/统一未命中，再接部门ACTIVE选择和成员页面。原冻结API/后端POST不改；候选只是提示，提交仍由原服务端最终复核。
- Impact/rollback/validation：当前页面前置BLOCKED，不把P01/P02客户端验收冒充页面可用。新端点泄露用户目录/跨项目旁路风险及独立权限、License、限流、真实PG测试列于CR；回滚撤增量端点/选择器，无Schema迁移。本次只记录设计与状态，未实现新增API。

## DEC-20260928-435 — PRJ-05-A07-P02 项目成员创建安全响应客户端实施前

- Date/WBS：2026-09-28 / Phase2 PRJ-05-A07-P02。Gate2冻结`PROJECT_MEMBER_CREATE`、PRJ-04-A10-P01～P03实际后端合同、P01前端单次写传输已具备。仅新增Project模块响应客户端、复用只读成员安全投影与测试；不改业务权限、实体、后端、Schema/Migration、API合同或依赖。
- Decision：本地白名单构造请求并校验Project/User/Department UUID、角色、可选UTC时间及原幂等Key；仅`201`且Trace、成员八字段、初始ACTIVE/`"v0"`、请求User/Role/Department/显式生效时间、ETag和Location一致时返回冻结安全投影。仅服务端状态与已知错误码匹配时认定明确拒绝；其他状态、畸形/不匹配回执、网络或超时一律“结果未确认”，不自动重试/换Key或把原始错误披露给UI。
- Impact/rollback/validation：风险为不完整回执被误认成功、服务端已提交却由客户端换Key重复创建、微秒时间比较被毫秒精度掩盖。测试覆盖安全投影、确定/未知分类、非法输入零网络、单次提交及微秒边界；回滚撤客户端及只读解析器导出，无数据库步骤。页面和实际浏览器/PG写链独立验收，不以合成客户端测试代替。
- Executed：前端462项测试、typecheck、build exit0；无正式信任/Server2025/Debian、实际浏览器或PG写入验收。

## DEC-20260928-434 — PRJ-05-A07-P01 项目成员创建受控前端传输实施前

- Date/WBS：2026-09-28 / Phase2 PRJ-05-A07-P01。Gate2冻结`PROJECT_MEMBER_CREATE`、后端PRJ-04-A10-P01～P03持久幂等/Windows显式写组合、既有SessionClient写命令桥均已具备。仅在前端Auth会话客户端增加该固定POST传输与测试；不改业务权限、后端、实体、Schema/Migration、API合同或依赖。
- Decision：新增`postProjectMemberCreate(projectId,body,key)`，规范Project UUID、8KiB JSON字符串和可打印16～128字节原幂等Key本地校验；与现有会话命令共用私有CSRF、同源Cookie/no-store/禁止重定向、超时Abort及互斥。401清内存证明；网络超时或响应不明不自动重试、不旋转Key。此层仅返回原Response，不分析201/错误或声明业务成功；后续安全响应客户端/页面独立任务。
- Impact/rollback/validation：风险为拼接不可信路径、意外泄露CSRF、双提交或不确定结果下产生重复成员；以无效输入零网络、固定路径/header/body、并发互斥、401和超时单次测试约束。回滚撤方法/测试，不涉及数据库升级。前端test/typecheck/build后归档；浏览器/PG写链与正式License/TLS另验。
- Executed：新增SessionClient固定成员POST方法及12个测试用例，全前端430/430、typecheck/build exit0。前端只交付原Response，业务结果仍待P02解析；页面与真实HTTP/PG写链未验。

## DEC-20260928-433 — PRJ-05-A06-P03 成员历史隔离浏览器联调实施前

- Date/WBS：2026-09-28 / Phase2 PRJ-05-A06-P03。冻结`PROJECT_MEMBER_LIST`、P01客户端/P02页面、后端Windows显式只读组合均已具备；仅扩展自有一次性PG/Vault/loopback浏览器夹具的互斥模式，不改生产API/Schema/权限/依赖。
- Decision：合成ProjectManager、ImplementationMember及50条额外成员历史，其中最后一条为REMOVED；浏览器先验普通成员详情可读而成员历史不可读，再验负责人50条首页/2条续页与移除历史。独立`--member-api-only`核实际HTTP状态、跨项目404、不同`page_size`游标拒绝与清理。临时数据库/角色/Vault由夹具统一回收，SQL核52条历史/51条ACTIVE及测试Session。
- Impact/rollback/validation：风险是PG服务停止、浏览器轮次切换导致验证进程中断或临时源残留；先核精确环境和命名源，完成时必须`VERIFY` exit0与自动清理，异常则以原进程/精确资源核实，不虚报。测试模式可撤，无Migration/升级。仅Windows11 loopback合成License，不替代正式信任、Server2025/Debian、性能/Gate3。
- Precondition observation：本轮开始本机既有PG18服务已停止；从原数据目录启动，日志显示WAL自动恢复并就绪，`prj05a04_%`临时库为0；再次停止的原因未证实，不能将此环境事件记为产品通过或缺陷结论。
- Executed/evidence：`--member-api-only` exit0：普通成员/无成员管理员成员历史404、负责人50+2/含一移除、外项目404、换page_size游标400，SQL52历史/51有效/3会话并自动清理。实际IAB：合成实施成员可见OWNED详情，但成员历史统一无权；合成负责人首页50条，下一页显示`Synthetic History 48/49`，最后一条“已移除”。`--member-browser` `VERIFY` exit0：SQL52历史/51有效/2会话，服务/库/角色/Vault清理通过；旧`--api-only`回归exit0，外部复查临时库0。无生产变更；正式信任/其他平台/性能/Gate3仍未验。

## DEC-20260928-432 — PRJ-05-A06-P02 项目成员历史页面实施前

- Date/WBS：2026-09-28 / Phase2 PRJ-05-A06-P02。P01安全只读客户端与冻结`PROJECT_MEMBER_LIST`、现有项目详情页已具备；仅新增前端Project成员历史页面、项目详情入口和路由/测试，不改后端、实体、Schema/Migration、权限或依赖。
- Decision：登录且非改密受限身份才能发请求；不以Session摘要角色猜测授权，服务端每次GET复核ProjectManager/CustomerManager权限。固定50条分页，下一页从P01不透明cursor读取；切换项目/失败清空旧成员与cursor，迟到请求按路由代次丢弃，重复成员跨页拒绝，服务端字符串仅文本展示。详情入口不扩大服务端权限。
- Impact/rollback/validation：风险为路由切换后旧项目成员残留、过期cursor续页或无权用户可见数据；页面合同验证无身份/受限零请求、成功/分页/空结果、安全拒绝清旧、路由迟到结果，跑全前端test/typecheck/build。回滚撤页面/路由/详情入口，无升级；实际浏览器/PG及正式信任另项验收。
- Executed：新增页面、路由与项目详情入口及8个页面场景；前端418/418、typecheck/build exit0。实际浏览器/PG、正式信任/其他平台和Gate3未验，不将页面合同冒充真实授权验收。

## DEC-20260928-431 — PRJ-05-A06-P01 项目成员只读前端客户端实施前

- Date/WBS：2026-09-28 / Phase2 PRJ-05-A06-P01。Gate2、冻结`PROJECT_MEMBER_LIST`、后端Windows显式成员历史GET、现有ProjectReadClient前置已满足。只处理前端Project成员分页读取/安全投影及测试，不改实体、DB Schema/Migration、后端API、权限或依赖。
- Decision：固定50条`page_size`，仅接受规范Project UUID和后端不透明签名cursor；对返回MemberView八个顶层安全字段及嵌套User/Department逐一验证并丢弃额外字段，分页状态/游标形状及重复ID失败关闭。浏览器仅相对同源Cookie GET/no-store/no redirect，超时不重试；服务端状态/错误只映射固定安全提示，不把响应正文或cursor载荷解释成客户端授权。独立页面另WBS。
- Impact/rollback/validation：风险为误显示跨项目成员、使用过期cursor或服务端异常信息泄露；通过目标路径、分页、无网络非法输入/错误、字段白名单及timeout单次测试约束。回滚撤新增客户端/测试，不需Migration/升级；完成前跑前端test/typecheck/build。此项前端合同不替代浏览器+PG、正式TLS/License及Gate3。
- Executed：新增前端只读Client与48个新测试场景；全前端410/410、typecheck、build exit0。无后端/API/Migration/权限/依赖变化；真实浏览器/PG页面集成仍待PRJ-05-A06后续任务。

## DEC-20260928-430 — AUT-05-A13-P04 管理员用户改名浏览器联调实施前

- Date/WBS：2026-09-28 / Phase2 AUT-05-A13-P04。P03页面合同与现有后端Windows显式write改名链已通过；仅缺二者真实浏览器联调。涉及一次性合成Auth User、现有隔离浏览器夹具及临时PG，不改生产 API/Schema/实体/权限/依赖。
- Decision：为原只读/状态浏览器夹具增加互斥的显式`--user-name-browser`写模式，复用随机loopback端口/临时库角色/Vault/合成License。只改合成Member用户名，浏览器Admin登录→详情`"v0"`→改名页面确认→写回执与独立详情`"v1"`；然后用旧名登录应拒，新名登录应成功。脚本终态查同UUID/new display/canonical/v1、固定改名Audit恰一条，并清自有源。原`--api-only`模式另回归。
- Impact/rollback/validation：只有验证夹具与记录变更；若浏览器或夹具中断，核精准临时库/角色/Vault并保留失败，不虚报。回滚可撤新模式。此轮仅本机HTTP/合成信任，不替代正式TLS、真实License、Server2025/Debian或发行Gate。
- Executed/evidence：首轮启动时本机既有 PostgreSQL 18 服务已停止，夹具退出1、尚未创建临时库；核查服务状态和 `prj05a04_` 临时库为0后，在原数据目录用 `pg_ctl` 启动，WAL自动恢复完成。停止原因未证实，未当作产品缺陷或虚报首轮通过。恢复后 Windows11 隔离浏览器 Admin 实际见目标 `v0`，显式确认改名，首次回执与独立当前 GET 均为同 UUID/新名称/`v1`；退出 Admin 后旧名称登录被拒，新名称登录成功。夹具 `VERIFY` exit0：SQL 同用户 `ENABLED/v1`、`USER_NAME_CHANGED` 恰1条、2项目/2会话/1有效成员，临时服务/库/角色/Vault 清理通过。原 `--api-only` 回归 exit0。无生产迁移、API 或权限变化；正式信任/其他平台/Gate3 保持未通过。

## DEC-20260928-429 — AUT-05-A13-P03 管理员用户改名页面实施前

- Date/WBS：2026-09-28 / Phase2 AUT-05-A13-P03。P01单次PATCH桥、P02安全响应、已验User详情GET及冻结`AUTH_USER_PATCH`已具备。单一问题是使管理员可从User详情安全改展示/登录名；涉及前端Auth页面/路由及User当前视图，不改后端实体/API/Schema/权限/依赖。部署管理员仍需当前不受改密限制身份与新鲜可写Session，服务端复核是最终授权。
- Decision：与启停页分开`/admin/users/:userId/name`，从当前详情进入，页面先独立GET取强ETag，目标/新名/版本显式确认后单次PATCH。无论200还是未知结果，清旧当前详情并再GET；200首回执和后来当前事实分开，未知结果禁止页面内继续提交，提示核对审计/重新登录，不用新请求猜执行结果。确定冲突清旧详情并要求重新读取。无身份/非Admin/改密受限零GET/写；只读Admin可看不可提交。改名影响旧登录名，页面明确告知。
- Impact/rollback/validation：仅前端路由/页面/测试/详情入口，无DB/API变更；回滚撤路由与链接保留P01/P02未使用客户端。需验权限、只读会话、确认/版本、写后GET、未知结果不盲重试、错状态清旧、路由换目标清旧、文本安全；全量test/typecheck/build。真实浏览器/PG另P04，不将组件mock验收当真实改名。
- Executed：新增独立改名路由/页面与详情入口，200 first和独立GET分开、未知结果封锁本页再次写、确定冲突清旧，路由换目标忽略迟到回执。新增9场景，前端362/362、typecheck/build exit0；未作实际浏览器/PG改名，P04继续。

## DEC-20260928-428 — AUT-05-A13-P02 用户改名安全响应客户端实施前

- Date/WBS：2026-09-28 / Phase2 AUT-05-A13-P02；P01固定传输已通过，冻结`AUTH_USER_PATCH`及真实User详情强ETag为输入。仅前端Auth响应解析/测试，不改实体、后端API/Schema/权限/依赖。
- Decision：客户端以已读安全User详情为前置，保守NFC/去边空/控制字符及长度检查并提交固定名称；对200只接受绑定原User、目标展示名、状态/角色/凭据/创建时间不变的安全八字段、响应头匹配强ETag、版本不变（真实no-op）或+1（真实改名）。200也是写入时点结果，页面必须另GET确认当前事实。401/403/404/409/400/422/428按状态+固定码归确定拒绝；503/异常/畸形200一律标结果未知，无自动重试，页面只允许对账。此客户端不把旧登录名保留为别名。
- Impact/rollback/validation：仅新客户端及测试，回滚删除文件；P01仍无页面调用，不影响旧功能。验证成功/no-op、目标与版本绑定、额外秘密字段不传播、所有固定错误与未知分流、输入零网络、调用方超时和并发仍由P01桥承担；全量前端/typecheck/build。实际浏览器改名另P04，不以单元测试冒充后端生产验收。
- Executed：安全客户端及26项合同场景已加；首轮18项因UUID正则少段失败，修复后353/353测试、typecheck/build exit0。只返回安全八字段，no-op/版本+1及错误/未知分流通过；页面/实际浏览器尚未验。

## DEC-20260928-427 — AUT-05-A13-P01 用户改名受控前端传输实施前

- Date/WBS：2026-09-28 / Phase2 AUT-05-A13-P01。输入为 Gate2 冻结 API-02 `AUTH_USER_PATCH`、现有 Windows 显式 write Factory 和安全 User 详情 GET；前置已满足。涉及前端 Auth `SessionClient`，实体仍为 User；只接固定 `PATCH /api/v1/admin/users/{user_id}` 名称字段，无新权限/API/Schema/依赖。
- Decision：会话桥只接收规范目标 UUID、强当前 ETag、单个用户名字符串，按固定 `{"username":...}` JSON 单次 PATCH；私有内存 CSRF、同源 Cookie、no-store、禁止重定向和超时约束与既有状态命令一致。401 清本地写证明；网络/超时不自动重试，不把未知结果解释为未提交。页面/响应验证另列 A13-P02/P03；仅凭桥不宣称改名可用。客户端可做保守输入界限，但最终 NFC/去边/唯一性由服务端判定。
- Impact/rollback/validation：非 Breaking、无后端/DB/角色变更。回滚仅撤新方法/测试，当前页面无入口；需测合法初始 `"v0"`、固定路径/请求头/body、拒绝非法目标/弱或超限版本/大正文、缺新鲜 CSRF、401、超时单次且不泄密，并跑前端全套/typecheck/build。改名后旧名登录失效是原已冻结行为，不在桥中猜测结果。
- Executed：新增 `SessionClient.patchAdminUserName` 固定单次 PATCH/私有 CSRF/强版本/受限 JSON；四组新合同测试覆盖 `"v0"`、零网络拒绝、401 与超时互斥。前端327/327、typecheck/build exit0。未接响应客户端或页面，实际 HTTP/浏览器不以此项宣称通过。

## DEC-20260928-426 — AUT-05-A12-P05-A02-A02 实施前

- Date/WBS：2026-09-28 / Phase2 AUT-05-A12-P05-A02-A02。输入基线为冻结 API-02 `AUTH_USER_ENABLE/DISABLE`、现有 Windows11 真实 ASGI/PG 状态链与 A01 已通过的初始 `"v0"` 页面修补；前置 Gate2/Phase1 已满足。涉及 Auth 管理员 User 状态浏览器验收及测试夹具，不改生产实体/API/权限/Schema。
- Decision：扩展原隔离浏览器夹具为显式 `--user-state-browser` 模式，继续随机本机端口/独立临时 PG 库与角色/合成 License/Vault；仅在该模式安装已有 Windows 显式 write Factory，并核合成管理员在真实浏览器对合成普通用户执行停用→服务端详情确认→启用→当前详情确认。默认只读模式及原 Project 验证不得受影响。HTTP loopback/合成 trust 不等于正式部署；不得操作真实账户。
- Impact/rollback/validation：只改验证脚本、进度/版本说明，不改生产代码或数据迁移。若新模式失败，保留真实失败证据并停服务、清本次精确临时库/角色/Vault；回滚可撤新模式，原只读模式应仍 PASS。验收浏览器可见初始 `"v0"`、两次首次结果与独立当前详情，DB 最终 `ENABLED/v2`、测试会话撤销及自有资源清理；旧 `--api-only` 回归。未验证正式 TLS/信任/发行/Gate3。
- Executed：真实浏览器合成Member不可读、Admin列表→详情`"v0"`→停用首次`"v1"`/当前停用→启用首次`"v2"`/当前启用均可见。`VERIFY` DB终态ENABLED/v2、旧Member Session撤销、两不可变结果、2项目/3Session/1成员及库/角色/Vault清理exit0；原`--api-only`回归exit0。生产代码/API/Schema/依赖未变；正式发行限制保留。

## DEC-20260928-425 — AUT-05-A12-P05-A02-A01 浏览器联调发现初始版本偏差

- Date/WBS：2026-09-28 / Phase2 AUT-05-A12-P05-A02-A01。Windows11 隔离浏览器中合成普通用户被管理员页拦截、管理员列表可读，但点新建账户详情显示通用失败且重试一致。实际 GET 200、安全八字段与强 ETag 均为 `"v0"`；三个前端入口错误地只接受从 `"v1"` 开始，造成初始行详情不可读、首次启停提交也会被本地拒绝。数据库与其他资源已使用从 0 开始的 lock_version，非后端响应故障。
- Decision：这是客户端兼容偏差，不修改冻结 API 或数据库。将只读详情、状态响应客户端、会话传输三处版本输入拓展为规范 `"v0"` 或无前导零的正整数，继续拒绝弱 ETag、前导零及超过安全可递增范围；补零版本回归并重跑全套前端及同一浏览器/PG 链。首次 `"v0"` 状态命令仍要求服务端 If-Match/当前权限/幂等核验。正式浏览器写入另项，不借这次只读联调宣称 PASS。
- Impact/rollback/validation：仅 Auth 前端客户端与测试，无 Scope、权限、DB/API 变更；回滚本修补会重现新建账户无法查看/启停，应保留修补。验证真实初始 `"v0"`、异常 ETag 拒绝、客户端原有全量测试及隔离浏览器详情；若中断清理仅本次夹具自有临时对象。
- Executed：三处前端强版本解析接受规范 `"v0"`，新增 `v0` 正例和 `v00` 反例；323/323 测试、typecheck/build 通过。实际隔离浏览器 Admin 列表→Member 详情/刷新均呈服务器当前 `"v0"`，普通用户列表受限；夹具 VERIFY 证实 2 项目、4 Session、1 有效成员及数据库/角色/Vault 清理 exit0。只读联调 PASS；状态按钮未提交，P05-A02-A02 仍未验。

## DEC-20260928-424 — AUT-05-A12-P05-A02-A01 实施前

- Date/WBS：2026-09-28 / Phase2 AUT-05-A12-P05-A02-A01；A12-P04前端页面合同与P05-A01后端实际Windows11状态链已通过。现有`validation/prj-05-a04-browser-project/serve.py`提供本机随机端口、只读显式平台组合、两个合成用户/临时PG，可验证浏览器匿名、普通用户和Admin详情读取；该夹具不安装User状态写路径。本项只做真实浏览器只读联调，不将其冒充启停按钮提交验收。
- Decision：在只读夹具中用合成成员和管理员分别登录，核普通用户不可读、管理员列表→详情强ETag/安全字段/刷新；不点击启停，也不创建账户。对浏览器启停写入另列P05-A02-A02，保留未验证状态。正向License仍合成，HTTP loopback不等于正式TLS/信任。
- Impact/rollback/validation：无生产代码、Schema、API、权限、依赖变化；结束向夹具发VERIFY，核PG计数与自有库/角色/Vault清理，浏览器测试标签关闭失败则记录不虚报。回滚仅停自有夹具；正式状态写浏览器证据待独立完成。

## DEC-20260928-423 — AUT-05-A12-P05-A01 实施前

- Date/WBS：2026-09-28 / Phase2 AUT-05-A12-P05-A01；A12-P04页面合同通过，冻结Auth User状态API与既有Windows11隔离Factory/PG验证脚本具备。本项仅重跑当前代码的真实ASGI/PG状态链及资源清理，作为前端页面后端依赖回归；不修改生产代码/API/Schema/权限/依赖。
- Decision：复用原`validation/aut-04-a11-p05-windows-user-state/verify.py`随机隔离库/合成License与真Scrypt链，核创建→普通用户拒绝→管理员停用/旧Session失效→启用/新Session→原Key首次重放，并核readonly/default关闭、构造失败与缺正式材料拒绝。与真实浏览器页面验收分离；本项不把合成信任或后端脚本当成UI/TLS/生产发行证明。
- Risk/rollback/validation：脚本生成临时PG库/角色及服务，结束须核自有清理；若中断外部复查精确前缀，不清未知资源。无迁移/代码回滚。验收脚本exit0与自有临时源不存在；实际浏览器交互另项追踪。
- Executed：首轮测试在连接`127.0.0.1:55432`时超时，`pg_ctl status`证实本机PostgreSQL未运行，非User状态断言失败。检视旧PID/进程及日志后，使用原Data目录/原loopback端口启动；日志记录此前非正常停机并自动恢复，`publication_%`和旧浏览器临时库catalog为0。重跑原脚本exit0：真Factory/ASGI/隔离PG/Scrypt创建、普通用户拒绝、停用旧会话401/禁登录、启用新会话200/旧仍401、原Key不可变first、readonly405/default404、构造故障与缺正式材料拒绝；原双Scope发布回归亦PASS。事后`publication_%`库0且PG仍运行。停机原因未确证，正式稳定性/浏览器页面/生产信任未因此PASS。

## DEC-20260928-422 — AUT-05-A12-P04 实施前

- Date/WBS：2026-09-28 / Phase2 AUT-05-A12-P04；Gate2冻结`AUTH_USER_GET/ENABLE/DISABLE`、CR-AUT-006及A12-P01～P03传输/响应/详情前端合同已具备。仅新增Auth User详情与启停页面、列表详情入口/路由和组件测试；不改实体、Schema、Migration、后端API/权限/依赖。
- Decision：只用服务器详情强ETag作命令版本，列表三字段只导航不作命令证明。无身份/非Admin/改密受限零详情读和零状态写；只读Admin可查看但不能提交。提交必须显式勾选目标/动作确认，调用方生成原Key且在未知结果时锁定原User/动作/If-Match/Key，禁止换动作或用新Key盲试；恢复需同Admin新鲜可写会话及显式确认。首次200是历史结果，清掉旧详情后独立GET辨当前状态；GET失败仍仅展示首次结果并标当前未核。确定版本/状态冲突清当前详情，要求重新读取；自停用后可能失去会话，只引导重新登录，不臆测Cookie。离页丢失内存原Key时提示核对审计，不承诺跨刷新自动恢复。
- Reason/impact/rollback/validation：状态管理页面要让管理员看清目标、强版本、结果与恢复边界，避免列表行直接启停和不确定提交重复变更。回滚撤页面、路由、入口及测试，无迁移；验收入口权限矩阵、详情/命令绑定、成功后当前重读、未知结果锁定与原Key恢复、确定错误清旧、XSS安全文本以及前端test/typecheck/build。真实PG/browser与正式信任另验。
- Executed：新增`/admin/users/:userId`详情与启停页面、列表详情入口；无身份/非Admin/受限零详情读/写，只读Admin可查但不能提交。当前详情强ETag+显式勾选才发命令；结果未知锁原四元组，原Key恢复成功后重读当前状态，历史first与当前显示分离。确定版本冲突清旧，credential0停用账户禁直接启用，self-disable提示最后Admin/会话风险。新增11页面场景（前端320/320、typecheck/build）；首轮测试夹具受限身份不符Session合同及选择器错误，修复后重跑；泛型异常改为结果未知并有回归。真实浏览器/PG另验。

## DEC-20260928-421 — AUT-05-A12-P03 实施前

- Date/WBS：2026-09-28 / Phase2 AUT-05-A12-P03；P01状态传输/P02安全响应通过，冻结API-02 `AUTH_USER_GET`和既有Windows显式read组合可用。列表只投影三字段，无强ETag，故原拟P03状态页面必须先拆出详情GET前置；不改变业务Scope/API，只调整内部执行顺序，页面顺延P04。
- Decision：新增Auth前端管理员User详情只读客户端，固定`GET /api/v1/admin/users/{user_id}`、同源Cookie/no-store/禁止重定向、单次超时、请求前规范UUID；仅接受安全8字段、返回ID绑定、强ETag与响应头一致、UTC有序时间，错误码仅安全文案。详情是读取时点事实，不能用列表行猜版本，也不能据详情替代写请求服务端重核。
- Impact/rollback/validation：仅前端Auth客户端/测试及进度，数据库/后端API/权限/依赖不变；撤新文件即可回滚。验收固定请求、安全投影、坏头/字段拒绝、权限/License/网络失败、前端test/typecheck/build。真实浏览器/PG留页面联调任务。
- Executed：新增User详情只读客户端及17个测试场景，安全八字段与目标/强ETag/UTC绑定，停用且credential0仅只读呈现；前端309/309、typecheck/build通过。首轮构建仅新文件ETag类型未收窄失败，修正后全套重跑通过。未本项实际浏览器/PG，下一P04页面使用该真实详情版本。

## DEC-20260928-420 — AUT-05-A12-P02 实施前

- Date/WBS：2026-09-28 / Phase2 AUT-05-A12-P02；输入冻结API-02 `AUTH_USER_ENABLE/DISABLE`、CR-AUT-006安全首次结果和P01私有状态POST。只新增Auth前端状态响应客户端/测试，不变实体、Schema/Migration、后端API/权限/依赖。
- Decision：响应只投影冻结安全8字段，强制绑定目标ID、请求动作的首次状态和If-Match版本+1、强ETag与UTC有序时间；不向前端传播密码/hash/内部撤销计数或服务端错误详情。明确状态码+错误码才归为确定拒绝，503/异常/畸形成功视为结果未知，保留调用方原目标/Key/If-Match；不据历史first推断当前状态或自行停用后当前Cookie是否已撤销。传输版边界收紧为版本必须可安全递增。
- Reason/impact/rollback/validation：后端可返回首次不可变历史，不能把它当当前GET；网络丢确认时新Key重试会改变业务。回滚撤新客户端及测试，不涉及迁移；验证安全投影、历史版、所有确定错误映射、未知结果、无写权限零网络、frontend test/typecheck/build。实际PG/browser留后续独立任务。
- Executed：新增状态响应客户端、安全8字段不可变投影、目标/动作/版本/ETag/UTC绑定与明确错误分流；新增21合同场景，前端292/292、typecheck/build通过。首轮因新客户端UUID正则少一段且返回类型未收窄失败，修正后重跑通过；P01传输版边界加拒绝MAX_SAFE_INTEGER以保证版本可递增。未本项进行真实HTTP/PG/浏览器，下一P03页面交互。

## DEC-20260928-419 — AUT-05-A12-P01 实施前

- Date/WBS：2026-09-28 / Phase2 AUT-05-A12-P01；Gate2已批准，冻结API-02 `AUTH_USER_ENABLE/DISABLE`、CR-AUT-006及Windows显式write组合已验证。仅前端Auth SessionClient增加两条固定User状态POST传输，不改生产实体、Schema、Migration、后端API/权限/依赖。
- Decision：仅接受规范非零UUID、`"vN"`强ETag、调用方原幂等Key和`enable|disable`枚举；空body且不发Content-Type，私有内存CSRF、同源Cookie/no-store/redirect-error、10秒受控超时、单次请求及Auth互斥。401清本地证明；其他状态和未知网络/超时不自动重试、不推断未执行。传输层不因self-disable的历史200盲清当前新Session，响应解释留独立客户端任务。
- Reason/impact/rollback/validation：已有后端状态命令但前端无受控写桥接；泛化任意URL/Body会扩大调用面。强版本/原Key防止非预期状态转换，服务端继续逐次重核Session/License/CSRF/权限。回滚撤方法和测试，无迁移；验证请求精确形状、无证明零请求、错误/互斥/超时/401、frontend test/typecheck/build。正式浏览器/PG、状态DTO和管理UI另验。
- Executed：新增固定启停POST传输及6项合同测试，请求不发送body/Content-Type，原Key/强If-Match/私有CSRF不出客户端，401清本地证明，超时单次停止而保留原会话。前端271/271、typecheck/build通过；未本项进行真实HTTP/PG或UI端到端，下一P02解析安全响应和确定/未知结果。

## DEC-20260928-418 — AUT-05-A11-P02 实施前

- Phase/WBS：Phase2/AUT-05-A11-P02；P01用户列表页面合同及现有Windows11隔离浏览器/PG夹具已具备。本项只运行既有两合成用户夹具，在本机浏览器验证匿名、普通用户及部署管理员的列表入口，不改生产代码/Schema/API/权限/依赖。
- Decision：以固定合成口令和临时库/角色/Vault连接验证浏览器视图；不创建真实账户、不输入用户凭据或客户资料、不将本机HTTP/合成License守卫当作正式TLS和信任验收。完成后给夹具VERIFY并核对资源删除。
- Risk/rollback/validation：浏览器会话可残留测试Cookie，夹具只使用本机随机端口且停止后失效；关闭测试页。前端页面显示、角色隔离、服务端PG Session及临时资源清理均取证；如果UI自动化不可用，记录未验而不虚报通过。无迁移；回滚为停止自有夹具和清理其自有资源。
- Executed：Windows11隔离服务在`127.0.0.1`随机端口启动；真实浏览器匿名及普通用户进入`/admin/users`均显示权限提示，合成部署管理员登录后显示两名合成用户及启用状态，刷新后列表保持。夹具收到`VERIFY`后实库核对2项目/2会话/1有效成员，停自有服务并证实临时库/角色不存在、Vault目标不存在（1168）。浏览器关闭操作被中断，未据此声称标签已关闭；本机随机端口已停止，测试Cookie不可再连接该夹具。未验正式TLS/License信任、Server2025/Debian、50+分页实际浏览器或完整UAT。

## DEC-20260928-417 — AUT-05-A11-P01 实施前

- Phase/WBS：Phase2/AUT-05-A11-P01；Gate2已批准，冻结`AUTH_USER_LIST`、后端Windows显式GET与AUT-05-A10前端候选列表客户端已具备。仅新增管理员只读用户列表页面/路由/导航，复用三字段安全候选投影；不变更实体、Schema、后端API/权限/依赖。
- Decision：同实例非受限DeploymentAdmin身份才可发同源GET，不要求CSRF；只消费服务端当前分页User投影，显示用户名/ID/启停，不显示密码、canonical、角色推断或未经服务端证明的项目归属。每次50条、显式加载更多；刷新/错误清旧页；重复ID/分页异常由客户端拒绝。页面可导航账户创建，但不将列表项升级为可任命事实；服务端仍逐页实时授权。无身份/非Admin/受限零请求。
- Reason/impact/rollback/validation：部署管理员需要浏览已建账户、核对未知创建结果，原候选控件只存在项目创建页且会话刷新后未展示管理清单。风险为过时账户状态/多页非固定快照，显式刷新及提示当前服务端结果；正式Audit核对仍需独立能力。回滚撤页面/路由/导航/测试，无迁移。验证零请求、空页、分页、错误清旧、安全投影及前端全量test/typecheck/build；本项不冒充User状态管理或真实浏览器/PG。
- Executed：新增`/admin/users`只读列表页面与入口，复用50条安全投影、显式加载更多/刷新、空页与失效清旧；只读Admin可读，非Admin/改密受限/无身份零请求。新增7页面场景，前端265测试/typecheck/build通过。未本项跑真实浏览器/PG或User编辑，下一独立浏览器只读验证。

## DEC-20260928-416 — AUT-05-A10-P04-A01 实施前

- Phase/WBS：Phase2/AUT-05-A10-P04-A01；P01～P03前端合同完成，原AUT-04-A09-P05 Windows User创建后端隔离验证已具备。此项仅加强/重跑原隔离ASGI+PG验证，让当前前端八字段/头/UTC/密码不回显合同与实际Windows显式写Factory同源；无生产实体/Schema/API/权限/依赖改动。
- Decision：复用全新唯一`publication_`临时PG/Vault合成材料，原管理员Session-CSRF创建、同Key重放/冲突、新账户登录/普通用户拒绝和readonly关闭矩阵；增加精确201八字段、ETag/Location/UTC、安全无密码与无Set-Cookie断言。退出后外部复查临时数据库前缀；不把ASGI TestClient冒充实际浏览器或TLS/正式信任。浏览器UI新凭据输入遵Computer Use规则留人工/独立安全验收，不以绕过UI规则替代。
- 风险/验证/回滚：原验证链庞大但已有历史，用少量断言防回归；任务中断需核自有库/Vault，不动生产。回滚撤新增验证断言，无迁移。验收验证脚本exit0、原矩阵、精确元数据与清理；正式trust/性能/三平台/Gate不关闭。
- Executed：原Windows User创建隔离验证增加首次201恰好八字段、ENABLED/NONE/credential1/v1、ETag/Location/no-store/无Set-Cookie、UTC时间与密码不回显、原Key重放头一致断言；实际PG/ASGI/真实Scrypt与新账户登录、普通用户拒绝、readonly405、缺正式信任拒绝链整体exit0，外部复查`publication_%`临时库0。未执行浏览器新凭据表单提交，依Computer Use安全边界留人工/独立验收；不把本项描述为实际HTTPS网络或可用包。

## DEC-20260928-415 — AUT-05-A10-P03 实施前

- Phase/WBS：Phase2/AUT-05-A10-P03；Gate2已批准，冻结`AUTH_USER_CREATE`、后端Windows显式写组合、P01传输和P02安全客户端具备。仅Auth创建账户页面/路由/导航，不改实体、Schema、后端API/权限/依赖。
- Decision：只有同实例正常DeploymentAdmin且保留内存CSRF时展示可提交表单；普通/受限/刷新只读零User创建请求。用户名和两次初始密码明确输入，确认相同后单次提交；调用`create`后立即清两项密码，不写持久存储或回显。201只展示用户名/User ID/状态，不显示初始密码，也不把新User提升Admin。未知结果锁原Admin ID/原NFC用户名/原Key，页面同账户有写状态、重输原密码且显式勾选后同Key重送；服务端验证密码一致。确定拒绝清尝试，幂等冲突停止页面内重试。刷新/离页原Key丢失须提示核对User/Audit后再操作，不自动新Key重试。
- Risk/impact/rollback/validation：密码JS内存无法承诺绝对清零，但同步清表单值并不复制到恢复状态；同Key换密码导致冲突、创建已提交而响应丢失是主要风险。测试无身份/普通/受限零请求、两次密码、原Key/用户跨状态阻断、成功无密码/不提升Admin、确定/不确定分流及前端全量test/typecheck/build；真实Windows11网络/浏览器/PG另项。回滚撤页面/路由/导航/测试，无迁移。
- Executed：新增`/admin/users/new`页面与入口，普通/受限/只读不显示写表单；输入两次密码并清空，成功仅显示User安全回执，未知结果锁原Admin/用户名/Key且重输原密码确认，确定拒绝释放尝试、幂等冲突阻断。9页面/路由场景，前端258测试/typecheck/build通过。无本项真实User写网络/浏览器/PG；下一P04。

## DEC-20260928-414 — AUT-05-A10-P02 实施前

- Phase/WBS：Phase2/AUT-05-A10-P02；Gate2已批准，输入冻结API-02 `AUTH_USER_CREATE`、CR-AUT-005实现增量及P01固定写桥接。仅Auth前端User创建DTO/响应分类，不改实体/Schema/后端API/权限/依赖。
- Decision：调用方提供原幂等Key；客户端按NFC/去边空/Unicode控制字符/显示长度做保守验证，密码仅验证UTF8 1～1024 bytes且不含NUL，规范化/大小写唯一性最终由服务端判定。单次提交后201必须核合法信封、八字段白名单、初始ENABLED/NONE/credential1/强v1、Location/ETag及请求用户名一致；不得回传密码、Hash、Cookie、内部字段。已知状态码+错误码的401/403/404/409/400/422为确定拒绝；503、断线、畸形201或未知结果均标不确定，不自行重试/改Key。客户端不持有密码；后续页面在结果不确定时清输入并要求同账户重新输入原密码，原Key原用户名锁定。
- Reason/impact/rollback/validation：服务端User创建幂等重放验证原密码，不可用普通同Key重放推断成功；需把确定/不确定结果明确交给UI，避免重复账号。前端casefold无法等价Python，拒绝自行生成canonical，保留服务端为唯一事实。风险为不同Unicode边界、未知成功、跨账号恢复；保守输入和响应核验、UI原Key流程及服务端重核。回滚撤客户端/测试，无迁移。验收白名单、密码无回显、201头/日期/状态、错误映射、单次未知、全量前端test/typecheck/build；不冒充完整UI或真实写链。
- Executed：新增`AdminUserCreateClient`，单次受控POST、NFC/展示名与密码字节预检、201初态/ETag/Location/UTC核验、八字段冻结投影、确定与不确定错误分流；不储存密码/Key且不自动重试。新增30参数化场景，前端249测试/typecheck/build通过；无本项真实浏览器/PG或后端全量，下一P03页面。

## DEC-20260928-413 — AUT-05-A10-P01 实施前

- Phase/WBS：Phase2/AUT-05-A10-P01；Gate2已批准，冻结API-02 `AUTH_USER_CREATE`、CR-AUT-005和Windows显式platform-write后端P05已具备。仅前端Auth SessionClient固定管理员User创建路径的受控传输，不变更实体/Schema/后端API/权限/依赖。
- Decision：复用现有会话客户端的私有CSRF、同源Cookie/Origin及单次写互斥语义，将固定POST `/api/v1/admin/users`作为第二条精确允许的写路径；不公开任意URL/Token/通用写入口。调用方持原幂等Key及正文并负责对未知结果同Key恢复，传输层不自动重试；401清本地身份/CSRF，503/超时/传输失败不推断提交成功。16KiB正文上限和有效Key预检，绝不记录请求正文。
- Reason/impact/rollback/validation：管理UI须创建新负责人账户，不能要求用户手工入库；密码只能经原同源受控通道，不可导入一般fetch或持久状态。风险为响应丢失后的重复创建与跨路径扩权，分别以原Key保留及精确路径/权限服务端重核控制。回滚撤本条受控方法与测试，无迁移。验证请求形状、401/超时/互斥/无CSRF零请求、全量前端test/typecheck/build；本项不称客户端解析/页面/真实写链完成。
- Executed：将原项目创建传输抽成两个精确路径的私有共用写方法，新增`postAdminUserCreate`仅`/api/v1/admin/users`、16KiB上限；CSRF仍私有，不暴露通用URL。7新参数化场景，前端219测试/typecheck/build通过；未跑本项真实User创建HTTP或页面。无Migration/后端API/依赖变化，下一P02。

## DEC-20260928-412 — PRJ-05-A05-P04-A02 实施前

- Phase/WBS：Phase2/PRJ-05-A05-P04-A02；P03前端合同及P04-A01真实HTTP/PG通过。仅扩自有Windows11隔离fixture的真实浏览器模式，使用全新临时库/角色/Vault、loopback Vite与Uvicorn，新增未归属启用合成负责人；不变更生产业务/Schema/API/权限/依赖。
- Decision：浏览器实际登录合成部署管理员，访问创建页并选择合成负责人、提交一次，观察成功回执；fixture收到核验信号后查询3项目、2有效成员、新负责人/审计/收据各1并清理。浏览器输入仅合成凭据/数据，不触碰客户资料。浏览器结果与SQL分别记录，任何UI/进程中断只记PARTIAL并精确清自有资源，不补写成功推断。
- 风险/验证/回滚：UI自动化窗口/轮次中断、临时资源残留，唯一命名、正常finally清理及外部复查；回滚撤新模式。合成License仅内部证据，正式trust/TLS/CR008/Gate3和可用包不据此关闭。
- Executed：真实IAB浏览器合成部署管理员登录、导航创建页、显示三名候选、选未归属的启用负责人、填项目并单次提交；页面显示项目创建已确认及ID。fixture接`VERIFY`后终态SQL 3项目/1会话/2有效成员、新负责人/创建审计/已完成收据各1，退出清自有库/角色/Vault。浏览器标签关闭调用被轮次中断，按Computer Use规则未再输入；随后本地PG服务异常停机，恢复时日志显示自动WAL恢复，恢复后外部前缀库/角色均0、原只读模式另轮回归exit0。该停机/恢复不影响已打印的fixture终态计数，但不能宣称浏览器标签已关闭或整个本机环境无异常。无生产代码/Schema/API变，范围仅Windows11合成。

## DEC-20260928-411 — PRJ-05-A05-P04-A01 实施前

- Phase/WBS：Phase2/PRJ-05-A05-P04-A01；P03前端合同通过，后端Project创建和Windows写工厂已有单独验证。此项仅扩原Windows11隔离PG/真实网络fixture的独立创建模式，检验页面所依赖的冻结Auth→User List→Project Create合同与SQL事实，不改业务代码/API/Schema/权限/依赖。
- Decision：新临时库/角色/Vault合成License源及本地loopback Uvicorn/代理，新增未分配启用用户。管理员真实登录后查候选，再用同Cookie/CSRF/幂等Key创建，原Key重放只落一项目一负责人一审计，异正文冲突不增写；无Cookie/普通用户拒绝。精确查询项目/成员/审计/收据并自动清理自有源。合成信任只作内部Windows11证据，不冒充正式发行。
- 风险/验证/回滚：中断可留下临时资源，使用唯一前缀和finally+外部复查；失败时不标PASS。回滚撤fixture增量，无数据迁移。下一独立真实浏览器UI链，正式trust/TLS/CR008/Gate3仍待。
- Executed：新`--create-api-only`模式真实loopback Uvicorn/代理/PG：无Cookie401、普通成员404、管理员候选200/创建201/原Key重放201/异正文409；SQL 3项目/2会话/2有效成员、新负责人仅1/创建审计仅1/已完成收据仅1，fixture退出清库/角色/Vault；外部复查前缀库/角色0。原`--api-only`只读模式另轮回归exit0并清理。测试运行环境临时venv安装正式依赖和httpx；未改生产依赖。下一真实浏览器UI，不冒充正式信任/HTTPS/Gate通过。

## DEC-20260928-410 — PRJ-05-A05-P03-A02 实施前

- Phase/WBS：Phase2/PRJ-05-A05-P03-A02；Gate2已批准，输入冻结PROJECT_CREATE、现有Session内存写桥接、项目创建客户端及P03-A01管理员用户候选GET。仅新增管理员创建页面/路由/入口，不变更实体、Schema、后端API、权限、依赖。
- Decision：页面仅在同实例已登录、非改密受限、DeploymentAdmin且有内存CSRF时加载候选和允许提交；后端仍最终授权。首负责人只能显式选择ENABLED候选，说明列表不证明未归属项目。成功仅显示创建回执，不导航管理员无权读取的项目详情。未知结果锁定原规范输入、原负责人、原管理员ID和原幂等Key；本页同账户且写状态可用后需再次确认才同Key重送，不产生新Key。确定拒绝解除恢复状态；幂等冲突停止页面内恢复。离页/刷新丢内存Key时提示核对，不自动新建。防止失效异步结果重新显示旧账户数据。
- 风险/验证/回滚：候选多页和会话切换、网络已提交但响应丢失；分页显式加载、界面请求前后核身份，确定/未知结果分流，测试无身份/非Admin/受限零请求、启停选择、原Key恢复及成功回执、UI构建。回滚撤页面/路由/导航/测试；无需迁移。实际Windows11 PG/浏览器写验收留后续独立任务，不冒充Gate3或可用包。
- Executed：新增管理员创建路由/入口/页面、启用候选选择、可选初始部门、创建成功回执与未知结果原Key/原输入恢复，冲突阻止页面重试。页面/路由新增7场景，前端212测试/typecheck/build通过。初轮3项失败为导航预期、受限会话测试样例及确认框定位，修正后全量重跑通过。未做实际PG/browser写链，下一P04。

## DEC-20260928-409 — PRJ-05-A05-P03-A01 实施前

- Phase/WBS：Phase2/PRJ-05-A05-P03-A01；输入冻结AUTH_USER_LIST、AUT-04-A07 Windows显式只读组合、PRJ-05-A05-P02创建客户端；Gate2前置满足。仅前端Auth管理员User列表GET安全投影，供后续负责人选择；无实体/Schema/后端API/权限/依赖变化。
- Decision：单次同源Cookie/no-store/无CSRF GET，固定50页、受控不透明cursor、严格信封与User ID/启停状态/名称，白名单投影。仅向页面提供启用账户候选，列表不提供当前项目归属，绝不提前宣称“可任命”；创建时后端`lock_eligible_manager`和成员唯一约束为最终事实。无身份/非Admin/受限会话在后续页面零请求，本客户端不自行授予权限。确定401/403/404安全固定提示，未知结果统一不可用；不自动翻页/重试。
- Reason/impact/rollback：避免手工UUID造成不可用表单，同时避免将账户启用等同项目资格。风险为多页候选和过时状态；页面需显式加载更多，提交失败展示服务端安全拒绝。回滚撤客户端/测试，不迁移。验收分页/游标/白名单/错误与超时单次、前端test/typecheck/build；不冒充完整选择器或创建链。
- Executed：新增管理员User列表同源单次GET、50条显式分页与opaque cursor约束、严格信封和启停/名称/ID安全投影，未知错误/超时不重试且不显示原始消息。新增32个参数化场景，前端205测试/typecheck/build通过；初次build因测试中unknown类型未收窄失败，修复并重跑通过。未接UI、未跑本项真实HTTP或PG写链；下一P03-A02。

## DEC-20260928-408 — PRJ-05-A05-P02 实施前

- Phase/WBS：Phase2/PRJ-05-A05-P02；输入冻结PROJECT_CREATE、PRJ-04-A05后端实际合同、A05-P01内存CSRF单次桥接及A01安全ProjectView。仅前端Project API DTO/解析；无Schema/后端API/权限/依赖变化，Gate2前置满足。
- Decision：调用方提供幂等Key并在重试时保留原Key/同一规范输入，Project客户端不生成Key、不自动重试。输入按服务端NFKC/去边空/长度/Unicode控制字符规则和规范UUID先校验；201必须校验JSON信封、ACTIVE/`"v0"`白名单ProjectView、请求与结果code/name、响应强ETag/Location严格匹配。401/403/404/409/422按状态码+已知错误码映射固定中文；503/传输失败/非预期状态或畸形201均视为可能已提交，抛带`uncertain`标志的安全错误而不回显原文。Auth仅提供CSRF传输，角色提示不是授权。
- Reason/impact/rollback：防重建同一客户项目、避免错误响应泄露内部内容；不改变服务端冻结合同。风险为前端误判未知结果或错误重用Key；P03页面须锁定原用户/原规范正文/原Key并显式恢复，跨账户不可重试。回滚撤Project客户端与测试；无数据迁移。验收严格白名单、合同头/错误映射/零自动重试、前端全量test/typecheck/build；本项不标UI/实际写HTTP通过。
- Executed：Project客户端白名单/本地规范化/201强ETag与Location/安全拒绝及未知结果分类、原调用方Key单次提交；26参数化场景，前端173/typecheck/build通过。有效只读会话零写测试经修正重跑。无页面或真实PG写证明，下一P03。

## DEC-20260928-407 — PRJ-05-A05-P01 实施前

- Phase/WBS：Phase2/PRJ-05-A05-P01；输入冻结PROJECT_CREATE、原Auth仅内存CSRF/HttpOnly Cookie及PRJ-04-A05后端写组合，Gate2前置满足。前端Auth写传输桥接是项目创建客户端的必要前置；无实体/Schema/API/服务端权限/依赖变化。
- Decision：在SessionClient增加仅接受现有`POST /api/v1/projects`的受控单次JSON提交方法，CSRF始终由会话客户端注入且不公开getter，使用同源Cookie、no-store、禁止重定向、原调用方幂等键、互斥和超时。请求返回原Response供后续Project模块白名单解析；401清本地身份/CSRF，其他结果不推断服务端提交成功、不自动重试，维持同账户原Key恢复能力。刷新后无CSRF立即拒绝，服务器仍负责Admin/License/Manager授权。后续需要其他写路径时逐项扩受控路径，不能暗中开放任意URL。
- Reason/impact/rollback：不把CSRF复制到页面或持久存储，也不把Auth摘要当授权；会话客户端仅耦合冻结路径，不依赖Project实体。风险为网络未知结果与后续页面误换Key，留P02/P03按原Key恢复；回滚撤桥接/测试，不迁移数据。验收同源请求形状、受限只读零请求、busy互斥、401清状态、超时无重试、前端全量test/typecheck/build。
- Executed：固定路径单次POST、不公开CSRF、原Key和互斥/超时/401清状态实现；8新场景，前端147测试/typecheck/build PASS。未接Project DTO/UI或跑真实写HTTP，不宣称创建可用。

## DEC-20260928-406

- PRJ-05-A04-P02：原浏览器fixture被轮次切换中断，浏览器行为证据保留而终态SQL缺失。选择在同一独立验证脚本增加`--api-only`自动退出模式，以新临时库做真实HTTP原始状态码/SQL精确计数/自动收尾；两轮证据分开说明，不伪造为同一次运行。无生产/API/Schema/权限/依赖变更，回滚撤该验证分支；风险是合成License不等于正式发行。
- Executed：无Cookie401、成员列表/详情200/外项目404、管理员空列表200/项目404；2项目/2Session/1有效成员终态SQL、脚本exit0自动清理且外部复查库/角色0、无Test Vault凭据。加原真实浏览器证据，A04仅Windows11合成范围PASS，Gate3/正式信任不据此关闭。

## DEC-20260928-405

- PRJ-05-A04实施前：以新的独立临时PG/角色/Vault、Windows显式只读平台组合与真实IAB测项目UI；仅合成License/游标签名供验证，不改变生产信任。按固定成员/管理员和两项目矩阵检查列表/详情、跨项目统一拒绝和空授权。风险是交互进程打断导致自有资源残留；精确命名、完成后核对与清理。无Schema/API/权限/依赖变更，详见进度。
- Executed partial：成员列表/详情、外项目统一拒绝、管理员空列表与页面退出已在实际Windows11浏览器观察；浏览器关闭操作中断后fixture句柄消失，终态SQL断言未执行。PostgreSQL恢复后精确清残留自有库/角色/Vault并复查为0。A04保持PARTIAL，不标整体PASS；下一P02补终态计数/HTTP证据。

## DEC-20260928-404

- PRJ-05-A03实施前：详情页只从URL取得规范ID并调用现有PROJECT_GET，绝不使用Auth摘要或列表项作为授权；客户端已核ID/强ETag，页面路由代次清旧内容并忽略晚到结果。无身份/受限零请求，无权/不存在共用404。仅前端路由/页面，无Schema/API/权限/依赖变化，风险/回滚/验收见进度。
- Executed：8新页面测试，前端139/typecheck/build通过；真实浏览器/PG未运行，不宣称端到端或Gate3通过，下一 PRJ-05-A04 联调。

## DEC-20260928-403

- PRJ-05-A02实施前：选择独立 `/projects` 只读列表页，以 AppShell 原 SessionClient 的内存身份作为发起条件，实际项目展示仅接实时 PROJECT_LIST；不从 Auth 授权摘要生成项目卡片，也不在该页自动 GET Session 恢复写权限。受限改密/无身份零项目请求；读错误清空旧列表。无 API/Schema/权限/依赖变化、无 CR；风险/回滚/验收详见进度。
- Executed：7新页面/跨路由测试，前端131/typecheck/build通过；Auth摘要有项目而服务端返回空页时页面保持空。真实浏览器/PG/正式信任未跑，本项只标页面合同通过，下一 PRJ-05-A03 详情。

## DEC-20260928-402

- PRJ-05-A01 实施前：冻结 PROJECT_LIST/GET 已由后端 Windows 显式组合提供，前端缺只读传输合同。选择 Project 模块独立客户端与白名单 DTO，不触碰 Auth/后端/Schema；列表遵守当前单项目上限，详情严格核对请求 ID 与强 ETag。服务端 Session/License/成员授权是唯一权限来源，管理员身份不等同项目可见权。风险/回滚与验收见进度，不新增 CR 或改写冻结合同。
- Executed：37 新项目客户端测试；前端 123/123、typecheck/build 最终通过。首次测试/类型检查失败为测试代码问题，修正后重跑；没有页面或本项真实浏览器/PG，不宣称项目入口可用或 Gate 通过。无 Migration/API/权限/依赖变化，下一 PRJ-05-A02。

## DEC-20260928-401

- AUT05A09实施前：登录页局部SessionClient随路由卸载丢内存CSRF，不能支持后续项目页连续交互。选AppShell实例级provide唯一客户端、LoginView注入并`toRaw`，保测试prop覆盖；新AppShell/刷新生成新客户端且不自动恢复写权限。仅内部前端状态生命周期，不改服务器Cookie/CSRF、API/权限/依赖。风险/回滚/测试见进度。
- Executed：新Auth InjectionKey/AppShell提供及LoginView重入读取，跨路由同实例身份/写状态保留、重建实例无状态且无自动GET；前端86测试/typecheck/build通过。无Migration/API/依赖或服务端授权变，真实浏览器/PG本项未跑，下一项目入口独立接线。

## DEC-20260928-400

- AUT05A08-P02实施前：后端改密成功撤销旧Session，503可能已提交。登录页只以服务器200视为成功；不确定时保原Key和UserID于组件内存、清全部密码/会话展示，同一用户重新登录后明确确认原两密码才可用原Key重送。异用户与409停止页面重试，刷新丢Key建议管理员核对。受限/普通都可用，刷新只读不可改，安全/回滚/验收详见进度；无API/Schema/权限扩张。
- Executed：前端85测试/typecheck/build通过；原Windows真实PG写工厂改密与旧Session401/新密码200/提交后503同Key恢复exit0，`publication_%`自有临时库count0。首次旧页面断言失败已更新重跑。computer-use Skill要求最终改密提交由用户接管，故未代点浏览器提交、不宣称浏览器端到端或Gate通过；记录为内部合成PASS/浏览器手动验收待办并继续独立任务。

## DEC-20260928-399

- AUT05A08-P01实施前：现有后端`AUTH_PASSWORD_CHANGE`已在Windows显式write组合，前端无客户端/页面。选在原SessionClient增加调用方提供幂等键的单次同源改密方法；本方法不产生新会话、不自动重试或持久保存秘密，不确定结果清本地状态，页面恢复另列P02。输入/错误/返回严格按既有增量合同，风险/回滚/验收见进度；不改冻结API、Schema、后端或权限。
- Executed：新增`changePassword`与固定409/422安全映射、严格UTF8/Key和版本投影，普通/受限两路径及失败/只读/坏响应14新测试；前端80测试、typecheck/build最终通过。首次类型检查因测试unknown收窄失败，已修正重跑；无实际浏览器/PG改密证明，下一P02页面与端到端。

## DEC-20260928-398

- AUT05A07按A05真实截图单独修页头两个导航项相邻问题，仅专属nav Flex间距/换行，不改认证/路由/API。Windows11浏览器桌面与360px视口、无水平溢出及Tab可见焦点验证，前端66/typecheck/build通过。自有临时Vite/浏览器已关闭；后端未运行显示不可用只反映测试环境，完整登录链以A05为准。无Migration/依赖，正式移动设备及全UAT/Gate/包待。

## DEC-20260928-397

- AUT05A06实施前：冻结API时间为RFC3339 UTC `Z`，A05真实PG/浏览器发现会话GET/续期可返回`+08:00`；三个Auth HTTP响应均直接`isoformat()`。依持续授权登记`CR-AUT-009`，选只在Auth响应投影统一UTC，不改变时刻/Session数据或冻结字段。naive拒绝、正负offset/真实PG及原安全链回归，兼容/风险/回滚见CR；实施和测试结果随后补记。
- Executed：三响应共享严格UTC formatter；15关联测试、1558全量无失败/2既有跳过，原9GET/12POST真实PG网络链与新UTC断言通过，自有源清理、开发wheel通过。无Migration/API字段/权限/依赖变，Gate3/完整包/正式HTTPS及三平台不据此通过。

## DEC-20260928-396

- Executed：AUT05A05 首轮浏览器暴露原生fetch receiver错误与PG时间偏移响应被客户端拒绝。前者改无receiver调用，后者仅接受严格显式RFC3339 offset并归一化为UTC，保持日历/期限校验；增添对应单测。原API/Schema/权限/依赖不变。首轮不合格与运行器/超时再启情况留在进度记录。
- 新独立合成浏览器完成错密码、三次登录、一次续期、两次退出、刷新后只读重登；实际PG审计计数4/3/1/2及2收据准确通过，临时库/角色/Vault清理通过。仅Windows11/loopback开发代理，服务端UTC输出一致性、页头布局及正式HTTPS/信任/Gate/包仍待，下一独立任务处理。

## DEC-20260927-395

- 2026-09-27 Phase2/AUT05A05实施前：独立真实临时PG/Vault/User browser fixture+原Uvicorn/Vite/Client页面，UI工具按computer-use skill，合成固定密码仅自有loopback，不保存密码。原21请求fixture与计数不动。
- 按预定浏览器操作验精确4Session/3issued/1renewed/2revoked，旧重登录Session未自动撤销如实记录，不放宽原服务语义。原API/Schema/依赖不变；900秒有界等待/自有进程及源清理，风险/回滚见browser-login进度，真实TLS/生产/Gate/包待。

## DEC-20260927-394

- Executed：原真实PG/Vault/Windows工厂2context已走Uvicorn/Vite/httpx，9GET/12POST及原登录/旋转/退出/重放竞争/审计计数全通过，响应无CORS；自有服务终止、库/角色count0与Vault不存在1168额外核查。最终网络exit0/前端63/typecheck/build通过，无真实浏览器/HTTPS/全应用证明；无生产/API/Migration/依赖变化，下一独立浏览器A05，CR008/Gate/包待。

- 2026-09-27/Phase2 AUT05A04实施前：只适配原真实临时PG/Vault Login fixture走Uvicorn/Vite/httpx网络，无mock成功SQL/Service。固定本轮允许的实际Vite Origin及正向localhost映射显式记录，恶意来源保留；仅测试target改自有端口，生产不变。
- 原default404/登录/会话/旋转/撤销/重放竞争/审计计数与cleanup保持；自有服务必须停止后清临时源，异常安全退出。编码前风险/回滚/验收见network-login进度；无API/Schema/依赖变，真实浏览器/正式trust/Gate/包待。

## DEC-20260927-393

- Executed：真实Vite/原OriginPolicy网络6请求及合成Cookie/CSRF/Key/body保留、无rewrite/CORS通过exit0；完整前端63/typecheck/build通过。首次Windows ESM路径与默认Vite CORS失败记录后修复，显式cors:false仅开发收紧，不改后端。无PG登录/真实浏览器证明，下一A04真实工厂网络链；无Migration/API/依赖，Gate/包待。

- 2026-09-27/Phase2 AUT05A03实施前：固定Vite /api/v1→127.0.0.1:8000、保Host/Origin/Cookie/CSRF/Key，原健康代理保留。真实网络自有端口探针使用原LoginOriginPolicy，只来源门验证不造登录成功；测试target临时覆盖明示。无CORS/后端可信源自动配置/依赖/API/DB变化。
- 前置/风险/验收/回滚见same-origin-proxy progress，正式服务须显式允许浏览器端口Origin，端口冲突不杀用户服务。下一实际PG与浏览器，性能FAIL/Gate/包保持。

## DEC-20260927-392

- Executed：/login中文页面/导航接实际Client，新增11用例，最终63/63/typecheck/build通过，36modules/JS100160/CSS4124；初轮5Vue代理private-brand失败修复toRaw后完整复验，保留诊断。无后端/API/Schema/依赖变化；真实浏览器/服务器/改密未验，下一A03同源Origin/Host代理前置，CR008 FAIL/Gate/包待。

- 2026-09-27 Phase2/AUT05A02实施前：Auth中文登录/当前身份页面，只接原Client及导航，不顺改后端/Origin/API。编码前/风险/回滚见login-page progress。
- 单提交、操作开始清密码、卸载丢弃响应；显式查询恢复只读提示重登、受限身份提示改密尚待。Client不作为授权，失败不冒充服务器退出。无Migration/依赖，实际浏览器/后端链另验。

## DEC-20260927-391

- Executed：新增43客户端契约用例，完整前端52/52/typecheck/build通过；Cookie同源、CSRF私有内存、受限/DTO、renew同User、原Key logout、错误/超时/互斥/无重试。GET只读恢复需重登写；尚未接页面且build未包含client，不是实际服务器/浏览器PASS。无后端/Migration/API/依赖变化，下一AUT05A02页面，性能/正式trust/Gate/包待。

- 2026-09-27 / Phase2 AUT-05-A01，实施前记录；仅既有Auth四接口Web客户端，不跨模块写数据，不含页面/管理/改密。本次Scope来自Phase2 Auth/SYS001，前置见session-client progress。
- 同源Cookie自动携带，CSRF私有内存，strict受限/DTO与安全错误，客户端不是授权边界；单实例请求互斥/有界超时/不自动重试。失败清本地身份但不宣称服务器撤销。
- GET无CSRF：刷新恢复只读身份，不伪造Token或浏览器持久化，写操作要求再次login；若未来免重登需另CR，不偷改冻结GET。无Migration/API/依赖/安全机制改变，正式trust/性能/Gate/包待。

## DEC-20260927-390

- Executed：四批各20请求/40真实KDF及20结果真验证，peak16/end0；串行P951672.890/1521.531ms，并行1275.076/1262.386ms。诊断exit0，不含HTTP/history，未达1秒，不接并行候选。完整unit/集成/coverage/wheel未重跑，生产不变；保CR008 FAIL，转同PhaseWeb登录客户端合同前置。
- Phase2 / AUT-04-A12-P08-A01；日期2026-09-27；实施前记录，状态EXECUTED。
- 读取完整CR008/实际profiler/Service共享lease与固定Scrypt；只做20请求双计算串行/并行固定16实际KDF上限的合成成本诊断。无API/Schema/权限/安全机制/依赖/生产配置变化。
- 原默认4不变，不用每请求16slot内再双线程造成32计算；本线程获取释放，全部计算结束后再擦除合成缓冲。不持久化秘密或外发。
- 风险/回滚/验收先记录于docs/progress/aut-04-a12-p08-a01-kdf-pair-design.md；诊断不是HTTP PASS，CR008/性能FAIL/Gate保留。测量后决定候选是否值得正式接线，避免无限slots调参。

## DEC-20260927-389

- Executed：2新增方法、1553unit无失败/2跳过，真实Windows登录链通过exit0；工厂364/369行98.645%、10/10分支100%，两前置guard覆盖、五CLI行未验保留，分母不变。新rawa30daa7e…旧5e9391c0…未变，完整19链Auth coverage/性能/wheel未重跑，无生产变更。下一P08A01 CR008固定KDF/同步V1性能设计，不降门槛或重复无改动压测，Gate/包待。

- Phase2/P07A41编码前检查见factory-preconditions；两个已识别前置guard测试，三工厂错误配置不读凭据，真实空Alembic目录head None不入UOW；不mock成功SQL或head。完整unit/Windows登录链factory独立coverage。
- 无生产/Migration/API/权限/依赖变，无升级，不代供正式信任；完整19链Auth coverage/性能/wheel另项，后继续CR008，Gate/包待。

## DEC-20260927-388

- Executed：1551unit无失败/2跳过、19实际链全通过，完整Auth3300/3382行97.575%、890/988分支90.081%，门槛通过/exit0但不等于所有安全/生产/Gate通过。行分母+3仅UserList布局、分支988不变，密码91.146%保持，Windows factory8/10未达另列。新raw5e9391c0…旧c5cc7625…未变；性能/wheel未跑，下一A41工厂两个前置失败关闭，Gate/包待。

- Phase2/P07A40编码前检查见bootstrap-coverage；完整unit+19实际链，全部Auth/密码/factory分列90%不变，独立runtime保旧raw，分母变化标注仅三UserList布局；不将安全本项当完整Gate/包完成。
- 无生产/Migration/API/权限/依赖变，无升级；性能/wheel另项，正式trust/CR008 FAIL/Gate/包待。

## DEC-20260927-387

- Executed：3新增方法，1551unit21.690秒无失败/errors0/2跳过；原临时PG初始化Audit失败User0、并发一Admin/一Audit/真实scrypt通过exit0并清理资源。无成功SQL模拟/正式账户/生产变化，不把count当九表证据；完整coverage/性能/wheel未跑，下一A40完整19链覆盖，Gate/包待。

- Phase2/P07A39编码前检查见initial-admin-source；Repo来源防御/真实inactive合同+原自建临时PG初始化回归，证据范围保持（失败User count不冒充九表全行），不创建正式账户。
- 无生产/Migration/API/权限/依赖变，无升级；完整unit跑，完整19链coverage/性能/wheel另项，保raw/90%，Gate/包待。

## DEC-20260927-386

- Executed：新增7方法，1548unit21.805秒无失败/errors0/2跳过、exit0；输入/UTF8字符/claim/Hash来源/底层错误拒绝，密码擦除/UOW退出/noCommit及Memoryview release通过。无正式账户创建或生产变更，完整coverage/性能/wheel未跑，下一A39初始管理员DB适配来源与原临时库验证，Gate/包待。

- Phase2/P07A38编码前检查见initial-admin-defensive；只内部Service合同/密码擦除，正式用户口令不代供给，底层RuntimeError沿原传播不假称统一固定码，Mock Port不冒充SQL。
- 无生产/Migration/API/权限/依赖变，无升级；完整unit跑，实际初始管理员来源另项，完整coverage/性能/wheel另项，Gate/包待。

## DEC-20260927-385

- Executed：七实际投影/同UOW当前改名禁用/真实22P02与22012→25P02通过exit0，九表回滚/健康重读及原发布回归通过。None不匹配、有效UUID字符串PG转换如实记录，不假称适配层校验/权限。无生产变化，unit1541本批未跑，coverage/性能/wheel未跑，下一A38初始管理员Service防御，Gate/包待。

- Phase2/P07A37编码前检查见member-names-source；真实名称投影/当前变化/缺行与非法编号SQL行为，不添加适配层权限或静默过滤；九表回滚/真实22012→25P02、健康重读。
- 无生产/Migration/API/权限/依赖变，无升级；unit1541本批不跑，完整coverage/性能/wheel另项，Gate/包待。

## DEC-20260927-384

- Executed：新增3方法，1541unit21.763秒无失败/errors0/2跳过、exit0；错误/真实inactive来源、缺来源原AttributeError与真实active无bind空tuple通过，无成功SQL模拟/生产变更。17链coverage/性能/wheel未跑，下一A37真实名称/缺行/非法编号行为，Gate/包待。

- Phase2/P07A36编码前检查见member-names-defensive；修正计划假设：适配层仅授权后最小名称投影、不承诺非法编号校验，不加新权限/静默过滤。测试原事务来源、真实inactive与active空tuple。
- 无生产/Migration/API/权限/依赖变，无升级；完整unit跑，真实名称/非法编号SQL另A37，17链coverage/性能/wheel另项，Gate/包待。

## DEC-20260927-383

- Executed：对4e2459e AST相等，1538unit无失败/2跳过、Windows实际列表链通过exit0，文件57/57行18/18分支；相对A32行分母+3/分支不变，改善含A33新增拒绝1边、本次映射3边。新rawc0963741…旧c5cc7625…未变，完整17链coverage/性能/wheel未跑，不推算全Auth。下一A36项目成员名称Auth来源，Gate/包待。

- Phase2/P07A35编码前检查见list-layout；仅三已审计guard等价分行，对原4e2459e AST相等，完整unit/Windows实际列表链与独立文件coverage实跑，保旧raw/90%，布局统计不冒充新用例。
- 无Migration/API/权限/依赖变，无升级；完整17链coverage/性能/wheel另项，Gate/包待。

## DEC-20260927-382

- Executed：三方法coverage/trace两轮3/3通过，guard57/59/61异常4/1/1次，实际拒绝到UOW55，原到68统计仍缺；noCommit/事务退出通过，仅三边不泛化其他缺口，无生产变更。完整1538/17链coverage/性能/wheel未跑，下一A35三guard等价分行，Gate/包待。

- Phase2/P07A34编码前检查见list-branch-audit；仅UserList三个异常坐标独立coverage/trace，noCommit/事务退出，保旧raw/90%不收秘密，不先认定统计问题。
- 无生产/Migration/API/权限/依赖变，无升级；完整1538/17链coverage/性能/wheel另项，Gate/包待。

## DEC-20260927-381

- Executed：新增6参数化方法，完整1538unit21.806秒无失败/errors0/2跳过、exit0；依赖/clock/篡改Query-Page/首末License/Access-UOW拒绝，noCommit/已入事务闭合，仅Port证据。无生产变更，17链coverage/性能/wheel未跑，下一A34三异常坐标audit，Gate/包待。

- Phase2/P07A33编码前检查见user-list-defensive；仅UserList依赖/clock/Query-Page来源/首末License/Access-UOW拒绝，固定码/noCommit/已入事务闭合。mock Port不冒充SQL，异常坐标后逐边审计。
- 无生产/Migration/API/权限/依赖变，无升级；完整unit实际跑，17链coverage/性能/wheel另项，原raw/90%保持，Gate/包待。

## DEC-20260927-380

- Executed：1532unit无失败/2跳过，17实际链全通过；完整Auth3260/3379行96.478%、876/988分支88.664%，门槛未达/exit1。行分母+15仅已记录布局、分支988不变，变化含实际补测/链及统计映射。密码91.146%保持、factory另列，新rawc5cc7625…旧18ef6f24…未变；性能/wheel未跑，下一A33 UserList，Gate/包待。

- Phase2/P07A32编码前检查见source-coverage；完整unit+17实际链，原完整Auth/密码/factory分列，90%不变，布局分母变化如实标注，新runtime保旧raw，不泛化功能PASS为Gate。
- 无生产/Migration/API/权限/依赖变，无升级；性能/wheel另项，正式trust/CR008 FAIL/Gate/包待。

## DEC-20260927-379

- Executed：正常实际身份读取及7拒绝（6None、1 SQL22012→25P02）通过exit0，九表回滚/健康重读及原发布回归通过；无生产变更、不冒充Project权限或正式trust。unit1532本批未跑，完整coverage/性能/wheel未跑，下一A32完整17链覆盖，Gate/包待。

- Phase2/P07A31编码前检查见project-read-source；真实临时PG正常当前uid、六None拒绝及一SQL22012→25P02原异常，九表回滚/健康重读；不mock成功SQL/停约束或扩Project权限。
- 无生产/Migration/API/权限/依赖变，无升级；unit1532本批不重跑，完整coverage/性能/wheel另项，下一17链完整复验，Gate/包待。

## DEC-20260927-378

- Executed：新增4方法、7token/5time/3Session/3缺来源拒绝，完整1532unit21.810秒无失败/errors0/2跳过、exit0；真实inactive不启动事务、原AttributeError保持，无成功SQL模拟/生产变更。coverage/实际链/性能/wheel未跑，下一A31真实数据库来源，Gate/包待。

- Phase2/P07A30编码前检查见project-read-defensive；非法token/time前来源拒绝、真实inactive Session不启动事务，缺session保持原AttributeError，不静默统一异常或更改datetime子类型合同。
- 无生产/Migration/API/权限/依赖变化，无升级；完整unit实际跑，真实数据库另A31、coverage/性能/wheel另项，Gate/包待。

## DEC-20260927-377

- Executed：真实有效读取与8拒绝（7返回None、1 SQL22012→25P02原异常）通过exit0，九表全行回滚/健康重读及原发布回归通过；临时库/合成来源，无生产变更，不称Review全流程通过。unit1528本批未跑，完整coverage/性能/wheel未跑，下一A30 ProjectReadAccess，Gate/包待。

- Phase2/P07A29编码前检查见review-access-source；实际临时PG当前用户/会话/CSRF、七拒绝场景和真实SQL22012后25P02传播，九表回滚与正常恢复读取；不mock成功SQL/停约束/改生产。
- 无Migration/API/权限/依赖变，无升级；unit1528本项不重跑，完整coverage/性能/wheel另项，Gate/包待。

## DEC-20260927-376

- Executed：新增3参数化方法，14个token-CSRF/5个time/5个事务来源拒绝通过，完整1528unit21.638秒无失败/errors0/2跳过、exit0；无成功SQL模拟、无生产变更。coverage/15链/性能/wheel未跑，下一A29实际数据库来源，Gate/包待。

- Phase2/P07A28编码前检查见review-access-defensive；仅Auth评审启动来源非法输入与真实inactive Session防御测试，不mock成功SQL，当前用户/CSRF实际SQL另A29。
- 无生产/Migration/API/权限/依赖变，无升级；完整unit实际跑，coverage/15链/性能/wheel另项，保旧raw/90%，Gate/包待。

## DEC-20260927-375

- Executed：对be1d88f AST完全相等，1525unit无失败/2跳过、真实状态final来源/回滚及原发布链通过exit0。文件108/108行38/38分支，行分母+4/分支不变；相对旧33/38改善含A26新行为1边与本次布局映射4边。新raw0d251b1c…旧18ef6f24…未变，完整15链coverage/性能/wheel未跑，不推算全Auth；下一A28 ReviewStartAccess合同，Gate/包待。

- Phase2/P07A27编码前检查见state-layout；仅四已审计guard raise分行，对原be1d88f AST等价，完整unit及实际状态final来源链实跑；布局统计不冒充新增用例，保旧raw/90%。
- 无Migration/API/权限/算法/依赖变，无升级，可撤布局；完整15链coverage/性能/wheel另项，Gate/包待。

## DEC-20260927-374

- Executed：新增1参数化方法三错误View，完整1525unit21.837秒无失败/errors0/2跳过；五方法coverage/trace两轮5/5通过，42→50新增真实拒绝已覆盖，其余四坐标拒绝已触发仍统计缺失。新rawe0a7580b…旧18ef6f24…未变，无生产变更，完整15链coverage/性能/wheel未跑，不推算完整Auth。下一A27四guard独立布局验收，Gate/包待。

- Phase2/P07A26编码前检查见state-branch-audit；五边中ActorProof.user_view类型无直接拒绝用例，补单一合同；其余边逐一实际coverage/trace，不先假定布局问题。
- 无生产/Migration/API/权限/依赖变，无升级；完整unit运行，完整15链coverage/性能/wheel另项，保旧raw/90%，Gate/包待。

## DEC-20260927-373

- Executed：对f936ff0 AST相等，1524unit无失败/errors0/2跳过，Windows实际详情链通过exit0。文件61/61行、20/20分支，原56/56/15/20，行分母+5/分支不变，布局映射改善非新增用例。新raw40f6e859…旧18ef6f24…未变。完整15链coverage/性能/wheel未跑，下一A26 UserState异常坐标核查，Gate/包待。

- Phase2/P07A25编码前检查见read-layout；仅A24已证实的五guard分行，原f936ff0 AST完全相同，完整unit及Windows真实详情链独立测量；统计映射改善不冒充新行为。
- 无Migration/API/权限/依赖变，无升级；可撤布局，保旧raw/90%，完整15链coverage/性能/wheel另项，Gate/包待。

## DEC-20260927-372

- Executed：三个方法coverage/独立trace两轮3/3通过，guard62/64/66/67/69异常4/3/1/1/1，实际到UOW60、到72统计坐标仍缺；noCommit/UOW退出通过。仅五边证据，不泛化其他缺口。无生产变化，下一A25五guard AST等价分行与完整unit/真实详情链，Gate/包待。

- Phase2/P07A24编码前检查见read-branch-audit；逐边核对UserRead五缺失异常坐标，三个既有方法独立coverage/trace、noCommit/UOW退出，不收私有数据，不套用旧布局结论。
- 无生产/Migration/API/权限/依赖变化，无升级；完整unit/15链coverage/性能/wheel另项，旧raw与90%保持，Gate/包待。

## DEC-20260927-371

- Executed：六guard仅分行，对eeb6558 AST完全相等；完整1524unit无失败/2跳过、实际创建来源/原发布链通过exit0。文件108/108行、30/30分支100%，原102/102、24/30，行分母+6/分支分母不变；统计映射改善而非新增用例。新raw81ad2ba3…、旧18ef6f24…未变。完整15链coverage/性能/wheel未跑、不推算完整Auth；下一A24 UserRead逐边核查，Gate/包待。

- Phase2/P07A23编码前检查见create-layout；A22证据后仅六guard raise独立行，原eeb6558 AST无位置完全相等、完整unit与实际创建来源链验证；新runtime，布局统计改善不冒充新增行为用例，不排除其他缺口或降低门槛。
- 无Schema/API/权限/算法/依赖变，无升级；可撤布局，冻结历史保留；完整15链覆盖/性能/wheel另项，Gate/可用包待。

## DEC-20260927-370

- Executed：四方法分别coverage/独立trace两轮4/4通过；六个guard异常真实触发（63/65/74/75/84各1、88对应raise89共4），原六个到94坐标仍缺。前五实际到UOW54、88实际到raise89，不能泛化所有缺口或关闭门槛。下一A23仅六guard AST等价分行独立验收；本项无生产变化，完整unit/15链/性能/wheel未重跑。

- Phase2/P07A22编码前检查见create-branch-audit；逐边核对ManagedUserCreate六个A21缺失坐标，四个现有unit方法在coverage/独立sys.settrace执行，禁止收秘密或套用旧单例结论。
- 无生产/Schema/API/依赖变，无升级，原raw/90%保持；不把审计当完整安全/Gate通过。后续有证据再决定独立修复或补测。

## DEC-20260927-369

- Executed：1524unit无失败/2既有跳过、15实际链全通过。完整Auth3232/3364行96.076%、852/988分支86.235%，90%分支未达/exit1；密码98.472%/91.146%保持、factory另列，范围/分母不改。新raw18ef6f24…、旧7d6fbfc0…重验未变。无生产变更，性能/wheel未跑；下一A22实际异常路径坐标核查，Gate/包待。

- Phase2/P07A21编码前检查见name-coverage；完整unit/contract与15实际链，新runtime保旧raw，完整Auth行/分支各90%及分母不改，密码/factory另列。不把单项PASS当Gate关闭。
- 无生产/Migration/API/权限/依赖变，无升级；性能/wheel不跑，正式trust/CR008 FAIL/Gate/可用包待。

## DEC-20260927-368

- Executed：修正后完整实际PG六场景及原名称/发布回归通过exit0；缺行/当前源/最大版本/重复/真实23514/时间倒退拒绝，九表退出回滚，TEST_ONLY约束确认撤销。无生产变化；unit1524本项未重跑，coverage/性能/wheel未跑，下一A21完整覆盖，Gate/可用包待。

- 验证计划修正：首轮exit1为脚本外键假设错误，非生产故障；updated_by无FK，账号授权由上层负责。改为临时未提交UOW增加TEST_ONLY检查约束产生真实23514，保留既有约束，退出撤销DDL与故障数据，完整重跑。

- Phase2/P07A20P02编码前检查见name-database-source；仅临时PG名称Repository实际缺行/错配/最大版本/唯一与其他IntegrityError/时间倒退和退出回滚。保留约束，不mock成功SQL。先记录后执行。
- 无生产/Migration/API/权限/依赖变，无升级；仅自建临时库合成数据，未提交故障回滚并九表比对，原名称修改回归；coverage/性能/wheel另项，Gate/可用包待。

## DEC-20260927-367

- Executed：新增4项参数化测试，完整1524unit/contract无失败/errors0/2既有跳过，21.643秒、exit0。前SQL非法来源拒绝、真实inactive Session与底层异常传播通过；未模拟成功SQL。生产/Migration/API/依赖无变；coverage/14PG/wheel/性能未跑，下一A20-P02实际数据库验证，Gate/可用包未通过。

- Phase2/P07A20P01编码前检查见name-adapter-defensive；仅名称Repo ID/version/Canonical来源前SQL拒绝、真实inactive事务与底层异常原传播；Domain错误不冒充Repo转换固定码、不mock成功SQL。真实缺行/原normalized/maxversion/IntegrityError另P02。
- 无生产/Schema/API/权限/算法/依赖变，撤测试无升级；完整unit实跑，coverage/14PG/wheel/性能未跑，旧84.717%/raw/90%与Gate/包缺项保持。

## DEC-20260927-366

- Executed：6新增方法，完整1520unit/contract无失败/errors0/2既有跳过、exit0；三依赖/六正文/两Unicode/两client/四Service/三投影故障拒绝，直接已分配buffer及Service attempt密码均清零，无Cookie/Token/私有详情。通用异常原500合同保持，不冒充SQL/Session回滚；生产无变，coverage/14PG/wheel/性能未跑，旧84.717%与Hash保留。下一独立User name patch Repo，Gate/包待。

- Phase2/P07A19编码前检查见login-http-defensive；仅Login HTTP依赖/正文/Unicode/client/Service/投影拒绝和bytearray擦除，限定ASGI client输入与Mock Port，不模拟SQL；通用异常沿原SYSTEM_INTERNAL合同，不改生产或权限机制。
- 无Schema/API/算法/依赖变，撤测试无升级；完整unit/contract实际跑，coverage/14PG/wheel/性能未跑，旧84.717%/raw/90%保持，正式trust/Gate/包待。

## DEC-20260927-365

- Executed：6新增方法，1514unit/contract无失败/errors0/2既有跳过、exit0；四依赖/五clock/三Query/六View/首末License/三Access-UOW故障拒绝，无commit/已进UOW退出，仅Port证据。无生产变化，coverage/14PG/wheel/性能未跑，原84.717%与Hash保持。下一独立Login HTTP输入/来源拒绝，完整安全/正式trust/Gate/包待。

- Phase2/P07A18编码前检查见user-read-defensive；仅User读取Service依赖/clock/篡改Query/View/首末License/Access及UOW异常拒绝，无commit/已进UOW闭合，Mock仅Port不冒充SQL授权或回滚。
- 无生产/Schema/API/权限/算法/依赖变，撤测试无升级；完整unit实际跑，coverage/14PG/wheel/性能未跑，旧84.717%/Hash/90%保留，正式trust/Gate/可用包待。

## DEC-20260927-364

- Executed：7新增参数化方法，1508unit/contract无失败/errors0/2既有跳过、exit0；三router八依赖、GET四/renew十一/logout七故障安全响应，固定error+trace、无Set-Cookie/Token/私有详情，renew前拒绝不rotate。仅Port合同不冒充PG/TLS，生产无变，coverage/14PG/wheel/性能未跑，原84.717%与Hash保持；下一独立User read Service，完整安全/Gate/包待。

- Phase2/P07A17编码前检查见session-http-defensive；仅GET/renew/logout依赖/Port异常/投影错配/非True/logout错误固定合同与无Set-Cookie/trace不泄漏；Mock仅HTTP边界，不冒充SQL或Cookie浏览器运行。无生产/Schema/API/机制/依赖变，撤测试无升级。
- 完整测试本批实际跑，14PG/coverage/wheel/性能未跑，原84.717%/raw/90%保留，不预报覆盖；正式trust/Gate/包待。

## DEC-20260927-363

- Executed：1501unit无失败/errors0/2既有跳过、14实际链全通过；完整Auth3200/3364行95.125%、837/988分支84.717%，false/exit1，综合92.762%不替代。密码91.146%保持、工厂8/10单列；完整范围/分母不变，旧a2fb0a38…复核不变，新7d6fbfc0…。下一Session HTTP拒绝与错误响应，性能/wheel未跑，正式trust/Gate/可用包待。

- Phase2/P07A16编码前检查见state-coverage；完整unit/14实际链统一覆盖，保原完整Auth与密码范围/90%行AND分支/工厂单列，独立新runtime不覆旧Hash。无生产/Schema/API/算法/依赖变，撤入口无升级。
- 实测前不推算比例，测试失败/覆盖不足都保exit1；性能/wheel本批不跑，正式trust/CR008 FAIL/Gate/可用包待。

## DEC-20260927-362

- Executed：实际缺User拒绝，八次真实Service final True→缺Session/time/proof/CSRF/User/live Session/other Admin拒绝或SQL22012+25P02，八次九表全行回滚/原Session保留；实际正常self-disable提交/准确撤销1 Session及原publication回归通过exit0。无生产变化，unit最近1501本批未跑，coverage/14链/wheel/性能未跑，旧82.186%与Hash保留；下一14链完整覆盖，正式trust/Gate/包待。

- Phase2/P07A15P02编码前检查见state-final-source；真实Service self-disable后原final True，再八故障原源拒绝、九表回滚/旧Session保留，最后真提交。DTO/time/CSRF注入明确，与同UOW SQL User/Session/Admin变化区分；TEST_ONLY角色/合成License，不mock成功SQL/禁触发器。
- 无生产/Schema/API/权限/算法/依赖变，撤验证无升级；原publication回归，unit1501本批不跑、coverage/14链/wheel/性能未跑，原raw/90%与正式trust/Gate/包缺项保持。

## DEC-20260927-361

- Executed：4新增方法、完整1501unit无失败/errors0/2既有跳过，exit0；八非法ID/八错自停用来源/两篡改DTO在SQL前拒绝，真实inactive Session lock/change/final三路径抛原AuthTransactionError且仍无事务。无模拟成功SQL；仅P01 PASS，实际末核/九表回滚P02待。生产无变，coverage/13PG/wheel/性能未跑，旧82.186%与Hash保持，正式trust/Gate/包待。

- Phase2/P07A15P01编码前检查见state-adapter-defensive；仅Repo非法ID/Access错自停用来源及篡改DTO前SQL拒绝，真实未开启Session事务拒绝，不mock成功SQL；Adapter原AuthTransactionError传播，Service才固定码，不混淆层次。
- 无生产/Schema/API/权限/算法/依赖变，撤测试无升级；完整unit跑，实际PG末核留P02，coverage/13PG/wheel/性能本批未跑，旧raw/90%与Gate/包缺项保持。

## DEC-20260927-360

- Executed：6新增方法，1497unit无失败/errors0/2既有跳过、exit0；七依赖/六clock-proof/四收据-first/八Repo/五first-Audit来源/最终proof改变拒绝，无commit、已进UOW均退出；末核拒绝允许先complete但不提交，不冒充SQL回滚。生产不改，coverage/13PG/wheel/性能未跑，原82.186%与Hash保持；下一User状态Access/Repo独立拒绝，正式trust/Gate/包待。

- Phase2/P07A14编码前检查见user-state-defensive；七依赖/clock/ActorProof/收据/Repo/first错误拒绝，无commit/UOW闭合，仅Service Port不冒充SQL。无生产/Schema/API/权限/算法/依赖变，撤测试无升级。
- 完整unit实际跑，coverage/13PG/wheel/性能本批未跑，旧82.186%/raw/90%保留；实际Repo另任务，正式trust/Gate/包待。

## DEC-20260927-359

- Executed：首次预期Service错误捕获时fixture未导出异常类导致AttributeError/exit1，直接导入正式异常类后重跑exit0；实际缺行/源比对、原密码True/False、四verifier故障、三SQL22012固定拒绝，实际insert/get后None故障九表全行回滚/密码擦除及同名称正常创建成功，原publication回归通过。无生产变化，unit最近1491本批未跑，coverage/性能/wheel未跑；下一独立User状态Service防御，13链统一覆盖后再测，不冒充全安全/Gate/包。

- Phase2/P07A13P02编码前检查见create-result-source；owned真实PG原Repo读取/写入/触发器、缺User/Credential/错DTO、verifier非bool/异常、实际SQL22012事务中止；真实insert/read后显式返回故障，Service全九表回滚及后续真成功，不mock成功SQL/禁触发器。
- 无生产/Schema/API/算法/依赖变，撤验证无升级；原publication回归，unit1491为最近结果本批未跑，coverage/性能/wheel未跑，原raw/90%与正式trust/Gate/包缺项保持。

## DEC-20260927-358

- Executed：5参数化方法，record20/get4/DTO4/事务故障6/hash6拒绝；首次1491通过，复查坏盐用例实际改参数，精确修正盐字段后再次完整1491无失败/errors0/2既有跳过，exit0。不mock成功SQL，未调用verifier；仅P01 PASS，实际来源P02待。生产不改，coverage/12PG/wheel/性能未跑，原82.186%与Hash保持，Gate/包待。

- Phase2/P07A13P01编码前检查见create-result-defensive；只Result Repo前SQL坐标/DTO拒绝及_session底层故障固定码，不mock成功SQL；实际缺行/原Credential和verifier来源P02真实PG另验。无生产/Schema/API/算法/依赖变化，撤测试无升级。
- 完整unit实际跑，coverage/12PG/wheel/性能本批不跑，原82.186%/Hash/90%保持，正式trust/Gate/包待。

## DEC-20260927-357

- Executed：新增6参数化方法，完整1486unit无失败/errors0/2既有跳过，exit0；九依赖/三收据/四重放/八写来源/四clock/十二hash合同拒绝，无commit/已进UOW闭合/密码擦除。仅Port证据，生产不改；coverage/12PG/wheel/性能未跑，原82.186%与Hash保持。下一Result Repo独立前SQL/异常与实际来源验证，正式trust/Gate/可用包待。

- Phase2/P07A12编码前检查见user-create-defensive；仅创建Service依赖/收据/first/写来源/clock/hash合同拒绝与无commit/UOW退出/密码擦除；沿现有unit规范DTO达分支，不mock成功SQL或冒充实际回滚。
- 无生产/Schema/API/权限/算法/依赖变，撤测试无升级；完整unit实跑，coverage/12PG/wheel/性能本批不跑，原82.186%与Hash/90%保留，正式trust/Gate/可用包待。

## DEC-20260927-356

- Executed：1480unit無失败/errors0/2既有跳过，12实际链全通过；完整Auth3190/3364行94.828%、812/988分支82.186%，false/exit1，不用综合91.958%代替90%分支。密码91.146%保持、工厂8/10单列；旧Hash不变，新a2fb0a38…。生产/分母不变、性能/wheel未跑；下一仅User创建Service拒绝边界，不豁免全Auth/Gate/包。

- Phase2/P07A11编码前检查见session-coverage；完整unit+12实际链同轮测量，保完整Auth/密码原范围/工厂单列与独立90%行和分支控制。新runtime保旧Hash，不改变生产或排除范围；无Schema/API/权限/依赖变，撤验证无升级。
- 测试与覆盖结果待实测，客观失败保留；正式trust/性能CR008 FAIL/Gate/可用包仍待，不由本批合成信任回归代替发行。

## DEC-20260927-355

- Executed：重跑exit0，实际Session健康/缺记录/错用户，三fact与三Port注入拒绝，实际reset受限无Project；实际唯一约束拒绝第二活跃成员后原投影健康，十二表逐次不变。原dualScope空/260publication回归通过。歧义分支未达，unit最近1480本批未跑，coverage/性能/wheel未跑，下一完整12链统一实测；正式trust/Gate/包未完成。

- Plan correction：首次实际第二活跃成员INSERT被uq_prj_members__user_active拒绝/exit1；原fixture清理。投影歧义分支未到达，不称通过；修正验证为实际约束拒绝/十二表不变/健康投影保持，不关约束、不mock成功SQL。该调整仅验证计划，无生产/冻结方案变化。

- Phase2/P07A10P02编码前检查见session-source进度；复用owned实际PG/Vault/publication fixture，真实当前行/缺记录/Project歧义与实际reset受限投影；fact字段/Project坏Port明确故障注入，不mock成功SQL。十二表全行不变作为只读证据。
- 无生产/Schema/API/算法/依赖变，撤验证无升级；原publication同轮回归，unit最近1480、coverage/性能/wheel本批未跑，90%/正式trust/Gate/包不冒充通过。

## DEC-20260927-354

- Executed：4参数化方法、1480unit无失败/errors0/2既有跳过，exit0；入口和真实未开启事务拒绝、token绑定优先且失败无fallback。仅P01 PASS，实际PG当前凭据/Project来源留P02，不冒充SQL成功或A10整体完成；coverage/11PG/wheel/性能未跑。

- Phase2/P07A10P01；编码前检查见session-projection进度。先做入口、真实未启动Session事务和token优先转接的拒绝合同；不mock成功SQL。源码无clock注入，纠正上一计划的time范围，实际Credential/Project来源保留P02真实PG，不标整个A10完成。
- 无生产/Schema/API/权限/依赖变；仅新增测试，撤测试无升级。完整unit实际跑，coverage/11PG/wheel/性能本批不跑，原Hash/90%与性能FAIL/Gate/包待保留。

## DEC-20260927-353

- Executed：新增6参数化Session方法，完整1476unit无失败/2既有跳过，exit0；输入/clock/proof事务前拒绝与擦除，CSRF/revoke/logout current-receipt/admin锁错误无后续写/Audit/complete/commit，UOW闭合。不模拟SQL成功，无生产变更；coverage/11PG/wheel本批未跑，原80.162%与Hash保持。下一Session投影与统一实测，90%/性能/Gate/包待。

- Phase2/P07A09编码前检查见session-defensive；Session依赖/proof/ID/time/token、CSRF/revoke失败与logout历史违约、admin锁拒绝，明确无Audit/complete/commit及UOW闭合，规范Record仅Port控制不冒充SQL。完整unit实际跑，PG/coverage后续保同范围/旧Hash；无生产/Schema/API/机制/依赖变更，风险回滚先记，90%/性能/Gate/包待。

## DEC-20260927-352

- Executed：1470完整unit无失败/2既有跳过，原五+六非密码实际入口共11全部通过；全Auth3168/3364行94.174%、792/988分支80.162%，密码91.146%保留，工厂8/10单列。新增ALL_AUTH独立90%检查false/exit1，不以综合90.993%或密码过线冒充全Auth通过；原Hash保留，新f6a57106…。无生产/Schema/API/依赖变化，wheel/性能未跑；下一A09 Session防御/no-commit边界，性能/正式trust/Gate/包待。

- Phase2/P07A08编码前检查见full-auth-coverage；完整unit+原五密码链+六已有非密码链实测，不造成功SQL；新入口明确增加完整Auth行/分支90%退出控制，避免继承仅密码过线exit0误报。保完整范围/旧raw、新runtime；无生产/Schema/API/算法/依赖变化，风险回滚先记，正式trust/性能/Gate/可用包待。

## DEC-20260927-351

- Executed：两Service对c004980 AST完全相等；1470unit无失败/2跳过与五实际链全通过，密码1031/1047行98.472%、350/384分支91.146%本范围90%通过/exit0。分母增30行14分支、不删排除，明确排版改善非新增用例；全Auth92.717%/78.239%仍未达，工厂单列。旧Hash保留，新57390683…；guard新84/85异常2次且无该缺边，审计expanded目录独立。无Schema/API/算法/权限/依赖变化，wheel/性能未跑。下一A08完整Auth原实际链纳入与真实缺口，不关闭性能/正式trust/Gate/包。

- Phase2/P07A07P02编码前检查见service-layout；基于局部复现仅两Service guard/raise分行，对c004980 AST等价为硬前置，完整unit/五PG/Windows+原完整范围覆盖，明确新行分母/非新增用例改善；不加排除、不改90%/生产机制/API/Schema/依赖。风险回滚先记，真实缺口与性能/正式trust/Gate/包待。

## DEC-20260927-350

- Executed：原source类型拒绝用例coverage/trace各通过，guard83异常2次却实际83→75退出、报告列83→162未覆；普通及retry/finally对照无缺口，with最小例compact记录13→12/列13→15缺，AST等价expanded无该guard缺。只证明一个对应问题，不豁免全部缺边；无生产变更，完整unit/PG/coverage/wheel未重跑，原86.757%与旧Hash保留。下一两Service同模式分行/AST等价和完整实际复验，90%/性能/Gate/包待。

- Phase2/P07A07P01编码前检查见branch-audit；现有拒绝用例独立coverage/line-exception trace与AST等价compact-expanded最小复现，不改生产或测量排除，不以一个复现替全部缺口豁免。安全坐标计数、独立runtime保旧Hash；风险回滚先记，90%/性能/Gate/可用包待。

## DEC-20260927-349

- Executed：1470完整unit无失败/2既有跳过，原四链+实际final链全通过；密码1007/1017行99.017%、321/370分支86.757%，全Auth92.831%/76.386%，工厂362/369行8/10分支单列，exit1为门槛未达。新Hashd45e9dd3…及旧JSON/Hash保留，无生产变更/wheel性能未跑。下一A07逐边审计对应现有用例和真实缺口，不无证认定不可达/工具误差，安全/性能/Gate/包待。

- Phase2/P07A06P03编码前检查见final-coverage；同轮完整unit、原四链加新实际final链完整覆盖测量，保完整范围/90%与旧JSON/Hash，不改生产或把综合率替代分支。风险回滚先记，无生产/Schema/API/依赖变更，性能/正式trust/Gate/可用包待。

## DEC-20260927-348

- Executed：两实际Service各四故障，共八实际final拒绝/九表全行回滚/原Session可用/密码擦除，actual SQL22012中止后固定Access错误；两正常commit/新Session控制与原双Scope发布回归通过，exit0。无生产变更，unit最近1470保留本批未跑，coverage/wheel/性能未跑。下一五实际链完整同轮覆盖，不关闭90%/性能/正式trust/Gate/包。

- Phase2/P07A06P02编码前检查见current-final；两实际Service先正向final可达，再同UOW实际live/count/User版本/SQL22012中止故障；Access拒绝、九表全行回滚/Session可用/密码擦除及正常提交控制。仅隔离PG/合成身份，触发器不禁用，无生产/Schema/API/算法/依赖变化；风险回滚先記，随后统一coverage，不宣称完整安全/性能/Gate/包通过。

## DEC-20260927-347

- Executed：3参数化Result方法覆盖12事务异常/六role-source与recheck/非法Result-draft-source组合，固定拒绝、无成功SQL模拟或verifier；完整1470unit无失败/2既有跳过。无生产变更，coverage/PG/wheel本批未跑，原85.676%与Hash保持。下一P02实际current-final与事务故障回滚，90%/性能/Gate/包待。

- Phase2/P07A06P01编码前检查见result-faults；Result底层事务异常固定拒绝与非法role/result不SQL，复用既有正常Hash/strict bool测试，不造SQL成功，不改生产/Schema/API/算法/依赖。完整unit实际跑，coverage/PG本批不推算，旧Hash与90%门槛保留；风险回滚先记，下一真实current-final异常，性能/Gate/可用包待。

## DEC-20260927-346

- Executed：完整1467unit无失败/2既有跳过，四实际PG/Windows入口全部通过；密码1003/1017行98.623%、317/370分支85.676%，全Auth92.711%/75.975%，工厂362/369行8/10分支单列。exit1为分支门槛未达，原JSON/Hash保留，新Hash45c4d14a…；无生产/Schema/API/依赖变化，wheel/性能未跑。下一结果来源与真实current-final异常补证，不关闭安全/Gate。

- Phase2/P07A05P03编码前检查见unified-coverage；复用原同轮完整unit和四真实PG/Windows测量，保21文件/Auth/工厂范围、旧JSON/Hash、新独立runtime与90%门槛。不改生产/Schema/API/算法/依赖；风险回滚先记，性能/正式信任/Gate/可用包待。

## DEC-20260927-345

- Executed：7个参数化Access输入/事务方法，非法输入不SQL或verifier，固定错误与严格bool控制；1467完整测试无失败/2既有跳过，exit0。无生产/Schema/API/算法/依赖变化；coverage/四PG/wheel本批未跑，原Hash与82.432%保留。下一统一真实覆盖，90%/性能/正式信任/Gate/包待。

- Phase2/P07A05P02编码前检查见access-inputs；授权输入与事务缺失/异常、安全错误不泄露及Session issue非法proof不SQL/verifier。不造SQL成功，不冒充PG；完整unit实际跑，后续统一覆盖与旧Hash保留。无生产/Schema/API/算法/依赖变化，风险回滚先记，90%/性能/Gate未通过。

## DEC-20260927-344

- Executed：4参数化Repo输入方法，reset7非法输入/change3类型/2上限/两Repo各3参数profile（p=True也拒绝），明确_session未调用，无成功SQL模拟。1460unit无失败/2既有跳过，exit0；没有生产变更、coverage/PG/wheel本轮未跑，原82.432%与Hash保留。下一A05P02 current proof/transaction与安全异常，然后统一实际覆盖；90%/性能/Gate/包待。

- Phase2/P07A05P01编码前检查见adapter-inputs。测试两个Repo非法参数/版本上限，明确_session/SQL未访问，不造SQL成功；完整unit实际跑，coverage/PG本批不推算，原报告/Hash保留。无生产/Schema/API/算法/依赖变更，风险回滚先记；下一适配器当前数据/异常与真实统一复验，90%/性能/Gate未通过。

## DEC-20260927-343

- Executed：4参数化方法共reset准备4/写7与change准备2/写8场景，first/hint/op/status/current-final错配拒绝；准备无KDF/reserve、历史写已verify1或2次后无repo/complete/commit、UOW闭合/密码擦除。1456unit无失败/2既有跳过，exit0。无生产/Schema/API/依赖改变，coverage/PG/wheel本轮未跑，最近82.432%不推算更新；下一适配器拒绝与统一实际复验，90%/性能/Gate/包待。

- Phase2/P07A04P03编码前检查见replay-defensive；历史prepare/write first-receipt坐标类型/op/status/current-final违约，明确未repo/commit/UOW闭合/擦除；只测可信Port错误，不冒充PG。完整unit重跑，coverage/PG本批不推算，旧Hash/范围保留，下一适配器与统一复验。无生产/Schema/API/算法/依赖改变，风险回滚先记，安全/性能/Gate未通过。

## DEC-20260927-342

- Executed：5参数化方法新写正向控制/两Repo返回/first/final防御专测通过，明确无commit/擦除/UOW关闭；1452unit无失败/2跳过与同轮四实际PG/Windows全通过。密码991/1017行97.443%、305/370分支82.432%，全Auth92.352%/74.743%，工厂单列，exit1保90%缺口。无生产/Schema/API/依赖变化，旧Hash保留/wheel未跑；A04还有历史写hint-first违约，下一P03再适配器，不宣称整项完成，性能/安全/Gate/可用包待。

- Phase2/P07A04P02编码前检查见write-defensive。建立可实际成功的Service Port fixture，再故障注入repo/first/current-final防御，明确未commit/擦除/UOW关闭；不修改生产或冒充PG。完整unit后独立四实际集成coverage、保旧Hash/完整范围，90%与性能标准不变，风险回滚先记。

## DEC-20260927-341

- Executed：A04-P01新增6参数化方法、reset9/change8缺依赖/13历史hint-first-source-actor违约/两类各4非法时间；未KDF/global/reserve/repo/commit，UOW闭合与擦除通过，最终1447unit无失败/2既有跳过。首次2个错op测试在DTO格式校验先拒绝，已改合法其他op并全量复验；再强化明确commit Spy并全量通过。无生产改动，coverage/PG/wheel本轮未跑，原79.189%不推算变更；A04-P02写后防御待，性能/90%/Gate/可用包未关闭。

- Phase2/P07A04编码前检查见service-defensive。第一批仅Service缺依赖/历史hint-first-source/时间违约，模拟可信Port故障且断言无KDF/写/密码擦除；完整unit实际重跑，四实际PG及新覆盖率本批不重测，不推算PASS。生产/Schema/API/算法/依赖不改，风险回滚先记，下一写后repo/result/final-proof边界，性能与完整安全门槛保持。

## DEC-20260927-340

- Executed：8个新HTTP防御参数化方法专门测试通过，1441unit无失败/2跳过、四真实PG/Windows入口通过。两个API行/branch100%，同一密码21文件982/1017行96.559%与293/370分支79.189%，全Auth92.082%/73.511%，工厂单列；exit1保留整体90%缺口，安全/性能/Gate未关闭。没有生产源码/Schema/API/依赖变化，原Hash保留，wheel未跑；下一Service可信Port违约与擦除测试，不用mock替代真实PG。

- Phase2/AUT-04-A12-P07-A03编码前检查见http-defensive-tests。按A02实际缺口测HTTP缺依赖/不可信principal-result/postcommit异常与secret擦除，测试替身不替代真实PG证据；全量unit+四实际集成覆盖重测、另目录保历史。无生产/Schema/API/权限/算法/依赖变化，性能FAIL与90%门槛/Gate缺项保留。

## DEC-20260927-339

- Executed：1433unit无失败/2既有跳过，真实reset-history+atomic/change-history+atomic/Windowsreset/Windowschange四入口全部通过；密码968/1017行95.182%、282/370分支76.216%，全Auth3056/3334行91.662%、705/974分支72.382%，工厂362/369行8/10分支单列。综合90.123%不抵消branch未达，exit1未关闭安全Gate；A01原Hash未覆盖，A02另目录/Hash与21全文件报告。无生产/Schema/API/依赖变更，wheel未跑，性能FAIL保持；下一按实际缺口补HTTP及Service异常防御。

- Phase2/AUT-04-A12-P07-A02编码前检查与风险回滚见integration-coverage。保持A01基线及全21文件/Auth/工厂范围，同一插桩执行1433unit与真实PG reset/change history/atomic和Windows HTTP；结果另目录，不覆历史。固定输出失败入口/类型，未达90保持exit1，无生产/Schema/API/算法/依赖变更。性能CR008 FAIL与Gate缺项不变。

## DEC-20260927-338

- Executed：1433 tests无失败/2既有跳过，新增3项scrypt边界/后端错误，49/49行/12/12分支；密码21文件791/1017行77.778%与204/370分支55.135%，全Auth2738/3334行82.124%与576/974分支59.138%，Windows工厂355/369行7/10分支单列。真实coverage exit1未达90，不伪报PASS；中途1个verify固定字符串测试期望已修并全量重测。完整分母/原JSONHash/缺口见test-report。无生产/Schema/API/依赖变更，wheel未重跑；下一真实PG/Windows coverage补证，性能CR008 FAIL保持。

- Phase2/AUT-04-A12-P07-A01编码前检查见security-coverage进度。使用已有本机coverage7.13.5测真实完整unit/contract分支与行，不新增生产依赖；密码全部相关API/Application/Infrastructure/进程容量计入明确范围，并独立报告全Auth。90%目标保持，无pragma/omit删路径；未实际执行的DB分支如实呈现，后续隔离PG补证。风险/回滚/安全输出先记，无生产/Schema/API变化，性能CR008仍FAIL。

## DEC-20260927-337

- Executed：真实Bootstrap16/原共享gate委托计时，五组各20成功、SQL0/两history九表不写/first-版本-Session原完整性与Windows/发布回归通过，固定KDF+slot+global计数通过、peak16/end0/timeout0。P95 GET119.308/reset fresh1006.003/change fresh1604.868/reset history842.946/change history1627.173ms；processpeak2285068288bytes，整体exit1 FAIL。默认4不改，CR OPEN。成本与结论见progress，下一独立安全覆盖率基线，不无限调slots；无生产/Migration/API/依赖变更，unit/wheel未重跑。

- Phase2/AUT-04-A12-P06-A04-P03-A06编码前检查见configured-profile。迁移旧测试剖析到真实Bootstrap共享预算，仅委托原gate计时不创建第二限额；五组实际计数/原完整性与性能验收，16独立进程一次。无生产/Schema/API/算法/依赖改变；风险回滚先记录，默认4/CR FAIL保留，后续转安全覆盖率避免无限资源试探。

## DEC-20260927-336

- Executed：真实Windows配置4与16独立进程混合fresh/history每批20成功/30真实KDF/共享peak4或16/end0/SQL0，旧Session失效、原结果/reset ETag与九表历史不写、旧Windows与发布回归通过。4 P95 2199.128/2507.062ms；16 1218.475/999.713ms，fresh仍超1秒，两run exit1整体FAIL。首次16外层默认4冲突安全拒绝，已修整个fixture配置来源并复验，无生产gate重置。默认4不改；unit/wheel本轮未重跑，CR/Gate仍开放，下一真实成本工具迁移。

- Phase2 / AUT-04-A12-P06-A04-P03-A05；编码前检查、风险/回滚/验收见mixed-http进度。实际Windows写工厂10+10同时新写/历史，真实Bootstrap容量、真实KDF计数/总峰值/结束0，九表历史不写与原结果。无生产源码/Schema/API/权限/依赖变化，保持性能原1秒标准，运行结果待验。

## DEC-20260927-334

- Executed：1426 tests无失败/2既有跳过，容量严格bound/5秒timeout/owner配对/线程界/异常恢复及两个Service strictTrue/擦除通过；真实PG10reset+10change混合fresh/history各30 KDF、合计peak4/end0、20原结果与历史九表无写、旧Session失效，原atomic/发布/wheel752486通过。Windows工厂尚未注入/默认两个旧4兼容保留，不虚报全部Auth或HTTP性能；下一非敏感配置与进程唯一budget装配，原性能FAIL/CR/Gate开放，无Migration/API/依赖。

- A03编码前设计见shared-capacity：先内部严格1..16/默认4/5秒共享预算及reset-change可信注入，活动总界/线程持有配对，权限-KDF-原事务不改；未注入保旧4，Windows配置/唯一进程装配另项，不能宣称全部Auth限额。单位/实际混合fresh-history待验，无Migration/API/依赖，原标准/CR008 OPEN。

## DEC-20260927-333

- Executed：8与16独立进程顺序5×20全部成功/SQL空/history九表不写/计数与peak8或16/end0/timeout0/原state-publication通过，均最终exit1整体FAIL。8 fresh reset1076.548/change2148.421/history1135.454/2159.915ms，peak1210707968；16 fresh975.244/1618.757/history859.607/1616.897ms，peak2285113344。单KDF由4的约310ms增至8约365～395/16约476～493ms，等待减少但计算竞争/取锁排队增大。生产4不改，不以单轮reset PASS关闭整体；下一显式容量+reset/change共同预算设计/混合验证，防两个16独立gate误称总限额。无生产变更，unit/wheel未重跑，CR/Gate开放。

- A02编码前检查见slot-comparison：已修history后test-only成本profiler支持4/8/16，8和16各独立进程顺序跑完整五组，新增实际slot峰值/最终0/等待统计；固定KDF/原标准/生产4不变，无Migration/API/依赖。单轮tradeoff不自动改生产、不无限重复，实测后选择下一步骤，CR008 OPEN。

## DEC-20260927-332

- Executed：5×20全成功/无SQL错/九表history不写与原状态/发布通过，实际计数reset20 KDF/change40、20 global、20 slot成功。slot等待P95 resetfresh1181.524/changefresh2446.818/history1145.744/2423.986ms；每KDF约310～321ms，global获取P95 fresh≤38.314/history≤7.056、持有至UOW退出fresh≤24.823/history≤8.860ms。HTTP四写约1.62/3.18秒仍FAIL/实际exit1，processpeak674357248；生产未改，unit/wheel未重跑。下一test-only8/16 posthistory资源成本比较，不降算法/标准、不改DB锁，CR/Gate开放。

- P03编码前检查见cost-profile：test-only包装实际KDF/slot/global锁/UOW成本，5×20原factory/PG正确性保留；静态阶段与聚合时长，不输出秘密/SQL/正文、不改4-slot/参数/API/Schema。计时有开销、不同分位数不相加；失败原exit1，按证据再选优化，CR008 OPEN。

## DEC-20260927-331

- Final：Windows change A04/reset A07两专门链依次exit0，实际普通/受限Cookie/登录/历史first/自reset-丢回执恢复及缺信任源/构造故障/原state-publication通过。完整功能内部PASS，性能仍FAIL，未执行生产升级/正式安全/UAT，不标程序包完成。

- Executed：1419 tests无失败/2既有跳过；真实PG历史双KDF无锁/current源-new hash不调用、任一错密码冲突、logout/renew/disable/laterchange4拒绝/License-disabled可重放、peer first中途提交旧Session拒绝新login恢复，九表无额外写与原atomic/发布/wheel751532通过。20五组全成功/SQL错误空，history change P953220.477ms（原8114.279/6锁超时），resethistory1650.695/fresh1642.030/changefresh3157.216，整体exit1性能FAIL。下一阶段成本/资源剖析，原强度/标准/CR/Gate保留；Windows专门链待结束追加。

- A04编码前检查见change-history：current Session短UOW取exact history双源、事务外4-slot真实双KDF，原global新身份/scope/reserve/fullfirst/双source/末核；miss最多一次退出后重准备，实际change撤旧Session必须拒旧请求。fresh原链/无Admin-License/构造兼容，无Migration/API/依赖/算法变，CR008延续，实际验证待。

## DEC-20260927-330

- Executed：1414 tests无失败/2既有跳过，实际PG KDF时独立global/caller/Session锁、role/logout/renew/License撤回九表无额外写、目标actual reset4历史保留；actual first中途提交正确重放/错误密码冲突、一次回退与擦除通过。原atomic/Windows reset完整链/发布/wheel751120通过。20并发reset历史20成功/P951634.794ms（原6014.758），fresh1598.708ms；change历史仍14成功6actual55P03/8114.279ms，整体exit1 FAIL。无Migration/API/依赖，下一change历史编排，CR/Gate不关闭。

- A03编码前检查见reset-history：短实际Admin准备取scope/hint/fullfirst/exact source，4-slot事务外真实verify；原global新权限/reserve/first/source/final，miss竞争只一次退出后重新准备，不锁内KDF。保原fresh链/兼容构造/无Migration/API/依赖/算法变更，CR008持续；验证待，不能提前PASS。

## DEC-20260927-329

- Executed：1409 tests无失败/2既有跳过；真实PG reset2/change3/later4后闭READ ONLY UOW历史真/最新false、六KDF独立锁可取，最后READ ONLY精确first/source无KDF、错role/source/trace拒绝九表无写；原reset原子及发布、wheel750773通过。Service未接入、性能未跑/上一FAIL保留，下一reset历史编排及bounded race，再change另项；无Migration/API/依赖，CR/Gate开放。

- A02编码前检查见 historical-source progress：在既有 auth first Repository 分离 exact source/无DB verify/fresh require_source，复用隐藏 PasswordHashResult 副本，原 verify 委托保持；source非权限，原 Service本项不改，无Migration/API/依赖。CR008继续，测试待，不以接口通过代替历史20性能通过。

## DEC-20260927-328

- Executed：1405 tests 无失败/2既有跳过，真实PG只读/未提交/回滚/原结果/锁定行20次查询/四scope/fingerprint/PENDING拒绝与九表无写通过；原reset prehash/原子真实change-history/发布通过，wheel750252通过。Service尚未调用，性能未重跑且上轮FAIL保留，下一历史source detached；无Migration/API/依赖，CR/Gate未关闭。

- 编码前检查见 AUT-04-A12-P06-A04-P02-A01 progress。既有平台 receipt 增加只读已完成提示，标量 SELECT/no autoflush/no lock/no commit；strict scope/fingerprint 和静态失败，不作为权限或写授权。原 reserve/complete 不变，无 Migration/API/依赖；真实验证后记录，不关闭性能 CR/Gate。

## DEC-20260927-327

- Executed：8/16/20-slot实验新写全20成功/SQL空；reset1110.913/1064.465/957.033ms，change2142.248/1674.781/1446.926ms，process峰值工作集1208188928/2281807872/2818846720 bytes，活动峰值等于上限且slot等待0。生产4不改，不能靠单轮reset达标关闭整体性能。原4历史reset20成功6014.758ms/change14成功6个actual global55P03/7908.389ms，九表不写/first保持；所有运行末exit1 FAIL，旧状态/发布通过。下一readonly receipt hint/source detached历史KDF及最终完整重验；无生产变更，unit1400/wheel沿用上一轮未重跑。

- P06A04P01编码前检查见progress：test-only8/16/20-slot分进程顺序比较固定KDF实际HTTP/正确性与peak working set，再原4-slot历史20重放/九表无写。production仍4、无Migration/API/依赖/权限变；阈值不变，全结果保留、失败非零，下一按实际证据决定调度/历史锁段修复。

## DEC-20260927-326

- Final unit：1400 tests无失败（2既有跳过），change Service11 unit含真实5线程4-slot界及新hash失败无写/擦除；1398后补test再全量通过，生产源码不再改。

- Executed：真实PG两个KDF阶段独立global/User/Session锁可取，logout/renew/disable/实际reset竞争九表无额外写、错误密码拒绝，普通/License-disabled及TEST_ONLY新角色实际fresh User版本正确。原原子change与Windows change/reset完整链、发布及wheel749932通过。20并发三组均20成功/SQL错误空/20+20first及旧Session失效，GET111.960/reset1631.262/change3178.707ms，普通写性能仍FAIL。无Migration/API/依赖，下一资源校准/history，CR/Gate不关闭。

- P06A03编码前检查见progress；本人proof/current不可变Credential源短UOW关闭后固定KDF（4 slots/5秒），写事务新身份及相同Credential ID/version/flag再核；false只拒fresh，历史仍原first双密码真实KDF，noLicense保持。source只请求内隐藏DTO、不缓存权利，原self末核与原子链不省略。无Migration/API/依赖，真实验收待。

## DEC-20260927-325

- Final unit：1393 tests无失败（2既有跳过），reset Service9 unit含实际5线程最多4活动hash；初次1392后补resource并发test再全量通过，无生产源码后改。

- Executed：reset新hash事务外/4 slots实施；真实PG计算时global/actor/Session独立锁可取、角色/logout/renew/target disable/License竞争后九表无额外写，原原子reset及Windows/发布通过。20并发GET106.973ms、reset1634.810ms/20成功改善仍FAIL；change7559.374ms/14成功6个实际global55P03，未改change。wheel749632通过，无Migration/依赖/生产升级；下一change及历史，CR/Gate未关闭。

- P06A02编码前检查见progress：reset预认证独立UOW退出后固定Scrypt（4 slots/最多5秒等待），原写UOW global锁/当前权/receipt/target expected/self末核仍全保留。预proof不是写权、不持久化密码，历史仍first KDF，change另项；无Migration/API/依赖。真实边界/撤权竞争及回归待，不预判性能通过。

## DEC-20260927-324

- Executed：三轮真实20客户端Windows/PG/Scrypt GET P95约108～120ms，reset20成功但约5.6秒，change14成功/6个503约7.3秒；第三轮实际SQL六55P03都来自deployment advisory lock。失败六用户版本/凭据/原Session保持，无change first/Audit；成功14及20reset first计数真实一致、原Windows状态/发布通过。验收FAIL，CR-AUT008先登记比较/风险/回滚/验证及下一预计算设计，未改生产代码/Schema/依赖。unit1388沿用上一轮未重跑，完整CR/Gate不关闭。

- P06A01编码前检查见progress；真实Windows Factory/PG/Scrypt、独立20异步客户端同步放行，完整HTTP GET/reset/change计时与数据库来源核对，nearest-rank P95/500ms与1000ms按原标准。正向trust合成，非实际网络/正式发行。只验证无生产变更；延迟失败如实登记，不降低KDF或去安全锁，下一按证据调整。

## DEC-20260927-323

- Executed：Windows实际write完整PG/Scrypt HTTP矩阵、真实登录reset→旧Session/password401→受限登录change→正常新登录/原first恢复通过；六新增构造故障dispose一次/九表不变，readonly405/default-login404/缺正式材料拒绝、旧状态/发布回归及1388无失败（2跳过）/wheel749399通过。无Migration/依赖/生产升级，正向trust合成；CR/Gate未关闭，下一完整验收缺项与20并发前置。

- P05A07编码前检查见progress；仅Windows显式write装配既有实际reset链、无测试回退，所有依赖构造失败原安全关闭；readonly/default/login保持不开放。无Migration/依赖/权限变化。真实factory HTTP与六依赖故障/正式材料缺失验收待，撤接线保历史。

## DEC-20260927-322

- Executed：1388 tests无失败（2既有跳过）；实际PG/Scrypt-ASGI strict JSON/来源/Session-CSRF-Key/强If-Match拒绝九表不变，normal/disabled/self的凭据版本与User ETag分离，实际change后正常Admin原Key历史Cookie保留；实际Audit回滚及self提交后末读503真实change/新正常Admin恢复first，原发布/wheel749262通过。无Migration/依赖/生产升级；合成License，默认404，Windows下一项，CR/Gate不关闭。

- P05A06编码前检查见progress；可选reset POST strict临时密码/true/来源/Session-CSRF-Key/强If-Match，正常Admin/License由原Service承担；公开仅版本，目标ETag用first User version非Credential版本，重放原ETag；self Cookie精确清除/normal新认证重放保留/未知末读503恢复。无Migration/依赖，真实矩阵待，Windows另项。

## DEC-20260927-321

- Executed：1384 tests无失败（2既有跳过）；真PG/Scrypt同Key单first/不同Key版本竞争、三旧Session含expired撤销/受限登录/真实change后历史恢复/disabled0保停用；四Port+三SQL/precommit/末License及实际角色撤销九表回滚、commit丢确认恢复；TEST_ONLY坏旧profile实际reset修复、唯一Admin self末核false回滚/丢确认/旧受限无新权/License-disabled真change后normalAdmin原first恢复。修正IssuedSession测试读取后完整复验，原发布/wheel747290通过。无Migration/API/依赖，License合成/无HTTP性能发行证明，下一可选reset HTTP。

- P05A05编码前检查见progress；原子reset actual Admin-CSRF/License前后/target expected/固定true，disabled/self保范围、Scrypt/Credential-root/allSession/Audit/first/receipt同UOW，self首次专用末核不跳过，历史恢复须正常Admin+当次临时密码。全密码finally擦除，无Migration/API/依赖；真实矩阵待。

## DEC-20260927-320

- Executed：1380 tests无失败（2既有跳过）；实际PG/Scrypt current normalAdmin-CSRF/部署锁、wrongCSRF/NONE与other-self拒绝，同UOW TEST_ONLY self reset实际first专用末核成功，伪造/过期及意外改名角色停用拒绝/savepoint恢复，旧及受限会话无新管理权、actualchange/newlogin恢复Admin；source/发布回归/wheel743224通过。无Migration/API/依赖，未验唯一Admin/License/原子reset/receipt/HTTP，下一完整原子命令。

- P05A04编码前检查见progress；复用normal current Admin-CSRF proof和部署锁，独立self首次commit前精确末核actualfirst/expected/trace/原normal凭据/原生命周期与本次受限换密、全部Session撤销count。旧/受限Session不授新管理权，最后Admin经change可恢复，License前后另Service负责。无Migration/API/依赖，真实矩阵待。

## DEC-20260927-319

- Executed：3新unit/1377 tests无失败（2既有跳过）；真PG/Scrypt caller-UOW first/server acceptedAt/当次临时密码匹配，差异/伪造源/KDF异常非bool九表无写且擦除；later真正change转normal3仍历史临时匹配，坏新profile及合法first后caller故障全部回滚/原会话保留，原发布/wheel741372通过。TEST_ONLY reset转换非当前授权/原子reset/receipt/HTTP证明；无Migration/API/依赖，下一normal Admin身份与self专用末核。

- P05A03编码前检查见progress；caller-UOW resetfirst get/record+server acceptedAt，当次newCredential精确true/actor/time/profile与真Scrypt历史source，不以currentCredential代历史、不持久密码等价物；oldHash不作重置前置（Admin可修复），旧ID/version由0049 source保障。无新Migration/API/依赖/授权，实际矩阵待验。

## DEC-20260927-318

- Executed：1374 tests无失败（2既有跳过）；真实空有数据0048-49往返十三旧表/ORM一致、normal2含expired/disabled0/self source、坏actor/Audit/time/count/normal-after/other及self受限拒绝与实际写后回滚、独立PG并发单first/immutable/非空down保head49；五旧Schema/Windows改密及原发布/wheel740067通过。Audit夹具FAILURE提前拒绝改合法FAILED证明source拒绝，不放宽生产。无生产迁移/API/依赖，TEST_ONLY源非KDF/原子reset/授权，下一真实Repository/source。

- P05A02编码前检查见progress；独立0049/ORM15字段reset first，current root/前后Credential/Admin actor/Audit/time/count真实source，disabled/count0/self保范围；other current normal/self before normal，来源不是当前Session-License授权。immutable/非空down，旧migration保留，无API/依赖；真实空有数据与来源/回滚/并发验收待。

## DEC-20260927-317

- Executed：6新unit/1374 tests无失败（2既有跳过）；15字段enabled/disabled/self/count0与安全单版本、严格shape/UTF8边界/擦除/非bool异常，实际内存Scrypt原临时密码匹配/尾空格-后来密码冲突/伪造first拒绝，wheel737736通过。无PG/HTTP运行或Migration/API/依赖，source夹具非持久来源/授权；next Schema设计明确未实施，完整reset/Gate仍待。

- P05A01编码前检查见progress；reset first15字段含Admin actor/原target_state/expected与前后凭据，count可0，disabled不启用，自reset不禁。公开仅版本，历史临时密码source严格真KDF/boolean/finally擦除；pure proof不授当前Admin/License权。自reset受限→先change→正常Admin再历史恢复，非失效Session绕过。无Migration/API/依赖，验收待。

## DEC-20260927-316

- Executed：1368 tests无失败（2既有跳过）；actualFactory真PG/Scrypt完整HTTP普通/受限矩阵、登录-Cookie jar改密清除-旧Session401/旧密码401-新login200同UUID、六构造fault实际dispose一次/八表不变、readonly/default/login404、旧Windows状态/缺正式材料拒绝与原发布/wheel735861通过。无Migration/API/依赖/生产升级，正向trust合成，非正式发行/Gate；下一reset前置。

- P04A04编码前检查见progress；仅Windows显式write装配原改密链，readonly/login/default关闭，原正式启动信任不放宽；当前proof/真实Scrypt/Audit/receipt同UOW，无Schema/API/依赖/权限变化。实际Factory/构造failure dispose及无材料拒绝待验，非正式发行证明。

## DEC-20260927-315

- Executed：1368 tests无失败（2既有跳过）；实际PG/Scrypt可选HTTP普通/受限转换、严格拒绝八表不变、无License gate、安全单版本响应/旧Cookie清除/旧401、新认证历史重放保Cookie/差异409、真实postcommit末读503再新登录同Key恢复/default404及原发布/wheel735734通过。surrogate夹具首轮httpx预先失败改原始字节验证422，无生产放宽。无Migration/依赖/生产升级；Windows/browser/reset/包/Gate未验，下一显式写装配。

- P04A03编码前检查见progress；可选冻结改密POST，严格来源/唯一Cookie-CSRF-Key/有界JSON，当前本人普通或受限，无License/Admin/If-Match。安全单版本响应、首次明确失效清Cookie/当前新认证历史重放不清、末读unknown503登录后恢复。无Migration/依赖，测试待，Windows另项。

## DEC-20260927-314

- Executed：1365 tests无失败（2既有跳过）；真PG/Scrypt原子变更、三Session含expired撤销、新登录/当前认证历史双密码恢复、差异拒绝八表不变；五Port+三SQL写后及precommit回滚、真实commit丢确认新登录恢复、同/不同Key两线程各单转换、受限源真正服务转normal，原发布/wheel733922通过。无HTTP/Migration/API/依赖/生产升级，内部PASS非完整包/Gate，下一可选改密HTTP。

- P04A02编码前检查见progress；本人normal/restricted Session-CSRF原子改密，无Admin/License/If-Match。固定本人receipt+非秘密schema fingerprint，首次精确末核/同事务commit，重放须当前有效认证及历史双密码真实KDF，原会话失效不授新写；密码finally擦除。无Migration/依赖/公开API，验证待。

## DEC-20260927-313

- Executed：1361 tests无失败（2既有跳过）；实际PG/Scrypt普通与受限身份及当前原密码，同一转换UOW锁定身份/first后专用末核成功，伪造Token/CSRF/trace/flag/version/到期拒绝，旧Session无新认证；来源/回滚/发布回归及wheel730294通过。仅Auth前置，TEST_ONLY转换非原子Service/HTTP/包/Gate证明；下一P04A02。

- P04A01 precode见progress；独立normal/restricted改密身份/真原密码与首次变更专用末核，不通过Admin proof、不将失效Session授新写。复用状态部署事务锁/5s等待，严格原生命周期/版本/CSRF/immutable first/count。无Schema/API/依赖，后续限定commit前调用；真实矩阵待验，非原子Service完成。

## DEC-20260927-312

- Executed：1359 tests无失败（2既有跳过）；实际PG/Scrypt当次两凭据匹配/各错及伪造first/异常非bool拒绝八表不变、后来Credential3不替代历史、record坏profile回滚、合法实际first写后caller故障八表回滚及原Session保留；原发布回归/wheel727401通过。TEST_ONLY转换非生产当前认证/原子改密证明；下一A12P04。

- A12P03A03 precode见progress；caller UOW get/record真实0048first、server acceptedAt、两Credential精确历史source+固定Scrypt预检与真实KDF，不授当前认证。无Migration/API/依赖/Key，撤未挂Port保历史；实际密码来源/异常/历史矩阵待验。

## DEC-20260927-311

- Executed：1357 tests无失败（2既有跳过）；真实空/有数据0047-48往返十二旧表及ORM一致、前后Credential/User/self Audit/time/count2含expired/未撤销及must-change=true源拒绝、first写后回滚/历史immutable/非空down保head48；四旧Schema/Windows受限Session/原发布回归及wheel726009通过。首轮新ORM表登记遗漏修复保历史严格断言，见progress。Schema TEST_ONLY非原子换密或当前密码授权证明。

- A12P03A02 precode见progress；CR-AUT007内0048/ORM first13字段，精确前后Credential/User/Audit/Session时间与撤销计数source，immutable及非空down拒绝。原0001～0047保留，无权限/API/依赖或生产迁移；升级备份停写，撤入口保历史。真实空/有数据往返及源矩阵待验，不把Schema当原子改密PASS。

## DEC-20260927-310

- Executed：9新增unit/1357 tests无失败（2既有跳过），严格immutable first/最小公开响应/两密码独立匹配与冲突/非bool异常/全部缓冲擦除通过，实际Scrypt内存两凭据及交换/重复旧/UTF8空格差异通过；wheel723773。无本轮PG/HTTP运行，内存source非持久来源/原子改密证明，下一Schema A02。

- A12P03A01 precode见progress；CR-AUT007内首次结果/source proof前置。私有前后Credential/User版本、Audit/trace与时间/撤销count，公开只新credential_version；重放两密码真来源分别验证，不保存明文/快速摘要/新Key，finally清缓冲。无Schema/HTTP/依赖、未授当前权限；后续A02持久来源再原子服务，完整改密Scope保留，测试待。

## DEC-20260927-309

- Executed：1348 tests无失败（2既有跳过），Windows真实PG/Scrypt普通false及受限login/GET/renew true-NONE-空项目、ForbiddenProjects未调用/业务404、坏旧Token或错User拒绝、精确源503不回退/受限logout通过；原状态/发布回归及wheel721845通过。TEST_ONLY凭据追加非实际改密，完整密码流程/正式信任/包未完成。

- 补充：保留冻结Session续期，受限续期只轮换受限身份、不清当前Credential标志/不授业务权限，严格能力白名单加入SESSION_RENEW；不是将临时凭据换为正常凭据。

- A12P02 precode见progress；CR-AUT007内非破坏boolean增量。login/GET/renew调用精确session projection，生产SQLview真实currentFact/共享锁绑定，无坏源fallback；required不读项目/输出NONE空项目，正常false。legacy opt-in adapter原resolve保兼容，无Schema/依赖，完整改密HTTP未完成，真实验收待。

## DEC-20260927-308

- Executed：1346 tests无失败（2既有跳过），真PG/Scrypt must-change会话五原业务proof拒绝七表不变、精确currentFact，TEST_ONLY normalCredential3使旧Session拒绝/新Session正常且历史保留；Windows状态链及原发布回归通过。历史漏洞脚本改为反回归，e8349c5证据保留。公开身份投影/改密HTTP/完整安全流程未实现，下一P02，不标全包PASS。

- AUT-04-A12-P01编码前检查见progress；CR-AUT007先登记。精确当前Credential事实及统一正常凭据谓词接部署读写/项目读写/Review五proof，Session身份不等于业务权限。无Schema/API/依赖变更，保正常登录；改密流程/reset不开放。真实权限矩阵/正常回归待验。

## DEC-20260927-307

- AUT-04-A12：实际隔离PG Credential2 must_change=true + 真Scrypt Session签发/校验/原Admin-CSRF proof仍成功，确认强制改密缺口，不标安全PASS；原Credential1保留、角色为TEST_ONLY，原发布回归通过。
- 先CR-AUT007记录选定受限改密Session/当前凭据事实/业务Ports实时拒绝，先完成改密再公开reset；真前后凭据校验历史幂等，不持久化快速密码摘要。无本轮生产代码/Migration/依赖；下一A12P01，完整修复/HTTP/包未实现。

## DEC-20260927-306

- Executed：1344 tests无失败（2既有跳过），actual Windows write Factory P04矩阵与HTTP创建/Scrypt登录/NONE拒绝/停用旧401/启用新200同UUID/旧不复活/首响应重放八表不变通过。readonly405/default-login404；五实际构造故障静态拒绝及dispose、缺正式信任拒绝，旧名称/原发布回归和wheel719469通过。初始readonly404误断言修正记录见progress；正式材料/性能/三平台/UI/包/Gate待。

- AUT-04-A11-P05：P04 f19e61f前置已验，编码前检查见progress；仅Windows显式write构造真实User状态依赖/router，原信任锚无fallback，readonly/login/default关闭。无Migration/依赖/权限变化，撤接线保历史；实际Factory/登录会话/构造故障矩阵待验，非生产/包PASS。

## DEC-20260927-305

- Executed：1344 tests无失败（2既有跳过），实际PG/Scrypt/ASGI两命令/历史首响应/角色-CSRF-Origin-License-version-Key拒绝七表不变、实际Audit后回滚、自停用Cookie/旧401/新认证重放不删Cookie及提交后末读503原Key恢复通过，原发布回归与wheel719338通过；验证SQL字段修正记录见progress。Windows/正式信任/性能/包未验。

- AUT-04-A11-P04：编码前检查见progress，P039e9f9c3真实原子链为前置。可选冻结状态POST，空body/严格Key/If-Match/当前Session-CSRF/Origin，安全首View；状态冲突映射冻结AUTH_USER_DISABLED409。
- 自停用实际当前Session复查才清Cookie，不根据历史结果误清重新启用后的新Session；确认读取故障静态503，原Key恢复。无Migration/依赖/Windows挂载；撤router保历史。真实HTTP和故障矩阵待验，不标PASS。

## DEC-20260927-304

- Executed：1336 tests无失败（2既有跳过）；真实PG/Scrypt同Key启停/不可变首响应、全Session撤销和旧Session不复活、七个实际写后故障回滚、提交前后故障与原Key恢复、自停用及重新认证重放、最后Admin/互停竞争、实际55P03锁超时及登录竞争通过，原双Scope发布回归通过。开发wheel717520；HTTP/Windows/性能/正式信任/完整包待，证据及夹具修正见P03progress。

- Date/WBS：2026-09-27 / AUT-04-A11-P03，precode见progress；P02实际0047/历史与旧回归87ad5b0。
- Decision：新Auth状态部署事务锁先Admin/target、lock_timeout5s；严格实际当前Actor proof、自停用有另一Admin且原Session生命周期/Token-CSRF/撤销reason-time-version和User原凭据角色/预期更新专用末核。全Session含expired同User updatedAt撤销、Audit/first/receipt同UOW；current authority与License重放再核。
- Impact/Rollback/Tests：无Migration/API/依赖/Key变化；撤未挂内部入口保0047历史。原Guard独立UOW，其他Auth锁竞争可能安全失败；真实并发/原子写后/commit确认/自停用/最后Admin/旧Session矩阵待验，不标正式权限/性能/完整包PASS。

## DEC-20260927-303

- Executed：1328无失败（2既有跳过），真空/有数据0046-47往返十一旧表保留/ORM一致；精确User/Credential/Audit/时间和未来accepted拒绝、真实2Session（含expired）撤销计数源/未撤销拒绝、插入后故障回滚/ENABLE零计数不复活、历史变更和非空down拒绝head完整；旧create/cancel/retry Schema及Windows名称/原发布回归/wheel711157通过。仅Schema/TEST_ONLY夹具，非当前权限/原子启停/完整包证明。

- Date/WBS：2026-09-27 / AUT-04-A11-P02，precode见progress；CR-AUT006先记录、P0143fd926。
- Decision：独立状态first表/ORM/0047精确User/Credential/Audit/time源，不修改0046；disable无active Session且撤销count对同updatedAt+USER_DISABLED源，enable0。immutable历史与非空down拒绝；不回填旧状态。
- Impact/Rollback/Tests：新增Schema但不新增权限/API/依赖/Key；原冻结保留，升级备份停写，撤未接线入口保历史。空/有数据往返、source拒绝/真实Session计数/不可变/ORM/旧Schema回归待验；非App授权/状态原子/正式供给/完整包PASS。

## DEC-20260927-302

- Executed：9新unit/1328无失败（2既有跳过），纯启停/版本/凭据/最后Admin规则与严格immutable首结果DTO通过，开发wheel708803。无DB/App/Session写/权限HTTP，未跑状态PG/HTTP集成，不标安全或完整功能PASS；CR-AUT006设计选定未整体实现，下一Schema0047。

- Date/WBS：2026-09-27 / AUT-04-A11-P01，precode见progress；已核冻API I/M/A与User/Session约束，现有仅createfirst不能表示状态首次响应。
- Decision：先CR-AUT006记录独立immutable statefirst+原receipt原子方案；纯转换/DTO先验。启停完整范围，最后Admin保护；自行停用有其他Admin时支持，不能直接跳过最终Auth，未来专用同事务证明。新增保护不是原冻结已确认条文。
- Impact/Rollback/Tests：本轮无Schema/API/依赖变；撤未接线纯Domain/DTO保历史。类型/转换/版本/计数/source/time待unit，DB/App/全Session/自停用/并发/HTTP/生产未实现，不冒充安全PASS。

## DEC-20260927-301

- Executed：1319无失败（2既有跳过），actualFactory名称PATCH真实HTTP全矩阵、旧登录401/新登录200同身份/原Session有效、NONE拒绝/首创建重放七表无写；readonly405不构造、三write构造fault实际到达/安全拒绝及unit dispose、default-login404/实际缺正式信任拒绝。旧Windows创建完整链与原发布/wheel706776回归通过；无Schema/依赖/权限/Key变化，正式供给/性能/三平台/UI/包待。

- Date/WBS：2026-09-27 / AUT-04-A10-P03，编码前检查见progress；P02 fff5e83真实HTTP通过。
- Decision：User名称PATCH仅Windows显式write挂载，复用原UOW/Admin-CSRF/License/Audit；readonly GET-only405，login/default404，不新增Key或fallback。
- Impact/Rollback/Tests：无Schema/依赖/权限变；撤接线保历史；actualFactory完整HTTP矩阵、新旧登录/原Session、构造fault真实到达/dispose/缺正式信任拒绝待验。正向合成材料，非正式供给/性能/三平台/包PASS。

## DEC-20260927-300

- Executed：7新Contract/1319无失败（2既有跳过）；真Session-CSRF/PG PATCH安全200/版本及no-op、历史first201对currentGET、禁用名唯一与状态保留、权限输入License拒绝六表不变/实际Audit后故障回滚；P01与原发布回归/wheel706685通过。默认404，Windows/正式供给/性能/包待。

- Date/WBS：2026-09-27 / AUT-04-A10-P02，precode见progress，P01 e26ce1b真PG通过。
- Decision：可选冻结User PATCH细化单username输入，不接受canonical/actor/role；原严格JSON/Origin/Session-CSRF/If-Match/safeView，内部当前Admin/License再次授权。无幂等Key要求，不改变冻结API或生产装配。
- Impact/Rollback/Risks：无Migration/依赖/权限变化；撤可选router保历史。未知提交确认GET核对，不盲重试；实际合同/PG测试待执行，Windows/正式信任/性能/三平台/包不标PASS。

## DEC-20260927-299

- Executed：7新unit/1312无失败（2既有跳过）、真PG规范化/禁用唯一/同版本竞争/新旧名称查找/no-op和stale、原Credential/Session/first/receipt保留和创建重放；权限与License拒绝六表不变、实际Audit写后/末尾License/真实Session撤销全回滚、不一致源拒绝、原发布回归/wheel705209。撤销夹具先缺原约束字段，修夹具重跑，不改生产安全。HTTP/正式供给/性能/三平台/包未完。

- Date/WBS：2026-09-27 / AUT-04-A10-P01，编码前检查见对应progress；输入冻结User/SC-02/API-02及0046。
- Decision：完整用户名修改复用原NFC/trim/casefold规范化；全局唯一含禁用身份，版本先于no-op；当前Admin-CSRF/License前后核验，变更与USER_NAME_CHANGED审计同事务。保留密码/状态/角色/Session及不可变首次创建历史。
- Impact/Rollback/Risks：无Schema/依赖/权限或Breaking API变化，不开放HTTP。旧名称不是永久保留别名；登录改用新名称。源不一致拒绝，no-op不写；死锁/DB/提交确认故障安全拒绝，Guard非同业务事务锁。撤未接线服务不回写历史；实际测试待完成，不标发行PASS。

## DEC-20260927-298

- Executed：1305无失败（2既有跳过）、actualWindows write HTTP完整创建重放和真登录Cookie/Session、NONE不能创建/七表无写、readonly405不构造新依赖/four write故障到达+unit dispose/default-login404/实际缺正式信任拒绝；旧User列表/Windows retry+混排及发布回归/wheel702222通过。修正仅validator冻结嵌套User字段断言，未改合同；正式供给/三平台/性能/安装包未验。

- Date/WBS：2026-09-27 / AUT-04-A09-P05，P04前置dc4da7a；precode见对应progress。
- Decision：User创建只接Windows显式write，用当前原Scrypt与Auth actual repo/first/replay/currentAdmin/Audit/receipt/License，无新Key或fallback；readonly GET-only405，default/login404。
- Impact/Rollback/Tests：无Schema/依赖/角色/Breaking变；撤新wiring保0046历史。actualFactory HTTP+真实新User登录、构造实际到达fault/dispose及缺正式信任拒绝/旧列表写回归；正向信任合成，正式账户/三平台/性能/包待。

## DEC-20260927-297

- Executed：六新Contract/1304无失败（2既有跳过），真PG HTTP201/强首ETag/同Key与密码用户名冲突/实际新凭据Session/后续停用v2对首201v1/权限格式拒绝六表无写与postAudit全回滚、原P03及发布回归/wheel702043通过。无Migration/权限/依赖/Breaking；默认404、Windows写装配和正式供给/性能/包未完。

- Date/WBS：2026-09-27 / AUT-04-A09-P04，P03前置eef52f1；precode见对应progress。冻结API02未枚举创建body完整字段，细化为username/password（write-only），保显示username服务端canonical/角色默认NONE，无Breaking。
- Decision：16KiB严格JSON/Origin-Host/Session-CSRF/Key，可选POST调用实际P03；共享Auth safeView投影并强制首次shape，Location/ETag/no-store；用户名冲突用已有CONFLICT_DUPLICATE，未知故障503。无Schema/权限/依赖，默认/Windows暂不挂。
- Tests/Rollback/Risks：真实PG HTTP幂等/原密码/后续停用重放/权限/六表无写、contract输入/异常/清理；撤router保历史，框架秘密副本/性能/正式供给/完整包待。

## DEC-20260927-296

- Executed：八新unit/1298无失败（2既有跳过）；真PG/Scrypt/currentAdmin-CSRF原子创建、同Key单身份/不同密码竞争冲突、后续停用换密返原view六表无写、九actual postwrite fault到达并回滚、末尾实际Session撤销/expiry及commit前/后确认故障/同Key恢复、原密码/发布回归/wheel700157通过。首轮commit proxy夹具错已修并加到达断言，无生产放宽；仅内部命令，HTTP/生产/性能/包待。

- Date/WBS：2026-09-27 / AUT-04-A09-P03，前置P01/P02同步ddd3f82，precode见对应progress。
- Decision：新当前Session-CSRF/Admin命令同caller-UOW原子Auth/Audit/receipt/first；规范化非秘密fingerprint必须加原Credential1密码证明才能重放，当前权限/License结束再核，旧入口不动。复用现有Auth Admin-CSRF策略具名Adapter，无新权限。
- Impact/Rollback/Risk：无Schema/API/依赖变，撤入口保历史；既有LicenseGuard自有UOW只证明前后检查，非业务同事务锁。KDF锁耗时/20并发/提交确认故障/正式供给/HTTP/完整包需真实后续证据。

## DEC-20260927-295

- Executed：八新unit/1290无失败（2既有跳过）；实际PG+真实Scrypt原1密码/UTF8精确变化、后续改名停用换2仍原1重放技术证明，伪造源/坏metadata beforeKDF/实际KDF故障静态拒绝及六表无写/清理、原Schema和发布回归/wheel696766通过。当前授权/完整请求receipt原子创建仍P03，未挂HTTP或宣称完整登录/生产/包/Gate。

- Date/WBS：2026-09-27 / AUT-04-A09-P02，前置0046真实验证并推送0c0422d；precode见对应progress。
- Decision：Auth只读原首次结果与Credential1固定source，私下严格SCRYPT V1 metadata检验再用原真实Verifier。坏源/格式/KDF故障不可用，精确UTF8密码不匹配才CONFLICT_IDEMPOTENCY；消费proof各路径尽力擦除，无hash公共DTO或新的摘要/key。
- Impact/Rollback/Tests：无Schema/API/权限/依赖变；撤未装配Port保历史。真实Scrypt+目标后续改名停用换密后仍核原1/五表无写、伪造源/非法proof/Verifier异常验证；当前Session-CSRF/License/完整请求receipt仍P03，性能/生产供给/包未完成。

## DEC-20260927-294

- Executed：5新unit/1282无失败（2既有跳过），实际PG空/有数据up-down-re-up十旧表保留、ORM parity/错误来源拒绝/真实插入回滚/三不可变/后续改名停用历史不变/非空down保0046；原retry/取消Schema及双Windows列表/发布回归、开发wheel694351通过。仅内部Schema，不是Scrypt/授权/原子幂等/HTTP/完整包证明。

- Date/WBS：2026-09-27 / AUT-04-A09-P01；编码前检查见对应progress。前置CR-AUT-005，0045 head；仅Auth首次结果Schema/ORM/严格DTO，不挂POST。
- Decision：复合FK原Credential1、原creator/Audit精确绑定与目标User行锁；首次ENABLED/NONE/version1/lock1安全快照、DB有限有序时间；无密码/hash/canonical/快速摘要，不回填旧User。不可变三触发器，历史非空down拒绝。
- Impact/Rollback/Tests：新增0046不改旧迁移；空/有数据往返、ORM parity、错误源/时间/重复/变更/回滚/历史保护验证；Schema不是授权或密码证明。撤新入口保历史，实际Scrypt/Session-CSRF/原子receipt/HTTP及最终包待后续。

## DEC-20260927-293

- Date/WBS：2026-09-27 / AUT-04-A08，实际旧User创建无Session-CSRF生产装配/原子receipt/不可变首次UserView，先CR-AUT-005，公开POST暂不开，不标PASS。
- Decision：receipt非秘密字段指纹+不可变初始Credential1真实Scrypt验证组合证明重放密码一致，拒绝仅username/明文或快速密码摘要；无需新增密码fingerprint密钥。Auth owned首次结果记录/FK/安全快照与原子命令后续实现，保原入口/冻结历史，默认新User NONE、不顺手提权。
- Impact/Rollback/Tests：拟0046需正式Schema/ORM/空有数据up-down/不可变/来源/已有历史down拒绝，撤新入口保历史；真实Scrypt/当前Session-CSRF/Admin/License/同Key并发/密码变化冲突/停用历史重放不复活各子项实测。当前仅设计，无生产迁移或新命令PASS。

## DEC-20260927-292

- Executed：1277无失败（2既有跳过）、两actualFactory真PG加密分页/每项ETag/当前权限五表无写、三dependency故障各模式实际调用/dispose、其他正向信任下实际固定User key缺失仍拒绝；default/login404。25相关实际验证入口exit0（23历史fixture补显式synthetic User key），wheel691255通过。新必需KeyRef升级/回滚已记，无生产fallback；正式账户/性能/完整管理面/Gate待。

- Date/WBS：2026-09-27 / AUT-04-A07，A04～A06前置。两显式platform挂User列表，独立user-list-cursor-v1强制来源，不借已供给Job/Secret key。缺Source拒绝半启动并dispose。
- Impact/Upgrade/Rollback：新必需KeyRef是显式平台升级前置，目标账户按原交互工具独立供给备份；撤列表接线回滚保历史，默认/login继续关闭。无Schema/角色/依赖/Breaking路径变；历史正向fixture需明确合成key补注入，禁止生产fallback。
- Tests/Risks：两actualFactory真PG分页与实时权限/无写、三constructor/source故障/实际缺正式材料拒绝，相关历史Windows回归；不外推正式账户/三平台/性能/完整管理/包/Gate。

## DEC-20260927-291

- Executed：3新测试/1276无失败（2既有跳过），实际本账户随机Vault失密/错误口令/防覆盖/恢复原key旧token/清理通过；A05真实PG HTTP和原发布回归/wheel691195通过。正式引用未供给、Windows列表尚未挂，无新Migration/依赖。

- Date/WBS：2026-09-27 / AUT-04-A06，User-list cursor独立user-list-cursor-v1，只读当前Windows账户Vault来源；缺钥/异常必须拒绝，无自动替代。
- Reason/Impact/Rollback：A05公开列表不能用测试key或借Job key作为生产信任；复用既有交互供给/备份机制，无Schema/新依赖/权限/API。停用新入口回滚保历史。
- Tests/Risks：实际随机临时Vault引用先确认不存在、失密/错口令/防覆盖/原key恢复旧cipher并自身清理；正式引用不供给，不把本账户测试当目标运行账户/三平台/完整包PASS。

## DEC-20260927-290

- Executed：3cursor+5Contract/1273无失败（2既有跳过）；实际PG加密完整多页/七同timestamp UUID稳定、跨真实Session页size/篡改/撤权限License拒绝五表无写，旧Windows详情与发布回归/wheel690520通过。公开列表可选/default404，Windows来源/挂载未完；无新Schema/依赖/角色。

- Date/WBS：2026-09-27 / AUT-04-A05，前置A04实际稳定分页。选Auth独立AESGCM cursor，不跨模块复用Jobs内部code；既有cryptography依赖，无新组件。Session摘要/page_size/family绑定，nonce随机/位置密文，当前权限每页核验。
- Impact/Rollback/Tests：可选冻结User列表GET、两query/no total/safe UserView，与详情共享投影；default/Windows暂不挂。无Schema/角色/依赖/Breaking，撤router保历史；真分页/权限/无写、cursor篡改跨context-key/恢复与源异常；正式来源/性能/全管理/包待。

## DEC-20260927-289

- Executed：六新unit/1265无失败（2既有跳过）、实际PG七同timestamp UUID tie稳定分页/空末页/停用目标可见、撤会话角色License拒绝五表无写，旧Windows详情与原发布回归/wheel687737通过。首次test引用失败改package相对引用完整重跑，仅内部列表，非HTTP/性能/完整管理面。

- Date/WBS：2026-09-27 / AUT-04-A04，固定User安全列表内部分页，沿A01 current Admin owned事实锁/License；目标仅metadata一次SQL快照，不共享锁整页，避免无必要全页锁与跨管理员列表锁序。
- Decision/Impact：created_at/user_id倒序有界keyset/n+1，含DISABLED目标，严格typedPage排序/唯一/位置边界，每页实时授权。无Schema/依赖/角色/公开API；分页位置私有，公开cursor/来源/索引性能另任务。
- Tests/Rollback：真PG同时间tie/完整分页/空末页/撤权无写/异常源unit，旧详情回归；撤服务保历史，非固定快照/性能/完整管理面/包/Gate证明。

## DEC-20260927-288

- Executed：1259后端无失败（2既有跳过），两真实Windows Factory完整User HTTP权限/版本/五表无写、三构造fault各模式明确被调用并dispose/实际缺正式材料拒绝、login/default404与旧Windows混排发布回归通过；wheel686148。无新Schema/KeyRef/依赖。正式信任合成；完整管理面/性能/Gate未完成。

- Date/WBS：2026-09-27 / AUT-04-A03，A01/A02前置。两显式platform User详情使用原Auth Admin owned访问与License Guard，不新增供给fallback；login/default不挂。仅详情，列表/写任务独立。
- Tests/Impact/Rollback：实际Factory/当前权限/元数据版本/五表无写/构造异常和缺正式信任拒绝半启动、旧路径回归；无Schema/API路径/依赖/角色变，撤接线保历史；正式供给/性能/三平台/完整管理面/包未验。

## DEC-20260927-287

- Date/WBS：2026-09-27 / AUT-04-A02，前置A01真实Reader。可选冻结User GET仅explicit router，无默认/Windows装配，Session.validate区分失效401，当前非Admin/未知target404；不利用缓存绕当前授权。
- Impact/Rollback/Tests：UserView仅既有安全metadata与独立lock_version ETag，GET无CSRF/写/Session续期，错误静态；无Schema/角色/依赖变，撤router回滚保历史。真实Session/权限/目标禁用/版本分离/无写及契约测试，正式材料/性能/完整包待。

## DEC-20260927-286

- Executed：6新unit/1253后端无失败（2既有跳过）、实际当前Session/Admin/目标停用可读与已撤Session/管理员降权停用/未知目标/License拒绝五表无写、原文件发布回归与wheel684687通过。撤销夹具初次缺合法reason/version被触发器拒绝，补齐原shape重验，不改保护。仅内部详情，HTTP/完整管理面/交叉锁性能待。

- Date/WBS：2026-09-27 / Phase2 AUT-04-A01；P05内部收口后回到冻结User管理缺口。选独立最小投影/只读Repository，不复用创建Service或整行ORM响应；当前Admin与License每次再核。
- Reason/Impact：已有User/Credential及生产Session，但缺管理详情读取；账户DISABLED仍是管理可见事实，不需读取密码表。无新Schema/API/角色/依赖，后续写幂等/列表/HTTP独立任务。
- Rollback/Tests：撤新Reader调用保历史；单位权限/异常/字段边界及实际PG当前Admin/禁用目标/撤权/无写，不宣称完整管理面/性能/Gate。

## DEC-20260927-285

- Executed P05-A：1247后端无失败/2既有跳过；真实双Scope Windows write HTTP新Job→实际Worker成功/首次v0重放、write/detail-list提示一致/readonlyfalse与405/PM降IMfalse/七构造拒绝无写，旧混排Windows/发布回归及wheel682697通过。首个角色fixture错名由Schema拒绝，修正正式名称完整重测。P05-B真实Doc无retry/坏源与非临时分类/归档和客户矩阵待，整体不标PASS。

- Date/WBS：2026-09-27 / Phase2 JOB-03-A02-P05；CR-JOB-006/0045/P04前置。Windows仅显式write挂双retry，ReadOnly/default/login不放写。
- Decision：写模式详情/列表共用Audit原失败Source和当前Project Export PM证明显示retryable，受权DEPLOYMENT Admin沿已验当前Admin事实；不把GET提示当CSRF权限。归档Audit Export维护例外仍遵循现冻结规则。缺source/构造/信任失败拒绝半启动，旧所有Owner registry保留。
- Tests/Risks/Rollback：真实Factory/Scope/角色/原源/新Worker/重放/错误拒绝及旧路径回归；撤接线保历史。不关闭三平台/正式材料/完整Scope/Gate。

## DEC-20260927-284

- Executed：双Scope真实HTTP新Job→Worker文件成功→GET当前与原PENDINGv0重放/十五表拒绝不写通过；用当前新Job ETag/新Key明确验证JOB_NOT_RETRYABLE，不误以幂等/版本冲突代替。5+5新测试/1239后端无失败（2跳过）及wheel681969；默认/Windows未挂、Doc unsupported只unit。下一运行与metadata。

- Phase2/JOB-03-A02-P04，2026-09-27；CR-JOB-006/API-03/0045/P03前置。可选双路径retry；严格空JSON，客户不得传Scope/Owner/路径。
- Decision：当前Session-CSRF/License及现安全Job详情Source再显式Owner分派，Audit写UOW全授权；已知受权无retry Owner409、隐藏/未知404，不让hint或读权限代替写权限。运行目录补冻结JOB_NOT_RETRYABLE码；安全首次新JobRef/state-v0/时间/链接，不透传内部lineage。
- Tests/Risk/Rollback：HTTP输入/错误/权限/实际Worker新成功后历史重放；默认和Windows此项未挂。撤可选Router/Adapter回滚保数据历史，公开retryable下一接线验证。

## DEC-20260927-283

- Executed：真实双Scope第三失败→并发受权新generation→新Worker实际文件成功→首次响应重放，旧终态不变；版本/Session/CSRF/Scope/角色/License及postAudit/lineage/receipt故障十五表回滚。1229后端无失败/2跳过、wheel677500；内部CSRF预期纠正ACCESS_DENIED、P02观察器改当前source零关系保全快照。HTTP/metadata待，不算完整包/Gate。

- Date/WBS：2026-09-27 / Phase2 JOB-03-A02-P03；CR-JOB-006/0045/原失败Port前置完成。现Owner当前Session/CSRF/License及PM export/Admin授权逐次再核；无新角色/Schema/API/依赖。
- Decision：同事务固定原源、receipt指纹含原Job/query/version，新Export/Job/Outbox/两Audit/Acceptance/immutable lineage原子保存，最后再授权。重放保首次Job/版本0而非当前状态；新Key才新generation，旧终态不变。不让通用Job权限覆盖更严格Owner规则。
- Tests/Risk/Rollback：真实PG/Worker失败→新Worker成功/并发幂等/历史响应/授权/强版本/写后故障回滚；关未公开入口保历史。公开retryable/HTTP待后续，不把内部命令视完整交付。

## DEC-20260927-282

- Executed：真实双ScopeWorker第三失败/版本/原pair/Audit及重复事件歧义-错误Attempt窗口拒绝十一表无写；7新unit/1223后端无失败（2既有权限跳过）、开发wheel674156与原Worker/文件发布回归通过。无Migration，未挂API/改retryable，下一P03当前授权+原子generation/receipt。只读来源PASS不是用户重试功能PASS。

- Date/WBS：2026-09-27 / Phase2 JOB-03-A02-P02，CR-JOB-006/0045前置完成，只新增只读原失败来源。
- Decision：Jobs owned结合原queue绑定、expected_version、第三真实Attempt/释放Lease/既有终态retry proof返回最小技术DTO；Audit own精确唯一历史SYSTEM失败Audit（固定Scope/actor/trace/window）。不让Audit读Jobs表、不让坐标替代当前Auth/License，不要求读历史事件时持当前Worker身份key。
- Validation/Risk：真实Worker5/15秒第三失败双Scope、原源/版本/状态拒绝无写、typed DTO与全后端；历史Audit proof不是新generation业务授权。新Port不挂HTTP，P03当前权限/receipt未完成；撤未接线Port回滚保历史。

## DEC-20260927-281

- Phase2/JOB-03-A02-P01，2026-09-27；前置重试核查/0044，CR-JOB-006先记录。只实现Audit不可变新old generation/首次版本Schema及DTO，无命令/API/角色/依赖变化。
- Decision：Audit owned Root/Acceptance/Audit来源trigger逐坐标、query/policy及Scope/actor/trace/时序校验，不读取Jobs私表；实际Jobs FAILED/Attempt/expected_version由下一owned Port提供。首版本固定0且新旧Export/Job不同，源可有多个generation；通用receipt后续原子编排，不在Schema中伪造授权。
- Risks/rollback：空表可down，有历史拒绝不可恢复drop；旧数据不补假来源，停入口回滚保历史。全部测试必须实际执行，Schema可合成Audit fixture但不据此宣称用户重试功能通过。

## DEC-20260927-280

- Date/WBS：2026-09-27 / Phase2 JOB-03-A01内部重试前置切片，对应冻结Job受控重试，不新增Scope。
- Evidence：Worker retry仅RUNNING原Lease；Audit enqueue实际回放相同原Job/Event不写；双Windows Factory当前成功Job retryable=false，retry POST405未注册。真实库无新旧generation链，直接开HTTP前置BLOCKED。
- Decision：先CR-JOB-006选择Audit owned不可变新generation/新Job原源/首次结果与同事务收据；禁止复活终态/裸复制payload。仅新增设计和验证，保0044；下一Schema评审，不把本核查当重试功能PASS。
- Tests/Risk/Rollback：实际临时库/双Factory原源和十八表无写、原混排/发布回归通过；首轮404假设纠正405 GET-only动态路由，不改生产。全后端/wheel为P05历史未重复。无生产回滚；未来lineage迁移必须阻止丢历史down、旧事实不改；其他Owner/正式材料/性能/Gate待。

## DEC-20260927-279

- Date/WBS：2026-09-27 / Phase2 JOB-01-A05-P05，前置P01～P04；仅显式Windows运行列表装配，不改Schema/冻结路径/角色/依赖。
- Decision/Reason：详情和列表共享显式Audit/Document Owner来源；强制独立Job-list cursor来源，失败关闭不借别的密钥。20旧正向fixture显式供给测试codec，保原断言；不能把缺新依赖而提前失败视为原路径验证。
- Impact/Tests：实际PG/双Factory/混排来源/稳定分页/权限License及十八表无写、新构造实际调用/释放、20旧脚本与1214后端无失败（2既有权限跳过）通过；wheel666922。无生产材料/三平台/性能/Parser/完整包/Gate证明。
- Rollback：撤两显式平台list wiring，保详情/历史；上线需独立KeyRef正式供给备份，缺失拒绝不自动创建。继续Phase2重试前置核查。

## DEC-20260927-274
## DEC-20260927-275
## DEC-20260927-276
## DEC-20260927-277
## DEC-20260927-278

- Phase2/P04仅新增同库Audit真发布+Doc真提交混合列表验收，原CurrentSession/Project/Admin和两Owner Port不变。Document PENDING available_at在临时库延迟避免原Audit-only最后claim误领，无生产时序变化。timestamp统一仅fixture用于UUID稳定keyset。
- 真实Worker Audit成功（不是SQL猜成功）/Doc PENDING、两Scope与Admin GLOBAL+DEPLOYMENT、IM/creator客户隔离/受限隐藏/License/坏actor拒绝十八表无写通过，原发布回归通过。无生产/Schema/API变化，unit/wheel沿用上轮未重跑；下一Windows列表挂载/失败关闭，CR/完整Scope/Gate待。

## DEC-20260927-277

- Phase2/P03固定Windows Job-list专用KeyRef只读入口，显式falsy resolver不走fallback；无Schema/API/权限/依赖/License变化。真实开发账户临时唯一Vault引用验证缺失/错误口令/禁止覆盖/加密备份原key恢复旧token，清理仅own引用及临时备份。
- 1213后端/2既有跳过、单独3新测试全部ok、P02实际HTTP15成功/10拒绝/1空延续回归通过。非正式账户材料/异账户/Server2025/运行接线/发行证明；下一Audit-Document矩阵再Windows挂载。撤只读入口保历史回滚。

## DEC-20260927-276

- Phase2/P02按CR-JOB-005以既有cryptography AESGCM保护Job-list隐藏坐标、专用Key/family-Session-project-scope-size绑定；不把完整性保护当保密、游标不授权限。可选冻结双路径GET/no-store metadata、稀疏页允许继续，default404，Windows密钥供给未接。
- 1210后端/2跳过、真实原列表Session/Scope/Source/分页矩阵经ASGI及十三表读不写、错context/tamper/密文不含坐标/恢复原key通过。无Schema/角色/依赖/Breaking；撤router/cursor可回滚保历史。测试key/License非生产；Audit/Windows/性能/完整Owner/Gate未完成。

## DEC-20260927-275

- Phase2/JOB-01-A05-P01按CR-JOB-005实现同UOW当前list授权、registry原source、Jobs-only有限candidate/keyset、customer只原actor。不可见资源允许空页继续，内部position私有，HTTP前加密游标避免泄露隐藏坐标。
- 原全权限矩阵加冻结LIST对应第27项、旧项保留；实际Session重复撤销测试碰immutable保护，仅拆独立会话不改DB。1201后端/2跳过及Document实际Scope分页/权限/坏源十三表无写通过；Audit/HTTP/游标/Windows/完整Scope待。无Schema或依赖变；撤内部list/policy回滚保详情和历史。

## DEC-20260927-274

- Phase2/P04仅Windows两显式platform注册Document Parse Job Owner、实际来源/结果/原Audit proof；原许可/当前权限、Audit Owner及default/login关闭保持。无Schema/API路径/依赖/角色改变。
- 先成功授权HTTP，再实际Factory与构造故障/真实正式信任不可用验证。Parser历史合成不冒充Worker/字节/质量，Document取消/重试不在本项注册。回滚撤registry及imports保历史。

## DEC-20260927-273

- P03成功结果：依据已存在0028 ParseRecord/ResultRef，Document owned Port精确核唯一成功记录、不可变result metadata/hash、原source及当前JobFacts时间/scope/job/version。公开仅DOCUMENT_PARSE逻辑parse_record_id，兼容原result类型；不得猜文档版本为结果、直接查Jobs表或把合成历史当实际Parser执行。
- Parse attempt为版本/profile序列，不猜Job attempt_count相等。无Schema/API路径/权限/依赖变化；增量文档留历史，撤新Port/Owner结果/type可回滚。实际Parser/Byte验证/质量/运行装配未由只读证明代替。

## DEC-20260927-272

后续验收：同原不可变actor、实际Session/current Project/Admin facts经原只读Service与可选HTTP双Scope读取通过，File/Version限制只在临时库执行且不假恢复。十三表读不写，无生产实现/Schema变化；合成License和TEST_ONLY密码记录不冒充生产登录证明。成功ParseRecord/运行装配依然未验，P03不整体关闭。

- Phase2/JOB-01-A04-P03：内部Owner先组合Jobs hint、Document/Audit原源、锁定原Queue pair，当前权限留AuthorizedJobReadService同UOW；不把hint/source当授权。未知SUCCEEDED实际ParseRecord证明安全拒绝，下一补真实结果核验，不猜文档版本为结果。
- 无Migration/API/角色/依赖变化；原Scope完整保留，尚未挂生产组合。内部PROJECT真实来源组合与1191后端/2既有跳过通过不代表当前Session、GLOBAL权限、Parser或整项P03完成。回滚撤内部Owner保历史。

## DEC-20260927-271

- Precode：Phase2/JOB-01-A04-P02，前置P01 Queue/original Upload Commit成立；Doc版本源与Audit证明是该单问题必要依赖，不跨模块私有SQL，详见document-source进度。无Schema/API/依赖/角色变更。
- Decision：Document owned Source锁并核真实上传/版本/文件/来源，Audit owned只读Port核唯一提交事件；不授当前权限/字节/解析结果。P01误用int32版本上限，实际Doc/Outbox bigint，先记录修正正bigint范围。
- Acceptance：真实GLOBAL/PROJECT完整提交来源/旧版本/错引用与当前状态拒绝无写，Source无路径/正文，原提交/Queue回归。当前Session/Owner投影下一项，回滚撤新只读入口保历史；证据待追加。
- Evidence：1185无失败/2跳过，真实PROJECT三次提交与GLOBAL实际私有文件staging/promotion/版本/原Audit/Job链通过，旧Version/错Scope/actor/version/trace/引用/Doc RESTRICTED/重复真实Audit来源拒绝九表无写，原P01/提交/文件与wheel通过。File/Version可见过滤已实现但专项实际限制未验，Access/License合成，不称当前Session/Parser执行/完整Owner通过；下一真实当前权限Owner投影。

## DEC-20260927-270

- Precode：Phase2/JOB-01-A04-P01，原Upload Commit/Parse enqueue/0044前置已验；Document Owner缺Jobs owned只读绑定接口，停止直接复用enqueue，拆前置Port后继续，非删Owner Scope。
- Decision：新增严格只读peek/find与Binding，Jobs owned核完整Job/Outbox/原trace与坐标；hint不授权，find不创建缺行。Document真实Upload/Version/File与当前权限下一项再验。无Schema/API/角色/依赖变化。
- Acceptance：单位安全/绝不enqueue、真实PROJECT提交来源读取与GLOBAL队列元数据分支/错pair/无写/原提交回归；GLOBAL队列不能冒充文件提交。撤新Port保历史回滚，证据待追加。
- Evidence：1181无失败/2跳过，原三次真实PROJECT Upload Commit→精确只读绑定、错Actor/Document/version/trace拒绝/缺Scope/ref不创建、八表无写；GLOBAL真实Queue元数据分支及缺Outbox孤立Job拒绝，无Doc原源/权限结论。原提交/文件回归与wheel通过，下一Doc-owned原源DTO/Repo/双Scope真来源再验，不冒充Parser执行或完整Jobs。

## DEC-20260927-269

- Precode：Phase2/JOB-02-A05，A04/0044/Windows提交与GET前置满足，详见windows-cancel进度；仅include_secret_write接项目取消，原信任/权限/事务依赖，无Schema/API/依赖变动。
- Decision：默认/login关闭404，readonly原GET匹配未支持POST405，Admin未提供取消POST；不新增stub。实际Audit取消Owner同UOW当前授权/来源/版本/首次receipt不变。
- Acceptance：实际Write Factory PG/Session两状态取消+Worker确认后重放与currentGET差异、拒绝无写/构造故障/正式缺材关闭，旧Windows提交/下载/发布回归。回滚撤write接线保历史，非正式材料/Gate/包通过；证据待追加。
- Evidence：真实Windows Write Factory提交PENDINGv0→HTTP取消v2；真实RUNNINGv1→HTTP请求v2→实际Worker确认/currentGETv3与原重放v2，拒绝十一表无写；三非写模式/无Admin取消入口、六构造故障与实际正式缺材拒绝半启动。旧Windows提交/下载/发布回归与1177无失败/2跳过/wheel通过。正向信任注入非正式账户，下一扩Document解析Owner前置，完整Jobs/其他Scope/Gate待。

## DEC-20260927-268

- Precode：Phase2/JOB-02-A04，A01～A03/0044与冻结API-01/03前置满足，详见cancel-http进度。只可选项目HTTP，无Admin/Schema/依赖/角色变化。
- Decision：Jobs显式Owner registry分派仅当前许可/Session后读hint、关闭只读事务后Owner原同事务再授权/绑定；Audit Adapter请求原JobId事务，严格首次版本非None。200状态/强ETag来自不可变收据，实时另GET，拒绝旧None而非猜值。
- Acceptance：严格JSON/Origin/Cookie/CSRF/Key/If-Match、默认/Admin404、真实PG权限/隔离/重放/版本/回滚。默认与Windows尚不装配，回滚撤可选入口保历史。结果待实际验证。
- Evidence：1177无失败/2跳过，真实PG-ASGI当前Auth/Audit Owner取消、HTTP同Key并发仅一次Audit、实际Worker当前v3 vs首次重放v2、当前权限/隔离/None/版本/指纹拒绝十一表无写、快照后故障回滚及分派后实际撤权Owner写UOW拒绝；原A03/发布与wheel通过。Admin仅取消Router404，原GET同挂405但无POST入口，首组合测试预期修正事实且不新增stub。下一只Windows write挂项目取消，正式材料/全Owner/Gate待。

## DEC-20260927-267

- Precode：Phase2/JOB-02-A03，前置A01/A02/0043及原授权/收据已验；CR-JOB-004在编码前登记。Audit owned最小版本快照ORM/0044/up/down，既有Audit事件仍唯一状态与Actor/Job来源，无API/依赖/角色变更。
- Decision：新JobId首次命令同事务读取实际锁版本并追加事件关联快照；重放保首次version，旧收据None不猜回填。不可变DB保护，含历史降级拒绝，公开HTTP不得接受缺版本。
- Acceptance：空/有数据up/down/parity、非法来源与immutable拒绝、真实状态变化后旧version重放/当前权限/故障全回滚及旧链路；只临时PG不生产。结果待证据追加。
- Evidence：1167无失败/2跳过；0044真实空/已有十表up/down/up、ORM parity/无猜回填、来源/不可变保护/含历史down拒绝；两Scope并发一快照、原请求v2→实际Worker当前v3重放state/v2、旧None保留、实际insert后十一表全回滚，旧A02/发布及wheel通过。首轮验证连接属性和精确metadata名单未更新已修复重测，详细失败保进度。INTERNAL_PASS，公开HTTP/正式材料/Gate待。

## DEC-20260927-266

- Precode：Phase2/JOB-02-A02，前置A01/0043和原Audit取消授权/收据满足；详见job-02-a02-owner-cancel进度。无Schema/API/角色/依赖变动。
- Decision：Audit owned不可变acceptance按JobId无锁预查原Root，同一取消UOW先当前原授权、后Root/pair锁并强核原受理JobId；强制显式expected_version，复用实际Root指纹，原export命令历史不改。不是generic未知Owner回退或HTTP公开许可。
- Acceptance：强类型/绑定/当前权限/双Scope真实状态与旧入口同Key去重/过期版本拒绝/回滚；公开完整响应快照与HTTP另验。回滚撤新Owner入口保历史；结果待实际验证。
- Evidence：1165无失败/2既有跳过；双Scope真实JobId取消/Worker确认、旧入口同Key去重、权限/指纹/过期版本/停用后重放拒绝十表无写、Audit故障回滚；原A01/发布回归及wheel通过。API-03仅冻结项目取消；GET才完整JobView，取消最小状态响应仍需首次强ETag版本，下一先CR补持久快照，不拼当前版本、不擅增Admin HTTP。

## DEC-20260927-265

- Precode：Phase2/JOB-02-A01；输入冻结API-01/03、0043与原取消授权/事务/收据，前置PASS。涉及Jobs事实和Audit内部取消；Job/Audit/receipt实体无DDL，公开API与权限不变。CR-JOB-003实施前登记。
- Decision：可选expected_version保留旧内部命令，显式版本绑定原指纹/operation；原持久重放先于版本比较，但始终当前授权。新命令锁内比较，冲突整事务回滚；owned锁定查询刷新数据库触发器版本，不猜加一。
- Acceptance：严格类型/范围、旧指纹、新版本冲突与旧版本重放、双Scope真实PG状态版本/审计失败回滚、原Worker确认/发布回归；无正式材料/性能/Gate/三平台/包通过。
- Risk/rollback：未来HTTP必须显式版本，None只兼容已有内部路径；回旧调用/代码保留历史，不生产迁移。结果待实际验证后追加。
- Evidence：1160无失败/2既有跳过；真实PG双Scope即时v2同UOW刷新、运行v1→请求v2→实际Worker确认v3、同Key并发单次/不同Key同版本仅一成功、终态只检查；版本/指纹冲突十表无写、原收据兼容、实际Audit后故障回滚。原请求/确认/到期取消及各原发布回归和开发wheel通过。结果INTERNAL_PASS，公开Owner/HTTP/正式材料/全Scope待。

## DEC-20260927-264

- Precode：AUD-03-A07-P02 windows-submit进度先记录，P01POST/原Submit/已接JobGET前置满足，只有原include_secret_write接Submit，默认/login/readonly关闭。
- Decision：复用真实事务Session/License/Project/Receipt/Queue/Audit，202不执行长任务。旧Windows下载回归写POST缺Origin预期改403，只读404不改，安全用例保留。
- Evidence：真实WriteFactory双Scope202→JobPENDING→generic真实组合Worker/实际Vault identity/heartbeat→SUCCEEDEDv2→原结果metadata/content SHA和size一致；重放/冲突/许可/项目拒绝与终态重放十表无写/单Attempt，STOPPED后静止dispose。三关闭模式404、三新构造故障及实际正式信任不可用拒绝半启动，旧下载/原发布回归通过。
- Impact：无Migration/权限/依赖/Breaking变化，撤写组合接线回滚；正向信任注入、Worker在验证进程内，非正式材料/独立服务端到端/UI/发行/Gate通过。下一JOB-02-A01原取消expected_version前置与同事务版本/幂等，完整Scope仍保留。

## DEC-20260927-263

- Precode：AUD-03-A07-P01 submit-http进度先记录，实际Submit/Receipt/JobGET前置满足，原冻结AUDIT_EXPORT路径/Role/错误码不改。
- Decision：可选POST严格8192 UTF8 JSON/白名单/aware日期原Spec、当前Session-CSRF+原事务重验，202固定原受理JobRef+export_id/status_url；重放终态不复活，实时状态另GET。scope冻结安全码正式注册，无本文正文/路径泄露。
- Evidence：5新Contract/1155无失败/2跳过，实际PG两Scope202/重复原refs无写/409/Session-CSRF-Origin-License/项目与角色拒绝；原Audit插入后故障十表回滚，原Worker真发布/GET SUCCEEDEDv2/终态重放保原受理且单Attempt，原发布回归通过。
- Impact：无Migration/权限/依赖变，默认/Windows尚未挂POST；撤可选Router回滚，原提交历史保留。下一Windows仅写模式接线；正式材料/其他Owner/性能/完整Scope/Gate/安装包待，不新增外发或生产操作。

## DEC-20260927-262

- Precode：JOB-01-A03 Windows装配进度先记录，原可选GET/Audit Owner/0043前置满足。
- Decision：仅原include_secret_read两显式工厂接任务详情，同原真实License/Auth/Project/Owner依赖；默认/login关闭，任何构造失败不发布半应用，不加测试密钥回退。
- Evidence：实际PG/ASGI双Factory双ScopeRUNNINGv1/SUCCEEDEDv2/原结果读取无写，401/403/Admin项目404、默认/login404；每工厂4新构造失败拒绝，撤正向测试来源后实际正式信任不可用拒绝且六业务表无写，旧metadata/content/腐坏拒绝/原发布回归通过。
- Impact：无本轮Migration/API路径/权限/依赖变，撤新Factory接线回滚；正向信任注入非正式账户/监听进程/浏览器/其他Owner/发行PASS。下一Audit导出POST复用真实提交与已接Job status_url，完整Scope/Gate保留。

## DEC-20260927-261

- Precode：JOB-01-A02-P02 GET进度先记录，0043真实版本满足前置，原API-01/03路径/Scope/权限不改。
- Decision：可选Router双Scope详情，原当前读取/Owner链、安全字段白名单、真实强vN/no-store；未知细分进度/检查点/原因null，不从payload猜。If-None-Match仍全授权，默认404；结果引用不授正文权。
- Evidence：5新Contract/1150无失败/2跳过，真实PG/ASGI原链8授权/13拒绝、六业务表读不写/真实状态与版本/原发布通过，条件请求撤销Admin401。首次脚本成功门槛误填10已据完整矩阵改精确8/13，保失败说明。
- Impact：无本轮Migration/依赖/权限变化、未接Windows组合；撤Router可选接线回滚，其他Owner/完整Jobs/If-Match/正式环境/浏览器/完整包/Gate待。下一A03 Windows显式装配后Audit POST。

## DEC-20260927-260

- Precode：JOB-01-A02-P01/CR-JOB-002，冻结API-01明确强v<lock_version>，发现Job缺字段后先Schema版本，不发布hash/弱ETag假兼容。
- Decision：新增0043/Job.lock_version与DB-owned业务UPDATE统一递增，heartbeat续租/同值更新不递增，手动版本/溢出拒绝；可信恢复INSERT允许历史版本。ORM/readDTO同步，旧Repo原授权不改。
- Evidence：真实空库up/down/up、有实际发布数据0042→0043旧业务六表保留/初始0；双Scope接受v0/claim v1/真实heartbeat稳定/publish v2，manual/overflow P0001事务无写。快照脚本排序/SQL重载类型错误按证据修正，失败保留进度，未改业务比较。
- Impact：新增Schema迁移，无公开API/依赖变；离线备份/停机升级，回滚须回代码并使旧ETag失效，不生产迁移。下一完整JobView/GET；If-Match/其他Owner/正式环境/完整包/Gate待。

## DEC-20260927-259

- Precode：Phase2/JOB-01-A01，CR-JOB-001在实施前记录；冻结通用Job详情授权链，不直接序列化ORM或以Job/Lease状态猜Owner结果。
- Decision：Jobs只读事实+显式Owner Registry，真实Session/License/Project/actor权限，同事务Owner原源绑定后再读快照；未知Owner/type失败关闭。Audit首个安全资源引用不授正文下载权；Project JOB_PROJECT_GET按冻结四角色/creator只读锁策略。
- Evidence：11新unit/1143无失败/2跳过，实际PG双ScopePENDING/RUNNING/SUCCEEDED、原发布Result、当前PM/IM/客户自身、Admin/项目隔离、User/Department停用/未知Session/错actor拒绝六表无写，原发布通过。初次新增测试边界和验证worker属性错误均记录后修正，不改领取语义。
- Impact：无Migration/API/依赖/升级，撤只读Service/Port/策略回滚。当前Audit Owner仅内部已验，不冒充通用HTTP/完整JobView/ETag/其他Owner/Gate/完整包完成；下一A02合同/版本前置后GET与装配。

## DEC-20260927-258

- Context：P06-P13-P08，当前acca660源码及真实验收记录；按项目Skill核对覆盖，不继续无界拆分已验有限调度子任务。
- Decision：有限隔离验收矩阵收口、CR-AUD-005整体保留复杂故障/部署风险；更新实际已完成耗尽/死锁说明。公开链先JOB-01-A01详情，再GET/装配/Audit POST。完整Jobs列表/写操作及其他Owner不取消。
- Evidence：Jobs无用户Read Service/API；Audit结果GET与内部submit存在但无POST；ORM无lock_version，不能以fencing或常数ETag冒充取消并发。原202要求可查询status_url；Owner权限/安全元数据必须先实现。
- Impact：本轮仅文档审查、未重跑代码测试，无Migration/API/依赖/升级，撤增量文档可回滚；用户不需作普通继续决定。正式材料/Gate/完整包不关闭。

## DEC-20260927-257

- Precode：Phase2/P06-P13-P07，CR-AUD-005，scan-window先记录保留拒绝游标/32动作回绕及新队首验证，原排序/权限/证明不改。
- Decision：成功调度保留最近拒绝位置，末尾或32次有结果动作刷新；只存常数技术状态，不无限排除坏行。窗口非秒数/吞吐/全局公平保证。
- Evidence：1132后端无失败/2既有跳过，双Scope各41健康完成，新高优先任务在31原任务完成后领取，坏技术行不动/STOPPED；混排步数91降25/拒绝78降12，旧末尾回绕与发布通过。新验证属性使用错误已修正并保留失败说明；开发wheel635273/SHA见进度。
- Impact/rollback：无Migration/API/依赖/升级；撤保留游标与刷新实现回滚，保旧入口/历史。CR-AUD-005/Gate3/正式材料/完整包不关闭；下一调度验收收口后推进公开Jobs HTTP前置。

## DEC-20260927-256

- Precode：Phase2/P06-P13-P06，CR-AUD-005，先记录mixed-loop进度，实际有限混排持续run与不可变请求Audit保护，不关闭trigger制造伪PASS。
- Evidence：两轮每轮12健康/4坏priority+1真实耗尽坏source，actual STOPPED，坏技术全行保原/健康全部发布；恢复测试源后发布、原第三代安全失败/actual lost-ack/旧字节/旧发布通过。Audit UPDATE实际P0001/六表无写；未证明真实Audit损坏恢复。
- Decision：每轮91steps/78rejections暴露claim清cursor后重扫开销，明确PERFORMANCE_NOT_PROVED，下一P13-P07先记录后优化回绕/新任务可见性，不能改优先级或无限排除。
- Impact/rollback：本轮仅验证/文档，无生产/API/Migration/依赖/升级，未重跑未变unit/wheel；撤脚本保历史。复杂故障/全局公平/正式材料/完整包/Gate仍待，CR不关闭。

## DEC-20260927-255

- Precode：Phase2/P06-P13-P05，CR-AUD-005，exhaustion-isolation进度先记录原单首候选风险/expiry游标/Owner只读原源预检和未知故障边界。
- Decision：旧peek/run默认保留，后台显式只读scan+固定技术拒绝，常数cursor/实例锁，拒绝后下一轮优先Claim；Source预检不授expire权，原Owner最终重验/真实证明保留，DB/identity/Lease未知错继续关/脱敏。
- Evidence：5新unit/1130通过（2既有跳过）；真实双Scope六场景第三次到期引用坏/缺Root/错pair精确reason，六表无写拒绝后健康任务发布，坏Job/Lease/Attempt全行不变；恢复合成源后原安全失败/actual commit-lost-ack/旧字节保留，真实CLI停止/旧发布/wheel635109通过。
- Impact/rollback：无Migration/API/依赖/升级，撤显式接线/新Port保旧入口和历史；长期混排/Acceptance真实矩阵/复杂Lease/预检竞争待，CR/Gate/正式材料/完整包未关闭。下一P13-P06混合持续循环及实际分类收口。

## DEC-20260927-254

- Precode：Phase2/P06-P13-P04，CR-AUD-005，在real-deadlock进度先登记局部检测时间/反向锁环、连续3次与55P03矩阵；不模拟错误取代真实PG证据。
- Decision：只验证脚本协调原UOW回滚后竞争释放，pg_blocking_pids核活阻塞；原真实分类器/3次上限不改，Worker生产timeouts保持原值。
- Evidence：双Scope6场景，8实际40P01（1+3各Scope）单重试成功/三次失败六表无写后同实例发布单Attempt/RELEASED/结果，2实际55P03非死锁/非SOURCE_REJECTED、无写失败后恢复；原发布回归通过。此前1125/2跳过保留，本轮不声称重跑unit/wheel。
- Impact/rollback：无生产/API/Migration/依赖/升级，撤脚本；耗尽坏源/Acceptance真实故障/复杂Lease/全局公平待，CR/正式材料/完整包/Gate未关闭。下一P13-P05耗尽坏源影响核查。

## DEC-20260927-253

- Precode：Phase2/P06-P13-P03-A02，CR-AUD-005，先记录source-admission进度，原claim入口/API错误码保留，只接明确原源分类与技术诊断。
- Decision：后台显式isolate_sources=True，实例锁/常数cursor在只读拒绝UOW退出后前移，正常claim/末尾清游标；SOURCE_REJECTED不写Job/Lease/Audit、不猜终态；Loop poll/拒绝数，CLI仅数量。未知DB/identity/commit仍原关闭/确认恢复。
- Evidence：6新unit/1125通过（2既有跳过）；真实双Scope格式错/零UUID/缺Root/错pair拒绝六表无写，后续正常发布/坏Job PENDING无Attempt，恢复原测试来源可发布；旧确认恢复/真实Windows CLI停止回归，wheel633740/SHA见进度。
- Risk/rollback：无Migration/API/依赖/升级，撤显式新接线保旧入口/冻结历史；对外AUDIT_UNAVAILABLE不改。Acceptance审计源真实矩阵/耗尽坏源/Lease不一致/反向锁序40P01/全局公平/正式材料/完整包/Gate待，CR不关闭。

## DEC-20260927-252

- Precode：Phase2/P06-P13-P03-A01，CR-AUD-005，先记录aud-p06-p13-source-cursor.md。范围仅Jobs owned Port，不跳过Root/身份/权限或猜终态。
- Decision：新增scan_next/typed cursor与reservation，按priority降序/available_at和JobId升序keyset，单次SKIP LOCKED一候选；原peek/reserve保留。仅确定格式/零UUID返回固定INVALID_EXPORT_REF，DB异常原失败关闭，原始payload不返回/不打印。
- Evidence：3新unit/1119通过/2既有跳过；真实双Scope跨两个坏ref到正常候选/末尾六表无写；旧admission仍坏源拒绝，恢复合成来源后实际发布及原发布回归通过；wheel632733/SHA见进度。
- Risk/rollback：無Migration/API/依赖/升级，撤新Port保历史；未接Admission/Loop，坏源整体仍FAIL，Root/pair/诊断/锁序deadlock待，CR/Gate/完整包未关闭。

## DEC-20260927-251

- Precode：Phase2/P06-P13-P02，CR-AUD-005先登记，aud-p06-p13-reservation.md检查原pair/identity/确认恢复保留与Job→Audit锁序风险。
- Decision：独立reserve_next SELECT FOR UPDATE SKIP LOCKED只预留不写，在Root前取得；原无锁peek不变，原授权/pair/current identity/claim/commit与lost-ack恢复不改。
- Evidence：3新unit/1116通过（2既有跳过）；实际双Scope两个只锁UOW不同候选/六表无写、锁优先head后续真实发布且首无Attempt、释放后首发布；原P03单claim竞争/回滚/代际与P06确认恢复通过、wheel631564/SHA见进度。
- Risk/rollback：无Migration/API/依赖/升级，撤reservation接线保历史；新版反向锁序实际40P01未制造、坏源仍FAIL，CR-AUD-005/全局公平/Gate/完整包未关闭。

## DEC-20260927-250

- Precode：Phase2/P06-P13-P01，先记录aud-p06-p13-queue-isolation.md，验证公平/坏源风险，不把缺陷复现当功能PASS。
- Evidence：真实PG队首锁55P03在SKIP LOCKED前中止/六表无写，坏payload同样阻塞正常第二；修复本轮合成来源后双方真实发布，原发布回归通过。
- Decision：依持续授权登记CR-AUD-005，下一先只锁不写SKIP LOCKED reservation、再有界坏源分类隔离；不吞全局DB/identity/commit确认失败、不伪终态、不改优先级。
- Impact/rollback：当前仅验证/记录，无API/Migration/依赖/生产代码改变；撤脚本保历史。P13-P02/P03未实施，公平隔离FAIL/完整包/Gate待。

## DEC-20260927-249

- Precode：Phase2/P06-P12-B02，CR-AUD-004/P11/P12-B01，先记录aud-p06-p12-pg-child.md。
- Decision：仅验证脚本映射临时Credential与Vault引用，真实Windows CLI/YAML/PG/固定Repo、独立隐藏Console；License替身显式测试，不改正式信任源，非秘密argv/env，无强杀。
- Evidence：六个实际子进程、双Scope真实发布/摘要/AVAILABLE/RELEASED/单Attempt/同Vault SYSTEM identity；缺正式公钥与idle六表无写，active外部CTRL_BREAK只排空第一任务/第二未领取，再once完成；原发布回归通过，临时来源已清理。
- Risk/rollback：无生产/API/Migration/依赖/升级改变，撤脚本保历史；非无限阻塞/SCM/正式License/完整包/Gate通过。下一P06-P13公平/坏源隔离。

## DEC-20260927-248

- Precode：Phase2/P06-P12-B01，CR-AUD-004，P12-A已暴露停止桥接竞态；先记录aud-p06-p12-stop-boundary.md。
- Decision：signal context提供精确bool只读Probe；Loop每次Step前正常栈request_stop，handler仍只置标志，保桥线程唤醒idle与原pending排空。无Schema/API/依赖变化。
- Evidence：禁桥线程确定性1执行/1领取STOPPED、Probe非法/异常无claim；1113通过/2既有跳过；恢复原长阻塞外部CTRL_BREAK测试通过，开发wheel631428/SHA见进度。
- Risk/rollback：内部扩展可撤，原冻结保留；不解决无限阻塞或尚未处理的信号；真实PG子进程/SCM/正式材料/完整包/Gate待。

## DEC-20260927-247

- Precode：Phase2/P06-P12-A，输入CR-AUD-004/P10/P11；独立外部Console验证先记录于docs/progress/aud-p06-p12-external-console.md。
- Decision：只创建隐藏新Console，发送器Attach指定本轮PID，清单严格仅双方后CTRL_BREAK广播；不向父Console投递，不强杀，不变生产机制。
- Evidence：外部idle/active可响应合成路径通过；1111后端通过/2既有跳过。首次活动长阻塞发生第二次ACTIVE，分段等待测试后通过，不冒充真实执行器修复。
- Risk/rollback：无Migration/API/依赖/升级，撤验证脚本；P12-B真实PG子进程与长阻塞停止/桥接竞态待核查，SCM/正式材料/完整包/Gate待。

## DEC-20260927-246

- Precode：Phase2/P06-P11，CR-AUD-004/ADR011，原Windows固定信任与generic组合/信号已验；实施前记录普通License runtime不接受有界Worker的兼容差异和最小专属入口，无签名字段/权益/Schema/API/依赖改变。
- Decision：保原函数，Worker函数仍固定product/machine/integrity/_assemble；Windows CLI固定账户源无秘密argv/env，缺源关、--once LIMIT非就绪，Application quiescent接口锁Loop/Step/真实全部HB，活线程拒绝dispose，无强杀。
- Evidence：5新unit/1111无失败（2权限跳过），实际临时Windows Credential/Vault+PG18当前Schema，真实包内公钥缺失失败关闭/六表无写和构造资源释放；明确合成Guard下实际Windows工厂经process adapter双Scope准入/heartbeat/物理发布/当前User撤权安全失败/stop无写、静止关闭，原发布/wheel通过。正式License来源/密码未供给，不冒充完整签名复验；临时credential已删除。
- Risk/rollback：无Migration/API/依赖/升级，0042保留，撤新装配保历史。外部Console/SCM/真实网络黑洞/公平隔离/未知恢复/HTTP/质量/其他平台/完整包/Gate待，下一P06-P12真实后台子进程/停止收口。

## DEC-20260927-245

- Precode：Phase2/P06-P10，CR-AUD-004/ADR011，前置Loop/组合已验；编码前进度记录信号最小callback与桥线程，补Loop前另记Windows长等待信号延迟兼容偏差。
- Decision：signal只置标志不锁/DB/I/O；正常50ms桥线程请求原Loop停止排空，主线程注册/进程互斥/handler全恢复，恢复失败poison要求重启而非猜安全。空闲按50ms小段保原poll截止，让Python主线程及时执行handler；不强杀/自动dispose数据库。
- Evidence：7新unit/1106无失败（2权限跳过），真实解释器SIGINT定向由60.052s降至0.122s并断言及时stop/保poll截止，两个独立合成进程idle与活动命令排空/一claim/handler还原，真实PG组合及发布回归/wheel通过。非外部Windows Console Ctrl-C/Break/SCM或生产性能证明。
- Risk/rollback：无Migration/API/依赖/升级，0042保留；撤未公开适配保历史。活动阻塞I/O/外部Console/服务控制/正式来源/CLI/公平隔离/未知恢复/质量/完整包/Gate待，下一P06-P11安全来源及CLI前置核查。

## DEC-20260927-244

- Precode：Phase2/P06-P09，CR-AUD-004/ADR011，前置原安全Owner/单步/Loop已验；实施前进度登记固定owned组合和启动失败关闭，无Schema/API/权限/技术栈变化。
- Decision：显式WorkerDatabaseRuntime+current完整Migration head/当前SystemActor，固定真实Audit/Jobs Repo/同Supervisor及原Project/License/Document Port；不自动生成密钥、创建线程/领取任务或关闭caller数据库。License实时正文授权，不将有效License作为安全收尾启动前提，不声称正式信任已供给。
- Evidence：4新unit/1099无失败（2环境权限跳过）；实际PG18/currenthead/临时Vault双Scope完整factory经Loop准入/周期heartbeat/发布/撤权安全失败/empty-stop无写及原发布/wheel通过。首次测试PG连接超时后确认原进程活且ready重跑通过，未重建；异常长测试耗时原因未验证，非性能证明。
- Risk/rollback：无Migration/API/依赖/升级，0042不变；撤未公开组合保历史。正式来源/CLI信号/服务/公平隔离/未知恢复/质量/完整包/Gate仍待；下一P06-P10进程生命周期/信号适配。

## DEC-20260927-243

- Precode：Phase2/P06-P08，CR-AUD-004/ADR011，前置P07已验，编码前progress规定Loop边界/停止非强杀，无Schema/API/权限/依赖变化。
- Decision：原Step有界或持续运行、实例互斥/空闲Event可中断；stop传原Step排空，只有actual STOPPED才报停止，LIMIT非停机证据；异常保原pending退出不盲重试，常数聚合计数不存业务输出。
- Evidence：5新unit/1095无失败（2环境权限跳过），真实PG-Vault双Scope经Loop PENDING准入/周期heartbeat/发布、撤权安全失败/空stop无写，旧发布回归/wheel通过。Event等待中断/并行run拒绝与异常排空为unit真实线程行为，非正式服务进程信号证明。
- Risk/rollback：无Migration/API/依赖/数据升级，0042保留，撤内部装配保历史。未知跨进程命令/坏源隔离/公平/CLI信号/服务与正式信任/质量/完整包/Gate仍待；下一P06-P09运行组合根/启动核查。

## DEC-20260927-242

- Precode：Phase2/P06-P07，CR-AUD-004/ADR011，原领取/确认/执行/耗尽已验；实施前progress记录单步边界和停止不是强杀。无DB/API/依赖/权限变更。
- Decision：每次最多一个业务动作，实例互斥/交替尝试优先，stop仅停新准入；异常保原pending，静止Reader核绑定旧代/前两次真实期限仅清本机pending（非Job成功/删除），其他仍原执行器核源排空。无法核验/活线程不猜状态或盲领。
- Evidence：6新unit/1090无失败（2既有环境权限跳过），真实bounded PG-Vault双ScopePENDING实际准入/周期heartbeat/发布、空和stop六表无写、实际撤权安全FAILED与原发布回归，开发wheel通过。实例交替/timeout排空和错facts/本机释放仅unit，未证明多Worker全局公平或实际timeout综合场景。
- Risks/rollback：坏源/无法核验终态可阻实例，未知跨进程恢复/隔离/loop待；无Migration/API/依赖/生产升级，撤内部装配保历史。下一P06-P08主循环/可中断等待/排空停止；正式信任/质量/完整包/Gate未完成。

## DEC-20260927-241

- Precode：Phase2/P06-P06，CR-AUD-004/ADR011，前置P06-P03/04/05已验；编码前进度记录领取确认不明的问题与最小确认方案，无Schema/API/技术栈或权限扩张。
- Decision：只保本次实际领取命令/Claim/identity；commit异常退出原UOW后新UOW完整原Root/pair/current同Worker-fence活Lease/未完成Attempt/actualClaim核验。没有真实证据则安全错误，commit异常不走deadlock重领；收据不授正文权限，无renew/文件/Audit/状态写。
- Evidence：3新unit/1084无失败（2既有权限跳过），实际双Scope提交前整回滚拒绝/不重领、实际commit后确认故障只一Lease/Attempt、六表只读、错Worker/期限/代际/成功拒绝、撤权仍业务capture拒绝与后续新代发布；开发wheel通过。首次测试脚本私有方法错误类型捕获范围修正后重跑，不冒充实际网络断线。
- Risks/rollback：无Migration/API/依赖，0042保留；撤内部确认分支保历史。已变代/过期拒绝而非猜成功，跨进程未知命令恢复/公平/坏源隔离/loop未验，下一P06-P07有界后台单步/停止控制；正式材料/质量/安装包/Gate未完成。

## DEC-20260927-240

- Precode：Phase2/P06-P05，CR-AUD-004/ADR011；前置耗尽安全失败已验，新增Jobs owned只读最早到期一个候选Port与Audit单候选收尾，不扩Schema/API/权限/依赖。
- Decision：只取audit/AUDIT_EXPORT当前RUNNING/第三Attempt/max3、一致ACTIVE Lease/未完成Attempt且真实期限已到；无锁hint非授权，扫描前后identity，原Owner重验Root/pair/Worker-fence/期限/静止锁才安全FAILED与Audit同事务。确认异常只核真实源，不盲试或读取正文。
- Evidence：6新unit/1081无失败（2既有Windows权限跳过）；实际PG-Vault双Scope候选与Worker-fence绑定、六表扫描无写/完成后无候选，受控收尾真实commit后确认故障恢复，P04拒绝/写后回滚/撤权/字节保留及原发布回归，开发wheel通过。
- Risks/rollback：无Migration/API/依赖/数据升级，撤未公开装配保历史。单候选可能被坏源阻塞，公平/隔离/多Worker扫描/loop未验，下一P06-P06领取确认恢复；正式材料/质量/完整包/Gate未完成。

## DEC-20260927-239

- Phase/WBS：Phase2/P04-P03-P06-P04，编码前CR-AUD-004耗尽政策已记录，前置P06-P03专属claim/真实来源已验。
- Decision：只允许当前第三Attempt/max3真实DB期限过期；最小SYSTEM审计、identity后验、最后实际到期再验和JobFAILED/LeaseEXPIRED/Attempt固定码同UOW。独立来源核验恢复真正commit后确认丢失；可选执行器装配共享实际Supervisor/identity。无User/License业务旁路、强杀或删除。
- Evidence：8新unit，1075后端无失败（2既有权限跳过）；实际bounded PG-Vault双Scope三代到期/活租约前代错Worker拒绝、Audit/state写后故障六表回滚，撤权仍capture拒绝但安全收尾，实际commit后确认故障执行器恢复/无写重放/原字节保留；旧执行器/发布/wheel通过。首次脚本相对路径缺file_root修正重跑，不冒充实际网络断线。
- Risk/rollback：无Migration/API/依赖，0042不改，无数据升级；撤未公开Owner/可选装配保历史，已失败不回RUNNING。下一P06-P05耗尽扫描，之后领取确认恢复/loop/CLI/HTTP；正式材料/质量/其他平台/可用包/Gate未完成。

## DEC-20260927-238

- Date/WBS：2026-09-27 / P04-P03-P06-P03；Phase2，CR-AUD-004，编码前已记录通用混领/静默耗尽与反序锁差异，前置单命令执行器/真实来源已验。
- Decision：保原Generic入口，专属audit/AUDIT_EXPORT无锁候选hint→原Root/pair→最终actual eligible Job/current lease；固定三次、Worker/fence/完整binding与当前identity/静止锁，refresh ORM旧缓存。已耗尽不静默终止，下一分项安全审计；确认异常不猜领取，不授SYSTEM业务角色。
- Evidence：7新unit/1067后端无失败（2既有环境跳过），实际bounded PG/Vault两ScopePENDING后真实发布、5秒实际retry deadline、3秒实际过期三代/第4次无写、独立Supervisor并发不重复、高优先级其他Owner不变，claim写后/identity故障整回滚，旧发布/wheel通过。错Root/pair仅unit注入，claim确认恢复/网络/主循环未验。
- Risk/rollback：候选或None不是权限/全队列状态，坏源隔离/公平调度尚待；到期不是进程强杀。无Migration/API/依赖/生产升级，撤未装配准入保历史。Next P06-P04到期耗尽安全审计，再确认恢复/主循环/CLI/HTTP；正式材料/质量/可用包/Gate未完成。

## DEC-20260927-237

- Date/WBS：2026-09-27 / P04-P03-P06-P02；Phase2，输入CR-AUD-004/ADR011；前置真实状态Reader和成功/终止/取消/retry来源核验已验，编码前检查登记。只接单命令，不混入claim/循环/HTTP。
- Decision：强制同Supervisor/安全identity，真实facts路由；RUNNING才原业务RunOnce，失败后静止/重读、成功不撤回、取消优先、固定终止或白名单retry。返回Outcome必须原源证明，提交丢失先核验；STOP_TIMEOUT不提前写、旧代仅原retry收据，等待期即时取消不重写Worker历史。未知/缺源/过期拒绝，不猜STALE成功。
- Evidence：13新unit/1060无失败（2既有环境跳过），实际bounded PG/临时Vault同周期heartbeat两Scope0/260新导出、已成功后撤权拒返回无写、停User安全FAILED无capture、首USER申请活/到期/render中取消、内容终止vs基础retry；四种实际commit后确认故障均真来源确认，重放六表无写/裸取消拒绝，旧发布/wheel通过。License合成，新增真实网络/执行器竞争/主循环未验。
- Risk/rollback：Outcome属于该command代次，不保证当前Job一直处于该状态；不存在失去身份/源的可猜成功。无Migration/API/依赖/生产升级，撤未公开编排保历史。Next P06-P03专属claim适配，后主循环/CLI/HTTP；正式材料/质量/可用包/Gate仍待。

## DEC-20260927-236

- Date/WBS：2026-09-27 / P04-P03-P06-P01；Phase2，CR-AUD-004/ADR011，前置安全转换/来源核验已验，编码前检查登记。执行器不能依调用方attempt/state断言选择动作，先实际owned读取。
- Decision：真实原Root/acceptance/pair+指定Worker/fence/原Attempt/Lease与当前Job/DB clock，明确当前和历史代次；当前identity前后/同Supervisor静止，内部无业务正文/文件/commit/renew/Audit mutation。撤权仅可获得最小hint以选择安全停止，后续业务和终态来源校验不取消；状态不是receipt。
- Evidence：5新unit/1047完整后端无失败（2既有环境跳过），实际PG临时Vault两Scope RUNNING/retry/真实新代/FAILED/SUCCEEDED/取消/到期六表读无写；撤User+License仍业务capture拒绝，错绑定/后identity拒绝，原发布/wheel通过。初次新unit漏必填参数修正重跑，不放宽生产校验。
- Risk/rollback：事实会过时，不可据此改旧代或推断完成；技术取消状态样本缺完成源不算业务取消PASS。无Migration/API/依赖或生产升级；撤未装配Reader保历史。Next P06-P02单命令执行器接线；主循环/HTTP/质量/正式信任源/完整可用包/Gate仍待。

## DEC-20260927-235

- Date/WBS：2026-09-27 / P04-P03-P05-P02；Phase2，输入CR-AUD-004/ADR011，前置当前授权/固定重试Owner/真实三次政策已验，编码前检查登记。
- Decision：原pair+实际历史Worker/fence RELEASED Lease/AUDIT_UNAVAILABLE Attempt与执行完成窗口唯一SYSTEM事件只读核验；尚等待校验实际deadline，已进新代校验实际下一Attempt启动与代次，历史收据不漂移也不授当前代权。第三次必须真实FAILED；当前User权限/identity前后有效，不commit/写审计/读文件、不猜STALE。
- Evidence：5新unit/1042后端无失败（2既有环境跳过），真实PG临时Vault两Scope三次真正commit后返回故障、真实5/15秒新代claim/最终FAILED旧收据相同、多次八表无写；错绑定/尝试/缺重复源/User与License/第二identity拒绝，旧发布/wheel通过。不声称真实网络断线或新增并发竞争通过。
- Risk/rollback：历史receipt不是当前Job.state，当前业务权或identity失效不能获receipt；无Migration/API/依赖或生产升级。撤未装配核验保历史。Next P04-P03-P06单命令执行器接线，后主循环/HTTP；可用包/Gate/完整Scope仍未完成。

## DEC-20260927-234

- Date/WBS：2026-09-27 / P04-P03-P05；Phase2，输入CR-AUD-004/ADR011；编码前政策/验收/回滚先记录。只做固定重试Owner，不绕过当前业务权限。
- Decision：固定AUDIT_UNAVAILABLE白名单，attempt1/2后5/15秒，attempt3 FAILED；当前User权限前后检查、同Supervisor真实静止、SystemActor前后来源、原pair与Jobs owned当前活代事实、最小SYSTEM retry/失败Audit与技术转换同UOW。下一代重新claim/授权，新fileID保旧历史；成功/取消/过期/旧代不可改。
- Evidence：6新unit/1037完整后端无失败（2既有环境跳过），真实PG-Vault两Scope真正5/15秒无提前claim、新代重新capture/render三新fileID旧字节保留、第三次FAILED与Audit一致；实际Audit/转换写后与后验授权/identity故障回滚，停User/License拒retry。旧发布/wheel通过，不声称网络断线或新并发竞争已验。
- Risk/rollback：数据库不可写/identity缺失不猜已调度，静止锁不是I/O强杀；固定短退避不保证故障治愈。无Migration/API/依赖或生产升级；撤未装配Owner保历史。Next P05-P02重试确认丢失只读核验，再执行器/主循环；可用包/Gate与完整Scope未完成。

## DEC-20260927-233

- Date/WBS：2026-09-27 / P04-P03-P04-P05；Phase2，CR-AUD-004/ADR011；前置首申请/活代ack/到期恢复/静止锁已验，编码前检查登记进度文件。
- Decision：只读复核原Root/acceptance/Job-Outbox、唯一首USER源、当前Worker/fence一致CANCELLED/Lease/Attempt/完成时间、唯一SYSTEM完成源和当前identity前后；活期RELEASED与到期EXPIRED严格区分，首申请Audit先于完成Audit，不猜STALE或仅状态，不commit/重复Audit/读文件。
- Evidence：6新unit，1031后端无失败（2环境跳过），真实PG临时Vault两Scope两种真正commit后确认丢失/重复八表无写；错绑定/类型/缺或重复源/identity失败拒绝，旧发布/wheel通过。初次unit合成时间窗错误修正重跑，不放宽生产校验；详见进度证据，不声称新并发/实际网络断线已验。
- Risk/rollback：即时取消非本Worker证明，当前受控identity失去即无成功receipt；无Migration/API/依赖或生产升级。撤未装配核验保历史终态，Next瞬时失败retry策略，执行器/主循环/公开HTTP/正式材料/质量/全Scope可用包/Gate保持待。

## DEC-20260927-232

- Date/WBS：2026-09-27 / P04-P03-P04-P04；Phase2，编码前检查已登记，输入CR-AUD-004/ADR011，前置首USER源、静止锁、受控identity、alive取消Owner已验。
- Decision：保留无Worker/fence的旧技术恢复，另增严格当前Worker/fence/一致Job-Lease-Attempt和实际DB时钟到期恢复；首USER源与当前identity核验→最小SYSTEM AUDIT_EXPORT_CANCEL_RECOVERED/LEASE_EXPIRED→identity后验→owned转换最后→commit。无权限扩张、文件删除或OS强杀断言。
- Evidence：4新unit，实际PG临时Vault两Scope真正2秒到期/未到期/旧代/错Worker/原Root/成功/重复/裸技术来源矩阵，Audit及恢复实际写后/后验identity故障整体回滚；撤User+License业务拒绝但安全恢复成功，首历史/字节/结果保留。完整后端1025项无失败（2环境跳过）、旧发布和开发wheel通过，包hash记录进度文件。首次hash文件名误用纠正复核，构建未失败。
- Risk/rollback：期限仅DB fencing；主执行同步I/O应已返回，静止锁非跨进程强杀。无Migration/API/依赖或生产升级，撤未装配Owner保终态历史；确认丢失/执行器/主循环/retry/HTTP与可用包/Gate待，Next取消确认丢失核验。

## DEC-20260926-231

- Date/WBS：2026-09-26 / P04-P03-P04-P03；前置实际首申请当前权限/USER Audit和owned Jobs ack/SystemActor/静止锁已验；输入CR-AUD-004/ADR011。只做当前活代安全确认，无权限扩张或新申请。
- Decision：同Supervisor静止→当前identity→原Root/acceptance/pair和CANCEL_REQUESTED首历史/唯一USER源→最小SYSTEM完成Audit→第二identity→owned真实Worker/fence/alive ack最后→commit。原User/License撤权禁止业务但不阻断安全确认，reason正文不入Audit、不删除字节、不修改首申请/复活终态。
- Evidence：4新unit/1021后端无失败（2环境跳过）、真实PG临时Vault两Scope真实申请后撤User+License仍安全ack，Job/RELEASED Lease/Attempt JOB_CANCELLED一致、唯一SYSTEM Audit，首历史/字节保留；Audit及ack写后/identity故障回滚，错绑定/已取消/成功/裸技术源/真实到期拒改，原发布/wheel通过。新ack/publish竞争未额外执行，不扩大旧fixture证明。
- Risk/rollback：静止锁不是跨进程/磁盘强杀，同步I/O应先返回；到期取消恢复/确认丢失/执行器/HTTP仍待。无Schema/API/依赖，撤未装配Owner保历史，Next到期恢复，整体包/Gate待。

## DEC-20260926-230

- Date/WBS：2026-09-26 / P04-P03-P04-P02；Phase2，前置原Root/acceptance/pair/真实取消权限与技术取消Port已验；输入API03/CR-AUD-004。内部可信Owner不接受客户端original actor/spec断言。
- Decision：可信Root→current auth→锁Root/pair→Jobs owned首事实→0015同UOW收据+首申请USER Audit/技术状态。以不可变Audit为首次响应源无需新Schema；同key重放原状态不随后续CANCELLED漂移，新keyCHECKED不覆盖首申请，所有已有首历史需唯一请求Audit佐证，裸技术取消拒绝。reason正文不入Audit或repr，首历史只留owned Job。
- Evidence：5新unit/1017无失败（2环境跳过）、真实PG两Scope并发重放一首申请/异payload冲突/后续技术ack后原响应八表无写/新key保历史、实际PENDING立即及SUCCEEDED结果不撤回，Audit/Job写后与后验auth故障整UOW回滚、裸状态缺源拒绝，原发布/wheel通过。
- Risk/rollback：测试technical ack只证响应漂移，不冒充Worker确认Owner/完成审计；公开HTTP-IfMatch/系统确认/到期恢复/主循环未完成。撤未装配服务保首源/状态/成功历史，无Schema/API/依赖或生产升级；Next原首申请Audit的受控系统确认，整体包/Gate待。

## DEC-20260926-229

- Date/WBS：2026-09-26 / P04-P03-P04-P01；实际取消技术Port缺Owner来源，导出提交权限仅PM，不能复用为冻结API03创建者或PM取消；Phase2前置真实Auth/License/Project事实已验。
- Decision：新取消申请Authority与Project owned只读锁住current member操作，PROJECT当前有效creator任何角色或PM、DEPLOYMENT当前Admin，Session-CSRF-License每次检查，Admin无Project旁路。Archived只能申请停止既有Job，不授导出/业务写；原actor/spec必须可信Owner从Root读取，DTO不是权限凭证。无Schema/API/依赖/基线扩张，仅落实冻结角色政策。
- Evidence：4新unit/1012无失败（2环境跳过）、实际PG两Scope当前身份/CSRF/License与creator各角色/PM/跨项目/暂停/管理员矩阵、Archived停止权限九表读无写、原发布/wheel通过；测试字段误用修正从新库重跑记进度。
- Risk/rollback：没有取消首申请/审计/持久幂等或后台确认，POST关闭；撤未装配Port/Policy保历史。Next Owner原Root绑定与首申请审计来源/幂等，再安全确认和执行器；全Scope/Gate/正式包保持未完成。

## DEC-20260926-228

- Date/WBS：2026-09-26 / P04-P03-P03；CR-AUD-004/ADR011和实际原pair/同UOW失败Owner前置PASS；单一问题为提交确认丢失后的原失败只读证明，无安全权限扩张。
- Decision：Jobs owned当前FAILED/RELEASED Lease/同Attempt错误与完成时间证明，Audit owned唯一原Scope/trace/actor/target/原因/前后状态及时间证明，当前SystemActor/同Supervisor静止锁前后核验。业务Owner不读Jobs私有表，不根据错误文字或单一FAILED猜成功，不重复审计/重写终态；接口未接执行器。
- Evidence：4新unit/1008后端无失败（2环境跳过）、真实PG双Scope actual commit THEN lost confirmation返回原失败/Audit，多次八表无写，RUNNING/成功/错绑定原因/技术FAILED无审计/错重复审计拒绝，原终止发布回归/wheel通过。unit Mock声明失败修复重跑记进度；取消/到期verify新矩阵没有额外执行，不借旧Owner证据扩大声明。
- Risk/rollback：无Schema/API/依赖，撤未装配核验保历史；Next取消安全Owner，再retry/执行器/主循环；生产材料/三平台/Gate/安装包待。

## DEC-20260926-227

- Date/WBS：2026-09-26 / P04-P03-P02；CR-AUD-004先登记、V2.1/总控/API02/ADR010基线核验完成，Jobs原pair/current失败Port/受控SystemActor前置PASS。仅内部安全失败终止，不扩大License恢复面或系统业务角色。
- Decision：相同Supervisor短静止锁拒真实活心跳/阻止重启，当前identity→原Root/acceptance/pair→最小SYSTEM Audit→再次identity→actual Jobs alive generation FAILED最后→同UOW commit；5固定不可恢复原因，原User仅历史，无正文/文件/发布/续租。ADR011记录新边界；主同步I/O必须先返回，锁不是全局强杀。
- Evidence：6新unit/1004无失败（2环境跳过）、真实PG临时Vault两Scope撤User/角色/License仍拒业务但终止唯一失败Audit，Audit与技术写后/identity故障回滚，成功取消过期接管旧代无写，实际活心跳拒收尾/停止后允许，私有字节保留/原发布/wheel通过。首轮测试错误均修正完整重跑记进度。
- Risk/rollback：瞬时retry/取消/确认丢失/执行器未接线，正式信任源/Gate/安装包待；撤未装配Owner保历史，不复活终态。Next失败提交确认丢失原源核验，再取消Owner及安全接线。

## DEC-20260926-226

- Date/WBS：2026-09-26 / P04-P03-P01；通用LeaseService自有事务不能与Owner审计原子，前置原pair/current/retry与单次执行已验。CR-AUD-004先登记撤权安全终止差异，不在本技术分项实现政策。
- Decision：新独立Jobs caller-UOW失败Port，不修改通用Service/Schema/API；严格原pair/current绑定、白名单error、严格bool/有界delay、既有3尝试。调用Owner必须先核验真实原源/系统身份，并负责同UOW审计/提交；不能把技术坐标当权限。
- Evidence：5新unit/998后端无失败（2环境跳过）、实际PG双Scope FAILED/retry限额、Attempt/Lease绑定/接管拒旧代/终态取消过期拒改、真实Audit写后caller异常整UOW回滚、私有字节保留/原发布回归/wheel通过。测试属性误用和相对build路径失败均修正重跑，有进度记录。
- Risk/rollback：Owner安全终止基线核验/策略、取消及主循环仍待；撤未装配Port保历史，无生产迁移，Next P02，正式包/Gate保持未完成。

## DEC-20260926-225

- Date/WBS：2026-09-26 / AUD-03-A06-A04-P03-A07-P04-P02；实际发布/恢复、受权周期和WorkerDB边界前置PASS。
- Decision：当前原源只读分类三路径只是提示；新command完整capture/render/publish，已登记源恢复，已成功直接重放不续租。finally stop，线程真实结束后再次受权DB成功/完整物理hash恢复才回结果；确认丢失/STALE不能猜成功或把成功Job改失败，未登记同代字节保留且不覆盖。
- Evidence：11新unit/993后端无失败（2环境跳过），真实PG bounded UOW+周期线程 dualScope空/260未capture新command完整成功/13表无写重放、stage-only同file恢复、未登记旧字节拒绝保原/实际commit确认丢失按原源返回/原User停用前置无写拒绝、旧发布回归/wheel通过。
- Risk/rollback：不claim/分派/自动技术失败或取消，未登记旧字节失败尚需正式终止/重试Owner；本轮没有新增runner并发/取消/新代运行证明，不冒充底层验证。撤未装配入口保历史，Next失败取消Owner政策/同UOW审计前置，再主循环/重启/提交Jobs HTTP；正式材料/三平台/网络/质量/Gate/可用包待。

## DEC-20260926-224

- Date/WBS：2026-09-26 / AUD-03-A06-A04-P03-A07-P04-P01；P03周期线程真实验证PASS，但join不能终止SQL阻塞。
- Decision：新增opt-in Platform Worker runtime，专用有限池/连接参数，每短UOW PG18限定+三LOCAL超时读回核验；普通API及通用数据库默认不改，参数绑定/无服务器全局配置，技术/Schema/API/权限基线不变。transaction终止连接必须rollback/失效恢复，不能继续commit。
- Evidence：4unit/982后端无失败（2环境跳过），真实PG LOCAL/普通UOW恢复、慢SQL前实际Audit回滚、多query总事务终止/新连接ready、单槽池真实满额超时及另一连接User锁导致受权心跳退出/实际线程结束/容量复用、原发布/wheel通过。
- Risk/rollback：仅SQL服务器和池等待证据，连接黑洞/客户端读写/pre_ping没有全网络墙钟保证，默认极限数据性能未验。撤未装配factory保历史；Next单次Worker协调+真实失败取消/主循环与停机策略核查，正式材料/三平台/质量/Gate/可用包待。

## DEC-20260926-223

- Date/WBS：2026-09-26 / AUD-03-A06-A04-P03-A07-P03；P02受权短事务心跳前置PASS。
- Decision：独立有界Supervisor，actual线程存活登记/同Job唯一，立刻首心跳后Event周期；check/stop传播安全错误、stop join超时保容量，不杀线程或解释STALE为成功；每次service自己短UOW，文件主线程不持事务。无Schema/API/权限/依赖调整。
- Evidence：5新增真线程unit/978后端无失败（2环境跳过），真实PG双Scope短3秒租约跨人为4秒实际提升返回延迟仍原子发布；后续STALE七表不变、真实撤权/取消停止且传播、原发布回归/wheel通过。
- Risk/rollback：周期为进程内非全局，延迟非性能证明；join不能强停DB阻塞，同步DB超时与Worker停机/单次协调需P04核查；撤未装配入口保历史。正式材料/三平台/Gate/质量/可用包待，POST仍关。

## DEC-20260926-222

- Date/WBS：2026-09-26 / AUD-03-A06-A04-P03-A07-P02；P01技术续租前置PASS。
- Decision：Audit新内部WorkerHeartbeat继承原capture检查以保User-first锁序/原Root/受理pair/current Lease，显式注入Jobs caller-UOW renewal后再授权/验期限commit；保持原三stage，无新增权限/Schema/API/依赖，不把Lease当授权，不挂HTTP或进行文件I/O。
- Evidence：5unit/973后端无失败（2环境跳过），真实PG双Scope所有原stage、13表源历史无写、User/PM/部署角色/License/错Worker/跨Root误绑/终态取消/实际到期/真实接管拒旧代与新代续期、renew写后故障和后验许可拒绝回滚，原发布/wheel通过。
- Risk/rollback：只证明短事务心跳，非周期调度/长任务运行；原死锁重试复用但本轮未新增独立真死锁注入。撤未装配服务保历史；Next有界协调/stop/失败传播/发布竞争，正式材料/三平台/质量/Gate/可用包仍待。

## DEC-20260926-221

- Date/WBS：2026-09-26 / AUD-03-A06-A04-P03-A07-P01。
- Finding：通用heartbeat自有UOW无法与Audit当前授权/Root/pair同事务，既有checkpoint必须保持只读。Decision：独立Jobs caller-UOW JobLeaseRenewal，前后当前实际claim重核、中间复用owned heartbeat，无自commit/跨Owner表/外部I/O，不用增大固定超时替代心跳；无Schema/API/权限基线调整。
- Evidence：5新unit/968后端无失败（2环境跳过），真实PG双Scope续期、并发串行/期限一致、未commit/后置异常回滚、错Worker/fence/成功/取消/到期拒绝、实际接管旧代拒绝新代可续；原发布完整回归和wheel成功。
- Risk/rollback：本项仅Jobs技术事实，不证明Audit权限或调度存活；撤未装配Port保历史。Next P02受权短事务心跳，再实际调度/Worker/提交Job接口；正式材料/三平台/性能/质量/Gate与完整程序包仍待。

## DEC-20260926-220

- Date/WBS：2026-09-26 / AUD-03-A06-A04-P03-A06-P03；前置P01/P02增量契约与实际授权/字节/资源生命周期PASS。
- Decision：Windows两显式平台模式挂既有四GET，复用Auth read/Project/License与各Owner公开Port；不额外要求Worker身份供给、不装配Worker或开放POST，无新Schema/角色/依赖。default/login-only404保留，装配异常沿用dispose+安全StartupError。
- Evidence：实际PG发布dualScope260与临时文件到两factory详情/完整Hash下载及Session/Scope/Admin旁路/许可/坏文件拒绝PASS；三构造故障不发布app，两模式dispose一次unit通过；旧WindowsAudit/上传Finalize完整回归通过，963后端无失败（2跳过）、wheel成功。
- Risk/rollback：Credential/License/cursor/write信任注入合成，不是正式账户/三平台/代理/性能验收。撤显式挂载保所有历史，Next Worker协调/心跳前置和实际循环，然后提交/Jobs HTTP；完整Scope、质量/Gate/可用包仍待。

## DEC-20260926-219

- Date/WBS：2026-09-26 / AUD-03-A06-A04-P03-A06-P02；前置P01契约/P03-A05快照PASS。
- Decision：仅新增Audit opt-in内容GET；准备至传输结束占有Router有界槽，Response外层finally覆盖尚未启动生成器/response.start失败；显式线程资源所有权使请求取消不能关闭活跃read或提前释放活跃prepare名额，线程完成后close/release。不顺手改普通文档下载。
- Evidence：7新增契约/ASGI测试覆盖start/body发送故障、未启动流取消、prepare/read取消容量保留/收尾、长度/读取失败；真实PG与实际文件双Scope空/260精确内容/Hash/当前权限、复制后撤销与损坏文件安全Audit通过；962后端无失败（2环境跳过）、开发wheel成功。
- Impact/rollback：无DB/依赖/权限变化，原冻结API保留、默认404，移除可选Router保历史；名额为进程内非全局，代理断网/三平台/性能/正式材料未验。下一项P03实际Windows组合，不关闭Gate3或交付目标。

## DEC-20260926-218

- Date/WBS：2026-09-26 / AUD-03-A06-A04-P03-A06-P01。
- Decision：先登记CR-AUD-003和非Breaking契约，保64cdf09；新增opt-in PROJECT/DEPLOYMENT成功结果详情，不复用普通DocumentVersion或静态URL，不序列化内部DTO/manifest。当前Session/License/实际PM或部署Admin由P03-A05真实源服务重核，路由二次验证坐标并显式安全投影。
- Evidence：4新契约测试/955后端无失败（2环境跳过）、真实PG双Scope已发布260条来源和当前权限、跨范围/Admin旁路/License拒绝及无业务写、旧原子发布回归/wheel通过。无Migration/依赖，默认404，未挂生产组合。
- Risk/rollback：移除opt-in路由即可，无历史删除；元数据不是物理完好证明，下载流/断连取消限额/P03装配/正式账户/三平台/Gate/可用包仍待。子任务分项验收不缩减原交付Scope。

## DEC-20260926-217

- Date：2026-09-26；WBS：AUD-03-A06-A04-P03-A05。
- Decision：新当前Session Scope授权读取实际成功源，原提交actor仅历史来源；共享Document安全快照原语但专用审计入口128MiB、普通100MB不变。Hash/copy在UOW外，返回前重复当前授权/source，内容失败受权同UOW最小Audit、保原历史。
- Reason：内部Worker权限不能用于浏览器读取；当前PM可读停用提交者历史，Admin无项目旁路。实际发现渲染128MiB与普通snapshot100MB不兼容，先在CR-AUD-002记录最小适配，不缩小合法导出或扩大普通规则。
- Impact：6新unit/951后端无失败（2跳过），真实dualScope/源/权限/复制后撤销close/坏文件审计与Storage128MiB边界PASS，旧下载/恢复发布回归；无Schema/API/依赖，未挂HTTP。
- Rollback：撤未装配内容入口，保所有来源与成功历史，不自动删文件。公开路径需增量契约/生命周期限额验证；正式账户/三平台/性能/完整包/Gate仍待。

## DEC-20260926-216

- Date：2026-09-26；WBS：AUD-03-A06-A04-P03-A04-P04。
- Decision：恢复读实际原计划和Document登记摘要/来源，不依赖失去的内存DTO或路径猜Hash。当前代STAGED/有效Lease才恢复三种真实物理形状；已成功必须Jobs真实终态Lease/Attempt+Result/AVAILABLE/完整Hash，Hash后重新当前授权，只返回原结果不写历史。
- Reason：必须处理提升后事务失败、至少一次/确认丢失，不能将文件存在或Audit宣称成功当Job事实；不得复活过期/取消旧代或重finish成功。
- Impact：6新unit/945后端无失败（2跳过）；真实双Scope三形状恢复/成功并发无写、确认丢失与坏/缺来源拒绝、接管保旧file/原capturePASS；无Schema/HTTP/依赖，新增owned只读Port不授予业务权。
- Rollback：撤未装配恢复入口，保所有来源/文件/结果，不自动删生产数据。中断注入非真实杀进程演练、License/正式账户/三平台/Gate/包待；下一项当前Session结果访问授权/内容公共Port。

## DEC-20260926-215

- Date：2026-09-26；WBS：AUD-03-A06-A04-P03-A04-P03。
- Decision：实际Owner预核权限/根/pair/Lease/capture/plan，事务外Hash，短UOW STAGED登记，再事务外提升，最后单UOW File AVAILABLE+SYSTEM Audit+Result+Jobs completion，完成后迅速commit；无跨Owner私有表访问。
- Reason：File提升不是成功，必须统一DB业务事实且保当前权限/租约/取消与原身份来源；不嵌套自提交Jobs service，不接受随机SystemActor或只凭旧Hash。
- Impact：双Scope真实成功链/实际撤权取消过期/系统材料丢失与四个DB写后回滚、真实取消两锁竞争PASS；5新unit/939后端无失败（2跳过）、三项实际回归/开发wheel通过。无Migration/HTTP/依赖；CR-AUD-002/ADR010范围不改。
- Rollback：撤未装配入口，保原计划/STAGED/私有提升文件及成功历史，不删生产数据或复活任务。下一项来源恢复/当前授权结果重放及下载；License合成、正式账户/三平台/完整交付与Gate仍待。

## DEC-20260926-214

- Date：2026-09-26；WBS：AUT-04-A01（AUD原子发布前置）。
- Decision：先记录CR-AUT-004再实现独立Windows当前账户Vault材料派生系统UUID；固定域/ref、启动pin完整摘要、每次使用重读，缺失/变化拒绝。复用既有加密备份，不新增User/角色/凭据登录、自动供给或业务授权。
- Reason：实际代码无受控SystemActor来源，不能用随机UUID或普通User冒充冻结Worker身份。完成此可独立验收前置才恢复真实发布。
- Impact：4项新增含临时Vault真实丢失/错误口令/恢复/换材料验证通过，全后端934项无失败（2跳过），开发wheel成功；无Schema/HTTP/依赖/License改变。
- Rollback：停未装配入口，保留Vault与历史，不自动删生产材料；正式账户/异账户及Server2025/Debian未验，下一Owner仍须全部当前权限/Lease/文件事实核验，不标完整包或Gate通过。

## DEC-20260926-213

- Date：2026-09-26；WBS：AUD-03-A06-A04-P03-A04-P02。
- Decision：当前授权/原pair/租约短事务页取固定封口成员，每页最多128，结束后才文件写；准备与结尾完整capture复核，fsync/hash在所有UOW外，失败文件仅私有保留。
- Reason：不能把当前源流放在持User/Job锁的长事务内写文件，不能仅凭旧plan/Hash延续当前授权；每页释放锁并重新核验。
- Impact：无Schema/API/依赖；不提升/写元数据/结果/Job成功。只DB阶段40P01限三次重试，整个文件流程不盲重试；同代已留文件不覆盖，需新代。
- Rollback：撤渲染入口，保留所有原计划/私有文件供后续受控恢复，不删除生产数据；心跳/原子发布/下载后续验收。

## DEC-20260926-212

- Date：2026-09-26；WBS：AUD-03-A06-A04-P03-A04-P01。
- Decision：新增Audit专用Jobs caller-UOW完成公共Port，用原Queue request/ref核对Job/Outbox、Checkpoint完整租约及Claim绑定，然后同UOW调用既有Repository finish；不嵌套自开事务LeaseService.finish，也不运行发布回调。
- Reason：真实文件/元数据/结果/Audit需Owner同事务提交，避免Job-first新事务或非原pair误完成；Lease必须在最后数据库步骤重新验证。
- Impact：无Schema/HTTP/依赖，原finish接口不变；权限、真实文件与结果/发布Audit为Owner前置，完成不授予这些权限。
- Rollback：撤新公共Port，历史状态保留；不能直接回退已成功任务或删除结果。

## DEC-20260926-211

- Date：2026-09-26；WBS：AUD-03-A06-A04-P03-A03-P04。
- Decision：renderer和结果Repository共用纯canonical manifest构造；读写都从实际own Root/acceptance/capture/plan/发布Audit重新绑定，而不信输入DTO或结果行；同请求读回首次结果，替换pubAudit/计划/内容拒绝。
- Reason：持久结果不能只是SQL行转DTO或相信Hash存在，需保持规范字节及来源且适配后续原子caller-UOW。
- Impact：无Schema/API/依赖，Repository不鉴权/commit/文件I/O/跨Owner私有访问；无新增公开下载。
- Rollback：撤应用代码，0042/不可变历史保留；真实SystemActor/Lease/文件/Job原子成功另验。

## DEC-20260926-210

- Date：2026-09-26；WBS：AUD-03-A06-A04-P03-A03-P03。
- Decision：0042 own唯一成功结果引用不可变渲染计划/发布Audit；规范manifest字节由own Root/capture/NEW文件事实独立重建精确核验，非只JSON语义相等；结果不直接读Jobs/Document私有表。
- Reason：原计划/文件存在不等于成功，清单不能包含自由正文或非规范字节；跨Owner事实须公共Port实际编排。
- Impact：新增Schema/ORM，无API/依赖；原0001～0041不变，原计划不猜回填成功；当前权限/真实SystemActor/Lease/原子发布后续验收。
- Rollback：空表可离线受控down，任何结果历史禁止down，先表排他锁；保留原冻结与历史，不删文件或结果。

## DEC-20260926-209

- Date：2026-09-26；WBS：AUD-03-A06-A04-P03-A03-P02。
- Decision：抽取既有Worker User-first授权/原pair/Lease检查以供capture及RENDER共用；RENDER只读已封口源，再登记或返回同代固定计划，前后当前权限/租约复核；own Repository不鉴权、不commit、不触及外模块私有表。
- Reason：不能以0041坐标或预分配file_id推断当前权限/Lease，不能RENDER时重捕获。
- Impact：无Schema/API/依赖变化；同代数据库重试只读原计划，部分文件失败必须新Lease代次；仅PG40P01整UOW限三次重试，未知commit不盲重试。
- Rollback：撤应用入口/代码，保留0041及不可变历史；后续唯一结果/文件/Job原子发布另任务验收。

## DEC-20260917-001

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-001|
|Date|2026-09-17|
|WBS|Repository Governance|
|Decision|启用“默认自主执行 + Gate 确认 + 异常升级”；自动执行批次和 WBS 边界检查周额度，剩余低于 20% 时保存检查点并停止新任务；允许在正确分支内自主同步 GitHub。|
|Reason|落实用户最新明确规则，减少普通确认和聊天消耗，同时保留重大变更、资源和远端安全边界。|
|Impact|后续 L1 任务自动执行，L2 记录后继续，L3/Gate 才请求确认；新增 `STATUS.md`、最小 Session 入口和额度保护。|
|Rollback|回退本决策对应提交，并恢复原有逐任务启动方式；不影响业务数据或正式技术基线。|

## DEC-20260917-002

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-002|
|Date|2026-09-17|
|WBS|P03-A02|
|Decision|来源资格审计只接受文件标题中明确的“合同”或“技术协议”作为确定性分类证据；历史解决方案不自动映射为标准能力或调研。|
|Reason|保持来源语义真实，避免为满足覆盖率把 AI 推断或目录名称写成已验证业务事实。|
|Impact|确认 20 条 CONTRACT、25 条 TECHNICAL_AGREEMENT；75 条 SOLUTION 排除。P03-A02 需要补充至少 55 条合格记录，并补齐 STANDARD_CAPABILITY、SURVEY。|
|Rollback|删除审计映射和证据，恢复全部记录为待确认；不会修改原始资料或用户工作簿。|

## DEC-20260917-003

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-003|
|Date|2026-09-17|
|WBS|P03-A05|
|Decision|使用百炼 `text-embedding-v4` 768 维作为换模重建验证目标，创建独立 `v2` index identity；保持当前 `v1` 激活，不自动切换。|
|Reason|官方文档和当前华北 2 工作区均支持该模型与维度，可同时验证模型和维度变化；独立索引满足既定不可原地换模规则。|
|Impact|120 条非客户合成记录完成真实全量重建；新增验证制品，不改变正式架构或当前激活绑定。|
|Rollback|删除 `v2` 验证制品即可；`v1` 未被修改。|

## DEC-20260917-004

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-004|
|Date|2026-09-17|
|WBS|P03-A06|
|Decision|所有 PROJECT Vector、Full Text、Hybrid SQL 在各自最内层查询强制使用参数化 `project_id = %(project_id)s`；缺失 ProjectId 在 Repository 调用前拒绝。|
|Reason|只在外层过滤可能让候选集、排序或中间结果接触其他项目数据；参数化内层过滤能同时控制隔离和注入风险。|
|Impact|6 个双项目检索场景跨项目泄漏为 0；形成后续 RetrievalService/Repository 的 PoC 约束。|
|Rollback|回退 PoC 查询实现和证据；不影响正式数据库，因为临时 Schema 已删除。|

## DEC-20260917-005

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-005|
|Date|2026-09-17|
|WBS|P03-A07|
|Decision|PoC Full Text 使用 PostgreSQL `simple` 配置和上游空格分词后的中文术语，并为相同表达式建立 GIN 索引。|
|Reason|PostgreSQL 内置配置不提供可靠中文分词；上游规范化无需引入新第三方组件，且能验证锁定的 PostgreSQL FTS 链路。|
|Impact|4 组 Top-5 Recall 100%，但正式链路必须保留术语规范化，不得把结果解释为数据库原生中文分词。|
|Rollback|删除 PoC FTS 脚本与证据；临时 Schema 已删除。|

## DEC-20260917-006

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-006|
|Date|2026-09-17|
|WBS|P03-A08|
|Decision|pgvector PoC 使用 HNSW + `vector_cosine_ops`，以 1,000 条合成向量和 4 组确定性近邻验证 Top-5。|
|Reason|与 POC-02 已验证索引方法一致，可隔离验证 RAG Repository 的向量 Top-K 行为和执行计划。|
|Impact|合成 Top-5 平均/最低 Recall 100%；不改变当前 1024 维真实索引绑定，也不形成真实语料质量结论。|
|Rollback|删除向量验证脚本与证据；临时 Schema 已删除。|

## DEC-20260917-007

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-007|
|Date|2026-09-17|
|WBS|P03-A09|
|Decision|Hybrid PoC 使用 Vector 0.6 + Full Text 0.4 的固定加权融合；每通道候选池取 Top-K 的 4 倍，并将 HNSW 基线设为 `m=32`、`ef_construction=200`、`ef_search=200`。|
|Reason|直接用最终 Top-K 作为候选池会截断并列结果；默认 HNSW 构建/搜索参数在组合数据上出现近邻漏召回。扩大候选池并提高索引构建与搜索深度后，4 组场景稳定召回全部组合相关项。|
|Impact|合成数据 Top-5 平均/最低 Recall 达到 100%，GIN 与 HNSW 均被使用；参数只是 PoC 基线，正式值仍需真实 Golden Dataset 校准。|
|Rollback|回退 Hybrid 查询、验证脚本和证据；临时 Schema 已删除，不影响正式数据库。|

## DEC-20260917-008

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-008|
|Date|2026-09-17|
|WBS|P03-A10|
|Decision|Reranker 采用可配置 provider/base URL/model/timeout，并通过统一适配层调用；PoC 选择百炼华北 2 的 `qwen3-rerank` OpenAI-compatible `/reranks`。外部失败默认 fail-open，保留检索原顺序并记录脱敏错误码。|
|Reason|官方文档将 `qwen3-rerank`列为当前文本 RAG 排序模型；可配置适配与 fail-open 能避免厂商绑定，并在限流或暂时不可用时保持基础检索可用。|
|Impact|真实 5→3 重排通过；429、超时和响应异常降级通过。业务模块仍不得直接调用厂商 SDK，正式启用策略需在 API/架构冻结时确认。|
|Rollback|移除 PoC Reranker 适配、脚本和证据；没有持久化业务数据或厂商响应正文。|

## DEC-20260917-009

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-009|
|Date|2026-09-17|
|WBS|P03-A14|
|Decision|Context Builder 只负责排序、预算、引用封装和 Trace 元数据；LLM 调用必须通过 POC-04 `AIService → ModelRouter → ProviderAdapter`。Prompt 以版本化定义传入，不写散落的业务内 Prompt 或厂商条件分支。|
|Reason|落实统一 RAG 和 AI Gateway 边界，并确保每次回答可追溯 ProjectId、Prompt 版本与实际 Chunk 来源。|
|Impact|Context 到统一 AIService 的确定性链路通过，结构化输出由 AIService 校验；该 PoC 不冻结正式 API Contract。|
|Rollback|移除 Context Builder/Orchestrator PoC、测试和证据；不影响 POC-04 网关。|

## DEC-20260917-010

|字段|内容|
|---|---|
|Decision ID|DEC-20260917-010|
|Date|2026-09-17|
|WBS|P03-A15|
|Decision|PoC 将最高检索分 0.5 设为“可进入 AI”的最低可靠度；空结果或低于阈值时禁止调用 AI。数据库失败直接停止，Reranker 失败 fail-open，AI 失败返回脱敏错误码和重试属性。|
|Reason|无证据仍调用模型会产生不可追溯答案；Reranker 是增强步骤，可降级，而检索数据库和最终 AI 的失败语义不同，应分别处理。|
|Impact|6 个成功/异常场景全部通过；0.5 只是合成 PoC 阈值，必须由真实 Golden Dataset 校准后才能成为正式配置。|
|Rollback|移除异常编排 PoC、测试和证据；不改变 POC-04 或数据库。|

## DEC-20260918-001

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-001|
|Date|2026-09-18|
|WBS|P03-A02|
|Decision|将用户明确指定的 `标准能力库/` 中名称含“调研”的业务表单归为 `SURVEY`，其余用户手册、标准接口和部署资料归为 `STANDARD_CAPABILITY`；历史方案不用于补齐四类来源。|
|Reason|目录用途由用户明确提供，文件类型与名称可形成确定性来源证据；继续使用历史方案映射会违反来源真实性约束。|
|Impact|20 份新增文档分为 19 份 STANDARD_CAPABILITY、1 份 SURVEY；与合同/技术协议合并后形成 120 条四类候选，P03-A02 从缺少语料转为等待人工确认。|
|Rollback|删除本地分区和 R4 候选输出，恢复 P03-A02 来源缺口；不修改用户原文件或旧 R2/R3 历史制品。|

## DEC-20260918-002

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-002|
|Date|2026-09-18|
|WBS|POC-05 / P03-A02|
|Decision|DOCX 解析遇到指向 `word/NULL` 的无效内部关系时，仅在临时副本删除该无效关系后重试；不得改写来源文件，其他异常继续失败关闭。|
|Reason|该关系不是有效 OOXML 内容，但会使 python-docx 中止整个文档；限定异常文本和关系目标的最小修复可恢复结构解析，同时保护原件与未知异常边界。|
|Impact|标准能力库 20/20 DOCX 解析通过，原件 20/20 未改变；新增关系过滤回归测试和警告记录。|
|Rollback|移除临时副本修复逻辑并恢复该文档 FAIL_PARSE；用户原文件始终未被修改。|

## DEC-20260918-003

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-003|
|Date|2026-09-18|
|WBS|P03-A02|
|Decision|R4 的“修改后确认”只有在补充说明不少于 20 个字符且同时包含“人工复核：”和“结论：”，并且锁定任务的查询、来源类型、分类、答案术语、引用定位、审核人和日期完整时，才转为 APPROVED。原分类为 HUMAN_CONFIRMATION_REQUIRED 时，仅依据人工结论中的明确短语确定性映射为 INSUFFICIENT_INFORMATION 或 NO_RELIABLE_MATCH；其余分类保持不变。|
|Reason|用户更新后的 120 条记录均已形成逐项复核和明确结论，继续统一视为 PENDING 会违背“修改后确认”的业务语义；同时必须防止空泛说明绕过 Golden Dataset 必填 Gate，并避免 AI 自行扩大人工结论。|
|Impact|120 条记录通过严格导入；38 条明确证据不足的记录映射为 INSUFFICIENT_INFORMATION，8 条明确无可靠业务匹配的记录映射为 NO_RELIABLE_MATCH，最终覆盖四类来源和六类结果。人工原文和数据集仍只保存在 Git 忽略的本地目录。|
|Rollback|恢复“修改后确认”统一 PENDING 的映射并删除当前 R4 导出；不修改用户工作簿、来源文件或历史 R1~R3 证据。|

## DEC-20260918-004

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-004|
|Date|2026-09-18|
|WBS|P03-A11~A13|
|Decision|将首轮 120 条真实 Golden Dataset 指标按原始门槛判定为 FAIL，保留脱敏失败证据；在用户确认 Quality Gate 前不降低门槛、不按模型输出事后改标签、不改变 Hybrid 0.6/0.4 或更换模型。|
|Reason|Top-5 Recall、分类准确率、来源引用准确率分别为 60.00%、14.17%、50.83%，均显著低于 95%、90%、98%；同时发现多数最终分类仍继承候选阶段关键词启发式值，需先验证标签一致性再调优。|
|Impact|POC-03 状态转为 `FAIL / BLOCKED_QUALITY_GATE`；建议先用明确的最终分类字段重新冻结 Golden Dataset，再分层诊断 Vector、FTS、融合与 Reranker 排名。|
|Rollback|无数据回滚；本决策仅记录已发生的验证事实。后续获批方案必须新建数据集/配置版本并保留本轮 R1 失败证据。|

## DEC-20260918-005

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-005|
|Date|2026-09-18|
|WBS|P03-A02-R5|
|Decision|在保留 R1 质量失败证据的前提下重新打开 Golden 标签 Gate。R5 只复用 R4 文字中可确定性识别且与已导出标签一致的 62 条明确结论；其余 58 条按“R4 分类 × 本次 AI 分类”归并为 7 组。工作簿默认保持未确认，只有人工选择全局批量确认后才按建议规则生效，单条最终分类优先于分组规则。|
|Reason|R4 的自由文本已包含部分明确人工结论，但要求用户重新逐条填写 120 条不友好；同时不能让 AI 自动把自身预测写成 Golden 真值。分组确认既保留人工 Gate，又将必要操作压缩为一次批量确认和少量例外。|
|Impact|新增四表 R5 工作簿、严格导入器和防篡改校验；当前 62 条无需重复确认，58 条等待 7 组规则确认。全局确认前不生成 R5 数据集，原始质量门槛、模型与 Hybrid 参数均不变。|
|Rollback|删除 R5 本地工作簿和导入脚手架，恢复到 R4/R1 失败检查点；不修改 R4 工作簿、R1 失败证据或用户源文件。|

## DEC-20260918-006

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-006|
|Date|2026-09-18|
|WBS|P03-A02-R5|
|Decision|R5 人工全局确认生效后，最终 Golden Dataset 只允许五类业务结论；`HUMAN_CONFIRMATION_REQUIRED` 是评审工作流态，不得作为最终分类。单条例外优先于分组规则，所有锁定来源字段继续失败关闭。|
|Reason|人工确认已将 58 条冲突记录归并为明确业务结论；把“需要确认”继续作为最终答案会混淆流程状态与业务事实，并使质量评估无法闭合。|
|Impact|R5 严格导入 120/120、问题 0，Schema 与覆盖审计 PASS；历史 R4/R1 证据保持不变。|
|Rollback|删除 R5 本地导出并恢复到等待确认状态；不修改用户工作簿或历史数据集。|

## DEC-20260918-007

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-007|
|Date|2026-09-18|
|WBS|P03-A11-R2|
|Decision|检索前对相邻中文字符之间由 OCR 插入的空白进行规范化，并增加来源类型过滤下的确定性词法 IDF 通道；保留原始 Chunk 文本、ChunkId 和来源定位，不改写证据原文。|
|Reason|扫描合同存在逐字换行，旧分词只能得到孤立单字；规范化后可恢复“合同的有效组成部分”等连续术语，同时不影响审计原文和引用身份。|
|Impact|R5 Top-5 Recall 从首轮 60.00% 提升到 95.00%（114/120），达到 P03-A11 门槛；该结果来自同一数据集的探索调优，生产声明仍需独立留出集。|
|Rollback|移除 OCR 字间空白规范化与词法通道；Chunk 和 Golden 数据无需迁移。|

## DEC-20260918-008

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-008|
|Date|2026-09-18|
|WBS|P03-A11~A13-R3|
|Decision|用户批准方案 A：对 6 条低区分度 Golden 样本生成 R6 问题与引用复核包。只允许修改这 6 条的问题和经证据页展示的引用集合；其余 114 条及全部 R5 分类逐对象保持不变。AI 建议在人工全局或单条确认前不得写入 R6 数据集。|
|Reason|6 条原问题由通用短语或 OCR 片段构成，缺少文档和业务场景，唯一目标 Chunk 排名为 8、11、24、27、41、117；修订问题比降低 98% 门槛或扩大 Context 更能保持验收语义和可追溯性。|
|Impact|新增三表 R6 轻量确认工作簿、本地证据定位器、严格导入器、防篡改与 114 条保留校验。当前状态为等待人工确认，P03-A12/A13 尚未重跑。|
|Rollback|删除 R6 本地输出和导入脚手架，恢复 R5/L3 检查点；不修改 R5 数据集、历史质量证据或用户源文件。|

## DEC-20260918-009

|字段|内容|
|---|---|
|Decision ID|DEC-20260918-009|
|Date|2026-09-18|
|WBS|P03-A11~A13-R3 / P03-A11-R4|
|Decision|正式验收以 R6 端到端 `Hybrid → Reranker → AIService` 结果为准；本地来源过滤、OCR 空白规范化和确定性词法 IDF 的 116/120 结果仅作为诊断，不得覆盖真实链路 72/120 的失败结论。下一 WBS 在保持模型、0.6/0.4 基线权重、门槛和 R6 标签不变的前提下，把已验证的来源类型过滤与确定性词法候选通道接入端到端检索链。|
|Reason|R6 真实复验三项分别为 60.00%、47.50%、51.67%；分层诊断显示 25 条通道召回缺失、15 条融合丢失和 8 条重排丢失，而本地确定性路径为 96.67%。当前差异属于检索实现路径不一致，不能以离线旁路结果宣称正式 Gate 通过。|
|Impact|P03-A11~A13 保持 FAIL，POC-03 保持 `FAIL / BLOCKED_QUALITY_GATE`。先完成无外部调用的检索契约对齐、回归和本地排名验证；再次调用百炼或 DeepSeek 前重新取得明确的数据外发授权。|
|Rollback|移除新增候选通道和来源过滤接线，恢复 R6 真实失败检查点；不修改 R6 Golden Dataset、模型、门槛或历史证据。|

## DEC-20260920-010

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-010|
|Date|2026-09-20|
|WBS|P03-A11-R4|
|Decision|端到端候选池按 `source_type + ProjectId` 过滤，分别获取 Vector Top-20、Full Text Top-20 和 OCR 规范化词法 IDF Top-20。Vector/Full Text 继续按锁定的 0.6/0.4 排序，随后与词法通道稳定去重合并，再交给外部 Reranker。检索缓存必须携带 `r4-source-filter-lexical-idf-v1` 版本及来源类型，旧缓存不得复用。|
|Reason|旧端到端链在每通道 Top-20 后过早压缩为 20 条且未按来源类型过滤，导致通道召回和融合丢失；词法旁路 116/120 已证明对 OCR 中文有效，但必须接入统一链且不能改变既定 Hybrid 权重。|
|Impact|本地 120 条候选池精确覆盖达到 119/120（99.17%），同文档覆盖 120/120，来源越界 0，候选数 13~59；增加只运行 Hybrid/Reranker、不调用 Embedding 或 DeepSeek 的 `--retrieval-only` 验收模式，完整向量缓存缺失或 Hash 过期时失败关闭。正式 Top-5 仍需新百炼重排验证。|
|Rollback|移除第三词法候选通道、来源过滤参数、检索缓存版本和 `--retrieval-only` 分支；恢复 R6 端到端失败实现，不修改 Golden Dataset、模型或门槛。|

## DEC-20260920-011

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-011|
|Date|2026-09-20|
|WBS|P03-A11-R5|
|Decision|最终 Top-5 采用保护性融合：保留百炼 `qwen3-rerank` 第 1 名，并加入 OCR 规范化、来源类型隔离的确定性词法 IDF 前 4 名；重复项按既有顺序去重并从两路补足。排序过程只使用查询和候选正文，不读取 `expected_relevant_chunk_ids`、答案术语、人工标签或单条 ChunkId 规则。R4 的 120 条真实重排结果允许按 pipeline version 脱敏缓存并用于无外部调用的确定性复算。|
|Reason|R4 候选池精确覆盖 119/120，但纯语义重排只有 91/120；失例包括 OCR 将 `MPP` 拆成单字符，以及同一 API 文档内多个语义等价 XML 片段。纯重排会覆盖高置信字面证据，保护性融合可同时保留语义首选与 OCR/标识符敏感结果。|
|Impact|Windows 11 R6 精确 Top-5 达到 114/120（95.00%），同文档 118/120（98.33%），120/120 个重排结果均源自获批的真实百炼调用，GIN/HNSW 命中，P03-A11 PASS。该结果没有门槛余量且使用同一数据集探索调优，必须保留“独立留出集后验验证”限制；P03-A12/P03-A13 状态不变。|
|Rollback|将最终 Top-5 恢复为纯百炼排序，P03-A11 回到 R4 的 91/120（75.83%）失败结果；保留 R4/R5 脱敏证据和 Golden Dataset，不降低门槛、不修改标签。|

## DEC-20260920-012

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-012|
|Date|2026-09-20|
|WBS|P03-A12-R1|
|Decision|Prompt v2 只允许五类正式业务标签，移除工作流态 `HUMAN_CONFIRMATION_REQUIRED`；模型必须先判断 Context 与问题的匹配性，再判断证据充分性，最后判断满足程度。Context 使用 OCR 字间空白规范化后的完整 Chunk（上限 1000 字），引用只允许一个最直接 Chunk。Prediction Cache 必须绑定 `PromptId + PromptVersion`；新增 `--prediction-only` 模式，缓存不完整时失败关闭，确保复验只调用 DeepSeek。|
|Reason|v1 将六类状态一次性并列，未建立证据 Gate，且每段只取前 600 字；47 条人工确认的 `INSUFFICIENT_INFORMATION` 中有 37 条被误判为 `STANDARD_SATISFIED`，6 条 `NON_STANDARD` 全部误判。需要先消除 Prompt 定义、上下文截断和缓存串版问题，再做真实模型复验。|
|Impact|120/120 条 v2 payload 离线准备完成，每条 5 个 R5 Context；精确证据可用 114/120、同文档 118/120、来源越界 0、规范化后正文截断 0、Golden 字段泄漏 0，外部调用 0。P03-A12 仍保持 FAIL，直到新的 DeepSeek 真实准确率达到 90%。|
|Rollback|恢复 v1 Prompt 与 600 字 Context 作为历史失败实现；删除 v2 payload/报告与 `--prediction-only` 模式，不修改 R6 Golden 标签、P03-A11 结果或验收门槛。|

## DEC-20260920-013

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-013|
|Date|2026-09-20|
|WBS|P03-A12-R2 / P03-A13|
|Decision|Prompt v2 真实复验未达门槛后，不继续在同一 R6 验收集上启动 Prompt v3，也不根据模型结果修改冻结标签、唯一期望 Chunk 或 90%/98% 门槛。先升级为 L3 质量 Gate，由用户决定是否重新打开 R6 业务语义评审，为问题补充可判定的需求/结论目标、人工分类理由和可接受引用集合。|
|Reason|Prompt v2 在 Top-5 已达 114/120 的条件下，分类仍只有 51/120，引用 62/120；主要错误为 30 条 `INSUFFICIENT_INFORMATION` 被判为 `STANDARD_SATISFIED`，6 条 `NON_STANDARD` 无一命中。抽样显示若干问题只要求摘录“采用何种方式/有哪些约定”，输入中没有要求模型判断标准满足或非标的业务目标；继续同集调优会把 Golden 分布或单条答案反向编码进 Prompt，不能证明泛化能力。|
|Impact|P03-A11 保持 PASS；P03-A12/P03-A13 保持 FAIL，POC-03 保持 `BLOCKED_QUALITY_GATE`。保留本轮脱敏聚合证据，查询、Context、逐条响应和 case-level 数据继续只留在 Git 忽略目录；任何新外发复验仍需按当轮范围授权。|
|Rollback|用户若批准重新打开 R6 Gate，则生成新版本数据集和独立留出集，保留 R6 与 Prompt v1/v2 作为历史失败基线；若不批准，则以当前失败结论结束 POC-03，不伪造通过状态。|

## DEC-20260920-014

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-014|
|Date|2026-09-20|
|WBS|P03-A12-R3 / P03-A13|
|Decision|用户批准重新打开 R6 业务语义评审。保留 R6 与 Prompt v1/v2 历史证据，新建 R7 全量 120 条语义、分类与引用确认包；AI 预填可判定目标、五类分类建议、分类理由和可接受引用候选，但只有全局或单条人工确认后才允许导出 R7。|
|Reason|Prompt v2 已证明 R6 中部分抽取式问题与满足程度分类、唯一期望引用之间不可由输入稳定推导。全量重新评审比继续同集调 Prompt 或降低门槛更能修复数据定义，同时保持历史可追溯性。|
|Impact|R7 工作簿含 120 条主确认项、五类结论说明、836 条证据候选和严格技术底稿；原文定位 120/120。AI 建议变更分类 73 条、引用 58 条；合同、技术协议和调研材料缺少标准能力交叉证据时保守建议资料不足。未确认预检为 120 PENDING、0 个问题且不输出数据集；129/129 测试 PASS。R7 因已使用 Prompt v2 诊断结果，只能作为校准集，不能在同一 120 条上关闭 P03-A12/P03-A13；仍须独立留出集。|
|Rollback|删除 R7 本地输出与新增脚手架，恢复 DEC-20260920-013 检查点；R6、Prompt v1/v2、90%/98% 门槛和历史失败证据均不改变。|

## DEC-20260920-015

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-015|
|Date|2026-09-20|
|WBS|P03-A12-R4 / P03-A13|
|Decision|用户完成 R7 全局确认后，严格导入并执行 Schema 与覆盖审计。R7 导入 120/120 PASS，但五类覆盖缺少 `NON_STANDARD`，因此不把数据集标记为覆盖通过，也不为凑数伪造标签。基于原始合同中直接出现的二次开发交付证据，生成仅含 1 条的 R7.1 例外确认表；只有人工确认后才允许修订该条业务语义与分类。|
|Reason|R7 的 AI 建议偏向保守，将所有合同类事项判为资料不足，导致已确认结果没有非标准样本；同时项目规则要求五类全覆盖，且 AI 建议必须经人工确认才能成为正式业务事实。|
|Impact|R7 本地校准数据集已生成且 Schema 有效，但覆盖 Gate 保持 FAIL；R7.1 只影响 1 条，其他 119 条不重审。130/130 测试 PASS，R7.1 两张表均渲染通过、公式错误 0；未调用外部 AI。即使 R7.1 覆盖通过，该批数据仍是校准集，P03-A12/P03-A13 仍需独立留出集关闭。|
|Rollback|若用户退回 R7.1，则保持 R7 的 `NON_STANDARD=0` 和覆盖 FAIL，不修改已确认数据；若确认，则保留 R7 作为历史版本，新建 R7.1 并重跑 Schema 与覆盖审计，不覆盖 R7。|

## DEC-20260920-016

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-016|
|Date|2026-09-20|
|WBS|P03-A12-R4 / P03-A12-R5|
|Decision|严格导入用户确认的 R7.1 单条例外，保留 R7 历史版本并新建 R7.1 数据集；导入后必须同时通过 Golden Dataset Schema 与覆盖审计。R7.1 通过后只作为 Prompt/检索校准集，不使用同批 120 条关闭 P03-A12/P03-A13，下一 WBS 建立独立留出集。|
|Reason|确认项具备直接二次开发证据，且人工确认字段完整；覆盖审计要求 100~200 条、查询唯一、四类来源和五类正式分类齐全。已参与模型诊断的数据若再次作为验收集会产生后验偏差。|
|Impact|R7.1 导入 1/1、问题 0、Schema PASS；120 条覆盖审计 PASS，分类分布为 38/15/1/57/9，重复问题 0，四类来源齐全。134/134 测试 PASS，未调用外部 AI。P03-A12/P03-A13 继续保持未关闭，直到独立留出集完成真实复验。|
|Rollback|保留 R7 数据集与其覆盖失败报告，删除本地 R7.1 输出即可回到确认前状态；已确认工作簿和两版数据集均不覆盖，便于追溯。|

## DEC-20260920-017

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-017|
|Date|2026-09-20|
|WBS|P03-A12-R5 / P03-A13|
|Decision|独立留出集目标锁定为 50 条，来源配额为标准能力 33、合同 7、技术协议 8、调研 2。来源锁必须排除 R7.1 标签、Prompt v2 Context、R4/R5 检索 Top-5 与 R7 评审候选的 Chunk，并排除与污染 Chunk 共享 Source Locator 的相邻重叠块；锁定失败时不得写出部分结果或复用污染样本。|
|Reason|50 条可使分类门槛 90% 对应至少 45/50，引用门槛 98% 对应至少 49/50，同时控制人工评审规模。当前 29 份文档均出现在校准集，无法文档级隔离，只能以未见 Case、Query、Chunk 和 Source Locator 作为最强可实现隔离；调研类在严格口径和仅模型暴露口径下均为 0/2。|
|Impact|来源锁脚手架与失败关闭测试已实现，但当前 WBS 因缺少新的调研来源而阻塞。需要至少 1 份、建议 2 份此前未进入 POC-03 的真实调研业务表单；原始资料、本地锁文件和内容不提交 Git。P03-A12/P03-A13 保持未关闭，验收门槛不变。|
|Rollback|删除留出集锁定脚手架和本地补充资料入口，恢复到 R7.1 校准集检查点；不会修改 R7/R7.1、Prompt v1/v2 历史证据或 90%/98% 门槛。|

## DEC-20260920-018

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-018|
|Date|2026-09-20|
|WBS|P03-A12-R5 / P03-A13|
|Decision|调研类事实证据以面对面访谈、现场交流及其形成的实际客户调研记录为准；调研业务表单只作为问题清单、字段和覆盖范围参考，不得替代客户事实结论，也不得单独满足独立留出集的调研配额。新增资料统一标记为 `ACTUAL_CUSTOMER_DISCOVERY_RECORD`，来源锁对未带该角色的调研块失败关闭。|
|Reason|多数客户不会完整维护标准调研业务表单，模板只能表达应调查什么，不能证明客户实际说过什么、确认了什么。用户明确说明本次新增文件是面对面交流形成的调研记录，应赋予其主要事实证据地位。|
|Impact|49 份新增记录本地解析与文件/正文 Hash 去重全部通过；50 条来源锁按 33/7/8/2 完成，历史表单的 13 个调研块被排除，调研 2/2 均来自新的实际记录。141/141 测试 PASS，外部 AI 调用 0。P03-A12/P03-A13 仍需独立问题、标签、引用人工确认和真实复验。|
|Rollback|移除证据角色强制校验会允许模板再次进入调研配额，因此仅能通过新的正式决策回滚；原始资料、R7/R7.1 和历史失败证据均不修改。|

## DEC-20260920-019

|字段|内容|
|---|---|
|Decision ID|DEC-20260920-019|
|Date|2026-09-20|
|WBS|P03-A12-R6 / P03-A13|
|Decision|在用户当轮明确授权范围内，仅将 50 条锁定候选编号、来源类型、证据角色和正文发送至 DeepSeek，生成问题、五类分类、理由、关键词和摘录建议。DeepSeek V4 结构化短任务通过统一 AIService 显式关闭思考模式；模型同义改写的摘录和关键词不得作为引用，必须由本地原文确定性替换并标记。全部建议仍保持待人工确认。|
|Reason|当前 DeepSeek V4 默认启用思考模式，JSON 模式多次耗尽输出预算并返回空正文；显式非思考模式符合官方接口能力，也保持业务模块只调用 AIService。引用必须逐字落地，不能把模型改写当成原文证据。|
|Impact|50/50 建议完成、问题 50/50 唯一、五类分类全覆盖，分布 23/3/10/13/1；累计请求尝试 227，Embedding/Reranker 调用 0。9 条摘录和 9 条关键词完成本地原文修复。R1 工作簿三表渲染、公式错误 0、50/50 原文定位及批量/例外交互回归 PASS；POC-03 146/146、POC-04 12/12 测试 PASS。P03-A12/P03-A13 状态不变，等待人工确认。|
|Rollback|删除本地 R1 建议缓存、工作簿和证据页即可回到 50 条来源锁检查点；若移除 DeepSeek V4 非思考开关，结构化短任务将恢复空正文风险。历史 R7/R7.1、来源锁和质量门槛均不修改。|

## DEC-20260921-020

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-020|
|Date|2026-09-21|
|WBS|P03-A12-R7 / P03-A13|
|Decision|将人工确认的 50 条独立留出样本保存为单独的 `poc-03.holdout.v1` 验收数据集，不与已经参与 Prompt 和检索调优的 120 条 R7.1 校准集合并。导入器必须独立重算生效状态，锁定确认表和技术底稿的来源字段，并同时验证 50 条固定范围、四类来源配额、五类分类、唯一问题/候选/Chunk、PROJECT 隔离和引用锁对齐。|
|Reason|沿用 Golden Dataset Schema 会要求 100~200 条并诱导把独立样本并入校准集，从而破坏独立验收边界。独立 Schema 可以复用相同业务字段，同时把来源锁指纹、配额和隔离属性设为可验证约束。|
|Impact|实际导入 50/50 APPROVED、0 PENDING、0 RETURNED、0 问题，人工例外 0；Schema 和 12/12 覆盖/隔离检查 PASS，POC-03 151/151 测试 PASS。完整数据集、问题、答案术语、审核人、客户正文和源文件名继续只存在于 Git 忽略目录。P03-A12/P03-A13 仍保持 FAIL，直到独立真实复验达到 90%/98%。|
|Rollback|删除本地独立留出集输出、新 Schema 和导入脚手架，可回到已确认工作簿与来源锁检查点；不会修改 R7/R7.1 校准集、历史 Prompt 结果、来源锁或质量门槛。|

## DEC-20260921-021

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-021|
|Date|2026-09-21|
|WBS|项目分析辅助 R2（Phase 0 本地成果）|
|Decision|将用户对 R1 的整体认可登记为“可作为调研执行输入基线”，并用确定性规则生成 R2：优先依据真实调研与合同/技术约束的组合和资料数量划分四个执行批次；范围、合同、接口、数据迁移、环境、权限、安全、合规、验收、切换和上线类主题标为 P0；R1 待确认项转为独立决策记录。|
|Reason|用户需要直接进入下一步执行，而不是继续逐条填写分析表。确定性分批和优先级便于安排访谈，同时保留证据入口和人工维护字段，避免把方案资料或 AI 建议误当客户事实。|
|Impact|12 个项目形成 60 条调研任务、39 条 P0 和 24 条决策记录；第 3/4 批明确要求先补真实业务调研。工作簿包含看板、任务、决策和说明四页，4/4 渲染、回读、公式与交互验证 PASS；POC-03 160/160 测试 PASS。客户数据与成品不提交，本轮外部调用 0，独立留出集外发 Gate 不变。|
|Rollback|删除 R2 本地输出和新增通用生成器即可回到已确认的 R1；R1 指纹、历史 PoC 证据、质量门槛及当前 HOLDOUT_LIVE_DATA_EGRESS Gate 均不改变。|

## DEC-20260921-022

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-022|
|Date|2026-09-21|
|WBS|项目分析辅助 R3（Phase 0 本地成果）|
|Decision|第一批无法安排客户访谈时，允许以已确认 R1 和 R2 为输入执行桌面调研，并生成带证据等级、局限声明和 TraceLink 的需求候选。标准/非标/差异项仅在有实际调研、合同或技术协议证据时标为可评审；仅有方案/风险资料时保留工作假设；所有待确认项均保持为未关闭前置决策。|
|Reason|项目需要进入下一分析环节，但现阶段不能获得新的客户访谈。桌面调研可以利用已有资料持续推进，同时必须显式隔离“资料事实、资料推断、工作假设和客户确认”，避免制造不存在的调研结论。|
|Impact|第 1 批 5 个项目形成 25 条桌面调研结论、40 条需求候选和 10 条未关闭前置假设；29 条可进入需求评审、1 条带工作假设、10 条受前置决策阻塞。工作簿 5/5 页签渲染、回读、公式和交互验证 PASS，POC-03 165/165 测试 PASS。本决策不形成正式 Requirement、不触发需求冻结或 Phase 6，也不改变独立留出集数据外发 Gate。|
|Rollback|删除 R3 本地输出和新增通用生成器即可回到 R2 调研执行计划；R1/R2 指纹、正式 Phase 0 状态、历史 PoC 证据、质量门槛及 HOLDOUT_LIVE_DATA_EGRESS Gate 均不改变。|

## DEC-20260921-023

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-023|
|Date|2026-09-21|
|WBS|后续项目分析与实施辅助工作|
|Decision|用户授权 AI 代为处理后续普通确认、资料缺口补全、候选项取舍和可回滚方案选择。AI 按“已有证据优先、保守默认、最小影响、可追溯、可回滚”原则直接形成推荐结论并继续执行，不再要求用户逐项填写或确认；证据不足时保留假设标识和 TraceLink。|
|Reason|用户当前无法投入时间逐项确认，希望项目连续推进，同时避免将未验证推断伪装成客户事实。将代决策范围和例外固化，可减少重复交互并维持审计边界。|
|Impact|后续需求候选收敛、普通字段补充、批次安排、文档结构和非破坏性实现选择可由 AI 自主决定并登记。该授权不替代正式 Gate、客户数据外发、安全/License 核心机制、已锁定基线变更、删除已确认 Scope、Secret 使用或不可逆外部操作所需的专项确认；周额度低于 20% 时仍按保护规则停止新任务。|
|Rollback|用户可随时撤销或缩小代决策范围；撤销前已登记的可回滚决策保留历史记录，未进入正式 Gate 的候选结论不自动升级为正式业务事实。|

## DEC-20260921-024

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-024|
|Date|2026-09-21|
|WBS|项目分析辅助 R4（Phase 0 本地成果）|
|Decision|按 DEC-20260921-023 的用户授权，将 R3 的 10 条前置假设分别映射到可复用的保守决策规则，并采用工作基线解除内部分析阻塞。规则必须同时给出纳入范围、明确排除、验收依据、风险和证据链接；受影响候选只能转成内部需求评审稿，统一标记为 `NOT_FORMAL_REQUIREMENT`。|
|Reason|用户要求后续普通确认和资料补充由 AI 代为决定。结构化工作基线可以让标准能力匹配和解决方案分析继续，同时保留未知项、合同解释和客户确认边界，避免概括授权越过正式 Gate。|
|Impact|第一批 5 个项目的 10 条前置假设全部匹配到专用规则，无兜底项；40 条候选全部进入内部需求评审稿，其中 P0 30、P1 10、高风险 6。工作簿 4/4 页签完成视觉和回读检查，50 个证据链接完整、公式错误 0，POC-03 170/170 测试 PASS。本轮外部调用 0，正式 Phase 0 与 HOLDOUT_LIVE_DATA_EGRESS Gate 均不改变。|
|Rollback|删除 R4 本地输出和新增通用生成器即可回到 R3；R3 指纹、原前置假设、客户资料、正式 Gate、历史 PoC 证据和质量门槛均不修改。|

## DEC-20260921-025

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-025|
|Date|2026-09-21|
|WBS|项目分析辅助 R5（Phase 0 本地成果）|
|Decision|将 R4 的 40 条内部需求评审稿一一映射为解决方案草案。标准功能优先使用标准配置；非标功能按接口适配、迁移链路、安全扩展或领域扩展实现；差异项优先采用兼容控制、数据/规则治理或受控流程扩展；代决策事项继承 R4 工作基线。接口、迁移和权限方案另生成结构化专项草案，全部标记为 `NOT_FORMAL_SOLUTION`。|
|Reason|下一环节需要把标准、非标、接口和差异结论转为可实施方案，同时不能在 Phase 0 或需求未正式化时创建正式 Solution。确定性映射和专项设计能保持 Requirement→Solution→Evidence Trace，并避免业务模块绕过统一适配、权限和审计边界。|
|Impact|5 个项目形成 40 条需求—方案映射：标准配置 10、非标实现 10、差异处理 10、工作基线专项 10；结构化专项包括 InterfaceSpec 11、MigrationSpec 7、PermissionDesign 3，高风险方案 6。工作簿 4/4 页签视觉和回读通过，61 个证据链接完整、公式错误 0，POC-03 176/176 测试 PASS。本轮外部调用 0，正式 Phase 0 与 HOLDOUT_LIVE_DATA_EGRESS Gate 均不改变。|
|Rollback|删除 R5 本地输出和新增通用生成器即可回到 R4；R4 指纹、需求评审稿、代决策记录、客户资料、正式 Gate 和历史 PoC 证据均不修改。|

## DEC-20260921-026

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-026|
|Date|2026-09-21|
|WBS|项目分析辅助 R6（Phase 0 本地成果）|
|Decision|把 R4 需求评审稿与 R5 解决方案草案按指纹和唯一 Trace 整合为内部交付包，并采用 W0 范围与决策收敛、W1 标准能力配置、W2 差异验证与治理、W3 非标与专项实现、W4 验收/交接/正式化的顺序组织后续工作。10 条 AI 代决策单列为正式化待办，21 项接口/迁移/权限设计单列为专项，30 个调研主题继续以实际调研记录和证据为主。|
|Reason|项目需要一份能够直接用于内部交接和后续计划编制的统一视图，同时不能把 Phase 0 期间生成的需求、方案和 AI 工作基线描述成正式业务事实。分段路线、进入条件和完成证据可让后续 WBS 保持可追溯、可验收和可回滚。|
|Impact|5 个项目形成 40 条交付项、21 项专项、10 条正式化待办和 30 个调研主题；工作簿 6/6 页签视觉和回读通过，71 个证据链接完整、公式错误 0，POC-03 183/183 测试 PASS。本轮外部调用 0，不创建正式 Requirement/Solution，不改变正式 Phase 0、冻结顺序或 HOLDOUT_LIVE_DATA_EGRESS Gate。|
|Rollback|删除 R6 本地输出和新增通用生成器即可回到 R4/R5；两份源包指纹、客户资料、历史版本、正式 Gate 和质量复验授权状态均不修改。|

## DEC-20260921-027

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-027|
|Date|2026-09-21|
|WBS|项目实施 WBS R7 / 管理层汇报 R8.1 / P03-A11~A13-R8 前置检查|
|Decision|把 R6 内部交付包展开为 5 个项目、60 项内部 WBS 草案任务，按 W0-W4 保留角色、依赖、进入条件、验收和证据追溯，但不填写实名、日期或承诺工期；同时生成 8 页管理层汇报，如实展示校准集 FAIL 和独立留出集待复验。留出集验证器只对 `poc-03.holdout.v1` 接受恰好 50 条，其他数据集仍保持 100~200 条。虽然用户授权“真实质量复验”且 DeepSeek 外发已有明确记录，本轮不得把该授权自动扩大到百炼 Embedding/Reranker；需用户另行明确其目的地和载荷范围。|
|Reason|WBS 与管理汇报可在不外发客户内容的前提下推进内部准备；实名、日期和正式工期需要资源与 Gate 事实，不能由 AI 编造。百炼调用会发送查询及候选正文，属于与 DeepSeek 不同的外部目的地，必须按最小授权原则单独确认。|
|Impact|WBS R7 为 60 项任务、40 个证据链接、5/5 页签检查通过；管理层汇报 R8.1 为 8 页并通过最终化、逐页渲染和原生图表检查；POC-03 188/188 测试 PASS。组合语料为 2,078 个 Chunk、50 条预期证据缺失 0，PostgreSQL 18.6/pgvector 0.8.6 前置检查 PASS；安全拦截前本轮外部调用 0，Phase 0 与质量 Gate 不变。|
|Rollback|删除 R7/R8.1 本地输出及三个新增生成器，回退留出集大小入口改动即可恢复至 R6 检查点；R6 交付包、客户资料、校准集结果、正式 Gate 和历史版本不受影响。|

## DEC-20260921-028

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-028|
|Date|2026-09-21|
|WBS|P03-A11~A13-R8 独立留出集真实复验 / P03-A12~A13-R9 质量改进|
|Decision|接受并冻结本轮独立留出集 98.00% / 48.00% / 74.00% 的真实结果：P03-A11 PASS，P03-A12/P03-A13 FAIL。门槛、人工标签和引用真值均不修改。首次装载发现的 17 个重复 ChunkId 只在逐字段完全一致时去重；同 ID 不同内容继续失败关闭。本轮 50 条已成为已见测试集，后续调优不得再次把它作为未见独立集的通过证据。|
|Reason|检索命中 49/50 但分类只有 24/50、引用只有 37/50，证明主要瓶颈位于业务分类判断和已召回候选中的精确引用选择。模型把 44/50 条判为标准满足，资料不足和非标功能识别明显不足。逐条针对本留出集写规则会产生数据泄漏，不能形成可推广的质量结论。|
|Impact|50/50 条百炼重排与 50/50 条 DeepSeek 预测完整完成，GIN/HNSW 命中，缺失预测与越界引用均为 0。新增两个重复 Chunk 失败关闭回归，POC-03 测试增至 190 项。管理层汇报更新为 R9，Phase 0 和正式编码 Gate 保持阻塞。下一 WBS 在本地分析 26 条分类失例、13 条引用失例和 1 条检索失例，并在独立开发集上设计修复。|
|Rollback|真实结果和审计证据不可回滚或覆盖；代码可回退重复 Chunk 处理与汇报生成器，但不得删除或改写本次质量失败历史。|

## DEC-20260921-029

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-029|
|Date|2026-09-21|
|WBS|P03-A12~A13-R10 独立留出集失败分层诊断|
|Decision|冻结 R10 诊断，采用“双来源证据装配 + Prompt v3 结构化判定 + 独立 Evidence Selector”作为下一轮独立开发集修复方向。当前 50 条只作为已见回归诊断集；不修改其标签、可接受引用集合或分数。|
|Reason|需求来源 17 条中检索命中 16 条但分类只命中 1 条，证明能力适配标签所需的标准能力对照未进入同来源上下文；模型 46/50 次引用第 1 名，正确证据位于第 2～5 名时只命中 2/12。13 条严格引用失例中有 8 条引用覆盖全部答案术语，说明未来数据冻结前还需完成可接受引用集合审查。|
|Impact|下一轮先建立与本留出集隔离的开发/校准集，区分文档事实与能力适配问题，保留 ProjectId 隔离并增加需求证据与标准能力证据双通道；模型供应商、Embedding、Reranker、PostgreSQL、质量门槛和总体架构均不变。任何新真实外部调用仍需当轮外发授权。|
|Rollback|可回退新增诊断工具和建议方案，不影响已冻结的 98.00% / 48.00% / 74.00% 真实结果；不得删除失败历史或把当前 50 条恢复为未见留出集。|

## DEC-20260921-030

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-030|
|Date|2026-09-21|
|WBS|P03-A12~A13-R11 Prompt v3 与 Evidence Selector 离线修复|
|Decision|按用户批准的方案 A 实现离线 Prompt v3、双来源证据装配和 Evidence Selector；遵循用户“不用重复验证”的决定，不对当前 50 条重新调用模型或重算质量分数。|
|Reason|R10 已确认能力适配缺少跨来源对照且引用存在首位偏差。离线合同和合成测试可以修复结构性缺陷而不泄漏已见留出集；但没有新的独立真实证据，不能据此声明 P03-A12/P03-A13 PASS。|
|Impact|新增文档事实/能力适配显式路由、条件 OutputSchema、需求与标准能力证据角色、ProjectId 失败关闭和查询支持度选择器。模型供应商、统一 AIService、数据库、质量门槛、人工标签及历史结果不变；POC-03 保持 FAIL，项目仅继续不依赖该结论的其他 Phase 0 PoC。|
|Rollback|删除 Prompt v3、Evidence Selector、对应测试和 R11 设计文档即可回到 R10 诊断状态；不会改变 v2 历史代码、真实调用缓存或冻结结果。|

## DEC-20260921-031

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-031|
|Date|2026-09-21|
|WBS|P05-A19 真实扫描 PDF 分层语义准确率|
|Decision|以“原页视觉抄录后再比 OCR”的 75 个分层检查点作为真实扫描语义 PoC 门槛：一般语义相似度不低于 0.85，数值、代码和版本完全一致，总召回不低于 95%，关键错误为 0。PaddleOCR 保持主链；未过门槛的 Tesseract 只作辅助回退，关键字段必须由主链或人工确认。依据用户批准，Windows 11 物理断网与 Debian 13 登记 `EXC-P0-004` 暂缓。|
|Reason|成功解析、OCR 行数和自生成术语召回不能证明真实扫描语义准确率。分层页面与人工视觉检查点可避免 OCR 自证；主辅链对照显示 PaddleOCR 75/75，而 Tesseract 只有 70/75 且含关键错误。用户已明确同意 Windows 11 保留 `PASS_LOCAL_ASSETS`、不主动断网，并曾明确 Debian 13 暂不验证。|
|Impact|POC-05 以 `PASS_WITH_EXCEPTION` 收口。Windows 11 与 Windows Server 2025 的已验证结论保留；Windows 11 物理断网、Debian 13 和 105 页逐字符全量标注仍不形成通过结论。原页、真值、客户内容和逐项结果只留在 Git 忽略的本地 artifacts，仓库保存匿名汇总。|
|Rollback|可删除本轮评分工具和匿名汇总并恢复 POC-05 `IN_PROGRESS`；不得把 Tesseract 基线失败改写为通过，也不得删除 `EXC-P0-004` 的历史批准记录。|

## DEC-20260921-032

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-032|
|Date|2026-09-21|
|WBS|POC-06 Word / PowerPoint 交付级样例|
|Decision|以 Microsoft Office 实开和 PDF 导出作为 Windows 目标应用验收主证据；Windows 11 结论为 PASS。Windows Server 2025 未安装 Word/PowerPoint，只记录 OOXML 包结构和 Hash 复验 PASS，POC-06 保持 `IN_PROGRESS / SERVER_OFFICE_BLOCKED`，不从 Windows 11 外推 Server 或 Debian 兼容性。|
|Reason|基线要求“可由 Microsoft Office 正常打开”。工作区 DOCX 渲染器因未安装 LibreOffice 无法运行，但 Windows 11 已由目标 Word 应用导出并完成 100 页视觉检查；Server 虚拟机缺少 Office，不能以结构验证替代实开验收。|
|Impact|Windows 11 形成 100 页 DOCX、50 页 PPTX、实开/PDF 导出、OOXML 完整性和 150 页全量视觉证据。PPTX 制件按当前工作区规范使用 Artifact Tool，不修改正式 `python-pptx` 基线。未经许可不在 Server 安装 Microsoft Office，也不将缺少环境记为通过。|
|Rollback|可删除 POC-06 样件、脚本和匿名证据并恢复 `NOT_STARTED`；不得将 Windows 11 的实验结果改写为 Server/Debian 通过，也不得隐去 Server 未安装 Office 的阻塞。|

## DEC-20260921-033

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-033|
|Date|2026-09-21|
|WBS|POC-08 Plugin Host|
|Decision|PoC 宿主采用“每次调用一个独立 Python 子进程 + 单条 JSON-RPC 2.0 stdio 请求/响应”的最小隔离实现。Manifest 在启动前检查必填字段、Plugin API 版本、OS、入口路径边界和入口文件 SHA-256；子进程只继承最小系统环境，不继承 DB/AI Key。|
|Reason|当前 Phase 0 需要直接证明 crash、timeout、invalid JSON、版本不兼容和独立升级，不需要提前引入常驻池、容器、微服务或自定义 TCP。短命子进程便于失败后立即回收，并与锁定的 stdio 协议一致。|
|Impact|Windows 11 和 Windows Server 2025 均完成 13/13 测试、10/10 验收场景和 20/20 并发调用；插件 crash/timeout 后 FastAPI 仍健康，invalid JSON 失败关闭，v1→v1.1 不修改宿主。SHA-256 只是本 PoC 的包完整性检查，不代表开发者身份签名；正式发布签名待后续冻结。Debian 13 未验证。|
|Rollback|删除 `poc/poc-08-plugin-host/` 和对应匿名证据即可回到 `NOT_STARTED`；不影响正式业务模块、数据库、API Contract 或发布签名方案。|

## DEC-20260921-034

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-034|
|Date|2026-09-21|
|WBS|POC-09 License|
|Decision|PoC 将 MAC 规范化为大写冒号形式后计算 SHA-256；License Payload 采用字段排序、紧凑分隔符的确定性 UTF-8 JSON，并由仅驻留开发者工作台进程内的 Ed25519 私钥签名。客户侧只使用公钥；`SystemTimeGuard` 记录本次运行最近成功时间并拒绝回拨。|
|Reason|基线已锁定 MAC → Normalize → SHA-256 → Ed25519，但未规定规范化文本和确定性序列化细节。显式规范避免分隔符/大小写导致同一网卡产生不同指纹，确定性 JSON 避免同一 Payload 因编码差异导致验签失败。|
|Impact|Windows 11 与 Windows Server 2025 均完成 26/26 测试和 10/10 场景；8 类非法授权全部拒绝，License/MAC/时间防护覆盖率 91%～94%，私钥和原始 MAC 未落盘。跨进程可信时间状态存储留待 Architecture Freeze，Debian 13 未验证。|
|Rollback|删除 `poc/poc-09-license/` 和对应匿名证据即可回到 `NOT_STARTED`；不改变 Ed25519、Payload 正式字段、数据库、正式 API 或商业授权规则。|

## DEC-20260921-035

|字段|内容|
|---|---|
|Decision ID|DEC-20260921-035|
|Date|2026-09-21|
|WBS|Phase 0 Debian 13 验证范围|
|Decision|依据用户明确决定，登记 `EXC-P0-005` 暂缓 POC-06、POC-08、POC-09 的 Debian 13 验证；POC-08、POC-09 以 `PASS_WITH_EXCEPTION` 收口。POC-06 仅解除 Debian 缺口，Windows Server 2025 Office 阻塞保持。|
|Reason|用户明确表示 Debian 13 不用验证。该决定满足 L3 例外确认要求，但不等于形成 Debian 兼容证据。|
|Impact|Phase 0 不再因 POC-08/POC-09 的 Debian 缺口阻塞；剩余正式阻塞为 POC-03 质量 Gate 和 POC-06 Windows Server 2025 Office 实开。Debian 发行与 Release Gate 仍不得宣称通过。|
|Rollback|用户可撤销例外并恢复 Debian 13 实机验证；恢复后 POC-06、POC-08、POC-09 在 Debian 结果形成前回到 `IN_PROGRESS`。|

## DEC-20260922-036

|字段|内容|
|---|---|
|Decision ID|DEC-20260922-036|
|Date|2026-09-22|
|WBS|Phase 0 Gate 1|
|Decision|用户批准 POC-03 和 POC-06 两项替代方案并正式确认 Gate 1。POC-03 保留分类 48.00%、引用 74.00% 的 FAIL，以 R11 + 强制人工确认收口；POC-06 以 Windows 11 Office 实开、Server 包结构/Hash 和 Server Office 豁免收口。|
|Reason|用户此前决定不重复本轮 POC-03 真实复验；POC-06 的 Microsoft Office 不是服务器运行依赖，且 Server 已确认制品 Hash/OOXML 与 Windows 11 一致。两项原验收无法在现有条件下继续，已按 L3 取得明确决定。|
|Impact|Phase 0 状态变为 `COMPLETE_WITH_APPROVED_ALTERNATIVES`，项目进入 Architecture Freeze。POC-03 质量指标转为 Gate 3/UAT 阻塞；Server Office 与 Debian 未验证范围转为 Release 约束；Gate 2 前仍禁止正式业务编码。|
|Rollback|撤销 Gate 1 时恢复 Phase 0 `IN_PROGRESS`：POC-03 重新执行全新独立留出集，POC-06 补齐 Server Office 实开；Architecture/Data/API 冻结活动停止。|

## DEC-20260922-037

|字段|内容|
|---|---|
|Decision ID|DEC-20260922-037|
|Date|2026-09-22|
|WBS|AF-01 Architecture Baseline Consolidation|
|Decision|在锁定模块化单体内把 V1 Scope 收敛为 Platform 公共模块、AI/RAG、Capability 与七个实施业务域，并单列 `output` 作为输出编排模块。`output` 只构造 OutputContext、调用 PluginService 和登记制品，不自行实现格式渲染或直接操作插件进程。|
|Reason|V2.1 功能子系统包含 Output，但最小模块清单未单列；若把输出编排并入 Plugin，会混淆业务输出上下文与进程/包管理边界。单列编排模块可以保持业务依赖稳定，又不改变 python-docx/python-pptx 与 Plugin 技术基线。|
|Impact|形成 22 个客户运行模块与 1 个独立 Developer Workbench 信任区的边界候选；所有跨模块写入通过 Application Port/Domain Event，文件、AI、RAG、Plugin、Review、Trace、Audit 各有唯一 Owner。未冻结实体字段、表或 API。|
|Rollback|在 Architecture Freeze 前可把 `output` 编排职责合并到 Solution Application 层并删除候选模块；不得把职责合并到 Plugin 进程管理实现或引入新的渲染技术栈。|

## DEC-20260922-038

|字段|内容|
|---|---|
|Decision ID|DEC-20260922-038|
|Date|2026-09-22|
|WBS|AF-02 Application Contract|
|Decision|模块间同步交互采用技术无关 Application Port；跨模块状态传播使用最小 Domain Event。第一版同步事件进程内分发，长任务和需要恢复的事件写 PostgreSQL Job/Outbox，并按至少一次处理与幂等消费设计；不引入消息队列。|
|Reason|模块化单体需要稳定边界但不需要分布式基础设施。Application Port 防止跨模块访问内部表，持久化 Job/Outbox 满足长任务和恢复需要，同时符合禁止 Redis/消息队列的基线。|
|Impact|六个公共服务、Document/Evidence 读取端口、18 个事件及错误语义形成候选 Contract；未固定 REST、ORM、表结构或 Python 签名。|
|Rollback|Architecture Freeze 前可合并或拆分事件语义；不得改为直接跨模块写表或新增消息队列，除非提交 L3 Change Request。|

## DEC-20260922-039

|字段|内容|
|---|---|
|Decision ID|DEC-20260922-039|
|Date|2026-09-22|
|WBS|AF-03 Security / File / Job / Runtime Boundaries|
|Decision|在 V2.1 基线内固定默认拒绝的请求安全链、受控文件生命周期、Secret 引用边界、PostgreSQL Job/Outbox 至少一次语义、三类日志以及 API/Worker/Plugin/Developer Workbench 信任区。Plugin 独立子进程只作为故障与凭据隔离，不宣称为可运行任意第三方代码的强安全沙箱。|
|Reason|模块与 Application Contract 已明确，但如果认证授权顺序、文件原子性、Worker 系统主体、Secret 解密范围和日志数据边界不统一，后续 Data/API 设计会产生绕过 ProjectId、泄露路径/凭据或重复任务写入的风险。V1 又明确禁止引入 Redis、消息队列、容器化插件和第三方市场。|
|Impact|后续 Data Model 与 API Contract 必须承载服务器端 Session、CSRF、资源授权、不可变文件版本、Job 租约/幂等、SecretRef、Audit 与可信时间状态语义；具体表名、字段、REST 路径、密码哈希库和服务管理器仍未冻结。Windows 11、Windows Server 2025、Debian 13 保持正式目标，但 Debian 与 Server Office 未验证事实不变。|
|Rollback|Gate 2 前可调整内部顺序或端口粒度；不得弱化默认拒绝、ProjectId 隔离、License 私钥隔离、文件受权访问或 Audit 不可普通删除等基线。若需引入新基础设施或强插件沙箱，提交 L3 Change Request。|

## DEC-20260922-040

|字段|内容|
|---|---|
|Decision ID|DEC-20260922-040|
|Date|2026-09-22|
|WBS|AF-04 Architecture Decision Records|
|Decision|将七项长期架构决策分别固化为 ADR-003～ADR-009，而不合并成单一总 ADR；其状态标记为继承已批准基线但尚未通过 Gate 2 完整冻结。ADR-009 单独保留 POC-03 质量失败和 Gate 3/UAT 阻塞，避免被一般 AI/RAG 架构决策掩盖。|
|Reason|模块化单体、AI/RAG、Plugin、License、Job、文件存储和质量控制的变更触发条件、回滚路径与验收 Gate 不同。独立 ADR 可以让后续 Data/API 设计逐项追溯，也能在某一决策被替代时保留其他决策稳定。|
|Impact|Architecture Freeze Candidate 将引用九份 ADR；ADR-003～009 均具备 Context、Decision、Consequences、Rejected Alternatives 和 Rollback/Change Rule。未引入新技术栈、Schema、API 或正式业务代码。|
|Rollback|Gate 2 前可合并、拆分或调整 ADR 候选；必须保留历史失败与用户例外，不得通过文档重组弱化 L3、Release、Gate 3 或 UAT 约束。|

## DEC-20260922-041

|字段|内容|
|---|---|
|Decision ID|DEC-20260922-041|
|Date|2026-09-22|
|WBS|AF-05 Architecture Freeze Candidate|
|Decision|将 AF-01～AF-04 的详细成果汇总为 `ARCH-CANDIDATE-V1`，采用“显式允许依赖、其余全部禁止”的依赖矩阵，并把同步请求、文件、AI 正式化、Job 和 Output/Plugin 固化为五类运行视图。七项 Phase 0 例外与五项持续风险全部保留关闭 Gate，不因形成候选而视为已解决。|
|Reason|Data Model Freeze 需要稳定的模块 Owner、跨模块 Contract、信任边界、运行流程和风险输入；单一候选清单可以消除多个设计文件之间的解释歧义，同时保留详细文档和 ADR 的反向追溯。|
|Impact|AF-01～AF-05 状态均为 PASS，项目进入 DM-01。Architecture 版本为候选而非正式冻结；实体字段、物理 Schema、REST API 和业务代码仍未授权，正式开发继续由 Gate 2 阻塞。|
|Rollback|Gate 2 前可回退为 AF-05 IN_PROGRESS 并修订候选；不得删除 Phase 0 失败/例外或绕过 L3。Gate 2 后的总体架构变更必须提交独立 Architecture Change Request。|

## DEC-20260922-042

|字段|内容|
|---|---|
|Decision ID|DEC-20260922-042|
|Date|2026-09-22|
|WBS|DM-01 Core Entity / Aggregate Catalog|
|Decision|采用“逻辑对象 Aggregate + 不可变 Version Aggregate”的正式制品模式；AI 建议只保留在 AITask/AIInvocation 聚合，人工显式接受后由目标 Domain 创建新的 Draft Version，再经 Review 指定版本正式化。为落实既有 Review/Event/Job/License 语义，补充 HandoverAnalysisVersion、PlanVersion、TrustedTimeState 和 OutboxEvent 等必要聚合根。|
|Reason|若版本作为可变字段内嵌在逻辑对象，送审锁定、历史确认、Trace 和并发编辑会相互冲突；若 AI 对象可直接切换为正式状态，则无法证明人工确认、证据和输入版本。独立 Version 与显式接受命令可以保持历史不可变和责任边界。|
|Impact|22 个客户运行模块形成 65 个 Aggregate Root，Developer Workbench 另有 3 个且不进入客户 Schema。后续 DM-02～DM-06 必须沿用 Owner、Scope、Version Ref 和 AI/正式事实分离；物理表和外键仍待 Schema V1。|
|Rollback|Gate 2 前可合并低价值运行聚合，但不得合并 AI Suggestion 与正式 Domain Version、不得取消不可变版本/ReviewSubject 或跨模块稳定引用原则；涉及这些原则的改变按 L3 核心数据模型调整处理。|

## DEC-20260923-043

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-043|
|Date|2026-09-23|
|WBS|DM-02 Platform and Security Data Model|
|Decision|Project 不保存 current_stage 可写副本，由 ProjectWorkflow 唯一拥有阶段状态；Review 绑定逻辑主题身份，ReviewRound 绑定具体不可变主题版本。用户名唯一键采用 trim + Unicode NFC + invariant case-fold；Session 只持 Token/CSRF 摘要并绑定 credential_version；Project Role 只存在 ProjectMember，DeploymentAdmin 保持独立部署角色。|
|Reason|复制 current_stage 会造成 project 与 workflow 的双写和反向依赖；Review 若永久绑定单一版本则无法同时满足送审锁定、退回升版重审和历史决定保留。规范化用户名、摘要 Session 与角色分离可让授权和凭据失效语义在 Schema/API 阶段保持唯一解释。|
|Impact|DM-01 聚合数量不变，但 PRJ-01、RVW-01、RVW-02 的包含语义已校正。后续 Schema 必须支持凭据版本失效、单一有效项目成员、Workflow 乐观并发、Review 轮次/版本唯一性、Secret 单 Active Version 与 TrustedTime 单调更新。|
|Rollback|Gate 2 前可调整规范化或状态命名；不得恢复 Project/Workflow 双写、覆盖 Review 历史、保存原始 Session Token/Secret 明文或合并部署/项目角色。触及安全或核心数据机制时按 L3 处理。|

## DEC-20260923-044

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-044|
|Date|2026-09-23|
|WBS|DM-03 Document / Evidence / Trace / Version Data Model|
|Decision|分离 Document 逻辑身份、不可变 DocumentVersion 与 FileObject 物理元数据；以类型化 EvidenceLocator 和 EvidenceBinding 表达证据定位与支持关系，TraceLink 仅表达业务制品间的来源与追溯。实际调研记录归为 PROJECT_RECORD 并作为主要事实来源，调研业务表单归为 TEMPLATE，只能辅助组织调研而不能独立证明客户事实。|
|Reason|逻辑对象、版本和物理文件混合会导致覆盖历史、路径泄漏和定位漂移；Evidence 与 Trace 共用一种关系会混淆“原文证明”与“业务制品来源”。明确实际记录优先也落实了用户此前确认的调研事实规则，并支持从待办一键定位原文。|
|Impact|DM-01 的 EVD-02 Scope 调整为 GLOBAL_OR_PROJECT。后续 Schema/API 必须实现稳定引用、九类定位器、文件状态与恢复、版本保留和图关系授权；Evidence Viewer 不得暴露绝对路径或把短摘录当作权威原文。本阶段仍未定义物理表、API 或 Migration。|
|Rollback|Gate 2 前可细化定位器和关系枚举；不得恢复绝对路径定位、覆盖 DocumentVersion、让模板独立证明客户事实，或重新合并 EvidenceBinding 与 TraceLink。触及核心数据模型时按 L3 处理。|

## DEC-20260923-045

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-045|
|Date|2026-09-23|
|WBS|DM-04 AI / RAG / Job / Plugin / Output Data Model|
|Decision|AITask 只通过统一 AIService 创建不可变 AIInvocation，并保存 Prompt/Input/Context/Provider/Model/Schema 与外发授权快照；Embedding Index 绑定精确模型、维度、Chunk Profile 和 Scope，不兼容变化必须新建索引并全量重建；Job/Outbox 采用至少一次、幂等与租约 fencing；Plugin 成功只产生待校验结果，OutputArtifact 在 FileObject/DocumentVersion/Hash 全部登记后才可发布。将 RAG-04 RetrievalRun Scope 从 PROJECT 校正为 GLOBAL_OR_PROJECT，以落实既有 GLOBAL/PROJECT 双知识域。|
|Reason|这些运行对象跨越外部 Provider、PostgreSQL、文件系统和独立进程，无法可靠承诺精确一次或依赖可变“当前版本”。不可变快照、Scope 隔离、fencing 和分阶段发布可避免模型/索引漂移、跨项目泄露、过期 Worker 提交和半完成制品；GLOBAL 检索记录也必须可审计，不能因目录先前误限为 PROJECT 而丢失。|
|Impact|后续 Schema/API 必须实现 AI、Embedding、Reranker 的逐次外发授权引用，以及 Invocation/Index generation、单一活动索引、Job Lease fencing、Outbox 消费去重、Plugin 精确包版本和 Output 发布完整性；既往 PoC/复验授权不得自动复用于未来调用。POC-03 分类 48%/引用 74% 的质量失败保持 Gate 3/UAT 阻塞，不因模型冻结而关闭；本阶段仍未定义物理表、API 或 Migration。|
|Rollback|Gate 2 前可细化状态名、策略字段和保留方式；不得允许业务模块直连厂商 SDK/pgvector、复用不兼容向量、移除 Project 隔离/外发授权、宣称精确一次、让 Plugin 直连数据库/Secret，或让 AI/插件结果绕过人工确认和制品校验。触及这些边界时按 L3 处理。|

## DEC-20260923-046

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-046|
|Date|2026-09-23|
|WBS|DM-05 Implementation Domain Data Model|
|Decision|实施业务主链统一采用逻辑对象与不可变版本分离，正式指针只指向通过 Review 的指定版本；GLOBAL Capability 是标准能力事实，项目的 STANDARD_FUNCTION、NONSTANDARD_FUNCTION、DIFFERENCE、PENDING_CONFIRMATION 是 RequirementVersion 判断。实际调研记录优先于 TEMPLATE；NeedConfirm/ActionItem 必须保存明确问题、影响、选项、建议、人工输入规格和 EvidenceRef。Requirement→Solution 以章节版本内覆盖快照加 TraceLink IMPLEMENTS 表达，不新增可变双写关系；PlanVersion 固定最多六级 WBS 和仅 FS 的无环依赖。|
|Reason|现有 R1～R9 验证成果同时包含标准、非标、差异和待确认草案，但明确不是正式需求/方案。若直接把表格行或 AI 结果当作事实，会丢失来源、版本和人工责任；若只复制原文到待办，又无法提供友好维护提示和精确原文定位。不可变版本、Evidence Viewer、Review 与 Trace 可以在保留真实调研优先原则的同时形成完整交付链。|
|Impact|后续 Schema/API 必须实现各业务对象的逻辑身份/版本指针、ReviewSubjectSnapshot、CapabilityAssessment、AnalysisItem 输入提示、面对面调研来源标识、需求覆盖、专项设计校验和 WBS DAG 约束。R1～R9 文件保持历史验证制品，不自动导入正式数据库或转为客户事实；POC-03 质量失败仍由 Gate 3/UAT 阻塞。|
|Rollback|Gate 2 前可细化业务枚举、专项字段和状态名称；不得让 GLOBAL 基线被项目反写、让模板/AI 自动成为事实、覆盖已审核版本、取消 Evidence/Review/Trace、把待确认项静默转正，或放宽六级 WBS/仅 FS/无环约束。触及核心业务模型时按 L3 处理。|

## DEC-20260923-047

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-047|
|Date|2026-09-23|
|WBS|DM-06 Data Model Candidate Consolidation|
|Decision|将 DM-01～DM-05 汇总为 `DATA-MODEL-CANDIDATE-V1`，保持 22 个客户运行模块、65 个 Aggregate Root 和 3 个物理隔离 Developer Workbench Root。统一五类 Scope、稳定引用、六类生命周期、正式化链与物理清理六项前置；RetentionPolicy/RetentionHoldEntry 作为 platform.SystemConfiguration 的受控子实体，不新增 Root。采用 R0～R8 九类候选保留策略，其中 Audit/签名/Review 与正式项目资料候选默认 5 年，AI/RAG/Job 运行记录 180 天，临时区 7 天；Active Hold 和保护引用始终优先。|
|Reason|Schema V1 需要单一、无冲突的关系、基数、生命周期和保留输入。只写“历史保留”无法指导清理与容量设计，而把合同/法规期限硬编码又会产生合规风险；版本化策略、可延长默认值、Hold 优先和引用预检能同时提供可实施基线与客户配置空间。|
|Impact|Data Model Freeze 的六个 WBS 全部 PASS，形成 25 条核心不变量、14 项风险和 15 项 Schema 交接要求。后续 SC-01～SC-05 必须映射这些约束并验证空库/有数据升级；候选期限不构成法律结论，客户合同可延长，缩短正式/审计数据期限需在 Gate 2/Release 评审。POC-03、Server Office 和 Debian 未验证结论保持不变。|
|Rollback|Gate 2 前可调整候选期限、物理清理实现和 Schema 交接顺序；不得移除 Hold/保护引用、允许普通用户删除 Audit/正式历史、破坏 Owner/Scope/版本/Review/Evidence/Trace 边界，或把候选 Data Model 描述为已冻结物理数据库。触及核心数据、安全或合规边界时按 L3 处理。|

## DEC-20260923-048

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-048|
|Date|2026-09-23|
|WBS|SC-01 Logical-to-Physical Schema Mapping|
|Decision|客户运行时采用单一 PostgreSQL 数据库和单一 `plm` 应用 Schema，不为 22 个模块分别创建 PostgreSQL Schema；以 `plt_`、`auth_`、`prj_` 等 22 个短前缀表达表 Owner。65 个 Aggregate Root 各映射一个唯一 primary table，Owned Entity 按查询、唯一、顺序、状态和引用需要拆表。固定目标类型优先直接 FK；Review/Trace/Audit/Event 等多态引用采用受控 discriminator + object/version/project 列组，不新增全局共享写 object_registry。Developer Workbench 使用独立数据库/部署。|
|Reason|V1 是单服务器模块化单体并使用同一应用数据库身份，22 个 PostgreSQL Schema 不形成真正安全隔离，却增加 Alembic search_path、跨 Schema FK、备份恢复和离线运维复杂度。模块前缀与 Application Port 能清晰表达 Owner；全局 object_registry 会成为所有模块共同写热点并破坏唯一 Owner。|
|Impact|形成 65/65 Root primary table 映射及 owned table 候选，表名使用 ASCII lower_snake_case、目标不超过 55 字符。SC-02 必须补齐 Scope/ProjectId、Version、固定 FK、多态白名单、唯一/CHECK 与不可变约束；SC-03/04 再定义索引、pgvector、Migration 和恢复测试。本阶段没有创建 ORM、Migration 或业务表。|
|Rollback|Gate 2 前可改为少量分组 Schema 或调整 table/child 拆分，但必须提供 Alembic、权限、备份和跨平台证据；不得把 Developer Workbench 放入客户数据库、取消 Owner 前缀/边界、用 JSONB 隐藏 ProjectId/核心 FK，或引入共享写 object_registry。|

## DEC-20260923-049

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-049|
|Date|2026-09-23|
|WBS|SC-02 Field Types and Constraints|
|Decision|主键使用 PostgreSQL 18 `uuidv7()`；时间使用 UTC `timestamptz(6)`，日历计划日期单独使用 `date`。状态采用 text + named CHECK，不使用 PostgreSQL ENUM/DOMAIN；固定长度 Hash 使用 `bytea` 并检查字节数。PROJECT/GLOBAL_OR_PROJECT 表显式保存 ProjectId/Scope，并以复合 FK 防跨项目归属漂移；FK 默认 NO ACTION、NOT DEFERRABLE，V1 不启用 CASCADE。Version/current pointer 使用复合归属约束，内容不可变、append-only、状态迁移及多态目标由数据库约束、受控 trigger 和 Application Command 共同保护。V1 不把 RLS 作为主防线且默认不启用，授权依靠 ProjectAuthorizationService、显式过滤、复合约束与负向测试。|
|Reason|有序 UUID 降低随机主键的索引局部性成本，同时不承载授权语义；text + named CHECK 比 ENUM 更利于 Alembic 的双版本升级/回退。显式 ProjectId 与复合 FK 能在 Repository 漏写过滤时继续阻止跨项目归属，而过早启用 RLS 会显著增加连接池、后台 Job、Migration 和恢复路径的策略复杂度。NO ACTION 与无自动级联保证 Retention、Hold、Audit 和保护引用先完成预检。|
|Impact|65 个 Root 已分配 M/V/A/R/SEC 字段 Profile，形成 28 组唯一语义、多态白名单、敏感列与数据库角色候选。SC-03 必须把条件唯一、授权过滤、Job/Outbox、Audit/Trace、Retention、FTS 与 pgvector 转为索引和关键查询计划；SC-04 再生成 Alembic 并执行空库/有数据 up/down、绕过 ORM 的负向测试。本阶段没有创建 ORM、Migration、业务表或索引。|
|Rollback|Gate 2 前可调整具体类型长度、CHECK 值、索引或受控 trigger 实现，但必须提供兼容 Migration 与 up/down 证据；不得弱化 Project 隔离、版本不可变、Secret/Session/License 敏感边界、Hold/保护引用预检，或让普通删除通过 CASCADE 绕过清理控制。若未来启用 RLS，须以 ADR 和连接池/Job/Migration/恢复全链验证后增量引入。|

## DEC-20260923-050

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-050|
|Date|2026-09-23|
|WBS|SC-03 Index and Critical Query Design|
|Decision|索引采用“约束索引复用 + 引用侧 FK B-tree + Project 前缀/keyset + 条件唯一 + 专用运行索引”的最小集合。Job/Outbox 使用短事务、稳定排序、`FOR UPDATE SKIP LOCKED`、Lease fencing 与消费幂等。全文使用受控中文 Token `search_body` 的 stored `tsvector` + GIN；向量使用按受支持维度由 Migration 创建的 HNSW 表达式索引族，查询强制 Scope/Project/EmbeddingIndex 过滤并启用 iterative scan，不足时只能在同授权范围扩大扫描或精确回退。V1 不启用按项目动态分区、每项目索引或 Runtime DDL。|
|Reason|PK/UNIQUE 重复索引和无消费者索引会增加单服务器的写放大与维护成本；Project 前缀和双向引用索引同时支撑授权、删除预检和稳定分页。pgvector 共享 HNSW 的过滤发生在近邻扫描过程中，不能只依赖默认候选数；模型维度又可能变化，因此需要受控维度索引、迭代扫描和同 Scope 精确回退。Job/Outbox 的至少一次语义要求数据库领取与外部执行分离，并由 fencing/幂等阻止过期 Worker 发布。|
|Impact|形成 20 个关键 Query ID、28 组唯一语义到 29 个物理唯一键映射、11 项风险及 SC-04 的数据规模/并发/执行计划验收计划。SC-04 必须生成 index manifest，验证 `EXPLAIN (ANALYZE, BUFFERS)`、多项目 Recall、20 Worker 领取/崩溃回收、Retention 保护引用和索引写放大；POC-02/03 的 HNSW 参数仅作初值，不能直接作为生产性能结论。HNSW `vector` 超过 2,000 维默认不兼容，替代表示需质量 PoC。本阶段没有创建 ORM、Migration、表或索引。|
|Rollback|Gate 2 前可依据 SC-04 计划删除冗余索引、调整列序/INCLUDE、HNSW 参数或固定 hash partition；必须保留 Project 隔离、同 Scope 精确回退、Job fencing/幂等和保护引用查询。引入独立向量库、消息队列、Redis、运行时 DDL或按客户动态分区属于超出当前方案的变更，须按 L3 处理。|

## DEC-20260923-051

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-051|
|Date|2026-09-23|
|WBS|SC-04 Migration and Recovery Validation|
|Decision|Gate 2 前建立独立 `VALIDATION_ONLY` Schema Contract：机器可读 manifest 覆盖全部 65 个 Root，关键安全/项目/文档/Review/Job/Audit/RAG/Trace/Retention/WBS 表使用代表字段与真实约束，其余 Root 只验证 M/V/A/R/SEC Profile。Alembic 0001 验证结构，0002 验证索引和 append-only guard；`plm.alembic_version` 位于应用 Schema。强过滤小向量集合允许 planner 使用 B-tree 后精确排序，HNSW 通过独立物理计划和 exact Recall 对照验证，不强制优化器采用成本更高的路径。|
|Reason|SC-01～SC-03 已冻结结构机制，但尚未形成每个 owned table 的完整生产列清单；直接生成完整业务 Migration 会把推断误写为正式事实。Profile + 关键代表表能在不越过 Gate 2 的情况下真实验证 PostgreSQL/Alembic、跨项目 FK、partial unique、GIN/HNSW、Job 并发、Retention 和恢复。优化器按选择性选择 exact fallback 是正确行为，强关 planner 选项不能作为生产性能证据。|
|Impact|Windows 11 上 4/4 单元、65 Root 空库/有数据 up/down、10/10 负向约束、20/20 Worker 唯一领取、Retention/Hold、备份恢复、GIN/HNSW 与敏感扫描通过；生成可重复 JSON 证据。SC-05 必须继续明确验证性/生产边界并汇总未细化 owned table；Gate 2 后正式 Migration 需冻结 revision、与最终 ORM 同步并重跑全量测试。Server 使用既有 POC-02 可行性证据，本轮未重跑；Debian 保持 Release 未验证约束。|
|Rollback|验证工作区可整体移除，不影响任何生产/客户数据库。可在 SC-05/Gate 2 前调整代表表和验证规模，但不得用 Profile 最小列替代正式字段设计、删除 Project 复合保护、append-only、Job fencing/幂等、Hold/保护引用或备份恢复要求。|

## DEC-20260923-052

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-052|
|Date|2026-09-23|
|WBS|SC-05 DB Schema Candidate 汇总|
|Decision|执行规则改为不自动读取 Codex/GPT 周额度，不再以剩余低于 20% 作为停止新任务或 WBS 的条件；仅在用户明确要求时查询。额度重置、购买或消耗 reset credit 仍需逐次明确确认。|
|Reason|用户在进入 SC-05 时明确取消原 20% 停止限制并要求不再检查；该最新明确指令优先于仓库此前的额度保护规则。|
|Impact|`AGENTS.md`、`.ai/SKILL.md`、项目开发 Skill 与 `STATUS.md` 的当前执行规则同步更新；历史决策和 Changelog 作为当时事实保留，不回写删除。该变更不影响 Gate、L3、Secret、客户数据外发或 Git 安全约束。|
|Rollback|用户可再次明确启用新的额度检查频率和停止阈值；在此之前不得自行恢复自动检查。|

## DEC-20260923-053

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-053|
|Date|2026-09-23|
|WBS|SC-05 DB Schema Candidate 汇总|
|Decision|以 `database-schema-v1-candidate.md` 作为 `DB-SCHEMA-CANDIDATE-V1` 单一规范入口，完整固化 65 个 Root primary table/PK/Profile 和 20 个 Query ID；SC-01～SC-04 作为受控明细附件。验证性 Schema Contract 仅作为机制证据，Gate 2 后按模块形成正式 ORM/Alembic，不将 generic Profile 最小列或 5 个代表 child 直接复制为生产 Schema。|
|Reason|逐字复制 SC-01～SC-04 会造成重复和漂移，但只有摘要又不足以检查 Root/Query 完整性。单一入口 + 机器 manifest + 受控明细能统一优先级、保留可追溯性，并如实区分设计候选、验证证据和正式生产实现。|
|Impact|Database Schema V1 候选覆盖 22 Owner、65 Root、29 个物理唯一键、20 个关键查询、14 项开放风险和 14 条 API Contract 输入。SC-05 静态一致性检查全部通过；项目可进入 API Contract V1，但 Architecture/Data Model/Schema/API 仍须 Gate 2 一并确认，正式业务编码继续阻塞。|
|Rollback|Gate 2 前可回退本汇总文件并恢复 SC-05 为待完成；不得删除 SC-01～SC-04 历史证据或把验证性 Migration 改称生产 Migration。若修改 65 Root、Owner、Scope、安全机制或基础设施，必须按 L3 处理。|

## DEC-20260923-054

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-054|
|Date|2026-09-23|
|WBS|API-01 Resource Catalog and Common Protocol|
|Decision|API V1 使用 `/api/v1` REST/JSON、multipart 流式上传和 SSE；JSON 成功/错误均携带 `trace_id`。PROJECT 资源强制 `/projects/{project_id}` 路径并再次校验归属；Session 使用 HttpOnly `plm_session`，状态改变请求使用 `X-CSRF-Token`。Mutable 资源以 ETag/If-Match 映射 `expected_version`，可重试写操作使用 Idempotency-Key，列表使用绑定 Scope/查询指纹的不透明 keyset cursor。65 个 Root 按 DIRECT/NESTED/READ_ONLY/INTERNAL 分类，内部 Job/Outbox/File/Embedding/安全状态不提供通用 CRUD。|
|Reason|统一 HTTP 外壳可避免各模块自行发明认证、分页、并发和错误语义；Project 路径、资源归属双检、固定版本引用和默认拒绝能够把 Architecture/Data/Schema 的隔离不变量提升为可测试 Contract。分类暴露可保留完整领域模型，同时避免把数据库 Root 或运行时细节机械暴露成 API。|
|Impact|后续 API-02～API-04 必须逐操作登记 Owner Port、Role、Scope、License、CSRF、If-Match、Idempotency、Audit 和错误码；API-05 汇总 OpenAPI/权限/错误/SSE。API Contract 工作从已同步的 Schema 检查点进入 `feature/api-contract-v1` 分支。DeploymentAdmin 不自动获得项目业务数据访问权；V1 不使用通用 DELETE、Offset 主分页、GraphQL、WebSocket 或任意 filter/order 表达式。|
|Rollback|Gate 2 前可修改具体路径名、Cookie/Header 名或资源暴露级别并重跑 65 Root/权限一致性检查；不得弱化 Project 隔离、Session/CSRF、固定版本、幂等、乐观并发、文件路径隐藏或内部 Root 不直出的安全边界。冻结后的 Breaking Change 必须走新端点、v2 或 API Change Request。|

## DEC-20260923-055

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-055|
|Date|2026-09-23|
|WBS|API-02 Platform, Security, Document and Governance Contract|
|Decision|平台/安全/治理 API 采用专用状态命令而非通用 DELETE/状态 PATCH；Session、FileObject、Parse runtime、TrustedTimeState 等内部 Root 不提供通用 CRUD。文件上传固定为 UploadIntent → 流式 Content → 幂等 Commit 三步，Commit 同步创建不可变 DocumentVersion 并返回 Parse JobRef。Review Round、EvidenceBinding 和 TraceLink 一律引用固定 Version；License 无效时只开放健康、登录、当前 Session 和 DeploymentAdmin 的五个 License 恢复端点。|
|Reason|内部运行 Root 直接暴露会允许客户端绕过 Application Port、状态机、文件一致性或可信时间。三步上传能隔离大文件传输与业务事务并支持崩溃恢复；固定版本引用保证 Review/Evidence/Trace 可审计。最小 License 恢复面既允许现场修复，又不会把无效 License 变成业务旁路。|
|Impact|形成 10 Owner/22 Root 的 86 个 Operation、42 个模块错误码、DTO 禁止字段、权限/Audit/测试矩阵。DeploymentAdmin 仍不是项目数据超级用户；Secret/临时密码 write-only，Viewer/下载不返回 Storage Locator，Trace 图逐节点授权。后续 API-03/04 必须沿用 API-01 公共 Envelope、CSRF、Project 隔离、If-Match、幂等和错误安全边界。|
|Rollback|Gate 2 前可调整具体路径、Operation 分组或角色白名单并重跑 Contract lint；不得改为通用内部 Root CRUD、返回 Secret/路径、动态 current 引用、跨项目可见、无 CSRF 状态写或扩大 License 恢复面。冻结后的 Breaking Change 走新端点、v2 或 API Change Request。|

## DEC-20260923-056

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-056|
|Date|2026-09-23|
|WBS|API-03 AI, RAG, Job, Plugin and Output Contract|
|Decision|所有可能向外部 AI Provider 发送数据的操作必须先生成可审计的外发预览，并取得绑定 Provider、Region、Purpose、Source、Payload Bounds 与单次逻辑操作的明确授权；授权只允许同一 Payload 的受限重试，不得复用 PoC、其他任务或历史轮次授权。AI Suggestion 始终标记 `NOT_FORMAL_FACT`，接受建议只能经目标 Owner Port 创建 Draft。Chunk、Embedding、Job Lease/fencing 与 Outbox 保持内部对象；Plugin 仅接受开发者签名包并通过独立子进程受控执行，不提供公共任意调用；Output Artifact 只有在二次校验和 Document 登记完成后才可发布。|
|Reason|外发授权必须能证明谁在何时为哪一最小载荷授权，避免授权漂移和客户数据越界；AI 建议、异步任务、插件及文件输出若直接暴露内部状态或绕过 Owner Port，会破坏事实确认、Project 隔离、at-least-once 幂等、fencing 与文件可追溯性。|
|Impact|形成 5 Owner/15 Root 的 79 个 Operation、51 个模块错误码、DTO、权限、SSE、强制 Audit 和测试矩阵。API-04/05 必须沿用逐次外发授权、`NOT_FORMAL_FACT`、Project 隔离、内部运行 Root 不直出、签名插件和输出二次校验边界。POC-03 的分类/引用质量仍为 Gate 3/UAT 阻塞项；本轮实际外部调用 0。|
|Rollback|Gate 2 前可调整具体路径、Operation 分组、角色白名单或事件粒度并重跑 Contract lint；不得弱化逐次最小外发授权、Project 隔离、AI 建议态、Job fencing、签名插件/无任意调用或输出校验与登记边界。冻结后的 Breaking Change 走新端点、v2 或 API Change Request。|

## DEC-20260923-057

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-057|
|Date|2026-09-23|
|WBS|API-04 Implementation Business Chain Contract|
|Decision|Capability、Handover、Survey、Requirement、Prototype、Solution 与 Plan 统一采用逻辑 Identity + 不可变 Version API；版本正文无 PATCH/DELETE，修订创建新 Version。各 Owner 的 `:submit-review` 只做送审前校验和 ReviewService 原子编排，不替代 API-02 的 Reviewer/锁定/决策规则；ReviewCompleted 后由 Owner 幂等更新正式指针、Trace、Audit 与 Outbox。实际调研记录优先于 TEMPLATE，AI Suggestion 只可经白名单 Owner Port 创建 Draft。所有跨阶段关系固定 VersionRef；上游替代只生成影响项，不自动改写或批准下游。|
|Reason|统一版本与 Review 编排可以让业务界面提供清晰动作，又不形成第二套评审引擎；固定引用、来源优先级和 Owner 正式化边界可防止模板/AI 冒充客户事实、动态当前版本漂移及跨模块直接写表。上游变化显式影响分析可保留历史交付并避免静默级联。|
|Impact|形成 7 Owner/28 Root 的 158 个 Operation、54 个模块错误码、DTO、Role × Resource 权限、SSE、强制 Audit 和测试矩阵。API-05 必须验证统一资源/Operation/错误/权限目录，保留不可变版本、Project 隔离、Evidence 定位、Review 锁、AI Draft 和影响分析边界。POC-03 分类/引用质量仍为 Gate 3/UAT 阻塞；本轮实际外部调用 0。|
|Rollback|Gate 2 前可调整具体路径、Operation 分组、角色白名单或 DTO 拆分并重跑 Contract lint；不得弱化版本不可变、固定 VersionRef、统一 Review、实际调研优先、AI 不自动正式化、跨项目拒绝、方案覆盖/Trace 一致或 WBS 六级/FS DAG 边界。冻结后的 Breaking Change 走新端点、v2 或 API Change Request。|

## DEC-20260923-058

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-058|
|Date|2026-09-23|
|WBS|API-05 API Contract Candidate Aggregation|
|Decision|`api-contract-v1-candidate.md` 作为 API V1 单一汇总入口，API-01～04 保持规范明细；不复制 323 个 Operation 形成第二份人工清单，而由 `contract_lint.py` 从四份源文档确定性生成带 SHA-256 的机器 manifest。manifest 统一索引 65 Root/暴露、Operation/展开 Path、错误、SSE、Query 映射和 18 个核心枚举族，但不冒充可部署 OpenAPI；Gate 2 后 FastAPI/Pydantic 生成的实际 OpenAPI 必须与该 manifest 做 Contract diff。|
|Reason|完整手工复制会形成重复规范和漂移，只有文字摘要又无法自动验证。单一汇总 + 受控明细 + 可再生机器目录既保留人类可评审语义，也提供实现和 CI 所需的稳定输入，并如实区分设计契约与尚未创建的运行 OpenAPI。|
|Impact|API-05 静态验证覆盖 22 Owner、65 Root、323 Operation、363 Method/Path 变体、150 错误、18 SSE、20 Query 映射和 18 枚举族，5/5 测试 PASS。Architecture/Data Model/Schema/API 四份 Gate 2 候选已齐备；Gate 2 仍需用户明确确认，正式编码未获授权。|
|Rollback|Gate 2 前可删除生成 manifest/校验器并恢复 API-05 为待完成；不得删除 API-01～04 历史或把未实现的 OpenAPI 描述为已运行。Gate 2 后修改冻结 Operation/DTO/枚举/错误/安全边界必须走非 Breaking 扩展、v2 或 API Change Request。|

## DEC-20260923-059

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-059|
|Date|2026-09-23|
|WBS|Gate 2：Architecture / Data Model / DB Schema V1 / API Contract V1 Freeze|
|Decision|依据用户明确指令“批准 Gate 2，冻结 Architecture、Data Model、DB Schema V1 和 API Contract V1”，将 `ARCH-CANDIDATE-V1`、`DATA-MODEL-CANDIDATE-V1`、`DB-SCHEMA-CANDIDATE-V1` 和 `API-CONTRACT-CANDIDATE-V1` 以提交 `64cdf09` 的内容冻结为正式开发基线。候选标识为保持历史 Trace 不重命名；Gate 2 对正式开发的阻塞解除，下一 WBS 为 Phase 1 `1.01 定义模块目录规范`。|
|Reason|AF-01～AF-05、DM-01～DM-06、SC-01～SC-05、API-01～API-05 已全部 PASS；跨层 22 Owner、65 Root、323 Operation、363 Method/Path、150 错误、18 SSE 和 20 Query 映射一致，API-05 Contract Lint 5/5 PASS。用户已完成正式 Gate 决策，满足进入基础工程的前置条件。|
|Impact|允许按 WBS 创建正式基础工程和业务实现；冻结后的总体架构、核心数据模型、DB Schema V1、Breaking API、技术栈、安全/License 机制或 Scope 变化必须走 L3 Change Request。批准不等于生产 ORM/Migration、运行 OpenAPI、性能、AI 质量、发行或 UAT 通过；POC-03 继续阻塞 Gate 3/UAT，Server Office、Debian 13、Ghostscript AGPL 发行合规和 SC-04 验证性边界继续保留。|
|Rollback|Gate 决策不得静默回退或通过技术提交抹除。若需撤销或修改冻结基线，必须由用户明确批准独立 Change Request，保留本决策、原冻结提交和全部历史证据；普通 Git revert 不改变该历史批准事实。|

## DEC-20260923-060

|字段|内容|
|---|---|
|Decision ID|DEC-20260923-060|
|Date|2026-09-23|
|WBS|1.01 定义模块目录规范|
|Decision|采用单仓库双应用布局：客户运行代码放在 `apps/backend` 与 `apps/frontend`；后端使用 `src/plm_assistant` Python src layout，FastAPI 与 Worker 共用 22 个 `plm_assistant.modules.<module>` 模块；每个模块固定为 `api/application/domain/infrastructure` 四层，跨模块只允许目标模块 `application.public`。License/Plugin 签名和 Release 工具放在物理分离的 `tools/developer-workbench`，不进入客户运行包。未进入实现 WBS 的模块不创建空 package。|
|Reason|该布局直接承载冻结的模块化单体、22 Owner 和 API/Application/Domain/Adapter 依赖方向，同时避免 FastAPI 与 Worker 复制业务代码。独立 Workbench 路径能防止私钥工具误入客户包；按需创建模块可避免 22 组空目录和伪实现。|
|Impact|后续 1.02/1.03 分别在稳定的 backend/frontend 根创建 App；模块 WBS 必须遵循固定层次、测试镜像和依赖白名单。新增运行模块或把 Workbench 合并进客户运行包属于 L3；普通模块内子目录调整属于 L2。|
|Rollback|在尚无运行实现和 Migration 时，可删除新增骨架并恢复为纯文档仓库；若需变更顶层布局，先更新机器 manifest、验证和本决策的后继记录。不得借回滚改变冻结的 22 模块、信任区或依赖矩阵。|

## DEC-20260924-061

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-061|
|Date|2026-09-24|
|WBS|1.02 FastAPI app factory|
|Decision|后端采用无模块级全局 App 的 `create_app()` 工厂，由 Uvicorn `--factory` 加载；每个实例拥有独立的 lifespan 与 `HealthService`。只注册 `/health/live`、`/health/ready` 两个非业务健康端点，Swagger、ReDoc 和外部 OpenAPI 暂不暴露。Readiness 通过 Composition Root 注入同步/异步探针，未启动、探针返回非 True 或抛异常时统一失败关闭为最小 `503 {"status":"NOT_READY"}`。直接依赖固定为 FastAPI 0.141.1、Uvicorn 0.53.0，测试按 Starlette 1.7 要求使用 HTTPX2 2.13.1。|
|Reason|工厂模式避免测试、Worker 或多实例共享可变状态，并为后续 Config、DB Session、日志、Trace 和 Router 逐步装配提供稳定入口。健康面符合冻结 Contract 的最小披露原则；注入探针允许后续数据库/存储检查接入而不改变公开响应。固定已在 Python 3.13.14 验证的直接版本可减少三平台漂移。|
|Impact|当前运行面只有两个健康端点，不初始化数据库、License、Session 或业务模块；外部 OpenAPI 仍为 404，但 `app.openapi()` 可供后续 Contract diff 使用。1.04/1.09 可向工厂装配基础设施；1.06 负责正式错误 Contract，1.08 负责 TraceId。|
|Rollback|删除 WBS 1.02 新增 package/测试并恢复 backend README/pyproject 即可回到 1.01；不影响数据库或客户数据。更换 FastAPI/Uvicorn、改变健康路径或暴露额外未冻结 API 必须按依赖/API 变更规则重新评审。|

## DEC-20260924-062

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-062|
|Date|2026-09-24|
|WBS|1.03 Vue app shell|
|Decision|前端采用 Vue 3 + TypeScript + Vite 的单页应用壳，使用 Vue Router 维护首页与 catch-all 404；目录先建立 `app` 与 `shared` 两个公共层，不预建业务模块。浏览器仅通过 same-origin `/health/ready` 读取后端就绪状态，开发代理只指向本机 `127.0.0.1:8000`；不在浏览器存储 Secret、Token 或业务事实。固定 Node 24/pnpm 11 工具链和直接依赖版本，并以 lockfile 及 workspace override 将传递依赖 `ini` 固定为无已知漏洞的 1.3.8。|
|Reason|最小应用壳为后续认证、错误处理和业务模块提供稳定挂载点，同时避免在对应 WBS 前形成伪页面或客户端信任边界。same-origin 健康检查不会引入厂商调用或跨域凭据；固定依赖和安全 override 可复现当前 Windows 11 验证结果。|
|Impact|当前 UI 只包含产品导航骨架、后端连接状态、可访问性基础样式、安全错误边界和 404；没有登录、权限裁决、业务路由、数据库或外部 AI 调用。后续业务页面应放入 `src/modules` 并经正式 API/权限 WBS 接入，客户端显示权限不得代替服务端授权。|
|Rollback|删除 WBS 1.03 新增前端源码、测试、lockfile 和验证证据并恢复 frontend README 即可回到空前端目录；不影响数据库、后端或客户数据。更换冻结技术栈、引入跨域业务调用或改变 `/api/v1` Contract 必须按对应 L3/API 变更规则处理。|

## DEC-20260924-063

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-063|
|Date|2026-09-24|
|WBS|1.04 SQLAlchemy session|
|Decision|客户运行时采用同步 SQLAlchemy 2.0.54 + psycopg 3.3.5；每个进程持有一个 `DatabaseRuntime`/Engine Pool，每个 Application Command 使用一次性 `SqlAlchemyUnitOfWork` 和独立 Session/事务。事务 `autobegin=False`，进入 UoW 时显式 begin；只有显式 `commit()` 才提交，异常、遗漏提交或显式 rollback 均回滚，退出始终关闭 Session。连接池启用 pre-ping、return rollback、recycle 和有限超时，隔离级别固定 `READ COMMITTED`；只接受 `postgresql+psycopg`。数据库 URL 由 Composition Root 注入且所有展示隐藏密码，本 WBS 不读取环境或 Secret。|
|Reason|同步 Session 与 Phase 0/SC-04 已验证的 PostgreSQL/psycopg 路径一致，也可由 FastAPI 同步依赖和独立 Worker 共用一套事务边界，避免在基础阶段维护同步/异步双栈。显式 begin/commit、默认 rollback 和一次性实例能防止请求间 Session 共享、隐式提交及连接池污染；技术无关 Application Protocol 保持业务层不依赖 ORM。|
|Impact|`platform` 提供 UnitOfWork Contract、SQLAlchemy Adapter、连接健康检查和安全 URL；业务 Repository 只能在对应模块 Infrastructure 内使用当前 UoW Session，不得把 Session 跨线程/请求缓存。异步端点不得在事件循环中直接执行同步数据库 I/O，应使用同步依赖/执行边界。1.05 使用独立 Migration 角色建立正式 Alembic；1.09 负责 URL/Secret 与 Engine 生命周期装配。本任务未创建业务 ORM、表、Migration 或 API。|
|Rollback|删除 WBS 1.04 的 UnitOfWork/DatabaseRuntime、测试与验证材料并移除 SQLAlchemy/psycopg 依赖即可回到 1.03；当前无数据库对象或客户数据需要回滚。若未来以 AsyncSession 取代该基础边界，应提交后继 L2 决策和等价事务/并发验证；不得借此改变 PostgreSQL 18、Schema、安全角色或冻结业务模型。|

## DEC-20260924-064

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-064|
|Date|2026-09-24|
|WBS|1.05 Alembic migration|
|Decision|正式 ORM Base 固定 `plm` Schema 和 PK/FK/UQ/CK/IX 命名约定；Alembic 环境与 revision 作为 `plm_assistant.migrations` 包随 backend wheel 交付。首个不可变 revision 为 `20260924_0001`，只验证 PostgreSQL 18 并建立 pgvector 0.8.6 平台基线，不创建任何业务表。`plm.alembic_version` 位于应用 Schema；online/offline 环境先幂等建立 `plm` Schema。downgrade 到 base 删除 revision 记录，但按冻结恢复边界保留空 `plm` Schema、版本表和共享 pgvector 扩展。迁移 URL 仅通过内存 Config attribute 注入，`alembic.ini` 不保存凭据。|
|Reason|WBS 1.05 需要建立可发行、可审计的正式 Migration 链，但 DB Schema V1 明确要求业务表按模块 WBS 逐项细化，禁止复制 SC-04 的 70 张验证表。先冻结 Schema/版本表/扩展/命名与打包机制，既能满足后续 revision 前置，又不会把 Profile 占位结构冒充生产 ORM。保留共享扩展和空 Schema 与冻结 SC-04 恢复边界一致，也避免 downgrade 破坏其他 revision 或数据库能力。|
|Impact|后续每个模块数据库任务必须继承此 Base、以新 revision 增量变更并完成 ORM、空库/有数据 up/down、漂移和恢复验证。Runtime Role 不得调用本迁移入口或拥有 DDL/版本表写权限；1.09 再装配 Secret/配置与部署命令。本 revision 不关闭 65 Root 正式 ORM、业务约束、索引或权限验证风险，当前业务表数量仍为 0。|
|Rollback|可执行 downgrade 到 base 清除 revision 记录；空 `plm` Schema、版本表和 pgvector 作为平台前置按设计保留，不包含客户数据。代码回退可移除迁移包与 Alembic 依赖。只有在确认没有后续 revision、业务对象或其他扩展依赖时，管理员才能通过独立维护步骤移除这些前置；不得在普通 downgrade 中级联删除。|

## DEC-20260924-065

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-065|
|Date|2026-09-24|
|WBS|1.06 Error contract|
|Decision|平台层建立受控错误码目录和统一 FastAPI 异常处理。已分类的 ApplicationError 按冻结 API-01 通用码返回；未分类异常固定为 SYSTEM_INTERNAL，Pydantic 校验只返回安全的 400/422 而不暴露原始输入。普通 HTTP 403 隐藏为与不存在资源一致的 404；CSRF、License 等已分类错误保留冻结的 403。框架 405 使用新增的兼容错误码 REQUEST_METHOD_NOT_ALLOWED，不修改任何冻结码语义。响应固定为 `error.code/message/details` + `trace_id`，并同步 `X-Trace-Id`、禁止缓存；在 WBS 1.08 Trace 中间件接入前，复用规范 UUID 请求头或生成 UUIDv7。|
|Reason|统一封装可以防止框架异常明文、校验原值、权限存在性、堆栈与内部路径进入公开响应，并为后续模块提供稳定的错误边界。405 使用独立码比错误地归类为请求格式错误更精确，属于 API-01 允许的非破坏性扩展。|
|Impact|只改变错误响应，不新增公开业务路由或数据库对象；两个健康端点的冻结最小响应保持原样。后续模块需先登记自己的业务错误码再使用；1.07 增加服务端脱敏日志，1.08 统一整个请求生命周期的 TraceId。|
|Rollback|移除平台错误目录、异常处理注册和对应测试，即恢复 WBS 1.05 行为；当前无数据迁移。若改变已冻结 `/api/v1` 错误 Envelope 或已有错误码语义，须走 API Change Request/L3。|

## DEC-20260924-066

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-066|
|Date|2026-09-24|
|WBS|1.07 JSON log|
|Decision|平台日志使用两个独立、由 Composition Root 注入的 JSON 行输出流，分别记录 Application 与 Integration 事件；不改 Python root logger，也不以自由文本格式化异常。写入 API 只接受登记事件、受控集成类型/Provider、规范 UUID、固定格式错误码和非负耗时，输出字段由代码白名单构造。未分类 API 异常记录 `request_failed`、`SYSTEM_INTERNAL` 与响应同一 TraceId，不记录 exception、request body、URL、SQL 或路径；日志写入失败不改变安全错误响应。Audit 保持独立，未来由 audit 模块写 PostgreSQL。|
|Reason|自由文本和第三方异常拼接易把 Secret、客户正文、绝对路径或 Provider 原始响应写进普通日志；事件/字段白名单在写入前拒绝不受控数据。按应用/集成分流可保持权限、保留期和排障职责分离，且不抢占后续 Audit、Trace、Config WBS。|
|Impact|仅增加平台日志能力和未分类 API 失败的安全记录；未新增业务 API、数据库对象或网络调用。当前记录不含请求性能、Actor/Project 等上下文；WBS 1.08 Trace 中间件和后续业务模块逐步接入受控字段。默认 Application 输出 stdout、Integration 输出 stderr；正式部署的收集、保留与访问控制由 Release 阶段配置。|
|Rollback|移除日志模块、App Factory 注入及异常处理中的安全记录即可恢复 WBS 1.06；无数据迁移。未来需要新 Provider 或事件时先扩充受控目录及测试，不允许改成任意消息透传。|

## DEC-20260924-067

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-067|
|Date|2026-09-24|
|WBS|1.08 TraceId middleware|
|Decision|采用纯 ASGI Trace 中间件，在每个 HTTP 请求入口只解析一次 `X-Trace-Id`：仅单个规范 UUID 可复用，缺失、格式无效或重复请求头一律生成 UUIDv7。TraceId 同时写入 `request.state` 与 ContextVar，响应头统一回传；上下文在请求结束后恢复，供 Application 和后续受控集成调用读取。新增受控 `request_completed` Application Log，仅记录 TraceId、HTTP 状态和非负耗时，不写 URL、Header 或正文。健康端点只增加响应头，不改变冻结的最小 body。|
|Reason|单次入口解析防止错误处理、业务代码和日志各自生成不同 TraceId；纯 ASGI 包裹整个响应发送过程，可覆盖同步/异步请求及流式响应，ContextVar 避免并发请求污染。重复请求头不能有歧义，按无效值处理更安全。|
|Impact|所有 HTTP 响应增加 `X-Trace-Id`；错误正文继续由 WBS 1.06 固定 Envelope 保持相同值。未来正式业务成功 JSON 仍须按冻结 API-01 由业务响应层提供 `data` 与 `trace_id`，中间件不会改写响应正文。当前无 Job/AI/Plugin/Audit 实例；后续入口应显式继承已验证的 TraceId，不能把它当授权或幂等凭据。无业务路由、数据库或外部调用变化。|
|Rollback|移除中间件装配、Trace 上下文及新增日志字段即可恢复 WBS 1.07；WBS 1.06 错误响应仍保留独立 Trace 回退。若需改变冻结的 Trace Header/Envelope 语义，必须走 API Change Request/L3。|

## DEC-20260924-068

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-068|
|Date|2026-09-24|
|WBS|1.09 Config/Secret|
|Decision|基础工程先实现非敏感 Bootstrap 配置与 Secret 单次访问边界，不提前创建 PLT-01/PLT-02 正式业务表/API。Bootstrap 采用基线建议的 pydantic-settings 2.15.0 与 PyYAML 6.0.3，显式加载受限 UTF-8 YAML、`PLM_` 环境变量，开发 `.env` 仅在调用者明确传入时读取；重复/未知键、未知环境字段、危险 YAML tag、超限文件或非法类型失败关闭，错误消息固定脱敏。密钥、密码、Token 不进入 Bootstrap schema。Secret 只用 `SecretRef`，按受控 Purpose/Consumer、ACTIVE、版本与密文元数据检查后调用注入的解密 Port；Audit Port 是必需依赖，失败关闭；明文仅作为单次调用的可变缓冲区使用并在退出时清零。加密算法、持久密文仓库与 Windows/Linux SecretKeyProvider 保持未实现，遵照冻结方案留待 PLT-02 与 Release 安全设计，不把当前 Port 冒充生产 Secret Store。|
|Reason|现有正式 Migration 仅是无业务表的平台基线，PLT-01/PLT-02 的版本化实体和 Audit 尚未实施；在 1.09 直接写持久 Secret 或私自选定平台主密钥机制会跨 WBS 且掩盖 Gate 风险。先锁定非敏感配置来源和失败关闭的单次访问契约，可让后续 DB/AI Adapter 使用统一引用，同时避免把明文配置或测试密钥写入 Git。pydantic-settings/YAML 选型直接落实已批准技术建议，不引入新的商业授权或更改安全基线。|
|Impact|backend 增加两项固定直接依赖和一个不含 Secret 的示例模板；无数据库对象、业务 API、真实密钥、外发或生产加密能力。App Factory 目前不自动从 YAML/.env 读取，也不以缺失的 SecretKeyProvider 假装连接数据库；PLT-01/PLT-02 后续 Task 必须实现正式 ORM/Migration、权限/API、审计、密文与主材料分离及恢复验证，才能标记生产 Secret 可用。|
|Rollback|移除 Bootstrap/Secret 边界代码、示例、测试及两项依赖即可回到 WBS 1.08；无数据迁移。任何把密钥写入 YAML/.env 发行包、弱化 Secret 消费方授权或改变冻结 PLT-01/PLT-02 API/数据语义的方案必须走对应 L3 Change Request。|

## DEC-20260924-069

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-069|
|Date|2026-09-24|
|WBS|PLT-01-A01 SystemConfiguration ORM/Migration|
|Decision|将本任务严格限定为 PLT-01 的非敏感配置身份表与不可变版本表；Root Active Version 使用同父复合 FK，Version 的 UPDATE/DELETE 用数据库触发器拒绝，已有配置数据的 Alembic downgrade 失败关闭。Settings/RetentionPolicy/RetentionHold 子表、版本命令、DeploymentAdmin 授权、Audit 与敏感值识别留给后续独立 WBS。配置值物理形状暂用 STRING/INTEGER/BOOLEAN/JSON 四类 JSONB 约束；应用层必须进一步校验 INTEGER 语义及禁止 Secret/客户正文。|
|Reason|SC-01/02 冻结了聚合所有权、M-DEP 和不可变版本约束，但未冻结 PLT-01 每个子表的完整业务字段与命令实现。先交付可独立验证的身份/版本存储，不把未实现的权限或敏感值检测称为已完成。拒绝含数据回退可避免默认 DROP TABLE 静默丢失正式配置历史。|
|Impact|新增正式 Alembic `20260924_0002` 和两张 `plm` 表；`retention_policy_id` 保留 nullable 占位，目标子表落地前不具备外键/保留策略功能。无公开 API、客户数据外发或冻结基线变更。后续业务命令在开放前必须补齐非敏感值筛查、单调版本分配、乐观并发、权限与 Audit。|
|Rollback|空表可降级到 `20260924_0001`；含配置数据拒绝回退，须经备份和受控数据迁移/恢复流程处理。不得通过禁用不可变触发器来绕过正式版本历史。|

## DEC-20260924-070

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-070|
|Date|2026-09-24|
|WBS|PLT-01-A02 配置版本命令与仓储边界|
|Decision|只交付内部创建/激活版本命令与 SQLAlchemy 仓储，不提前暴露管理 API。受控配置值使用开发者拥有的键、Schema 版本、类型及精确值白名单；不提供任何默认可写策略，也不允许客户请求动态登记策略。写命令必须注入部署写授权 Port 和同事务 Audit Port，主记录行锁序列化版本号并以 lock_version 防陈旧写。A01 已发布迁移不可改写，以新增 `20260924_0003` 为不可变版本补充 API-02 已冻结要求的 `schema_version`。|
|Reason|冻结 API 要求非敏感值、Schema 版本、乐观锁、DeploymentAdmin 和强制 Audit；当前真实 Auth/License/Audit/Idempotency 适配器未落地。白名单与 Port 失败关闭使内部逻辑可验证，又不把测试替身冒充生产安全能力。版本数只由锁定的 Root 分配，避免并发产生重复或跳号。|
|Impact|A01 旧数据升级时 Schema 版本安全归为 1；有非初始 Schema 版本时拒绝回退到 `0002`。当前无公开 API、客户数据外发、新依赖或冻结基线改变；配置身份创建、持久幂等、真实认证/License/CSRF/Audit 和默认策略留给后续 WBS。A01 `version_state` 被解释为版本可用性，生效版本只由 Root 指针决定，避免更新不可变历史。|
|Rollback|移除内部命令、仓储和策略代码即可撤回未暴露功能；数据库 `0003` 仅在所有记录 Schema 版本为 1 时可安全降级到 `0002`，否则先完成受控备份/迁移，不强制删除或改写正式历史。|

## DEC-20260924-071

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-071|
|Date|2026-09-24|
|WBS|PLT-01-A03 配置身份与幂等命令|
|Decision|为已冻结的 API-01/02 幂等要求，增加 PLT-01 技术性命令收据表，不新增 Aggregate Root 或客户业务实体。以 `(actor_id, operation, SHA-256(Idempotency-Key))` 唯一约束确定部署范围内重放；只存规范请求 SHA-256 和结果引用，原始键/值不持久化。`INSERT ... ON CONFLICT DO NOTHING` 在同一事务中预约收据，随后配置写入、Audit Port、完成收据原子提交；完成收据由专用触发器禁止 UPDATE/DELETE，源 FK 设置索引。含收据数据的迁移回退失败关闭。|
|Reason|冻结 API 明确同键同 payload 返回原结果、不同 payload 返回冲突，而进程内字典无法跨重启/并发保证。技术表只承载请求去重事实，不改变 PLT-01 业务聚合的 Root/Version/Retention 映射；摘要化避免 Idempotency-Key 误含敏感材料时明文留库。事务收据确保 Audit 失败也不会留下假的成功重放。|
|Impact|新增普通增量迁移 `20260924_0004`；A02 内部命令签名增加必填 idempotency_key，仍无公开 API、客户数据外发或新第三方依赖。正式 Auth/License/CSRF/AuditEvent 和受控 Retention 尚未接入，命令不得对外开放。Phase 1 基础工程按实施方案收口并写阶段总结，转入 Phase 2 AuditEvent；Gate 3 不自动通过。|
|Rollback|空收据表可降级到 `0003`；有收据时必须先备份并完成受控恢复/迁移，不允许普通 downgrade 删除重放历史。移除本任务内部命令修改不影响 A01/A02 已保存的配置主记录和不可变版本。|

## DEC-20260924-072

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-072|
|Date|2026-09-24|
|WBS|AUD-01-A01 AuditEvent ORM/Migration|
|Decision|AUD-01 首步只提供真实存储模型，不开放写/查 API。Audit Root 保持 DEPLOYMENT Owner Scope；`event_scope` 标示被审计操作的部署或项目上下文，PROJECT 必填 `target_project_id`，DEPLOYMENT 不得填写。多态目标在库内固定为冻结的 65 个客户运行 Root 类型或全空（无可定位对象的认证失败），不包含 Developer Workbench。仅存受控 action/outcome/reason/state 码、标识与可选 SHA-256 主体提示摘要，不存请求正文、Secret、文件或完整 AI 输入输出。数据库触发器禁止普通 UPDATE/DELETE/TRUNCATE；非空 downgrade 拒绝。|
|Reason|冻结模型要求 AuditEvent 只追加、项目隔离、来源可追溯和最小安全摘要；冻结 SC-02 允许部署 Owner 与项目目标并存，SC-03 固定三组索引。当前 Auth/Project/License 未落地，外键或真实权限不能伪造；安全码替代任意自由文本，避免向审计库复制敏感内容。|
|Impact|新增迁移 `20260924_0005` 和一张 `plm` 表；无冻结基线变更、新依赖、公开 API 或客户数据外发。数据库管理员仍有 DDL 权限，因此触发器不是防篡改封存；AuditService 权限/事务 Port、读隔离、Retention/Legal Hold 和备份权限控制留待对应 WBS。|
|Rollback|空表可回退到 `0004`；含审计事件时须备份并进行受控恢复/迁移，普通回退失败关闭，不能删历史记录换取迁移通过。|

## DEC-20260924-073

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-073|
|Date|2026-09-24|
|WBS|AUD-01-A02 AuditService append Port/Repository|
|Decision|Audit 的跨模块公开入口仅暴露只追加 AuditService 与不可变 AuditEventDraft；Audit 模块内部 Port/SQLAlchemy 仓储不对业务模块开放。Service 接收调用方已开启的事务并直接插入，不创建、提交或补偿第二事务。输入只接受 UUID、受控大写码、结构化目标和可选 32 字节主体提示摘要；数据库白名单与 append-only 触发器作为第二层约束。|
|Reason|冻结 DM-02 要求强制审计与业务状态同事务提交，且只由 AuditService 追加。由业务用例掌握事务可避免 Audit 成功而业务回滚或相反；自由文本会扩大敏感内容进入审计库的风险。Auth/License/Project 权限仍未落地，本任务不以测试替身伪装成公开可用写入口。|
|Impact|只新增 Audit 模块 Application/Domain/Infrastructure、测试与验收脚本；A01 迁移与冻结 API 不变，无新依赖或客户数据外发。业务命令只有在真实权限和 Audit 适配器接线后才能开放。下一项单独完成只读查询及项目隔离。|
|Rollback|移除 A02 新增服务、Port、仓储和测试即可退回 A01；已提交的审计事件仍由 A01 append-only 表保护，不得清理历史以撤销代码。|

## DEC-20260924-074

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-074|
|Date|2026-09-24|
|WBS|AUD-01-A03 审计只读查询与项目隔离|
|Decision|内部 AuditQueryService 必须注入权限 Port 并在 Repository 查询前检查；Project 读取固定 `event_scope=PROJECT AND target_project_id=授权项目`，部署读取固定 `event_scope=DEPLOYMENT AND target_project_id IS NULL`，DeploymentAdmin 不自动读取项目 Audit。时间查询要求显式、最多 31 天，页大小 1～200，排序固定 `occurred_at DESC, audit_event_id DESC`；内部 keyset position 不作为公开游标，对外签名/Scope/查询指纹绑定在未来 HTTP API 任务中实现。投影排除主体提示摘要。|
|Reason|冻结 API-01/02 要求权限先行、项目隔离、受控筛选、完整性保护分页和不暴露敏感材料；SC-03 已冻结对应 Audit 索引。真实 Auth/License/Session 尚未落地，当前不提供公开路由或伪造权限适配器。31 天上限是可回滚的内部初值，控制无界查询，不改变冻结外部 API 语义。|
|Impact|只新增 Audit 内部查询与测试，不改 A01 Schema/索引或冻结 `/api/v1`。权限 Port 必须由后续真实认证/项目授权实现；公开 API 上线前还必须加入签名游标及 Scope/查询指纹校验。审计导出另行 WBS 实施。|
|Rollback|移除内部查询 Service/Repository 和测试即可回到 A02；不删除审计事件，也不改变已冻结查询索引。|

## DEC-20260924-075

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-075|
|Date|2026-09-24|
|WBS|AUT-01-A01 User/Credential ORM/Migration|
|Decision|User Root 先以 DISABLED、credential_version=0、无当前凭据建立，随后同事务追加不可变 PasswordCredential 版本并由复合 FK 指向本 User 的相同版本；只有存在当前凭据才可 ENABLED。用户名展示值与规范值分列，规范值部署内普通唯一，停用不释放。凭据只保存不可逆 Hash、算法 ID、非敏感参数、版本和变更时间；算法选择/哈希验证由后续专门任务完成，不以本迁移中的合成测试值作为生产方案。数据库触发器禁止凭据历史 UPDATE/DELETE/TRUNCATE 与 User 凭据版本倒退；非空 downgrade 拒绝。|
|Reason|冻结 DM-02/SC-01～03 要求身份与凭据版本分离、唯一用户名、一个有效凭据和 Session 凭据版本失效。先创建 DISABLED Root 避开循环 FK 插入顺序，同时由复合 FK 阻止把别人的或旧版本凭据设为当前；不得在 Schema 任务中假装选定密码算法或开放登录。|
|Impact|新增正式迁移 `20260924_0006` 与两张 Auth 表，无新依赖、公开 API、客户数据外发或冻结基线变更。Unicode trim/NFC/casefold、密码 Hash 策略、命令授权/审计、Session 失效须由后续 WBS 实现并验证；原始密码和哈希不得进入 DTO/Audit/日志。|
|Rollback|空 Auth 表可降级到 `0005`；一旦有身份/凭据历史，普通 downgrade 失败关闭，必须先备份并通过受控恢复/迁移处理，不删除账号历史。|

## DEC-20260924-076

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-076|
|Date|2026-09-24|
|WBS|AUT-01-A02 User/Credential 内部命令与规范化|
|Decision|本项只实现内部 User 创建，不提前实现登录、重置密码、停用/启用或公开管理端点。用户名以 `strip → NFC → casefold → NFC` 得到规范值，拒绝空值、控制字符及 Schema 长度越界；数据库唯一键处理并发重名。命令必须注入同事务权限、密码 Hash 和 AuditService，先授权再哈希/写库；初始凭据版本为 1，默认普通部署角色。Hash 结果只允许受控算法 ID、非敏感整数参数和限定长度编码值；不内置或宣称生产算法。原始密码从调用方可变 UTF-8 缓冲区传入并在成功/失败后尽力清零。|
|Reason|冻结 DM-02/API-02 要求服务端 canonical username、DeploymentAdmin 授权、write-only 密码、同事务 Audit 和凭据版本。生产密码算法、Session/License 和持久幂等尚未落地；独立 Port 与无公开路由可验证创建流程及失败关闭，同时避免在普通实现任务中擅定安全核心机制。|
|Impact|新增 Auth Domain/Application/Repository 与合成测试；不改 A01 Schema、冻结 API 或技术栈，无新依赖/真实客户数据外发。只有未来正式 Hash Adapter、真实 Auth/License/Session 授权和幂等收据就绪后才能开放 `AUTH_USER_CREATE`；测试算法 `TEST_ONLY` 不属于生产支持。Python/第三方组件可能复制密码缓冲区，清零不是内存绝对擦除承诺。|
|Rollback|移除内部命令、仓储及测试即可回到 A01；已有 User/Credential/Audit 历史不能因代码回退而删除，须继续遵守 A01 非空 downgrade 拒绝。|

## DEC-20260924-077

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-077|
|Date|2026-09-24|
|WBS|AUT-01-A03 生产密码哈希与凭据校验|
|Decision|首版采用 Python 3.13/OpenSSL 标准库 `hashlib.scrypt` 固定 V1 Profile：每条凭据 16 字节独立随机盐、`N=2^17,r=8,p=1,dklen=32`、256 MiB `maxmem` 上限、自描述编码与独立 `algorithm_id/parameter_set` 一致性校验。Verifier 只接受本 Profile，拒绝由数据库记录选择任意耗时参数，使用 `hmac.compare_digest` 比较导出值。密码输入上限同步收紧为 1024 字节；保留既有 Port，使将来算法升级新建 Profile/版本，不静默重写旧凭据。无 Argon2id 第三方依赖或安全基线替换。|
|Reason|冻结方案要求不可逆 PasswordHasher，但未规定库与参数。[OWASP 密码存储建议](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)首选 Argon2id，标准库可用时推荐的 scrypt Profile 为 `N=2^17,r=8,p=1`；[Python 3.13 `hashlib` 文档](https://docs.python.org/3.13/library/hashlib.html)提供 scrypt 与显式内存限制。此选择不新增重要第三方依赖，属于当前已批准安全机制的具体实现；对畸形参数失败关闭避免存储内容触发资源耗尽。|
|Impact|新增 Auth Infrastructure Hash/Verifier，无 Schema、API 或新依赖；本机单次创建约 317ms 仅为观测，不代表三平台吞吐或安全审计通过。每次哈希约需 128 MiB 工作内存，公开登录前仍必须实现 Origin/Host/限流、Session/CSRF、License/权限、统一失败响应和平台负载验收。Python/OpenSSL 可能复制密码字节，调用方清零不保证绝对擦除。|
|Rollback|移除新适配器可返回仅 Port 的 A02，但已保存的 `SCRYPT` 凭据将无法验证；上线后不得直接撤销而不提供兼容验证或受控凭据迁移。普通代码回滚不删除用户/凭据历史。|

## DEC-20260924-078

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-078|
|Date|2026-09-24|
|WBS|AUT-02-A01 Session ORM/Migration|
|Decision|Session 为部署级运行聚合，物理表只存 32 字节 Session Token 摘要与 CSRF 绑定摘要，不存 Cookie/CSRF 原值。`(user_id,credential_version)` 复合 FK 指向不可变 PasswordCredential 历史，Session 是否仍有效还须后续服务重新检查 User ENABLED、当前凭据版本、绝对/空闲到期与撤销。`state` 由时间/撤销事实派生，不持久化。Token 摘要唯一，额外 `(user_id,revoked_at)` 索引用于用户全会话撤销；更新触发器禁止身份/摘要/绝对期限替换、last_seen/idle 倒退及撤销复活。|
|Reason|冻结 DM-02/API-02 要求服务端 Session、Token/CSRF 不可逆摘要、凭据变化使旧 Session 失效和撤销不可恢复；SC-02 R-DEP Profile 允许专用列覆盖通用状态。复合 FK 保留历史版本，但不能代替实时 User 状态校验；避免误把数据库行存在等同于已认证。验收中显式补上 `revoke_reason IS NOT NULL`，以防 PostgreSQL CHECK 对 NULL 的 UNKNOWN 结果放行。|
|Impact|新增普通增量迁移 `20260924_0007` 和一张 Session 表，无冻结 API/架构变更、新依赖或客户数据外发。真实 Token 生成/哈希、Cookie/CSRF、续期/撤销及 License/项目授权均须后续独立 WBS 实现；当前仅持久层，不可开放登录。|
|Rollback|空表可降级到 `0006`；含 Session 记录时普通 downgrade 拒绝，必须备份并走受控恢复/迁移，不删除历史以强制通过。|

## DEC-20260924-079

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-079|
|Date|2026-09-24|
|WBS|AUT-02-A02 Session 签发/校验/撤销内部服务|
|Decision|内部 Session 签发须由注入的 `SessionIssueAccessPort` 对当次认证证明、User 和当前凭据版本作明确许可；没有生产适配器时不得开放登录。每次生成独立 32 字节随机 Token/CSRF，数据库只存各自 SHA-256 摘要。内部默认绝对期限 8 小时、空闲期限 30 分钟，允许受控配置但上限 24 小时且空闲期不超过绝对期；本任务校验不滑动空闲期。校验实时重查 User ENABLED、当前凭据版本、撤销及双期限；撤销需有效 Token 与绑定 CSRF，更新与 Audit 同事务。|
|Reason|冻结 DM-02/API-02 规定服务器端 Session、凭据变化失效、CSRF 和审计，但未固定内部期限数值。保守初值与强制认证证明 Port 防止仅凭 UserId 签发；无公开路由避免跳过 Origin/Host、限流、Cookie 与 License。固定 Token 长度使摘要存储和输入检查简单；原值不进入数据库或 Audit。|
|Impact|新增 Auth Application Service、Auth Infrastructure Repository、单元及 PostgreSQL 临时库验证；无 Schema/Migration、公开 API、第三方依赖或客户数据外发。Cookie 设置、Origin/Host、真实密码证明/License 适配、登录限流、续期轮换、全会话管理员撤销及项目授权仍需后续任务，当前不能开放真实登录。|
|Rollback|未接入公开入口，移除本服务/适配器即可回退代码；已签发 Session 的撤销历史及 Audit 不删除。调整期限需安全评估和兼容测试，不改变冻结的摘要/凭据版本机制。|

## DEC-20260924-080

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-080|
|Date|2026-09-24|
|WBS|AUT-02-A03 Session 续期轮换|
|Decision|把已冻结 API-02 的 Session 续期轮换细化为独立内部 WBS A03。仅有效 Session + 绑定 CSRF 可续期；在单一数据库事务中先将旧记录撤销为 `RENEWED`，再创建独立随机 Token/CSRF 的新记录及 Audit。新记录继承旧会话绝对到期时间，仅将空闲期限延至 `min(当前时间+空闲期, 原绝对期限)`；因此轮换不能无限延长认证会话。新旧 Token 或 CSRF 发生重复则失败关闭。|
|Reason|冻结 API-02 已规定 `AUTH_SESSION_RENEW` 必须轮换；A02 仅实现初始签发/校验/撤销。将轮换独立验收符合一 WBS 一问题。继承绝对期限可保留“绝对到期”的安全含义，而同事务写入保证 Audit 或新记录失败时旧 Session 继续有效，不出现半轮换。|
|Impact|仅变更内部 Auth Application Service 与测试，无 Schema/Migration、公开 API、外部依赖或客户数据外发。Cookie 原子替换、多标签行为、Origin/Host、限流、License、真实登录与管理员撤销仍未接入，不能宣称对外续期已可用。|
|Rollback|未接入公开路由，可移除内部续期命令；既有 Session/Audit 历史不删除。|

## DEC-20260924-081

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-081|
|Date|2026-09-24|
|WBS|AUT-02-A04 Session 管理员批量撤销|
|Decision|将冻结 API-02 的 `AUTH_USER_REVOKE_SESSIONS` 底层能力拆为内部 A04。服务必须注入真实管理员权限 Port，验证 actor 的 Session、License、DeploymentAdmin 后，锁定目标 User 行并批量撤销该用户尚未撤销的 Session；单次 Audit 与撤销同事务。未注入生产权限适配器时默认拒绝。重复调用返回本次实际撤销数 0，并保留审计，不删除历史。|
|Reason|Session 签发已锁定 User 行；管理员批量撤销采用相同 User 行锁以序列化并发签发，避免撤销时漏掉已在提交中的新 Session。权限 Port 阻止凭 UserId 直接执行高权限命令；单事务 Audit 避免无证据的状态变更。|
|Impact|新增 Auth 内部管理员撤销命令与 Repository、测试；无 Schema/Migration、公开路由、第三方依赖或客户数据外发。`AUTH_USER_DISABLE` 仍需在未来 User 状态命令里与撤销同事务接线；生产权限/License/CSRF 尚未接线，此内部命令不能直接暴露为 API。|
|Rollback|移除内部命令可回退代码；已撤销 Session 不可恢复，Audit 历史不得删除。|

## DEC-20260924-082

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-082|
|Date|2026-09-24|
|WBS|AUT-02-A05 生产密码证明适配|
|Decision|将原候选“生产认证证明与权限接线”拆分：A05 仅实现内部 Session 签发的真实密码证明，管理员权限适配须待 LicenseService 形成后另列任务。`PasswordIssueProof` 持有短时可变字节缓冲区且不显示于 repr，Session 签发结束无论成功、拒绝或异常均清零。Auth Infrastructure 在同一事务中只对 ENABLED User 的当前 PasswordCredential 调用已批准 scrypt Verifier；错误/畸形证明统一拒绝，无密码或哈希进入 Audit、Session 或日志。|
|Reason|冻结 API-02 允许 License 无效时登录，但管理员业务接口仍需有效 License；当前仓库没有正式 License 模块，不能用测试许可绕过。把密码证明单独验收可完成不受阻塞部分，又避免把未实现的 License/权限或 Origin/Host/限流误报为已可用。|
|Impact|新增 Auth 内部密码证明 DTO、Verifier Port、SQLAlchemy 适配、测试；无 Schema/Migration、公开 API、第三方依赖或客户数据外发。密码缓冲区清零不承诺 Python/OpenSSL 内部副本绝对擦除。公开登录仍需用户名解析、统一失败/审计、Origin/Host、限流、Cookie/CSRF 等后续工作；管理员权限接线仍依赖 License。|
|Rollback|未接入公开路由，移除适配器可回退；不修改现有 Credential/Session 历史。|

## DEC-20260924-083

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-083|
|Date|2026-09-24|
|WBS|LIC-01-A01 LicenseInstallation ORM/Migration|
|Decision|按冻结 SC-01/DM-02 建立 `lic_installations` 与不可变 `lic_installation_documents`。签名文档以最多 64 KiB 原始字节快照与 32 字节 SHA-256 摘要保留，关联 `public_key_ref`，不存公钥私钥或原始 MAC；每次安装独立 UUIDv7。状态限 `IMPORTED/ACTIVE/SUPERSEDED/REJECTED`，partial unique 保证至多一个 ACTIVE；进入非 IMPORTED 状态须有验证结果引用。更新触发器只允许 IMPORTED→ACTIVE/REJECTED、ACTIVE→SUPERSEDED 及受控同态验证引用更新，终态不可复活；文档禁止更新/删除，安装历史禁止删除。INSERT 不设只允许 IMPORTED 的触发器，以保证含 ACTIVE 历史的备份恢复；初始导入状态由未来受控服务保证。|
|Reason|冻结模型要求签名文档历史、单一 ACTIVE、不可变签名内容和私钥隔离，但未固定长度与具体列。64 KiB 是可调整的 L2 存储上限；原始字节避免 JSON 重新序列化破坏签名材料。用数据库约束守住状态/单例及历史更新，避免恢复时触发器拒绝历史状态。|
|Impact|新增两张正式 License 表与迁移 `20260924_0008`；无公开 API、验签/激活服务、新依赖或客户数据外发。`validation_result_ref` 待 LIC-02 建表后加正式关联与验证来源检查；仅有非空 UUID 不证明签名、机器、时间或 License 有效。测试使用明确标注的合成无效签名文档，只验 Schema，不构成 License 验证。|
|Rollback|空表可降级至 `0007`；存在安装或文档历史时普通 downgrade 拒绝，必须备份并按受控恢复方案处理，不删除历史以强制降级。|

## DEC-20260924-084

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-084|
|Date|2026-09-24|
|WBS|LIC-01-A02 Ed25519 签名真实性预检|
|Decision|用户已在本轮明确批准将 POC-09 验证的 `cryptography 50.0.1` 纳入后端生产依赖。原候选“签名文档验证与受控导入”拆分：A02 仅实现最多 64 KiB 签名文档的严格 UTF-8/JSON envelope 与 Ed25519 签名真实性校验；公钥只能由注入的可信 `PublicKeyResolverPort` 按引用提供，不接受请求自带公钥。采用 POC-09 的 UTF-8、字段排序、紧凑分隔符确定性 Payload 序列化；重复 JSON 键、非标准数值、畸形签名、未知公钥、超深/超量载荷均失败关闭。返回类型明确标记仅为 `SignatureVerifiedDocument`，不提供 License `VALID` 或 Entitlement。|
|Reason|当前 LIC-02 验证事件、LIC-03 可信时间、正式机器/产品/功能规则与受控导入事务尚未实现；仅签名正确不能当作有效授权。拆分使已批准的密码学依赖可独立验收，同时不越过冻结的机器指纹与可信时间信任边界。|
|Impact|正式后端新增已获用户批准的 `cryptography==50.0.1` 直接依赖及 License 内部验签组件；无 Schema/Migration、公开 API、私钥落盘或客户数据外发。生产公钥配置装配、语义 Schema/产品/功能/机器/有效期/可信时间校验、导入历史/Audit/激活仍属后续任务；测试私钥只在测试进程内即时生成，不序列化。|
|Rollback|尚未接入公开路由或 License 状态决策，可移除验签组件与依赖；不修改 License 安装历史。若未来替换 Ed25519 核心机制必须走 L3，不由本决策授权。|

## DEC-20260924-085

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-085|
|Date|2026-09-24|
|WBS|LIC-02-A01 LicenseValidationState ORM/Migration|
|Decision|建立部署级单例 `lic_validation_states` 与追加不可变 `lic_validation_events`，验证码至少覆盖冻结 DM-02 的八类，并增加产品不符/可信时间状态损坏安全分类。`VALID` 行必须具备活动安装引用、32 字节机器指纹摘要、事件引用、对象型权益快照与验证时间；但这些列形状不代替密码学/机器/时间验证。状态变更要求新事件引用、版本单调加一和更新时间不倒退。安装记录的 `validation_result_ref` 在本迁移升级为指向验证事件的正式 FK；验证事件的可选 `installation_id` 保留可查询来源引用但不反向设 FK，以避免安装↔事件外键循环阻断备份恢复。已有非空且无对应事件的旧引用在升级前拒绝，要求受控核对。|
|Reason|冻结 SC-01/DM-02 要求当前安全状态与不可变验证历史分离；单例与 VALID 必备形状可在数据库失败关闭。单向 FK 既落实安装结果指针的来源完整性，又让事件→安装→状态按依赖顺序恢复；事件来源 ID 的匹配关系由未来 LicenseService 在同事务检查，不可凭事件行自行放行。|
|Impact|新增两张正式 License 表与迁移 `20260924_0009`；无公开 API、实际授权判定、新依赖或客户数据外发。测试仅使用合成验证事实，即使状态行标为 VALID，也不代表真实有效授权；TrustedTimeState 与 LicenseService 仍未实现。|
|Rollback|空表及无新验证 FK 引用时可降级到 `0008`；有状态或事件历史时普通 downgrade 拒绝，须备份并受控恢复，不删除验证历史。|

## DEC-20260924-086

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-086|
|Date|2026-09-24|
|WBS|LIC-03-A01 TrustedTimeState ORM/Migration|
|Decision|按冻结 DM-02/SC-01 建立 `lic_trusted_time_states` 部署单例与追加不可变 `lic_trusted_time_events`。单例初态允许尚未成功验证的空时间、版本 0；前移后必须有 UTC 成功时间、正版本、对象型完整性元数据及事件引用。更新触发器要求身份不变、时间严格前移、版本恰好 +1、事件引用变化及更新时间不倒退；事件禁止 UPDATE/DELETE/TRUNCATE，状态禁止 DELETE/TRUNCATE。事件结果码仅要求非空且限长，不在存储层提前冻结 License 分类或完整性算法。|
|Reason|冻结基线要求原子 expected_version、单调时间和追加检查事件，但完整性算法由后续 TrustedTimeStatePort 实施。数据库负责可稳定验证的结构与转移约束；不设置 INSERT 只能空态的触发器，以允许含历史前移状态的普通备份恢复，初始写入和完整性认证必须由受控服务保证。|
|Impact|新增两张 License 表和 Alembic `20260924_0010`；无公开 API、新依赖、客户数据外发或真实 License 判定。数据库表中的完整性元数据仅为存储位，不能单凭行内容放行业务。|
|Rollback|空表可降级至 `0009`；存在状态/事件历史时普通 downgrade 拒绝，须先备份并按受控恢复方案处理。|

## DEC-20260924-087

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-087|
|Date|2026-09-24|
|WBS|LIC-03-A02 TrustedTimeStatePort 单调更新与完整性边界|
|Decision|在冻结模型留出的 `integrity_metadata` 实现空间内，选用无新增依赖的 HMAC-SHA256-V1 对部署状态 ID、最新成功 UTC 时间、版本及最新事件 ID 做确定性绑定；元数据只保存算法、受信任密钥引用和 tag，密钥由独立注入解析器提供，不在数据库、Git、日志或客户端输入中取得。内部端口要求 expected_version，使用 PostgreSQL 行锁和条件 UPDATE，明显回拨（相对上次成功时间超过内部允许容差）、旧版本或完整性错误失败关闭。容差由可信内部调用方给定，受 0～5 分钟硬上限约束，容差内不回写较早时间。成功事件/Audit 与状态同事务，拒绝事件/Audit 在状态事务回滚后独立持久化。|
|Reason|DM-02 明确完整性算法由 TrustedTimeStatePort 细化、时间只能前移且回拨/损坏/冲突拒绝并审计。HMAC 是状态完整性机制，不改变 License 的 Ed25519 签发、MAC 规范化或私钥隔离；未接入生产密钥源时默认失败关闭。一次性初态由未来部署装配显式创建，日常端口不自动补建缺失状态，避免数据库被清空后静默重置。|
|Impact|新增内部端口、HMAC 适配和 PostgreSQL 仓储，无 Schema/Migration、第三方依赖、公开 API 或客户数据外发。仅使用合成测试密钥验证；生产 Secret Store 解析器与初始化尚未完成，不能据此判定 License 有效。高权限数据库初态重置及数据库与密钥/备份同时回滚不在此离线方案的可检测保证内，也不宣称硬件可信时间。|
|Rollback|端口尚未接入公开路由和 LicenseService，可移除内部实现而不改变既有 Schema 与历史；已写入的 HMAC-V1 状态不应无验证地改写，未来算法迁移须保留验证/受控转换策略。|

## DEC-20260924-088

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-088|
|Date|2026-09-24|
|WBS|CR-LIC-001 / LIC-02-A02 前置基线变更|
|Decision|用户明确同意“修改已锁定方案，采用方案B”。首版 License 维持 `plm.license.v1` 七字段签名 Payload，限定为本产品全功能整体授权；不提供多产品或细分功能权益。原 V2.1 与 Gate 2 冻结提交保留历史，正式差异由 `docs/changes/CR-LIC-001-single-product-full-bundle.md` 与 V2.1 License 补充承载。|
|Reason|七字段载荷没有产品/功能权益；原 ADR-006/DM-02 的细分验证无法在不更换签名 Payload 的情况下实现。用户选择保留载荷并收窄首版授权粒度。|
|Impact|修订 ADR-006、DM-02、执行指令与状态；不改 MAC→SHA-256→Ed25519、私钥隔离、有效期、可信时间、Schema 或 `/api/v1`。生产可信公钥须限定本产品；无法按功能差异化授权。|
|Rollback|不静默回退已批准业务规则。若未来需要多产品或功能分级，另提 L3、采用新版签名载荷并定义兼容/迁移。|

## DEC-20260924-089

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-089|
|Date|2026-09-24|
|WBS|LIC-02-A02 LicenseService 综合验证|
|Decision|本项只实现内部综合校验，不把 `SignatureVerifiedDocument` 或结果写成活动 License。受信任本产品专用公钥引用、实施人员选定 MAC 和当前 UTC 时间均由独立 Port 提供，客户端不能指定；严格接受 `plm.license.v1` 七字段，复用 LIC-01-A02 Ed25519 验签。先校验签名/Schema/机器/签发及有效期，再推进可信时间；产出 `VerifiedFullBundleLicense` 但不持久化验证状态。|
|Reason|CR-LIC-001 保留七字段并取消细分权益，必须避免在代码中伪造签名保护的产品/功能列表。分离内部判定与下一任务的状态/Audit 编排，避免未完成权限/导入事务前对外开放。|
|Impact|新增 License 内部服务、测试与临时 PostgreSQL 集成验证；无 Schema/Migration、新依赖、公开 API 或客户数据外发。生产公钥必须本产品专用，选定 MAC 和可信时间密钥/初始化尚待装配；本项测试密钥仅在进程内生成。|
|Rollback|未接入公开路由或安装状态，移除内部服务可回退；不改 v1 签名载荷、既有表或历史记录。|

## DEC-20260924-090

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-090|
|Date|2026-09-24|
|WBS|LIC-02-A03 验证结果持久化与审计编排|
|Decision|只对已有 IMPORTED 安装从不可变文档取证并调用内部 LicenseService；完整验证成功记录 VALID 事件，但不更新部署级 ValidationState、不激活安装。事件、安装结果引用和 Audit 由同一数据库事务提交，拒绝事件不包含权益。|
|Reason|验证成功是安装候选的真实性与当前机器/时间判定，不等于管理员授权激活；部署级运行许可必须待受控激活和状态投影实现后才可能为 VALID。先保持失败关闭，避免单个事件绕过权限边界。|
|Impact|无 Schema/API/依赖变更；可信时间前移由既有独立事务完成，若随后结果记录失败，安装仍为 IMPORTED 且没有新结果引用，不能激活，重试需新的可信时间版本。|
|Rollback|没有公开入口或状态激活；回退代码不删除已写入的不可变验证/Audit 历史。|

## DEC-20260924-091

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-091|
|Date|2026-09-24|
|WBS|LIC-01-A03 受控导入命令与初始安装记录|
|Decision|内部导入命令由 Auth 所有的适配器在同一事务验证 Session Token、CSRF、当前凭据版本、未撤销/未超时状态和 DeploymentAdmin；公钥引用只取本产品可信 Port。Ed25519 预检成功后存 IMPORTED 安装和不可变文档；预检拒绝写无安装关联的脱敏验证事件及 Audit，绝不存失败文档正文。|
|Reason|冻结 API 的 LICENSE_IMPORT 恢复面不能绕过 Session/CSRF/Role/Audit；在 HTTP 装配和完整 License 判定尚未完成时，先把候选导入与激活分离。Auth 模块拥有身份表的查询，License 不直连 Auth 表。|
|Impact|无 Schema、Migration、新依赖或公开 API；成功导入的 `validation_result_ref` 仍为空且状态仅 IMPORTED，后续综合验证和激活必须另行执行。过大或未授权请求不落库；验签失败留摘要、分类和追踪，不留 Payload。|
|Rollback|内部命令尚无公开路由；移除代码不删除已形成的不可变安装、验证和 Audit 历史。|

## DEC-20260924-092

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-092|
|Date|2026-09-24|
|WBS|LIC-01-A04 受控激活与部署验证状态投影|
|Decision|激活命令内部先复核管理员 Session/CSRF，再调用 LIC-02-A03 对目标 IMPORTED 安装执行本次完整验证；仅 VALID 可继续。激活事务再次核对权限和事件的安装/文档摘要/同追踪号、完整本产品权益、有效期及 60 秒新鲜度；旧 ACTIVE→SUPERSEDED、新安装→ACTIVE、部署单例状态→VALID、Audit 同事务。|
|Reason|冻结 DM-02/ADR-006 要求成功验证才可激活、至多一条 ACTIVE、旧记录保留历史；旧 VALID 事件不能成为可重复使用的客户端激活凭据。双次权限检查覆盖验证跨事务窗口；60 秒界限缩短状态漂移窗口。|
|Impact|无 Schema/API/依赖变更。验证记录先于激活提交，若激活权限/并发/Audit 失败，成功验证事件仍作为历史存在但安装保持 IMPORTED；不得据此开放业务。首次投影版本为 0，后续每次更新 +1。|
|Rollback|无公开路由；代码可回退但不可删除已形成的安装、验证与 Audit 历史，已有 ACTIVE 需受控迁移或后续激活替换。|

## DEC-20260924-093

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-093|
|Date|2026-09-24|
|WBS|LIC-02-A04 运行时许可检查与失败关闭|
|Decision|内部 Guard 对受许可操作每次读取并锁定部署级状态，核对 ACTIVE 安装、不可变文档摘要、当前验证事件与状态一致；再读取经完整性校验的可信时间版本并调用现有 LicenseService 全量验签/机器/时窗/单调时间检查。成功或拒绝均追加验证事件、更新单例状态并与 Audit 同事务。状态行锁贯穿检查，串行化并发运行时验证；任何 DB/审计/可信输入失败都拒绝，不信任旧 VALID 缓存。|
|Reason|冻结 ADR-006/DM-02 要求任一验证失败即停止受许可业务。单独读取可信时间版本后释放状态锁会使并发成功检查互相冲突，甚至把合法状态投影为无效；贯穿行锁避免该竞态。|
|Impact|无 Schema/API/依赖变更；每次 Guard 检查写新事件与 Audit，运行性能尚未验收。可信时间推进与状态事件仍是先后两笔事务，后者失败时 Guard 拒绝且不能把旧状态当放行依据。状态拒绝后只允许未来受控恢复命令重验证，不由普通 Guard 自动复活。|
|Rollback|内部入口尚未挂路由；可撤销代码但不可删历史事件和 Audit。|

## DEC-20260924-094

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-094|
|Date|2026-09-24|
|WBS|LIC-02-A05 受控重验证与状态恢复|
|Decision|内部恢复命令仅接受当前 DeploymentAdmin Session+CSRF；在锁定部署状态与 ACTIVE 安装的同一事务中读取不可变签名文档和最新事件，再以可信时间版本调用原 LicenseService 全量验证。成功才追加 VALID 事件并恢复状态，失败追加分类拒绝事件；安装结果引用、状态投影和 Audit 同事务。|
|Reason|运行时 Guard 失败关闭后不得自行复活；已冻结恢复面允许管理员触发重验证，但不能直接把数据库状态翻转为 VALID 或重置可信时间完整性。|
|Impact|无 Schema、Migration、依赖或公开 API 变更。可信时间前移与状态事务仍是两个事务；若后者失败，本次命令拒绝，不能据此放行业务。|
|Rollback|内部入口未挂 HTTP；代码可撤销，不删除已形成的不可变验证/Audit 历史。|

## DEC-20260924-095

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-095|
|Date|2026-09-24|
|WBS|执行纪律 / LIC-03-A03 前置决策|
|Decision|接受用户持续授权，按 `CR-EXEC-001` 将原 L3/Gate 的逐项许可改为偏差先记录、按证据执行与持续交付。LIC-03-A03 采用用户选择的方案 A，先做受控初态初始化，生产密钥来源与恢复留待 PLT-02/Release。|
|Reason|用户明确要求减少确认并持续交付；冻结架构仍将跨平台密钥保护与恢复安排在 Release 安全设计。|
|Impact|更新仓库执行约束、Skill、STATUS 与追溯文档；不自动通过 Gate，不上传 Secret/客户数据，不把测试密钥标作生产密钥。|
|Rollback|保留原 V1.0 和冻结提交，可恢复旧流程；已经形成的偏差与验证历史不删除。|

## DEC-20260924-096

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-096|
|Date|2026-09-24|
|WBS|LIC-03-A03 一次性受控可信时间初态初始化|
|Decision|使用已存在的 Auth DeploymentAdmin Session+CSRF 适配器授权内部初始化；只在可信时间状态与事件均为空时插入版本 0/空成功时间单例，并与 Audit 同事务。PostgreSQL 事务 advisory lock 串行化同时初始化请求，事件表 SHARE 锁防止检查到插入之间出现事件历史；已有状态/历史绝不重置。|
|Reason|用户选择方案 A，只允许创建首次空状态，不提前决定生产密钥来源。冻结 DEC-20260924-087 禁止日常可信时间端口在缺失时自动补建。|
|Impact|无 Schema/Migration、公开 API、新依赖或生产 Secret；生产密钥保护和恢复留待 PLT-02/Release，测试不可当作生产 License 验收。|
|Rollback|未挂外部路由；代码可撤销，但已经创建的单例及 Audit 不删除，恢复依正式备份流程。|

## DEC-20260924-097

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-097|
|Date|2026-09-24|
|WBS|PLT-02-A01 SecretRecord / SecretVersion ORM/Migration|
|Decision|按冻结 DM-02/SC-01～03 建立部署级 SecretRecord 与密文版本；版本的密文、元数据、Key Provider 引用及创建事实不可改，activated_at/retired_at 仅可沿 CREATED→ACTIVE→RETIRED 单向变化。当前版本用同父复合 FK；partial unique 保证同一记录至多一个活动版本，记录状态用 lock_version 约束。|
|Reason|保留密文与主材料分离及历史追溯，防止跨 Secret 引用和静默覆盖；冻结模型虽称 SecretVersion 不可变，但版本激活/退役需要受控生命周期字段变更，内容本身始终不可变。|
|Impact|新增两表和迁移 `20260924_0011`；无公开 API、新依赖或生产密钥来源。非空历史拒绝普通降级，升级前需备份。|
|Rollback|空表可降级到 `20260924_0010`；有历史时须走受控备份恢复，不能删除密文历史。|

## DEC-20260924-098

|字段|内容|
|---|---|
|Decision ID|DEC-20260924-098|
|Date|2026-09-24|
|WBS|PLT-02-A02 活动密文信封只读适配|
|Decision|将原候选“元数据读取与信封适配”拆为单一内部读路径：SQLAlchemy 仅从 ACTIVE SecretRecord 的 current_version_ref 读取同父、已激活且未退役的密文版本，转换为现有 SecretEnvelope；管理元数据查询另列 A03。|
|Reason|内部消费与管理员查询具有不同权限/数据最小化边界；先验收受控消费适配，避免通用密文查询扩散。|
|Impact|无 Schema/Migration、公开 API 或解密器实现；生产加密主材料和正式写命令仍未具备。|
|Rollback|可移除内部只读适配，不修改已存 Secret 历史。|

## DEC-20260925-001

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-001|
|Date|2026-09-25|
|WBS|PLT-02-A03 Secret 管理元数据只读查询与权限边界|
|Decision|内部详情与分页服务先用 Auth-owned 无 CSRF DeploymentAdmin 只读 Session 证明，再执行 License Guard，最终同事务复核管理员身份并读取只含安全列的投影；普通查询不读取 encrypted_payload、encryption_metadata 或 key_provider_ref。|
|Reason|冻结 GET 合同仅要求 Session+License，不能套用写操作的 CSRF；Guard 检查跨事务，第二次身份复核缩小权限撤销窗口；只投影安全字段降低误回显风险。|
|Impact|新增 Auth 内部只读权限适配及 Platform 服务/仓储；无 Schema、Migration、公开 API 或新依赖。Guard 尚未挂 HTTP，测试使用合成许可替身。|
|Rollback|内部服务未公开；撤销代码不影响 Secret 历史或冻结 API Contract。|

## DEC-20260925-002

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-002|
|Date|2026-09-25|
|WBS|PLT-02-A04 Secret 加密算法与密文写入边界|
|Decision|按 CR-PLT-002 采用版本化 AES-256-GCM；随机 96-bit nonce，AAD 绑定 SecretRef/用途/消费者/版本号/Key 引用，严格拒绝非 V1 元数据；加密输入与解密失败缓冲区尽量清零，主密钥仍只由外部 Key Provider Port 解析。|
|Reason|冻结模型规定只存密文、算法元数据和 Key 引用，但未定密文算法。Authenticated Encryption 可在不改 Schema/API 下提供完整性和上下文绑定。|
|Impact|新增内部加解密适配、合成测试和 PostgreSQL 临时库验证；无 Migration、新依赖、公开 API 或生产 Key Provider。生产安全验收仍未满足。|
|Rollback|尚无正式 Secret 写命令；已有历史密文不可静默转换或删除，后续算法升级须版本读取或受控重加密。|

## DEC-20260925-003

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-003|
|Date|2026-09-25|
|WBS|PLT-02-A05 Secret 管理写入与轮换命令|
|Decision|内部写服务在 License Guard 前先检查管理员 Session+CSRF，写事务再次检查；创建生成 SecretRef，轮换以活动记录行锁及 expected_version_no 保护，旧版先退役再激活新版并更新 Record，Audit 同事务。Cipher 草稿放入 Platform 应用层契约以保持依赖方向。|
|Reason|防止无权操作触发 License 信息侧信道，避免失效 Session/CSRF、并发轮换和审计失败留下部分密文。冻结 API-02 的 write-only 值与当前期望版本在内部命令层先形成可验证边界。|
|Impact|无 Schema/Migration、新依赖或公开 API；License Guard 与写事务分离导致检查后变化窗口，正式集成前须复核。生产 Key Provider 未实现，合成验证不能视为真实 Secret 可用。|
|Rollback|内部服务未公开；已存密文历史不可删除或覆盖，应使用新受控版本/状态命令恢复，不能普通降级。|

## DEC-20260925-004

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-004|
|Date|2026-09-25|
|WBS|PLT-02-A06 Secret 停用命令|
|Decision|把上一检查点暂列的“停用命令与管理 API 接线”拆为 A06 内部停用命令和 A07 公开 API/生产装配前置审查；停用将活动版本退役、Record 置 DISABLED 且 current_version_ref 清空，要求期望 lock_version 与同事务 Audit。|
|Reason|当前 FastAPI 仅开放健康检查；生产 Auth/License/Key Provider 装配、If-Match 与幂等基础尚未齐备，直接挂路由不能满足冻结 API-01/API-02 的安全协议。先验收不可逆读取拒绝的状态命令，公开接线另行验证。|
|Impact|仅时序/任务粒度调整，不改变冻结 API Contract、Schema 或数据模型；无 Migration/新依赖。公开 Secret API 仍未可用，完整程序包仍未交付。|
|Rollback|内部服务未公开；已退役密文历史不删除、不直接复活，恢复必须另走受控新版本命令。|

## DEC-20260925-005

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-005|
|Date|2026-09-25|
|WBS|PLT-02-A07 Secret 管理 API 前置检查|
|Decision|A07 公开路由暂不接线，保留 BLOCKED_BY_PREREQUISITES；先实施 AUT-03 登录/Session HTTP 安全、生产 License/Key Provider 装配和幂等/版本协议，再恢复 A07。CR-PLT-003 记录将 Key Provider 安全设计前移的时序差异。|
|Reason|TestClient 实测登录及 Secret 路由均 404，仅健康路由 200；若以合成 Guard/Key Provider 挂路由会违反冻结 API-01/API-02 和生产 Secret 分离要求。|
|Impact|不变更冻结路径、Schema 或权限；A07 未完成，不得声称管理 API/真实 Secret 可用。项目继续不受阻塞的 Auth/平台基础任务。|
|Rollback|尚无公开 Secret 路由；若前置不能满足，保持默认 404 和失败关闭，不能以测试替身代替生产装配。|

## DEC-20260925-006

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-006|
|Date|2026-09-25|
|WBS|AUT-03-A01 登录可信 Host/Origin 边界|
|Decision|将 A07 前置的“登录 HTTP 安全边界”拆为可信 Host/Origin、限流、凭据编排和 Cookie/CSRF 独立可验收项；首项采用显式允许集合，非 loopback 仅 HTTPS，缺失/重复来源拒绝，转发头不参与信任判断。|
|Reason|当前无公开登录路由与可信部署源配置；一次性开放会混入未验证限流和凭据流程。严格来源策略先作为独立组件验证，不把 `X-Forwarded-Host` 当作可信目标。|
|Impact|无公开 API、Schema、Migration 或新依赖；登录仍 404。反向代理须保留可信 Host；配置、限流与 Cookie 另行验收。|
|Rollback|组件未挂路由；移除不会改变现有健康接口，不能以宽松默认源替代。|

## DEC-20260925-007

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-007|
|Date|2026-09-25|
|WBS|AUT-03-A02 登录限流策略与持久化边界|
|Decision|依 CR-AUT-001 在 PostgreSQL 建 Auth 私有窗口桶，以来源地址与规范化用户名两个独立 SHA-256 摘要键原子预约尝试；来源限 30 次/5 分钟、账户限 10 次/5 分钟，拒绝及数据库不可用时不进入密码验证。|
|Reason|单机部署可运行多个 API 进程，进程内限流可绕过；双维度限制来源爆破与分布式针对账户尝试，且不落原始地址/用户名。|
|Impact|新增 ORM/Migration，密文/API Contract/架构不变；摘要不等同匿名化，数据库仍需访问控制与短期保留。限值、代理来源与清理调度须在正式登录装配前验证。|
|Rollback|短期计数桶可在维护窗口清理，确认无登录流量后按 Alembic down 回退；不得删除 Audit/User/Session 历史。|

## DEC-20260925-008

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-008|
|Date|2026-09-25|
|WBS|AUT-03-A03 登录用户名/密码证明与 Session 签发编排|
|Decision|登录先预约限流，再规范化用户名并查活动身份；不存在或停用的用户执行受控 scrypt 假验证以缩小时间差，成功身份交既有 SessionService 再次锁用户/校验真实密码并原子签发 Session+Audit。所有凭据失败对外统一 `AUTH_INVALID_CREDENTIALS`，追加不含原始用户名/密码的拒绝审计；密码可变缓冲区始终清零。|
|Reason|复用已验证的 Session 与密码 Port，避免按用户名查询与签发之间的停用/换密竞争；不让错误类型直接暴露用户存在性。|
|Impact|仅新增 Auth 应用编排、只读身份仓储和假验证适配，无 Schema/Migration、公开 API 或新依赖；HTTP Cookie/Origin/限流真实客户端地址仍待装配。|
|Rollback|内部服务未挂路由；撤销不改变已签发 Session 历史，已有 Session 只能按正式撤销命令处理。|

## DEC-20260925-009

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-009|
|Date|2026-09-25|
|WBS|AUT-03-A04 登录 HTTP Cookie/CSRF 接线|
|Decision|增加显式注入的登录 Router，默认应用不挂载；HTTP 入口先校验已配置的精确 Host/Origin，再限制 JSON 正文为 4096 字节且只收 username/password。Session Token 仅放 HttpOnly/SameSite=Lax Cookie，HTTPS Origin 自动设置 Secure，受信任 loopback HTTP 用于本机验证；CSRF 原值仅在本次成功响应 DTO 给前端内存，错误统一安全 Envelope。|
|Reason|在生产依赖装配前验证 HTTP 边界，防止默认开放未配置的登录；保持冻结 API-01/02 的传输与失败语义。|
|Impact|新增登录 HTTP Router、可选应用装配和已冻结 AUTH_INVALID_CREDENTIALS 错误码映射；无 Schema/Migration、新依赖或默认公开登录。Session 查询/续期/注销和初始管理员仍由后续 WBS 完成。|
|Rollback|移除可选 Router 注入即可恢复默认 404；已签发 Session 不能仅靠下线 Router 撤销。|

## DEC-20260925-010

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-010|
|Date|2026-09-25|
|WBS|AUT-03-A05 登录 SessionView 真实身份投影|
|Decision|把冻结 SessionView 的 user/deployment_role/authorized_projects 设为登录 Router 必填的只读投影 Port。Auth 适配器只从当前 ENABLED User 读身份和部署角色；项目摘要必须由 Project-owned Port 显式提供，尚无 ProjectMember 层时不设置生产默认空列表。投影失败时不发 Cookie、返回固定服务不可用错误。生产装配与初始管理员顺延为 A06。|
|Reason|上一项 HTTP 边界的最小 DTO 缺少冻结字段；Auth 不应自行伪造项目成员事实或长期把缺失数据写为空项目权限。|
|Impact|登录 Router 签名要求真实投影，旧的可选接线测试需增加投影替身；无 Schema/Breaking API，新响应补齐冻结结构，仍不默认开放。已签发但投影失败的 Session 在服务器端保留至超时，后续评估补偿撤销。|
|Rollback|回退该非公开 Router 装配；不改变已冻结 API 或 User/Session 数据。|

## DEC-20260925-011

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-011|
|Date|2026-09-25|
|WBS|AUT-03-A06 初始 DeploymentAdmin 离线受控创建|
|Decision|仅在本机离线命令入口创建首个 DeploymentAdmin。应用服务使用专用 PostgreSQL 事务级 advisory lock 串行化，确认整个 User 表为空后在同一事务写 User、scrypt 凭据和不含密码的 Audit；任何已有 User 即拒绝，不能用于管理员恢复或新增普通用户。初始密码至少 15 个 Unicode 字符、最多 1024 UTF-8 字节。CLI 通过终端无回显读取数据库 URL 和双次密码，不能从参数或环境变量接收初始密码；无回显不可用时失败关闭。|
|Reason|初次部署时不存在可验证的管理员 Session，既有 UserCommandService 正确地要求已登录授权。离线单次初始化可解除循环依赖，但必须独立于公开 API 并禁止重新引导提权。|
|Impact|新增 Auth bootstrap 内部服务、SQL 适配和受控 CLI；无 Schema/Migration、公开路由或新依赖。初始化凭据仍需部署者现场设置，不能由 AI 代用户填写真实密码。生产登录 Router 与 Project 授权读取仍待后续任务。|
|Rollback|在尚未执行初始化的部署可移除 CLI；已创建的管理员属于正式 User/Audit 历史，不得简单删除，应走未来受控管理员迁移/停用流程。|

## DEC-20260925-012

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-012|
|Date|2026-09-25|
|WBS|AUT-03-A07 登录生产依赖装配前置|
|Decision|按 CR-AUT-002 保留默认登录关闭，A07 暂不记 PASS；先建设 Phase 2 范围内的 Project/ProjectMember 持久层及授权摘要读取，再在安全运行配置完成后恢复生产装配，随后继续 Session HTTP。|
|Reason|现有项目授权摘要和运行信任源缺口无法由空列表或测试配置安全替代。|
|Impact|仅实施顺序调整，无冻结 API/Schema 变化；Gate 3/UAT 不受自动放行。|
|Rollback|前置补齐后可直接恢复 A07，保留本次核查记录。|

## DEC-20260925-013

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-013|
|Date|2026-09-25|
|WBS|PRJ-01-A01 Project/Department/ProjectMember ORM 与 Migration|
|Decision|按冻结 PRJ-01～03 建立三张 `plm.prj_*` 表：Project 代码部署内唯一；Department 代码在同项目 ACTIVE 状态唯一；ProjectMember 对未 REMOVED 用户建立全部署与同项目 partial unique；ProjectMember.department_id 与 project_id 通过复合 FK 锁定同项目。三者保留状态、时间、乐观锁版本和不可删除 FK；本任务不开放读写 API 或自动生成项目事实。|
|Reason|真实项目授权摘要需要可验证成员事实；数据库必须阻止跨项目部门绑定及多项目有效成员，不能依赖登录响应空列表替代。|
|Impact|新增普通增量 Migration 和 ORM，无现有表变更、公开 API 或新依赖。Project 状态/角色变更的应用命令与授权读取后续单项完成；已有库升级保留所有数据。|
|Rollback|仅确认三张表无数据且无下游 FK 后允许 Alembic downgrade；有数据时拒绝自动删除。|

## DEC-20260925-014

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-014|
|Date|2026-09-25|
|WBS|PRJ-01-A02 项目成员授权摘要读取|
|Decision|Project 模块公开只读 `ProjectAccessSummary` DTO，并在当前事务中按 UserId 查询 ACTIVE、已生效、未结束的 ProjectMember；只返回 ACTIVE Project 与 ACTIVE Department 的项目 ID/名称/角色，不缓存也不以 DeploymentAdmin 身份推定项目成员。Auth SessionView 复用该公开 DTO，并从显式 Project Port 取得摘要。|
|Reason|冻结模型将 ProjectMember 作为项目权限唯一事实，Session 不持久化权限快照；部署管理员不自动拥有项目数据访问权。|
|Impact|无 Schema/Migration、公开 API 或新依赖；补齐登录响应所需的真实 Project 摘要读层，但完整 ProjectAuthorizationService 的逐操作判定仍待后续 WBS。|
|Rollback|移除只读适配器并恢复 Auth Port 未装配状态；不改变项目成员或 Session 历史。|

## DEC-20260925-015

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-015|
|Date|2026-09-25|
|WBS|PRJ-01-A03 ProjectAuthorizationService 逐操作授权|
|Decision|Project 模块对冻结 API-02 的项目路径操作维护显式角色白名单；未登记操作默认拒绝。每次在新事务中从 Project、ACTIVE Member、ACTIVE Department 重读状态，目标 Member/Department 由数据库反查 owner ProjectId 并与路径交叉校验；DeploymentAdmin 不自动成为项目成员。归档项目只允许授权读取，不允许写。普通无权/不存在/跨项目统一 `RESOURCE_NOT_FOUND`；有权成员对归档项目写入返回 `PROJECT_ARCHIVED`。|
|Reason|登录摘要不能当权限快照；冻结模型要求按资源实际归属和当前成员事实重新校验。`PROJECT_LIST` 的授权列表与部署级 `PROJECT_CREATE` 的管理员命令另在对应读/写任务接线，不能用项目成员角色替代。|
|Impact|新增 Project 内部授权 Service/SQL Repository，无 Schema/Migration、公开 API 或新依赖。调用者仍必须先经 Auth Session、License、CSRF 等契约前置；本服务只实现 Project 角色/Scope 判定，不宣称全链路开放。|
|Rollback|内部 Port 尚未挂公开路由；撤销本实现不改变业务数据。|

## DEC-20260925-016

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-016|
|Date|2026-09-25|
|WBS|PRJ-01-A04 Project 创建命令|
|Decision|Project code 与可选 department seed code 做 Unicode NFKC、去首尾空白与 casefold 归一化，再由数据库唯一约束兜底；未提供部门 seed 时原子建立 `DEFAULT`/`默认部门`，保证首位 ProjectManager 的必需 Department FK。创建命令先验证当前管理员 Session/CSRF，再执行 License Guard，再在同一写事务重新验权并由 Auth-owned Port 锁定 ENABLED 初始负责人；Project、Department、Member 和 Audit 原子提交。|
|Reason|冻结 API 允许 department seed 缺省，但冻结 DM-02 要求每个 Member 有同项目 Department；创建者不自动成为项目成员。归一化统一代码大小写与兼容字符，锁定负责人防并发重复绑定，数据库约束最终兜底。|
|Impact|内部服务、Auth 只读资格 Port 与 Project 写适配器；无 Schema/Migration、公开 API 或新依赖。生产 License/HTTP 装配仍待后续。|
|Rollback|内部命令尚未公开；撤销代码不自动删除已创建项目或审计历史。|

## DEC-20260925-017

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-017|
|Date|2026-09-25|
|WBS|PRJ-01-A05 Project 列表与详情读取|
|Decision|Project 只读 Application Port 先执行 License Guard，再由 Auth-owned Port 在查询事务验证当前 Session、User 状态与凭据版本；Project-owned SQL 在同一事务重读 ACTIVE 且已生效 Member、ACTIVE Department 与 Project 当前状态，不使用登录时摘要。`PROJECT_LIST` 仅返回当前有权项目；`PROJECT_GET` 对不存在、无成员或跨项目统一隐藏。ARCHIVED 允许受权读取。冻结单有效项目成员不变量使当前列表最多 1 项，DTO 仍保留 Page 形状，`next_cursor` 为 null。|
|Reason|避免 Session 摘要陈旧与 DeploymentAdmin 隐式越权；列表和详情共用当前成员事实。模型强制单一未移除成员，当前不产生多页，因此无须提前引入未验证的公开游标格式。强 ETag 仅从 Project.lock_version 生成。|
|Impact|新增 Auth 只读 Session 身份适配器、Project 查询 Service/Repository；无 Schema/Migration、公开 API 或新依赖。公开 GET 仍须由后续 HTTP 装配并应用 API-01 Envelope/trace。|
|Rollback|撤销未公开的查询 Port；不改变项目数据。|

## DEC-20260925-018

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-018|
|Date|2026-09-25|
|WBS|PRJ-01-A06 Project 元数据修改与归档内部命令|
|Decision|`PROJECT_PATCH` 首版只允许修改 Project 显示名称，不允许经通用 PATCH 修改 ProjectCode；编码不可静默复用，未来如需改码须专用受控命令和旧码保留机制。`PROJECT_PATCH`/`PROJECT_ARCHIVE` 均要求当前 ProjectManager、ACTIVE Project、Session/CSRF、License、expected lock_version 与同事务 Audit；归档不提供普通反向操作。Project 授权 Port 增加写事务内核验，写操作锁定项目/成员/部门事实并在同事务更新。|
|Reason|冻结 API-02 仅写“metadata”，未规定可修改 code；DM-02 明确 ProjectCode 不可静默复用，而当前冻结 Schema 不保存旧 code，直接改码会释放旧码导致复用。名称是可安全修改的显示元数据；乐观并发和事实锁避免撤权/归档竞态。|
|Impact|新增内部 Project 写命令/SQL Repository，授权 Port 增加同事务入口；无 Schema/Migration、新依赖或公开 API。若未来需要 code 修改，先按正式变更流程设计历史保留与升级。|
|Rollback|内部命令未挂公开路由；已有名称/归档变更保留在 Audit，归档不可自动回滚为 ACTIVE。|

## DEC-20260925-019

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-019|
|Date|2026-09-25|
|WBS|PRJ-02-A01 ProjectMember 授权列表读取|
|Decision|`PROJECT_MEMBER_LIST` 在 License Guard 与 Auth 当前 Session 验证后，于同一数据库事务调用 ProjectAuthorizationService 的 `PROJECT_MEMBER_LIST` 策略；仅 ProjectManager/CustomerManager 可读取该路径 Project 的成员历史。Project Repository 只读 ProjectMember/Department，Auth-owned Port 批量提供 user_id/display name，Project 不直接查询 Auth 表。内部分页以 `(project_member_id ASC)` 做稳定 keyset，原始 after_id 不对 HTTP 客户端暴露；后续公开路由必须按 API-01 封装完整性保护的不透明 cursor。|
|Reason|成员列表需保留 ACTIVE/SUSPENDED/REMOVED 历史，同时防止其他项目成员和 Auth 凭据数据泄漏。用户显示名由 Auth Owner 提供，避免跨模块内部表访问。内部 keyset 位置不是可直接暴露的 API cursor。|
|Impact|新增 Project 内部列表 Service/Repository 与 Auth 最小用户摘要适配器；无 Schema/Migration、新依赖或公开 API。归档 Project 仍允许授权只读。|
|Rollback|撤销未公开查询 Port；不改变成员历史。|

## DEC-20260925-020

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-020|
|Date|2026-09-25|
|WBS|PRJ-02-A02 ProjectMember 创建命令|
|Decision|创建成员由当前 ProjectManager 在 License Guard、Session/CSRF 后于同一事务执行：锁定当前项目权限事实，Auth-owned Port 锁定 ENABLED 目标 User 并返回最小显示名，Project-owned Repository 锁定同项目 ACTIVE Department、检查目标 User 未有任何非 REMOVED membership，插入单一角色/部门成员并同事务 Audit。数据库 partial unique 与复合 FK 作为并发/跨项目最终防线；目标 User 缺失/停用或部门不合规则固定拒绝，已分配返回 `PROJECT_USER_ALREADY_ASSIGNED` 且不披露另一项目。允许可选未来 effective_at，未提供由数据库取当前时间。|
|Reason|冻结模型要求一个 User 同时最多一个未移除成员，部门必须同项目；跨模块 User 状态只能通过 Auth Port，不能由 Project 直查 Auth 内部表。锁 User 与 Department，再结合数据库约束可防并发重复和归属漂移。|
|Impact|新增 Project 内部创建 Service/Repository、Auth-owned 目标资格适配器；无 Schema/Migration、新依赖或公开 API。公开 POST 的 Idempotency-Key 仍待正式 API 安全装配。|
|Rollback|内部命令尚未公开；已创建成员如需撤销，应走后续 REMOVE 命令保留历史，不物理删除。|

## DEC-20260925-021

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-021|
|Date|2026-09-25|
|WBS|PRJ-02-A03 ProjectMember 角色/部门修改命令|
|Decision|依据 CR-PRJ-001，在冻结的当前成员表之外增加 Project-owned 角色/部门变更历史子表，不改当前权限读取路径；每次实际变更在同一事务更新成员版本、插入前后值历史并写 AuditEvent。无变化返回原 ETag，不制造事件。最后一名当前有效 ProjectManager 不允许降级，以避免项目无法再管理。|
|Reason|冻结 DM-02 要求角色变更历史，而原 Schema 与通用 AuditEvent 无法完整追溯角色和部门的旧、新值。项目行锁使当前授权与负责人数量检查串行，成员版本锁与数据库约束防覆盖。|
|Impact|新增 Migration `20260925_0014`、Project 内部修改命令及 Auth 最小显示名 Port；无公开 API Breaking Change。必须升级数据库后部署本版。|
|Rollback|历史表为空时可降级到 `20260925_0013`；已有历史需保留，不允许自动丢弃。内部命令未公开，可停用但不可篡改已写历史。|

## DEC-20260925-022

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-022|
|Date|2026-09-25|
|WBS|PRJ-02-A04 ProjectMember 暂停/恢复/移除命令|
|Decision|三项内部命令复用同一状态 Service/Repository，但调用不同的冻结操作策略；仅允许 ACTIVE→SUSPENDED、SUSPENDED→ACTIVE、ACTIVE/SUSPENDED→REMOVED。每次变更需当前 ProjectManager、Session/CSRF、License、目标归属、expected_version 与同事务 Audit。恢复要求关联部门 ACTIVE。暂停/移除最后一个当前有效 ProjectManager 拒绝。未来生效成员提前移除时 `ended_at = greatest(statement_timestamp(), effective_at)`，状态立即 REMOVED。|
|Reason|统一状态矩阵避免各命令实现分歧；最后负责人保护防管理权限被清空，数据库时间约束要求提前移除的 ended_at 不早于 effective_at。|
|Impact|新增 Project 内部状态 Service/Repository，无 Schema/Migration、新依赖或公开 API；正式 POST 幂等和 If-Match 留给公开 API 安全接线。|
|Rollback|内部命令未公开；已移除成员不可原地恢复，只能按后续受权创建命令重新分配并保留原历史。|

## DEC-20260925-023

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-023|
|Date|2026-09-25|
|WBS|PRJ-03-A01 Department 授权列表读取|
|Decision|`PROJECT_DEPARTMENT_LIST` 在合成 License Guard 与 Auth 当前 Session 证明后，于同一事务检查 ProjectAuthorizationService 的当前成员事实。Project Repository 只查目标 Project 的 ACTIVE/INACTIVE Department，不访问 Auth 表；内部按 department_id ASC 稳定 keyset，返回最多 200 项及内部 after_department_id。归档项目受权只读保留。|
|Reason|冻结 API-02 授权所有当前 ProjectMember 读取所属项目部门；历史部门须保留，权限不得依赖缓存或客户端 project_id 声称。稳定内部 keyset 避免更新造成分页位置漂移；公开 API-01 cursor 后续必须签名或完整性保护，不暴露原始 ID。|
|Impact|新增 Project 内部只读 Service/Repository；无 Schema/Migration、新依赖或公开 API。|
|Rollback|内部查询尚未公开，可移除该 Port；不影响部门数据与历史。|

## DEC-20260925-024

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-024|
|Date|2026-09-25|
|WBS|PRJ-03-A02 Department 创建命令|
|Decision|Department 创建沿用 Project bootstrap 的 NFKC/trim 显示值与 casefold 规范化语义，在当前 ProjectManager、Session/CSRF、License 与项目 ACTIVE 检查后，以 PostgreSQL `uq_prj_departments__project_code_live` 部分唯一索引作为并发最终防线。冻结 DM 的“DepartmentCode 项目内唯一”按更具体的冻结 SC-02/03 部分唯一索引解释为同项目 ACTIVE Department 唯一；INACTIVE 历史保留且其代码可被新 ACTIVE Department 复用。创建与 Audit 同事务，冲突固定 `CONFLICT_DUPLICATE`。|
|Reason|冻结 SC-03 明确为 partial unique，已有 ORM/Migration 仅对 ACTIVE 行唯一；保持现有 DB 基线与可追溯历史，不额外改变冻结 Schema。|
|Impact|新增 Project 内部创建 Service/Repository；无 Schema/Migration、新依赖或公开 API。对停用部门编码复用的 UI 展示需要在未来公开设计中结合 ID/状态区分，不能只凭 code 认定历史身份。|
|Rollback|内部命令尚未公开，可停止新建；已有 Department 不物理删除，若需撤销须走后续受控停用并保留历史。|

## DEC-20260925-025

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-025|
|Date|2026-09-25|
|WBS|PRJ-03-A03 Department 名称/编码修改命令|
|Decision|仅 ACTIVE Department 可由当前 ProjectManager 在同事务 Session/CSRF、License、目标归属及 expected_version 检查后修改名称和/或编码。编码沿用 NFKC/trim/casefold；同项目 ACTIVE 部门不得重复，项目行锁串行化受权写入且 DB partial unique 兜底。真实变更版本+1并写 Audit，无变化返回原 ETag 不制造事件；INACTIVE 历史不允许普通 PATCH。|
|Reason|维持冻结 API-01 强 ETag、API-02 逐操作权限与 SC-03 活动编码唯一；禁止修改停用历史，避免旧引用被悄然改写。|
|Impact|新增 Project 内部 PATCH Service/Repository；无 Schema/Migration、新依赖或公开 API。当前 AuditEvent 可追溯操作者/对象/时间，但不保存字段级旧/新 code/name，不能支持逐版字段恢复；如后续正式要求该能力须单独 Change Request。|
|Rollback|内部命令尚未公开，可停止使用；已修改元数据不能依赖 Audit 自动恢复旧值，需有正式备份或后续受权修订。|

## DEC-20260925-026

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-026|
|Date|2026-09-25|
|WBS|PRJ-03-A04 Department 停用命令|
|Decision|仅当前 ProjectManager 可对所属 ACTIVE 项目内的 ACTIVE Department 执行一次性停用；先核对 Session/CSRF、License、目标归属与 expected_version，再在项目行锁保护下检查目标部门没有 ACTIVE/SUSPENDED ProjectMember。仅 REMOVED 历史引用不阻止停用，不做成员静默迁移。成功时版本+1并与前后状态 Audit 同事务提交；重复停用拒绝。|
|Reason|冻结 DM-02 与 API-02 明确成员引用阻断和 `PROJECT_DEPARTMENT_IN_USE`；项目行锁与成员新建/修改命令共享写入序列，数据库查询在同事务内复核，避免并发创建与停用形成矛盾状态。|
|Impact|新增 Project 内部停用 Service/Repository；无 Schema/Migration、新依赖或公开 API。仅通过正式服务写入可受项目锁保护；部署数据库角色权限仍须保证应用外写入受控。|
|Rollback|内部命令未公开；已停用部门按冻结状态模型无普通恢复命令，若业务需要重用编码可新建部门，旧 DepartmentId 和历史引用保持不变。|

## DEC-20260925-027

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-027|
|Date|2026-09-25|
|WBS|AUT-03-A07-P01 可信 Origin 部署配置|
|Decision|在现有非敏感 BootstrapSettings 中新增默认空的 `trusted_origins`，允许 YAML 显式数组和 `PLM_TRUSTED_ORIGINS` JSON 数组覆盖；配置层限制最多 16 项、非空和单项长度，但不在 Platform 层复制 Auth 的 URL/Host 规则。最终装配仍必须调用既有 `LoginOriginPolicy` 校验 URL、HTTPS/loopback、Host 匹配，任何失败不得挂载登录路由。|
|Reason|CR-AUT-002 要求可信 Origin 生产来源，而现有 Auth 策略已有精确语义；配置层只持有非敏感部署值，避免 Platform 反向依赖 Auth 或维护两套可能分叉的来源校验。|
|Impact|新增非敏感配置和测试；无 Schema/Migration、新依赖、公开 API 或权限变化。配置加载成功本身不代表生产登录可用，安全数据库凭据和端到端装配仍待完成。|
|Rollback|删除部署配置即可恢复默认空来源；当前默认应用不挂登录路由，无数据迁移。|

## DEC-20260925-028

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-028|
|Date|2026-09-25|
|WBS|AUT-03-A07-P02 Windows 数据库凭据来源|
|Decision|依 CR-AUT-003 使用当前 Windows 运行账户的 Credential Manager Generic Credential，固定生产 Target `PLMProjectTool/Database`；本机无参数、无回显交互写入/轮换，运行时只读。URL 必须为带 Host、用户名、密码的 `postgresql+psycopg`；读取/写入失败统一脱敏拒绝，不回退到环境变量/YAML/测试 URL。|
|Reason|安全数据库凭据是 AUT-03-A07 的真实前置；使用系统账户保护的持久存储，比把密码保存在普通配置中更符合已冻结 Secret 边界。固定 Target 防止运行时路径注入；测试只操作 UUID 合成 Target。|
|Impact|新增 Windows 专有基础设施和部署入口；无 Schema/Migration、新依赖或公开 API。目标服务账户需现场录入，跨账户/跨机器不自动迁移；Debian 仍需独立来源。Python/SQLAlchemy 内存副本不可保证绝对清零。|
|Rollback|停止调用该来源并关闭服务；生产 Vault 凭据不会自动删除，由部署管理员通过系统凭据管理手工移除或轮换。|

## DEC-20260925-029

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-029|
|Date|2026-09-25|
|WBS|AUT-03-A07-P03 Windows 生产登录组合根|
|Decision|单独提供显式 Windows 登录应用工厂，不更改普通 `create_app()` 的默认无登录行为。启动顺序为可信 Origin 策略 → 当前账户 Credential Manager 数据库 URL → PostgreSQL 连通性与 `plm.alembic_version` 等于包内迁移 head → 真实 Auth/Project/Audit 接线；任一步失败均不发布应用且释放连接。进程退出释放 Engine。本机 Uvicorn 明文入口只绑定回环 IP，禁用代理头信任；对外 HTTPS 由本机受控反向代理提供。|
|Reason|让 CR-AUT-002 的项目摘要与安全来源成为真实生产依赖，同时避免把测试注入应用冒充默认产品入口。仅 `SELECT 1` 不能证明 Schema 已升级；非回环明文监听会让密码暴露于网络。|
|Impact|新增组合根、Windows 启动入口及应用生命周期清理；无 Schema/Migration、新依赖或冻结 API 变化。Windows 11 合成 PostgreSQL/Windows Vault 链路已验证；Server 2025 服务账户、HTTPS 代理与 Debian 来源仍需单独验收，不能由本项推定通过。|
|Rollback|不调用 Windows 启动入口即可保留原默认健康-only 应用；无数据迁移，已签发的测试 Session 随一次性库删除。|

## DEC-20260925-030

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-030|
|Date|2026-09-25|
|WBS|AUT-03-A08 当前 Session 查询 HTTP|
|Decision|冻结 GET Session 仅验证唯一严格格式的 `plm_session` Cookie 和当前 Session，再读取最新 User/ProjectMember 摘要；响应只含身份、授权摘要与到期时间，不回显 Cookie/Token/CSRF，也不刷新期限。只读请求必须有单一可信 Host；若客户端提供 Origin 则仍按已冻结登录来源策略精确校验，不要求浏览器 GET 必须带 Origin。仅显式生产组合根挂载，普通应用继续 404。|
|Reason|API-02 对 GET 标记 `S` 而非 `C`，CSRF 原值仅在创建/轮换响应发放；强行要求所有 GET 带 Origin 会拒绝合法浏览器读取。Host 必须可信以避免不受信域名承载 Cookie 身份投影，实时摘要不能复用登录时的旧权限。|
|Impact|新增 Auth 只读 HTTP 入口、Host 策略及生产显式挂载；无 Schema/Migration、新依赖或冻结 API Breaking Change。Windows 11 真实 PostgreSQL 验证成员暂停后摘要即时刷新；业务请求仍须逐操作重新授权。|
|Rollback|停止显式挂载 Session Router 即恢复默认 404；GET 不修改 Session/项目数据，无迁移回滚。|

## DEC-20260925-031

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-031|
|Date|2026-09-25|
|WBS|AUT-03-A09 Session 续期 HTTP|
|Decision|冻结 `POST /api/v1/auth/session:renew` 使用唯一严格 Cookie、`X-CSRF-Token`、精确 Origin/Host 且不接受请求正文。先验证当前 Session/CSRF 并读取 User/Project 投影，确保投影失败不会先撤销旧凭据；之后调用已验收的同事务 Session 轮换/Audit，成功只通过 HttpOnly Cookie 和本次 DTO 返回新 Token/CSRF。绝对到期保持原时刻，旧凭据立即失效。|
|Reason|API-02 的续期控制为 S/C/A 而非 I；投影属于响应必需内容，若轮换后才发现投影故障会让浏览器收不到新凭据。预检与轮换间的并发由轮换服务再次校验 Session 关闭，不把预检当成最终授权。|
|Impact|新增 Auth 续期 HTTP 与显式生产挂载；无 Schema/Migration、新依赖或 Breaking Change。投影可能在相邻事务之间被项目成员变更，后续业务请求仍须实时重验授权；多标签旧凭据按冻结轮换语义失效。|
|Rollback|停止显式挂载续期 Router 即恢复默认 404；已成功轮换的 Session 不反向复活，用户可重新登录，无数据库迁移。|

## DEC-20260925-032

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-032|
|Date|2026-09-25|
|WBS|API-RUNTIME-01 通用持久幂等收据|
|Decision|按 CR-API-001 新增与配置专用收据并列的 `plt_idempotency_receipts`；范围为 actor/project/版本化 operation/Key SHA-256，部署级 NULL Project 通过 `UNIQUE NULLS NOT DISTINCT` 仍唯一。只存规范化请求 SHA-256 和非敏感结果引用/HTTP 状态，不存 Key/正文/Token/完整响应。reserve→业务/Audit→complete 必须在同一事务；已完成行触发器禁止修改/删除，PENDING 误提交后失败关闭；非空表禁止 downgrade，暂不自动过期清理。|
|Reason|冻结 API-01 要求跨进程/重启重放同一语义，现有 `plt_configuration_command_receipts` 受 CHECK/外键限制，不能混入 Auth/Project 命令。单独增量保留 Gate 2 历史与旧配置收据语义。|
|Impact|新增 ORM/Alembic `20260925_0015`、应用范围/指纹与 PostgreSQL 收据仓储；无公开 API/新依赖。调用方必须先完成授权并保证结果引用可重建原语义，ProjectId 归属由调用方验证。记录会持续增长，Retention 和误提交 PENDING 的受控恢复仍需单独设计。|
|Rollback|停止新命令挂载；新收据为空时可 downgrade 到 `0014`，非空时拒绝以保留去重历史。旧表和旧业务数据不变。|

## DEC-20260925-033

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-033|
|Date|2026-09-25|
|WBS|AUT-03-A10 Session 注销 HTTP|
|Decision|注销首次请求以有效 Session、匹配 CSRF、可信 Origin/Host 与合法幂等 Key 为前置，在同一 UoW 内预留 `V1_AUTH_LOGOUT` 收据、撤销 Session、追加 `SESSION_REVOKED` Audit 并完成指向该 Session 的 200 结果引用。已撤销 Session 仅在原 Token/CSRF、同 Key/同 Session 指纹、收据已完成、撤销原因确为 LOGOUT 时返回原 200 并再次清 Cookie；并发等待收据后重新读取 Session 状态。不同 Key 对旧 Session 返回 401，不同 Session 同 Key 返回 409。|
|Reason|冻结 API-02 的注销同时标记 S/C/I/A，但首次成功后 S 已失效；为了满足 API-01 同 Key 同结果重试，不可用普通 Session 再授权，也不可把所有旧 Cookie 当幂等成功。通过持久收据与已撤销原因双重绑定，重试只获取原注销语义，不恢复权限。|
|Impact|新增 Auth 注销 Application/HTTP 接线，复用 `0015` 收据；无新 Migration、新依赖或 Breaking Change。已完成收据与 Session 历史的 Retention 需协同设计，当前不得自动删除。默认应用仍不挂 Auth 路由。|
|Rollback|停止显式挂载注销 Router 即恢复默认 404；已撤销 Session 不反向复活，用户需重新登录；收据与 Audit 保留供追溯。|

## DEC-20260925-034

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-034|
|Date|2026-09-25|
|WBS|PLT-02-A07-P01 Windows Secret 主密钥只读来源|
|Decision|依 CR-PLT-003 的安全装配前置，Windows 侧使用当前运行账户 Windows Credential Manager Generic Credential 作为独立主密钥读取来源，严格映射受限 key_ref，要求正好 32 字节；读取器不创建、覆盖、导出或自动回退到配置/环境变量。此项只是 OS 来源适配，不宣称生产 Key Provider 和恢复已完成。|
|Reason|现有 AES-GCM Secret 密文引用 key_ref，需要密文库外的受保护来源；Windows Vault 可由当前运行身份访问且不需将原始主密钥放进仓库、YAML 或数据库。缺失、错账户或错长度必须失败关闭。|
|Impact|新增 Platform 基础设施适配器与 Windows 11 合成测试；无 Schema、Migration、公开 API、新依赖或冻结合同变化。服务账户供给、独立备份与异机恢复、Server 2025/Debian 13 均未验证。|
|Rollback|移除该只读适配器注入即可回到原先未装配状态；测试临时凭据已删除，无真实主密钥或业务密文迁移。|

## DEC-20260925-035

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-035|
|Date|2026-09-25|
|WBS|PLT-02-A07-P02 Windows 主密钥供给和独立恢复|
|Decision|为当前账户 Windows Vault 的 32 字节主密钥提供本机交互式首次供给、加密备份、目标为空时恢复；备份采用独立口令经 scrypt 派生的 AES-256-GCM 加密，并以 key_ref 绑定 AAD。首次供给先生成不可覆盖的新备份，后写 Vault 并回读校验；恢复先验证备份和口令，拒绝覆盖任何已存在目标。备份文件不进入源代码、数据库或普通配置。|
|Reason|仅依赖当前账户 Vault 会在账户/主机丢失时造成历史 Secret 密文永久不可读。独立加密备份允许受控异账户恢复，同时避免应用自动获取恢复口令；旧 Vault 条目必须避免误覆盖。|
|Impact|新增 Platform 密钥生命周期和本机运维入口；不改变冻结 API、数据模型、算法中的 Secret 密文格式或目标平台。备份口令及文件由部署人员分开离线保管，不能自动恢复。Windows 11 合成验证后仍须 Server 2025 目标账户/恢复验证，Debian 13 暂不验证。|
|Rollback|停止使用运维入口，保留原 Vault 条目及已生成的加密备份供人工保管；不删除真实主密钥、密文或审计。错误供给和恢复不能覆盖既有条目。|

## DEC-20260925-036

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-036|
|Date|2026-09-25|
|WBS|PLT-02-A07-P03-A01 Windows 选定 MAC 本机匹配来源|
|Decision|Bootstrap 仅可包含一个显式选定、非秘密的 MAC；License 的 Windows SelectedMachine Port 在每次验证时以 Windows IP Helper 的 GetAdaptersAddresses 读取本机网卡，只有选定 MAC 规范化后与本机某个 6 字节网卡地址匹配才返回。缺配置、枚举失败、虚构地址和格式异常一律失败关闭，不回退到 `uuid.getnode()` 或配置自证。|
|Reason|现有 LicenseService 只对 Port 返回值作 SHA-256；若 Port 直接透传配置，复制配置即可使不同机器声称相同指纹。现场显式选择仍符合 ADR-006，但必须与当前机器事实绑定。|
|Impact|增加 Windows License 基础设施与非敏感 Bootstrap 字段；不改变七字段签名载荷、MAC 规范化/哈希算法、Schema 或公开 API。MAC 可由虚拟网卡提供，不能抵御有系统级控制权的伪造；Server 2025 和 Debian 13 仍须分别验证/实现。|
|Rollback|不装配该 Port 时公开受许可业务保持关闭；不修改已有 License 文档、可信时间或数据库数据。|

## DEC-20260925-037

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-037|
|Date|2026-09-25|
|WBS|PLT-02-A07-P03-A02 本产品发行公钥来源|
|Decision|客户运行时公钥只可来自后端 wheel 内的本产品发行清单，不从请求、数据库、普通 YAML、环境变量或 License 文件读取公钥。解析器固定产品代码和唯一 key_ref，严格校验 Ed25519 原始公钥格式及清单字段，缺失/错误即拒绝装配。开发 wheel 可以不含真实发行清单而失败关闭；正式 release 构建必须显式核对签发公钥已装入包。|
|Reason|现有 StaticPublicKeyResolver 仅是依赖注入边界，生产若从可编辑配置建立信任锚，攻击者可替换公钥并自签 License。包内受信公钥与签发私钥物理隔离，保持 ADR-006 的离线验签边界。|
|Impact|新增 License 基础设施与发行检查；无签名载荷、Schema、API 或加密算法变更。真实发行密钥与私钥备份仍必须在 Developer Workbench 单独生成和保管；当前未生成时不把生产 License 标 PASS。|
|Rollback|不装配解析器即可保持原受许可业务关闭；测试公钥不进入正式包，已有 License 文档/数据库不变。|

## DEC-20260925-038

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-038|
|Date|2026-09-25|
|WBS|PLT-02-A07-P03-A03 Developer Workbench License 签发密钥仪式|
|Decision|先修正实际工作台私钥目录的完整 Git 忽略规则；仅在本机交互终端从隐藏输入取得由操作员保管的强口令，生成 Ed25519 私钥并以加密 PKCS#8 PEM 独占创建于工作台 private 目录，公钥清单独占创建于客户后端包内。禁止自动用测试钥、空口令、命令行或环境变量口令代替。独立备份/恢复与最终 wheel 验证是发行门禁。|
|Reason|现有忽略规则只覆盖根级 `developer-workbench/private/`，没有整体覆盖实际 `tools/developer-workbench/private/`；若非 `.pem` 文件误入目录可被 Git 纳入。正式签发私钥尚不存在，不能用合成测试钥冒充生产信任锚。|
|Impact|修复忽略规则、增加开发者工作台工具与测试，不改冻结载荷、Schema 或公开 API。真实密钥生成依赖人工秘密口令和独立备份保管；工具可先实现/合成验证但未举行仪式前 P03-A02 和发行 Gate 仍未通过。|
|Rollback|工具不运行则无密钥；若仪式尚未发行，保留生成的加密私钥及公钥供核对，不自动覆盖、轮换或删除。已经发行的公钥不可静默替换。|

## DEC-20260925-039

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-039|
|Date|2026-09-25|
|WBS|PLT-02-A07-P03-A04 Windows 可信时间 HMAC 密钥来源|
|Decision|可信时间使用独立固定引用 `trusted-time-v1` 的 32 字节随机密钥，通过已有当前 Windows 账户受保护 Vault Port 供给，部署时沿用加密备份/空目标恢复流程；组合根在装配前强制检查密钥可用。HMAC 对 pristine 空初态也先检查密钥，不允许无密钥的空初态被视为可信。不得将密钥放入数据库、普通 YAML、环境变量或 License 文档。|
|Reason|LIC-03-A03 只创建受控空初态，现有 HMAC verify 对 pristine 状态提前返回 True，若未先检查独立密钥，装配层可能误以为可信来源已就绪。独立 key_ref 避免与业务 Secret 主密钥混用；当前 Vault/备份机制可复用而不改变冻结 HMAC 规则。|
|Impact|调整 License 完整性失败关闭与 Windows 组合入口；无 Schema/Migration、签名载荷或公开 API 变更。真实目标账户密钥尚需现场供给与备份演练；Server 2025 和 Debian 13 状态不变。|
|Rollback|不挂载 License 组合入口则受许可业务保持关闭；既有可信时间状态不自动重置或改写，丢钥只可从匹配备份受控恢复。|

## DEC-20260925-040

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-040|
|Date|2026-09-25|
|WBS|PLT-02-A07-P03-A05 Windows License 生产组合根|
|Decision|Windows 组合根只从已安装包内唯一产品公钥、配置中显式选择且本机存在的 MAC、当前运行账户独立可信时间 Vault 密钥和当前 PostgreSQL Schema 形成 LicenseService/TrustedTimeStatePort/RuntimeGuard；任一缺失则拒绝装配，不自动降级合成 Port。恢复登录面与受许可业务路由分离，当前不公开管理路由。|
|Reason|内部 License 组件单独通过测试不代表生产信任链；组合根必须保证各 Port 来源和数据库版本一致，避免部署端可替换公钥或空可信时间无密钥仍放行业务。|
|Impact|新增 Windows 入口组合和合成/临时库验证，不改七字段载荷、Schema、API 或权限。真实签发私钥/公钥和目标账户 Vault 密钥仍待现场仪式；本项不能据合成数据宣称生产 License PASS。|
|Rollback|不调用此组合根即可保持原生产登录/健康面；无数据迁移或自动密钥生成，已有 License 状态不修改。|

## DEC-20260925-041

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-041|
|Date|2026-09-25|
|WBS|PLT-02-A07-P04-A01 Secret 元数据详情只读 HTTP|
|Decision|先实现可选挂载的单条 Secret 元数据详情 GET。严格检查可信 Host/Origin、唯一有效 Session，再由既有内部服务复核 DeploymentAdmin 与 License；投影仅含冻结允许的元数据和强 ETag。列表的不透明游标及写操作另立任务，不在本项以明文分页或虚假依赖替代。默认应用不挂载，正式信任锚就绪前不公开生产管理路由。|
|Reason|内部安全投影和会话服务已存在，可以独立验证单条只读 HTTP 契约；写入/轮换仍受正式密钥、If-Match、幂等及审计接线制约。|
|Impact|仅增加可选 HTTP Router、元数据锁版本投影和测试；不改变冻结 API、Schema、Migration 或生产路由。|
|Rollback|不注入该 Router 时保持默认 404；无数据变更。|

## DEC-20260925-042

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-042|
|Date|2026-09-25|
|WBS|PLT-02-A07-P04-A02 Secret 元数据列表安全游标|
|Decision|列表只允许 `created_at DESC, secret_id DESC` 的固定 keyset 顺序；游标以 HMAC-SHA256 完整性保护并绑定资源族、DeploymentAdmin Scope、当前 Session 摘要、分页参数指纹和最后一项排序键。签名密钥由装配层显式注入且必须为独立 32 字节秘密；缺失时不得装配生产列表。保留既有内部 UUID 分页供历史调用，本项新增 HTTP 专用排序方法。|
|Reason|冻结 API-01 要求默认最多 200 条、稳定顺序及不透明完整性保护游标；既有内部 UUID 升序分页不足以构成公开列表合同。|
|Impact|新增只读列表 API/游标/仓储查询与测试，不改变 Schema、Migration、写 API 或默认应用挂载。生产密钥供给继续纳入后续装配验收。|
|Rollback|不注入列表 Router 时默认 404；可保留原内部列表，不迁移数据。|

## DEC-20260925-043

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-043|
|Date|2026-09-25|
|WBS|PLT-02-A07-P04-A03 Windows 游标签名密钥来源|
|Decision|列表游标使用独立固定引用 `secret-list-cursor-v1` 的 32 字节随机密钥，通过当前 Windows 账户受保护 Vault 解析；缺钥、长度错误或读取失败拒绝装配。供给与独立加密备份/空目标恢复复用既有本机交互工具，不自动生成、打印或写入配置。|
|Reason|游标不能与业务 Secret 主密钥或可信时间 HMAC 密钥共用；目标账户密钥必须可恢复，否则服务重启/迁移后分页全部失效。|
|Impact|新增 Windows 组合入口和合成/临时 Vault 恢复测试，不改 API、Schema、Migration；真实目标账户供给/恢复需后续部署验收。|
|Rollback|不装配列表 Router 时仍保持默认 404；既有游标不作数据迁移，丢钥只能从对应备份受控恢复。|

## DEC-20260925-044

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-044|
|Date|2026-09-25|
|WBS|PLT-02-A07-P04-A04 Windows Secret 只读生产组合根|
|Decision|保留当前登录/恢复启动入口；新增显式 `--platform` 启动模式，仅在现行 PostgreSQL Schema、包内正式产品公钥/本机 MAC/可信时间密钥和独立游标签名 Vault 密钥全部可装配时同时挂载登录与 Secret 只读详情/列表。任一前置失败则整个平台模式拒绝启动并释放数据库，不回退到合成 Guard 或静默退回登录模式。写接口仍关闭。|
|Reason|Secret 只读路由已具备 Session、管理员及 License 保护；生产组合必须在真实信任源齐备后才开放，又不能因其缺失剥夺既有登录/恢复面。|
|Impact|扩展 Windows 组合与启动模式，增加失败关闭测试；不改冻结 API、Schema、Migration 或登录默认行为。正式公钥/目标账户密钥尚缺，平台模式不能标生产 PASS。|
|Rollback|不传 `--platform` 继续运行原登录模式；无数据迁移，失败启动不挂载只读路由。|

## DEC-20260925-045

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-045|
|Date|2026-09-25|
|WBS|PLT-02-A07-P05-A01 Secret 轮换锁版本对齐|
|Decision|内部 `RotateSecret` 的期望条件从当前密文 `version_no` 改为记录 `lock_version`，与冻结 API-01 强 ETag/If-Match 一致。持久层在锁定活动记录时验证锁版本，并读取真实当前密文版本号计算下一版本；实际写事务同时核查记录锁版本与当前版本，旧锁版本不触发加密/写入。|
|Reason|旧实现只核对密文版本号；两者虽在正常活动路径通常相等，却不能证明公开 `If-Match` 正确落在记录并发版本上。|
|Impact|仅修改内部命令/仓储签名与验证，不改公开 API、Schema、Migration 或密文版本规则；更新全部内部调用和历史验证脚本。|
|Rollback|保留原冻结 API 与数据库数据；如实现异常可回退该内部代码，公开写路由仍保持关闭。|

## DEC-20260925-046

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-046|
|Date|2026-09-25|
|WBS|PLT-02-A07-P05-A02 强 If-Match 请求边界|
|Decision|写请求仅接受恰好一个 ASCII `If-Match: "vN"`，其中 N 为无前导零的正整数且小于 PostgreSQL bigint 上界；缺失映射冻结的 428 `CONFLICT_VERSION_REQUIRED`，重复、弱标签、通配符、列表、畸形或越界映射 400 `REQUEST_MALFORMED`。解析后只向内部命令传记录 `lock_version`。|
|Reason|冻结 API-01 要求强 ETag 与 If-Match；宽松 HTTP 解析可能把弱/复合条件误当成单资源并发版本。|
|Impact|新增无状态解析器和边界测试；无 Schema、Migration 或公开写路由变更。|
|Rollback|写路由尚未开放，可移除解析器；不影响现有只读/登录功能。|

## DEC-20260925-047

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-047|
|Date|2026-09-25|
|WBS|PLT-02-A07-P05-A03 Secret 创建持久幂等|
|Decision|创建命令强制 `Idempotency-Key`；在当前管理员与 License 复核后，同一数据库事务先按 actor/全局范围/操作/Key 摘要预约通用收据，指纹只包含 purpose、consumer 与 Secret 值的 SHA-256 摘要，不持久化明文。相同请求重放只返回原 SecretRef，不重新加密/审计；不同请求返回冻结的幂等冲突。密文、Audit 与完成收据同事务提交。|
|Reason|公开 Secret 创建可重试，原内部服务单独提交会在网络重试时重复创建；现有 Migration `0015` 已提供原子收据。|
|Impact|修改内部创建命令和依赖签名、单元/临时库验证；轮换/停用与 HTTP 接线另项完成。无 Schema/Migration/已公开 API 变更。|
|Rollback|写 HTTP 仍关闭；实现异常可回退代码，既有历史 Secret/收据不删除。|

## DEC-20260925-048

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-048|
|Date|2026-09-25|
|WBS|PLT-02-A07-P05-A04 Secret 轮换/停用持久幂等|
|Decision|轮换与停用命令均强制合法 Idempotency-Key。完成管理员/License 复核后，在写事务内按 actor/部署全局/操作/Key 摘要预约通用收据；轮换指纹只含 SecretRef、期望锁版本和新值 SHA-256，停用指纹只含 SecretRef/期望锁版本。轮换完成收据引用不可变新密文版本，重放在相同 SecretRef 下读取原版本号；停用完成收据引用退役版本，仅在归属吻合时承认重放。密文状态、Audit 和收据同事务提交。|
|Reason|冻结 API-01 要求可重试写命令幂等；现有轮换/停用事务已原子，但网络重试会遇陈旧版本冲突，无法区分同请求重放。|
|Impact|修改内部命令/仓储 Port 与验证，不改 Schema/Migration 或已公开 API；HTTP 写路由继续关闭。|
|Rollback|写路由未开放；既有历史记录和收据不可删除，故障时仅回退未发布代码。|

## DEC-20260925-049

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-049|
|Date|2026-09-25|
|WBS|PLT-02-A07-P05-A05 Secret 创建 write-only HTTP|
|Decision|新增仅显式注入的 `POST /api/v1/admin/secrets`：先验证可信 Host/Origin、唯一 Cookie/CSRF/Idempotency-Key 与现行 Session，再读取受限大小的 JSON，要求精确三字段 `purpose`、`allowed_consumer`、`secret_value`，拒绝重复键/非标准常量/未知字段；受控枚举与非空 UTF-8 值交给内部创建服务。201 响应仅 SecretRef、强 ETag、Location 和 TraceId，永不回显值/密文。默认/当前生产组合不挂载写 Router。|
|Reason|冻结 API-02 要求 Secret 值 write-only、DeploymentAdmin、Session/License/CSRF/幂等/Audit；已有内部服务与收据可支撑可选 HTTP 契约，但正式主密钥/发行信任锚尚未供给。|
|Impact|新增 HTTP 边界、错误码注册与契约测试；不改 Schema/Migration/冻结路径。JSON 解析产生短生命周期不可原地清零的字符串，使用大小上限、不记录请求体、可变明文字节清零并保持部署前置关闭。|
|Rollback|不注入 Router 仍 404；无数据库迁移或自动 Secret 创建。|

## DEC-20260925-050

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-050|
|Date|2026-09-25|
|WBS|PLT-02-A07-P05-A06 Secret 轮换 write-only HTTP|
|Decision|新增仅显式注入的 `POST /api/v1/admin/secrets/{secret_id}:rotate`：与创建相同的可信来源/Session/CSRF/幂等安全门，登录校验后严格解析单个强 If-Match 并作为记录锁版本；请求仅接受有界非空 UTF-8 `secret_value`，200 仅返回 SecretRef、新密文版本号、ACTIVE 状态与原语义强 ETag，不回显原值/密文。默认与当前生产组合不挂载。|
|Reason|冻结 API-02 轮换需要 S/L/C/I/M/A；内部轮换及收据已具备，可独立验证 HTTP 边界，正式主密钥/License 仍未供给。|
|Impact|新增可选 Router、错误映射和验证；不改 Schema/Migration、冻结路径或生产启动行为。复用创建 JSON 安全解析规则；JSON 不可原地清零的短生命周期字符串风险继续按 P05-A05 控制。|
|Rollback|不注入 Router 仍 404；无数据迁移或自动轮换。|

## DEC-20260925-051

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-051|
|Date|2026-09-25|
|WBS|PLT-02-A07-P05-A07 Secret 停用 HTTP|
|Decision|新增仅显式注入的 `POST /api/v1/admin/secrets/{secret_id}:disable`。可信 Host/Origin、唯一 Cookie/CSRF/Idempotency-Key 与现行 Session 先验证，再严格解析单个强 If-Match 为记录锁版本；请求体必须为空，200 仅返回 SecretRef、DISABLED、空当前版本、原语义新强 ETag 与 TraceId。默认和当前生产组合不挂载。|
|Reason|冻结 API-02 停用需要 S/L/C/I/M/A；内部停用/收据已经保证同事务，HTTP 必须拒绝未经声明的请求体和弱/缺失版本条件。|
|Impact|新增可选 Router、契约/临时库验证；无 Schema/Migration、冻结路径或生产启动行为变化。|
|Rollback|不注入 Router 仍 404；不触及既有 Secret 数据。|

## DEC-20260925-052

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-052|
|Date|2026-09-25|
|WBS|PLT-02-A07-P05-A08 Windows 生产 Secret 写装配|
|Decision|保留现有默认登录与 `--platform` 只读模式，新增显式 `--platform-write` 组合；此模式在 Schema、包内 License 公钥/选定本机 MAC/可信时间 Vault、游标独立 Vault 和当前账户固定 `secret-master-v1` 主密钥均可用后，才构造共用的 SecretWriteService 并挂载创建/轮换/停用路由。任一来源缺失则拒绝启动，不从 YAML/环境变量/请求获取主密钥或测试替身。|
|Reason|可选 write-only HTTP 已验证，但正式组合不能因路由存在而隐式开放；固定引用避免普通配置控制加密主材料选择，显式模式保留当前只读装配语义。|
|Impact|Windows 启动入口增加非默认模式与组合测试；无 Schema/Migration/冻结 API 变化。正式发行公钥/目标账户密钥供给及 Server 2025/HTTPS 验收仍独立，不能由合成组合声称生产 PASS。|
|Rollback|退回 `--platform` 只读模式，不卸载或改写既有 Secret 密文；无数据迁移。|

## DEC-20260925-053

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-053|
|Date|2026-09-25|
|WBS|PRJ-04-A01 Project 列表/详情 HTTP|
|Decision|将已有 ProjectReadService 以仅显式注入的 `GET /api/v1/projects` 与 `GET /api/v1/projects/{project_id}` 接入 HTTP。先校验可信 Host 和当前 Session，再由 Project 服务在事务内重复校验会话、License 与成员/部门授权；列表仍只返回当前至多一个授权 Project，固定 Page 结构，无需生成游标，接受规范 1～200 `page_size`，拒绝 cursor/未知/重复参数。详情统一隐藏跨项目并返回强 ETag。真实 License Guard 拒绝映射为冻结的 `LICENSE_OPERATION_DENIED`，基础设施失败保持 503。默认应用不挂载。|
|Reason|内部读取与单有效成员 Schema 已验证，但无前端可用的冻结 Project GET API；显式边界可先验证权限隔离，同时不绕过尚缺的正式发行信任源。|
|Impact|新增 Project HTTP、错误分类、契约/临时库测试；无 Schema/Migration 或冻结路径变化。若未来允许多项目成员，必须另行实现完整性保护 keyset cursor，不得沿用无游标假设。|
|Rollback|不注入 Router 即恢复 404；无数据迁移或 Project 数据改写。|

## DEC-20260925-054

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-054|
|Date|2026-09-25|
|WBS|PRJ-04-A02 Windows 显式平台 Project 读取组合|
|Decision|仅在 `--platform` 与 `--platform-write` 已完成 Schema、License 信任链和游标签名密钥装配后，使用现行 SessionService、LicenseRuntimeGuard、Auth Session 读 Port 与 Project SQL 读仓库挂载 `PROJECT_LIST`/`PROJECT_GET`。默认登录模式及未供齐信任源时保持不可访问。|
|Reason|Project 可选 HTTP 与内部授权读取已通过，但还缺正式组合入口；复用现有安全前置避免创建第二套 Session 或 License 判定。|
|Impact|只改 Windows 组合根与合成/临时库验证，不变更 Schema、冻结 API、Project 数据或普通启动行为；真实目标账户/发行材料与 Server 2025 仍待验收。|
|Rollback|改用默认登录模式，Project 路由继续 404；无数据迁移。|

## DEC-20260925-055

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-055|
|Date|2026-09-25|
|WBS|PRJ-04-A03 Project 创建同事务持久幂等前置|
|Decision|在现有内部 Project 创建服务上新增独立的 HTTP 用途幂等创建方法，不改变原 `create` 的历史返回 DTO；使用 `API-RUNTIME-01` 通用收据按管理员 actor/`V1_PROJECT_CREATE`/Key 范围与规范化请求指纹进行事务预留，在同一事务提交 Project、初始 Department/Manager、Audit 和只含 ProjectId 的结果引用。对重放以原请求规范化字段和不可变 `created_at` 重建冻结 `ProjectView` 的首次 201 语义，强 ETag 固定 `"v0"`；不用当前可变 name/state/lock_version 冒充首次结果。|
|Reason|冻结 API-01 的可重试 POST 必须持久幂等；现有内部创建没有 Idempotency-Key，直接开放 HTTP 会使同键网络重试产生重复写入或错误响应。通用收据只能存一个非敏感结果引用，冻结创建响应恰为 ProjectView，不要求重放内部 Department/Member ID。|
|Impact|增加 Project 应用方法、只读 `created_at` Repository Port、单元/临时 PostgreSQL 验证；无 Schema/Migration、新依赖或公开 API。若项目历史行异常消失则失败关闭。|
|Rollback|停止调用新幂等方法，旧内部 `create` 语义保持；保留已完成的收据/Project/Audit 历史，不删除数据。|

## DEC-20260925-056

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-056|
|Date|2026-09-25|
|WBS|PRJ-04-A04 Project 创建 HTTP|
|Decision|新增仅显式注入的 `POST /api/v1/projects`，验证可信 Host/Origin、唯一 Cookie/CSRF/Idempotency-Key 和现行 Session 后解析最多 8 KiB、UTF-8、无重复键/非标准常量的 JSON。只接受 code/name/initial_manager_user_id 与可选 department seed，UUID 必须 canonical lowercase；调用 `create_idempotent`。201 仅返回冻结 ProjectView、ETag/Location/TraceId，不返回初始成员内部 ID。默认和当前生产组合先不挂载。|
|Reason|内部管理员原子创建与持久幂等已具备，现需补齐冻结浏览器请求边界；在正式 License 信任源未供给前仍需保持生产默认关闭。|
|Impact|新增 Project HTTP、错误码映射、契约/临时库验证；无 Schema/Migration、冻结 API 或安全机制变更。|
|Rollback|不注入 Router 即恢复 404；既有 Project/审计/收据保留，无数据迁移。|

## DEC-20260925-057

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-057|
|Date|2026-09-25|
|WBS|PRJ-04-A05 Windows 显式平台 Project 创建组合|
|Decision|仅在 `--platform` 与 `--platform-write` 已经通过 Schema、License 信任链和游标签名密钥装配后，以现行 SessionService、LicenseRuntimeGuard、Auth 管理员/初始负责人 Port、Project SQL 创建仓库、Audit 与 `0015` 收据构造 ProjectCreateService，并挂载 `PROJECT_CREATE` Router。默认登录模式继续 404。|
|Reason|内部原子创建、持久幂等和可选 HTTP 已验证；复用显式平台组合可向正式可用程序推进，避免第二套权限/许可判断或在普通模式隐式开放。|
|Impact|只改 Windows 组合与测试；无 Schema/Migration、冻结 API 或项目规则变化。正式发行公钥/目标账户材料和 Server 2025 仍待验收。|
|Rollback|退回默认登录模式，Project 创建路由不挂载；已有 Project/审计/收据不可回滚删除。|

## DEC-20260925-058

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-058|
|Date|2026-09-25|
|WBS|PRJ-04-A06 Project 元数据 PATCH HTTP|
|Decision|将通用强 If-Match 解析器补齐对规范 `"v0"` 的接受；仍拒绝弱、多值、前导零和越界形式。原因是冻结 API-01 明确 ETag 映射当前 `lock_version`，Project 初始值为 0。新增仅显式注入的 `PATCH /api/v1/projects/{project_id}`：可信来源/Session/CSRF、强 If-Match、仅 name 的有界 JSON，调用现有 ProjectWriteService；200 返回安全 ProjectView 与新强 ETag。默认/当前平台组合先不挂载。|
|Reason|不接受 v0 会让刚创建 Project 的首次 PATCH 永远无法满足冻结并发合同；内部服务/SQL 已支持 expected_version=0。|
|Impact|通用解析器接纳合法初始版本，Secret 内部轮换/停用仍自行拒绝其不合法 v0；新增可选 Project HTTP 与测试，无 Schema/Migration、冻结 API 或安全规则变化。|
|Rollback|不注入 Project PATCH Router 恢复 404；解析器可回退，但会重新引入 Project 首次修改不可用缺陷，因此须先替代此合同实现。|

## DEC-20260925-059

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-059|
|Date|2026-09-25|
|WBS|PRJ-04-A07 Windows 显式平台 Project PATCH 组合|
|Decision|仅在 `--platform` 与 `--platform-write` 既有 Schema、License、游标信任源前置全部通过后，复用当前 Session、License Guard、Project 授权/SQL 写仓库和 Audit 组合 ProjectWriteService，并挂载 PRJ-04-A06 PATCH Router。普通默认登录模式保持 404。|
|Reason|可选接口和内部写服务已分别验证；复用单一平台组合根可防止多套 License 或权限判断。|
|Impact|仅组合根和合成端到端验证；无新 Migration、依赖、冻结 API 或 License 机制变化。正式公钥/目标账户材料和 Server 2025 仍待。|
|Rollback|恢复普通登录模式或移除显式平台 PATCH 注入，路由保持 404；既有 Project 修改和 Audit 不删除。|

## DEC-20260925-060

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-060|
|Date|2026-09-25|
|WBS|PRJ-04-A08-P01 Project 归档持久幂等前置|
|Decision|冻结 `PROJECT_ARCHIVE` 含 I 控制，公开 HTTP 前先为内部归档新增同事务 `0015` 收据。作用域为当前负责人/Project/`V1_PROJECT_ARCHIVE`/Key 摘要；请求指纹含 ProjectId 与 expected_version。首次执行锁定当前权限后归档、Audit、收据原子提交。增加仅内部归档重放权限检查：负责人角色、Project/Member/Department 当前事实加锁，但允许读取已归档项目；不扩展冻结的 13 个公开操作。重放仍检查当前 Session、License 和负责人角色，再从已归档 Project 读取既有结果，不重复写入。|
|Reason|现有内部归档只支持强版本，若直接公开 POST，同 Key 重放在项目已归档后会被拒绝，违反冻结 API 的幂等控制。|
|Impact|Project 内部应用服务/仓库与测试；复用已有 Migration `0015`，不改变冻结 API、Schema 或 License。普通内部 `archive()` 保留兼容。|
|Rollback|不接入公开路由即可停用新路径；已提交的 Project 归档为单向业务事实，不回滚删除，仅可恢复代码到旧内部命令并保留收据历史。|

## DEC-20260925-061

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-061|
|Date|2026-09-25|
|WBS|PRJ-04-A08-P02 Project 归档 HTTP 边界|
|Decision|新增仅显式注入的 `POST /api/v1/projects/{project_id}:archive`。可信 Origin、Cookie Session、CSRF、规范 Idempotency-Key、强 If-Match 必填；请求正文必须为空。调用 P01 同事务归档幂等服务，成功 200 ProjectView、强 ETag、no-store；不同指纹 Key 409，默认/当前生产组合先不挂载。|
|Reason|冻结 API-02 明确 S,L,C,I,M,A 和 200 ARCHIVED；沿用现行写路由边界避免另设认证或请求格式。|
|Impact|新增可选 Project Router/契约与临时库 HTTP 测试，无 Schema、Migration、冻结 API 或新依赖。|
|Rollback|停止注入 Router 即恢复 404；已归档 Project 不提供逆向写接口。|

## DEC-20260925-062

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-062|
|Date|2026-09-25|
|WBS|PRJ-04-A08-P03 Windows 显式平台归档组合|
|Decision|只在 `--platform`/`--platform-write` 已通过 Schema、License 与游标信任源前置时，为现有 ProjectWriteService 注入通用 `0015` 收据，并挂载 P02 归档 Router；PATCH 继续复用同一服务，普通默认登录模式保持 404。|
|Reason|内部幂等与可选 HTTP 已验证；复用单一组合避免第二套身份/License/权限逻辑。|
|Impact|仅 Windows 显式组合、合成端到端测试和版本记录；无新 Migration、冻结 API 或新依赖。|
|Rollback|退回普通登录模式或不注入归档 Router，保留既有 Project/Audit/收据事实；正式信任源缺失时仍失败关闭。|

## DEC-20260925-063

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-063|
|Date|2026-09-25|
|WBS|PRJ-04-A09-P01 Project Member 列表 cursor 前置|
|Decision|沿用内部 MemberId 升序 keyset；公开 cursor 采用独立 32 字节 HMAC-SHA256 密钥、URL-safe 规范编码，绑定资源族 `project-member-history`、ProjectId、Session 摘要、page_size 查询指纹与最后 MemberId。生产 Windows 来源使用独立当前账户 Vault 引用 `project-member-list-cursor-v1`，在后续显式组合 WBS 接线；无签名密钥时不得开放列表。|
|Reason|冻结 API-01 要求不透明、完整性保护、Scope/查询绑定 cursor；内部 `after_member_id` 不得直接暴露为可构造查询参数。|
|Impact|新增 Project API cursor 编解码及测试，无 Schema/Migration、冻结 API 或第三方依赖变化；正式目标账户须额外安全供给并备份此密钥。|
|Rollback|不挂载成员列表路由保持 404；已签发 cursor 可自然失效，但不得静默更换密钥后宣称分页连续。|

## DEC-20260925-064

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-064|
|Date|2026-09-25|
|WBS|PRJ-04-A09-P02 Project Member 列表可选 HTTP|
|Decision|仅显式注入成员列表 Router；复用当前 Host/Session 验证、P01 HMAC cursor 与 PRJ-02-A01 Service。请求仅 page_size/cursor，响应仅安全 MemberView Page。内部 Service 将 RuntimeLicenseError 映射为 `LICENSE_OPERATION_DENIED`，避免生产 HTTP 将已知许可拒绝误报为 503；其他异常仍失败关闭。|
|Reason|冻结 API-02 只允许 ProjectManager/CustomerManager 读取成员历史，API-01 要求完整性保护分页和安全响应；现有 Service 将 License 异常统一包成 PROJECT_UNAVAILABLE，需在公开前修正。|
|Impact|Project 成员读服务、可选 Router、测试和文档；无 Schema/Migration、冻结 API、依赖或权限扩张。默认/当前平台组合仍 404。|
|Rollback|停止注入 Router 恢复 404；License 错误映射可独立回退，但会使已知许可拒绝错报 503。|

## DEC-20260925-065

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-065|
|Date|2026-09-25|
|WBS|PRJ-04-A09-P03 Windows 成员 cursor 密钥来源|
|Decision|新增独立只读 Windows 当前账户 Vault 装配入口，固定引用 `project-member-list-cursor-v1`；缺钥/错长失败关闭。沿用已有交互式通用密钥供给、加密备份/恢复流程，仅使用 UUID 范围测试引用进行 Vault 丢失恢复验证；本任务不产生正式密钥。|
|Reason|成员列表 cursor 必须能跨重启、备份恢复保持签名有效，不能取随机进程密钥、普通 YAML 或 Secret 列表专用签名密钥。|
|Impact|Windows 组合入口与测试，无 Schema/Migration、API、安全算法或新依赖变化；正式账户需单独供给/离线保管。|
|Rollback|成员列表不挂载即可停用；更换或丢失密钥会使旧 cursor 失效，须按备份流程恢复。|

## DEC-20260925-066

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-066|
|Date|2026-09-25|
|WBS|PRJ-04-A09-P04 Windows 显式平台成员列表组合|
|Decision|仅在 `--platform`/`--platform-write` 的 Schema/License/Secret 游标前置通过后，再读取独立成员 cursor Vault 密钥；任一密钥缺失则整个显式平台启动失败。复用当前 Session、License、Project 授权、Auth 用户摘要与成员 SQL 读层挂载 P02 Router；普通默认模式保持 404。|
|Reason|成员 cursor 的签名源必须在路由开放前稳定且可恢复；沿用单一生产组合避免接口自行获取密钥或放宽授权。|
|Impact|Windows 组合根、合成端到端与既有组合测试注入点更新，无 Schema/Migration、冻结 API 或新依赖。正式目标账户需独立供给和备份。|
|Rollback|退回普通登录模式或移除成员 Router 注入；旧 cursor 仅在原密钥恢复后可继续使用。|

## DEC-20260925-067

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-067|
|Date|2026-09-25|
|WBS|PRJ-04-A10-P01 成员创建 HTTP 幂等前置|
|Decision|依 CR-PRJ-002 新增 Project-owned 不可变创建结果快照，通用收据仅保存快照引用；同 Key 重放首次 MemberView，并重新检查当前 Session/CSRF、License 和 ProjectManager。|
|Reason|成员角色、部门、状态与显示名称均可变化，读取当前行无法履行冻结 API-01 的首次响应重放合同。|
|Impact|新增 Migration `20260925_0016`、ORM、内部服务和测试；不改 `/api/v1` 结构，不开放公开创建路由。|
|Rollback|新表为空可降至 `0015`；已有快照时拒绝降级，须保留版本并受控迁移。|

## DEC-20260925-068

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-068|
|Date|2026-09-25|
|WBS|PRJ-04-A10-P02 成员创建可选 HTTP|
|Decision|复用 Project 创建的 8 KiB 严格 JSON、可信 Origin/Session/CSRF/Idempotency-Key 边界；body 仅接受 `user_id`、`role`、`department_id` 及可选 UTC `effective_at`，ProjectId 只取路径。MemberView 复用已有安全投影，默认与当前平台组合均不挂载。|
|Reason|冻结 API-02 指定成员创建路径和 201 MemberView；内部 P01 已具备原样重放，接口不应自行绕过服务授权或回显内部字段。|
|Impact|Project 可选 Router、应用工厂注入点、测试和版本记录；无 Schema、Migration、Breaking API 或新依赖。|
|Rollback|移除 Router 注入后恢复 404；不影响内部成员创建与已存结果快照。|

## DEC-20260925-069

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-069|
|Date|2026-09-25|
|WBS|PRJ-04-A10-P03 Windows 显式平台成员创建组合|
|Decision|仅在 `--platform`/`--platform-write` 的 Schema、License、Secret 与成员 cursor 前置检查全部成功后装配成员创建；复用现行 Session、ProjectManager 授权、P01 收据/快照及 Audit。普通登录模式不挂载。|
|Reason|成员创建不能成为绕过生产信任源的平行入口，且须与既有 Project 路由共享同一安全组合根。|
|Impact|Windows 组合根和合成验证；无新 Schema、Migration、冻结 API 或依赖。|
|Rollback|移除该 Router 注入，恢复成员创建 404；历史成员及幂等快照保持不变。|

## DEC-20260925-070

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-070|
|Date|2026-09-25|
|WBS|PRJ-04-A11-P01 ProjectMember 更新可选 HTTP|
|Decision|新增仅显式注入的成员 PATCH Router：复用可信 Origin/Session/CSRF、有界严格 JSON、强 If-Match 解析，body 仅接受非空 `role`/`department_id` 子集；调用既有 PRJ-02-A03 服务并复用 MemberView 安全投影。默认及当前 Windows 平台组合不挂载。|
|Reason|冻结 API-02 要求角色/部门更新为受 ProjectManager 控制的版本化 PATCH，已有内部服务负责跨项目、最后负责人、历史和 Audit，不应在 HTTP 层重复业务规则。|
|Impact|Project 可选 Router、应用工厂注入点、测试与文档；无 Schema/Migration、新依赖或 Breaking API。|
|Rollback|撤销 Router 注入恢复 404；不回滚已成功提交的成员变更历史。|

## DEC-20260925-071

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-071|
|Date|2026-09-25|
|WBS|PRJ-04-A11-P02 Windows 显式平台成员更新组合|
|Decision|仅在 `--platform`/`--platform-write` 的 Schema、License、Secret/成员 cursor 可信来源全部就绪后装配成员 PATCH，复用真实 Session、ProjectManager 授权、PRJ-02-A03 历史与 Audit。普通登录模式不挂载。|
|Reason|成员更新不能经独立路线绕过生产信任源或现行成员授权；公开前置与既有 Project 路由保持一致。|
|Impact|Windows 组合根、契约与临时 PostgreSQL 组合验证；无新 Schema/Migration、冻结 API 或依赖。|
|Rollback|移除 Router 注入恢复成员 PATCH 404；已提交的角色/部门历史保持不变。|

## DEC-20260925-072

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-072|
|Date|2026-09-25|
|WBS|PRJ-04-A12-P01 成员状态命令持久幂等前置|
|Decision|依 CR-PRJ-003 以 Project-owned 不可变类型化快照保存 SUSPEND/RESUME/REMOVE 首次 MemberView；通用收据仅保存引用，三个操作分别作用域化，重放重新检查当前 Session/CSRF、License、ProjectManager 与目标归属。|
|Reason|状态、角色、显示名和版本会继续变化；现有内部命令重复执行会触发版本/状态冲突，当前成员行不能履行冻结 API-01 的原语义重放。|
|Impact|Migration `20260925_0017`、ORM、内部服务/授权查询及测试；不开放 HTTP，不改变冻结状态机。|
|Rollback|新表为空可降至 `0016`；已有快照时拒绝降级并保留幂等证据。|

## DEC-20260925-073

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-073|
|Date|2026-09-25|
|WBS|PRJ-04-A12-P02 成员状态命令可选 HTTP|
|Decision|一个仅显式注入的 Router 提供 `:suspend`、`:resume`、`:remove` 三个冻结 POST；共享可信 Origin、Session/CSRF、Idempotency-Key、强 If-Match 和空请求体边界，各自调用 P01 持久幂等服务，返回安全 MemberView/ETag。|
|Reason|三命令具有同一安全协议，但状态机与操作作用域由 Project Service 分别执行；HTTP 不自行判断授权或重建首次响应。|
|Impact|Project 可选 Router、应用工厂注入点、测试与文档；无新 Schema/Migration/依赖或 Breaking API。默认和当前 Windows 组合不挂载。|
|Rollback|移除 Router 注入恢复 404，已提交的状态事件、审计与幂等快照保持不变。|

## DEC-20260925-074

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-074|
|Date|2026-09-25|
|WBS|PRJ-04-A12-P03 Windows 显式平台成员状态组合|
|Decision|仅在 `--platform` 和 `--platform-write` 已有信任源与 Schema 门禁后装配成员状态服务及三个路由；默认登录模式保持 404。|
|Reason|沿用当前 Project 组合的 Session、License、ProjectManager、Audit 和同事务幂等，不增加额外的无保护入口。|
|Impact|Windows 平台组合与测试；无新 Schema/Migration/依赖和 Breaking API。|
|Rollback|移除平台组合注入恢复 404；既有事件、审计和快照保留。|

## DEC-20260925-075

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-075|
|Date|2026-09-25|
|WBS|PRJ-04-A13-P01 Department 列表游标前置|
|Decision|部门历史分页使用独立资源族 `project-department-history` 与专用 32 字节密钥签名游标，绑定 ProjectId、当前 Session、page size 和 `department_id` 稳定位置；跨资源族、跨会话/项目或篡改均拒绝。|
|Reason|冻结 API-01 禁止公开内部 keyset ID，现有成员列表游标不可作为部门游标复用，避免资源族混用和错误密钥域。|
|Impact|新增 Project API 游标编解码与测试；暂不开放 GET，不改 Schema、Migration 或冻结路径。Windows 独立密钥来源由后续组合任务验证。|
|Rollback|移除尚未公开的部门游标组件；不存在持久数据迁移。|

## DEC-20260925-076

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-076|
|Date|2026-09-25|
|WBS|PRJ-04-A13-P02 Department 列表可选 HTTP|
|Decision|沿用 Project Member 列表的可信 Host、当前 Session、严格分页参数、独立签名游标和安全投影边界；内部部门读取将正式 RuntimeLicenseError 映射为冻结的 `LICENSE_OPERATION_DENIED`。默认应用不挂载。|
|Reason|冻结 API-01/02 要求受权部门 page、跨项目隐藏和 License 拒绝；内部 keyset ID 不能直接暴露，许可失败不能被误报为 503。|
|Impact|Project 可选 Router、应用工厂注入点、部门读取错误映射和测试；无新 Schema/Migration/依赖或 Breaking API。|
|Rollback|移除 Router 注入恢复 404；错误映射可单独恢复但会重新违反冻结 License 错误合同。|

## DEC-20260925-077

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-077|
|Date|2026-09-25|
|WBS|PRJ-04-A13-P03 Windows 独立部门游标密钥来源|
|Decision|固定 Windows 当前账户 Vault 引用 `project-department-list-cursor-v1`，只读解析独立 32 字节密钥；缺失/错长拒绝启动。正式供给和备份需运行账户操作员完成，测试只使用临时 UUID 引用。|
|Reason|部门游标不能复用成员或 Secret 游标密钥；跨重启稳定签名需可恢复的当前账户安全来源。|
|Impact|新增 Windows 只读适配与合成 Vault 备份恢复测试；不生成、导出或提交正式密钥，不改 Schema/API。|
|Rollback|移除未接入生产组合的适配；测试临时 Vault 引用清理，正式资料不受影响。|

## DEC-20260925-078

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-078|
|Date|2026-09-25|
|WBS|PRJ-04-A13-P04 Windows 显式平台 Department 列表组合|
|Decision|仅在 `--platform` 与 `--platform-write` 已有 Schema/License/现有 cursor 信任源门禁后，再要求独立 Department cursor Vault 密钥并挂载 Department GET；默认登录模式保持 404。|
|Reason|沿用当前 Session、Project 授权、License Guard 和独立游标来源，不引入无保护入口。|
|Impact|Windows 平台组合、契约与 PostgreSQL 集成测试；无新 Schema/Migration/依赖或 Breaking API。|
|Rollback|移除平台 Router 注入恢复 404，已有部门事实不变。|

## DEC-20260925-079

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-079|
|Date|2026-09-25|
|WBS|PRJ-04-A14-P01 Department 创建持久幂等前置|
|Decision|按 CR-PRJ-004 新增 Project-owned 类型化首次 DepartmentView 快照，复用 `0015` 通用收据；旧内部创建命令保持，新增独立幂等入口。|
|Reason|当前 Department 可被修改或停用，仅凭部门 ID 无法履行冻结 API-01 的原响应重放。|
|Impact|Migration `20260925_0018`、ORM、Repository、Service 与测试；不开放 HTTP，不改变部门唯一性或授权规则。|
|Rollback|新表为空可降至 `0017`；已有快照时拒绝降级并保留幂等证据。|

## DEC-20260925-080

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-080|
|Date|2026-09-25|
|WBS|PRJ-04-A14-P02 Department 创建可选 HTTP|
|Decision|只在显式注入时提供冻结 `POST /api/v1/projects/{project_id}/departments`；复用可信 Origin、Session/CSRF、Idempotency-Key、严格 JSON 和 P01 持久幂等服务，返回安全 DepartmentView/ETag/Location。|
|Reason|HTTP 边界不重做权限或首次响应重建；保持默认应用 404 与既有业务状态机。|
|Impact|Project 可选 Router、应用工厂注入点、契约/集成测试；无新 Schema/Migration/依赖或 Breaking API。|
|Rollback|移除 Router 注入恢复 404，已提交的部门、审计和幂等快照保留。|

## DEC-20260925-081

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-081|
|Date|2026-09-25|
|WBS|PRJ-04-A14-P03 Windows 显式平台 Department 创建组合|
|Decision|仅在 `--platform` 与 `--platform-write` 既有 Schema、License 和游标信任源门禁通过后装配部门创建服务及 Router；默认登录模式保持 404。|
|Reason|复用当前 Session、ProjectManager、License、Audit 和同事务幂等，不引入额外无保护入口。|
|Impact|Windows 平台组合与测试；无新 Schema/Migration/依赖或 Breaking API。|
|Rollback|移除平台 Router 注入恢复 404；既有部门、审计与快照保留。|

## DEC-20260925-082

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-082|
|Date|2026-09-25|
|WBS|PRJ-04-A15-P01 Department 修改可选 HTTP|
|Decision|按冻结 API-02 增加可选部门 PATCH Router；复用已验证的内部服务，要求可信 Origin、Session/CSRF 与强 If-Match，响应安全 DepartmentView/ETag；默认应用保持 404。|
|Reason|公开边界无需重写权限、许可、并发或审计规则；与现有 Project/Member 修改入口一致。|
|Impact|新增 Router、应用工厂可选注入点、契约与 PostgreSQL 临时库验证；无 Schema/Migration 或依赖变化。|
|Rollback|移除可选 Router 注入恢复 404，已完成的修改和审计记录保留。|

## DEC-20260925-083

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-083|
|Date|2026-09-25|
|WBS|PRJ-04-A15-P02 Windows 显式平台 Department 修改组合|
|Decision|只在 `--platform` 与 `--platform-write` 既有 Schema、License 和游标信任源门禁通过后装配 Department 修改服务及 Router；默认登录模式保持 404。|
|Reason|复用现有 Session、ProjectManager、License、Audit 和强版本服务，不新增无保护入口。|
|Impact|Windows 平台组合与契约/隔离 PostgreSQL 验证；无 Schema/Migration、依赖或 Breaking API。|
|Rollback|移除平台 Router 注入恢复 404；已完成的修改与审计记录保留。|

## DEC-20260925-084

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-084|
|Date|2026-09-25|
|WBS|PRJ-04-A16-P01 Department 停用持久幂等与快照|
|Decision|按 CR-PRJ-005 复用 `0015` 通用收据，新增 Project-owned 不可变首次 DepartmentView 快照；旧非幂等内部命令保留，新增独立幂等入口。|
|Reason|停用后版本/状态改变，读取当前部门无法重放冻结 API-01 的首次 200 响应。|
|Impact|Migration `20260925_0019`、ORM、Repository、Service、错误码与测试；不开放 HTTP，不改变成员在用规则。|
|Rollback|新表为空可降至 `0018`；已有快照时拒绝降级并保留幂等证据。|

## DEC-20260925-085

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-085|
|Date|2026-09-25|
|WBS|PRJ-04-A16-P02 Department 停用可选 HTTP|
|Decision|只在显式注入时提供冻结 `POST /api/v1/projects/{project_id}/departments/{department_id}:deactivate`；使用可信 Origin、Session/CSRF、强 If-Match、Idempotency-Key 与 P01 持久幂等服务。|
|Reason|HTTP 边界复用已验证的权限、成员在用、许可、并发与快照语义；默认应用保持 404。|
|Impact|Project 可选 Router、应用工厂注入点、契约/隔离 PostgreSQL 验证；无新 Schema/Migration/依赖或 Breaking API。|
|Rollback|移除 Router 注入恢复 404；已停用的部门、审计及快照保留。|

## DEC-20260925-086

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-086|
|Date|2026-09-25|
|WBS|PRJ-04-A16-P03 Windows 显式平台 Department 停用组合|
|Decision|仅在 `--platform` 与 `--platform-write` 既有 Schema、License 和游标信任源门禁通过后装配部门停用服务及 Router；默认登录模式保持 404。|
|Reason|复用当前 Session、ProjectManager、License、Audit、强版本与同事务持久幂等，不新增无保护入口。|
|Impact|Windows 平台组合与契约/隔离 PostgreSQL 验证；无新 Schema/Migration/依赖或 Breaking API。|
|Rollback|移除平台 Router 注入恢复 404；已停用部门、审计与快照保留。|

## DEC-20260925-087

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-087|
|Date|2026-09-25|
|WBS|DOC-03-A01 FileObject 持久层|
|Decision|按 CR-DOC-001 为 FileObject 建独立 M-SCP Root 及追加式状态事件表；Locator 只保存受控相对值，内容字节不入库。|
|Reason|DocumentVersion 和上传恢复必须建立在 Scope/Project、Hash/Size/MIME 与状态历史可约束的元数据上；数据库表不能替代 Storage Adapter。|
|Impact|Migration `20260925_0020`、Document ORM、Alembic 注册、约束与验证；无公开 API、文件写入或新增依赖。|
|Rollback|空表可降至 `0019`；已有 FileObject/事件时拒绝普通降级。|

## DEC-20260925-088

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-088|
|Date|2026-09-25|
|WBS|DOC-03-A02 受控本地 Storage Adapter|
|Decision|Storage Adapter 只接受内部 UUID 生成的 ASCII 小写 Locator，绑定 `global`/`projects/{project_id}` 与隔离 `temp`；拒绝符号链接/Windows 重解析点、大小写别名和既有目标，使用同卷硬链接发布完整暂存文件后移除暂存链接。|
|Reason|既有公开 API/业务模块不能触碰物理路径；独占暂存和无覆盖发布可使完整内容原子可见，同时避免覆盖历史版本。|
|Impact|Document Infrastructure 与合成文件系统测试；不改数据库/API/依赖。未来提交仍需 FileObject 状态事务和恢复器，不以本 Adapter 宣称全链原子。|
|Rollback|不接入组合根即可停用 Adapter；临时文件由后续受控清理流程处理，不自动删除未知文件。|

## DEC-20260925-089

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-089|
|Date|2026-09-25|
|WBS|DOC-03-A03-P01 FileObject 状态流转策略|
|Decision|先将冻结 DM-03 的 FileObject 状态图和可清理边界实现为无 I/O 的内部领域策略；数据库命令、内容完整性证明、引用/保留检查及恢复审计分别在后续子项实现，不提前开放 AVAILABLE 或清理入口。|
|Reason|当前 A01 仅有表约束、A02 仅有存储适配器；直接把文件发布或数据库字段改写当作完整状态命令会绕过跨资源恢复与审计。|
|Impact|Document 内部领域代码/单测；无 Schema、公开 API、依赖或冻结基线变更。|
|Rollback|不接入调用方即可停用；无数据迁移或状态变化。|

## DEC-20260925-090

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-090|
|Date|2026-09-25|
|WBS|DOC-03-A03-P02 FileObject 失败/限制状态事务命令|
|Decision|先实现不需要文件内容或保护引用证明的 `STAGED→FAILED` 与 `AVAILABLE→RESTRICTED` 内部命令，使用当前事务的行锁/expected_version、状态事件、Audit 与通用幂等收据；AVAILABLE 发布和清理状态仍不开放。|
|Reason|A01 元数据与 A03-P01 状态图已具备，但 DocumentVersion/物理 Hash 验证和清理引用检查尚未具备；先落实失败关闭/限制读取所需的安全状态变更，避免单独发布未证明的文件。|
|Impact|Document Application/Infrastructure 与 PostgreSQL 隔离验证；复用既有 `0015`/`0020`，无新 Migration、公开 API 或依赖。|
|Rollback|内部调用未装配至 HTTP；移除服务接线即可停止新命令，既有状态/事件/Audit/收据按历史保留，不逆向改写。|

## DEC-20260925-091

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-091|
|Date|2026-09-25|
|WBS|DOC-01-A01 Document 逻辑身份持久层|
|Decision|依据 CR-DOC-002 先建 Document Root；latest/effective 指针在 DOC-02 建表前均为 NULL，不能用自由 UUID 代替版本外键。|
|Reason|冻结 DM-03 要求 Document/FileObject/DocumentVersion 分离；当前 DOC-02 尚缺，必须防止悬空或跨 Scope 的版本引用。|
|Impact|后续 Migration `0021`、ORM、约束和验证；本登记本身不改变运行 Schema/API。|
|Rollback|本登记无需数据回滚；后续 Migration 仅在空表时允许普通降级。|

## DEC-20260925-092

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-092|
|Date|2026-09-25|
|WBS|DOC-02-A01 DocumentVersion 持久层|
|Decision|依据 CR-DOC-003 在 `0022` 建独立版本与来源引用表，使用 FK/触发器守护同 Scope、文件状态/摘要、前驱、指针和不可变字段；文件字节、发布命令与恢复流程保持在后续任务。|
|Reason|既有 `0021` Document 指针被安全地锁为 NULL，只有版本 Root 和数据库约束完备后才能解除初态限制，不允许自由引用。|
|Impact|Document ORM/Migration/临时 PostgreSQL 验证；无公开 API/新依赖，不修改原冻结提交。|
|Rollback|空版本且指针 NULL 可降至 `0021`，有版本时拒绝普通降级并保留历史。|

## DEC-20260925-093

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-093|
|Date|2026-09-25|
|WBS|DOC-03-A03-P03 FileObject 内容证明与受控 AVAILABLE 发布|
|Decision|只在内部已受权 STAGED FileObject 上，按 DB 记录的 UUID Locator/Hash/Size/MIME 校验暂存字节，限额流式 SHA-256 后同卷无覆盖提升，再校验正式文件；随后独立数据库事务行锁重检 STAGED 与版本并原子写 AVAILABLE/状态事件/Audit/幂等收据。|
|Reason|文件系统与 PostgreSQL 不共享事务；先物理发布后提交数据库可让失败保持业务不可见，残余由恢复器按冻结矩阵处理，不能以调用方传入的布尔值当作文件证明。|
|Impact|Document 内部 Storage/Application/Repository 与合成文件及隔离 PostgreSQL 验证；无 Migration/公开 API/新依赖。MIME/特征的上传校验、正式 Document 权限装配和崩溃恢复仍为后续任务。|
|Rollback|服务不挂公开组合根即可停止新发布；已经提升但未提交的文件不盲删，按恢复矩阵核验/隔离清理；已 AVAILABLE 的历史不得回写。|

## DEC-20260925-094

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-094|
|Date|2026-09-25|
|WBS|DOC-03-A03-P04-P01 发布后数据库未提交的受控恢复|
|Decision|先实现只针对明确 FileObject 的内部恢复：授权与版本核查后，要求 STAGED 元数据、暂存路径不存在、最终路径存在且独占，按数据库摘要/大小有界重校验，再复用行锁、状态事件/Audit/幂等收据同事务完成 AVAILABLE。暂存和最终路径同时存在、缺失、异常或 Hash 不符均失败关闭，保持业务不可见，不自动删除/改写。|
|Reason|冻结 DM-03 恢复矩阵允许最终文件存在且 DB=STAGED 时校验后继续提交；同时存在的硬链接窗口及缺失/损坏需单独隔离策略，不能把未知文件当作完成证明。|
|Impact|仅 Document 内部 Storage/Application 与合成文件、隔离 PostgreSQL 验证；不新增 Migration、公开 API 或依赖。P04-P02 再处理双路径窗口和隔离分类，P04 整体不因 P01 完成而关闭。|
|Rollback|停止内部恢复装配；已成功提交的 AVAILABLE 与历史不可回写，失败仍 STAGED 且无物理删除。|

## DEC-20260925-095

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-095|
|Date|2026-09-25|
|WBS|DOC-03-A03-P04-P02 双路径硬链接中断窗口恢复|
|Decision|只允许暂存与最终路径均为同一普通文件的恰好两条硬链接、Scope 派生路径匹配、两侧有界流式 Hash/Size 校验一致时，删除暂存目录项、重新校验独占最终文件，再沿独立恢复幂等作用域与 DB 行锁/Audit/事件同事务提交 AVAILABLE。其他双路径情况失败关闭且不删除、不提升状态。|
|Reason|当前 Storage Adapter 的无覆盖提升用硬链接后删除暂存入口；崩溃可能恰好落在两步之间。该明确窗口可恢复，但不能将两个不同文件或额外硬链接当作同一可信内容。|
|Impact|仅内部 Document Storage/Application 和合成 Windows 文件/隔离 PostgreSQL 验证，无 Migration/公开 API/新依赖；异常隔离分类留 P04-P03。|
|Rollback|停止该内部命令装配；若暂存入口已删而 DB 提交失败，保持 STAGED/最终文件独占，可由 P04-P01 重试，不回写已提交历史。|

## DEC-20260925-096

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-096|
|Date|2026-09-25|
|WBS|DOC-03-A03-P04-P03 缺失/异常文件隔离分类与审计|
|Decision|新增仅内部显式指定 FileObject 的隔离命令，并要求注入的停写/无活动发布证明 Port 在前后事务均通过。对无文件、仅暂存、最终文件摘要不符或两条互不相同的普通文件，前后两次检查形态一致后以行锁原子写 STAGED→FAILED、分类失败码、状态事件/Audit/幂等收据；不删除任何文件。已验证最终文件、可恢复的同一硬链接对、重解析点/不安全路径等不自动判失败，保持 STAGED 交受控恢复或人工处理。|
|Reason|冻结恢复矩阵要求半完成版本不可见且恢复动作可审计；但 STAGED 可能属于仍在运行的发布，单凭年龄或文件快照不允许自动置 FAILED。当前生产停写证明未接线，内部能力不得作为自动扫描器对外装配。|
|Impact|Document Storage/Application/Repository 和合成文件/隔离 PostgreSQL 验证；无 Migration、公开 API 或新依赖。正式 Quiescence Port、TTL 清理、AVAILABLE/DocumentVersion/Parse Job 的其他恢复矩阵行后续实施。|
|Rollback|停止内部装配；FAILED 历史保留，不倒写为 AVAILABLE，重新上传产生新 FileObject；物理文件未删，可人工核查。|

## DEC-20260925-097

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-097|
|Date|2026-09-25|
|WBS|DOC-03-A03-P04-P04 生产停写证明前置核查|
|Decision|现有应用无正式维护模式、上传并发栅栏或活动发布证明；不以年龄/人工布尔值替代，不装配 P04-P03 隔离命令。将正式 Quiescence Port 与目标账户演练放入运行时维护/上传任务，先推进无此依赖的 DOC-02 内部版本提交。|
|Reason|STAGED 也可能属于活跃发布；错误置 FAILED 会使合法上传无法完成，违反冻结恢复矩阵与失败关闭要求。|
|Impact|仅记录前置与时序，不改变 Schema/API；DOC-03-A03-P04 整体未 PASS，Gate 3/Release 不因此放行。|
|Rollback|本记录无运行时回滚；后续正式实现需另行验证再装配。|

## DEC-20260925-098

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-098|
|Date|2026-09-25|
|WBS|DOC-02-A02-P01 上传来源的内部 DocumentVersion 提交|
|Decision|先仅实现已发布、持久 FileObject 的上传来源版本提交：服务端按 UUID 派生最终 Locator 和 DB Hash/Size 重校验字节；授权后在短事务行锁 Document/FileObject，检查 ACTIVE Project、预期 Document lock_version、文件同 Scope/Project 和未被引用，按 latest 生成连续版本号/前驱，写不可变 Version、UPLOAD 来源引用、latest 指针、Audit 与幂等收据。effective 指针保持原值，不自动视为正式业务有效版本。|
|Reason|冻结 DM-03 区分 latest 与 effective，真实上传/生成/迁移的来源语义不同；先把已具备的发布文件接成可追溯上传版本，避免在 Parser/Review 尚未就绪时自动生效或伪造其他来源。|
|Impact|Document 内部 Application/Repository 与合成 PostgreSQL/文件验证；无 Migration、公开 API 或新依赖。其他来源、Parser Job/Outbox、上传 HTTP、正式授权/文件 ACL 和恢复协调另列子任务；DOC-02-A02 整体不因 P01 关闭。|
|Rollback|不装配内部提交入口可停止新提交；已提交版本和来源不可删除/倒写，失败事务回滚 Version/指针/Audit/收据，孤立已发布 FileObject 留给恢复矩阵处理。|

## DEC-20260925-099

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-099|
|Date|2026-09-25|
|WBS|DOC-02-A02-P02 非上传来源引用前置核查|
|Decision|生成/转换/迁移来源的正式 Owner 与授权 Port 未建立，不把自由 UUID 写成已验证来源；该子任务停在前置，独立推进 API-02 必需的上传链。|
|Reason|不可变来源引用一旦写入即难以纠正，伪造可追溯性会污染正式业务事实。|
|Impact|仅任务顺序调整与文档记录；DOC-02-A02 整体未 PASS。|
|Rollback|无运行时变更；Owner 可验证后恢复各来源子任务。|

## DEC-20260925-100

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-100|
|Date|2026-09-25|
|WBS|DOC-03-A04-A01 UploadIntent 持久层前置|
|Decision|按 CR-DOC-004 增加独立 UploadIntent 控制 Root，不混入 FileObject 或 Document；先完成 Schema/ORM 与迁移验证，再独立实现 Create/Content/Commit/Abort。|
|Reason|冻结 API-02 要求三步上传及崩溃重试，当前 Schema 没有短时意图、Token 摘要/过期和命令状态的可持久载体。|
|Impact|后续 Migration `0023`、Document ORM、临时库验证；当前记录本身无运行 Schema/API 变化。|
|Rollback|空表可降级，非空意图保留并拒绝普通降级，不能清除已创建的版本或文件历史。|

## DEC-20260925-101

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-101|
|Date|2026-09-25|
|WBS|DOC-03-A04-A02 受权 UploadIntent 创建与短时 Token|
|Decision|仅在内部创建入口实现同事务授权、持久幂等、审计和短时 Token；以稳定的独立 256-bit 密钥对 upload_id、actor_id、scope/project 作域分离 HMAC，数据库只保存 Token 的 SHA-256 摘要，重放由相同输入重新派生并比对摘要。过期时间和状态以数据库为准，过期/终止后不再返回 Token。服务不得自行生成或持久化生产密钥，未提供受控密钥来源时不装配。|
|Reason|随机 Token 不可在不保存明文的条件下恢复首次幂等响应；确定性派生既可重放，也保持数据库泄露时 Token 不可直接使用。|
|Impact|Document Application/Repository、Token 适配与测试；不改冻结 API、Schema 或现有生产组合。密钥必须在所有未过期 Intent 生命周期内稳定，轮换/失密时失败关闭；目标账户安全供给及 Content/Commit/Abort 另列任务。|
|Rollback|撤去未装配的内部创建入口即停止创建；已有 Intent 按 TTL 过期，不删除历史。事务失败回滚 Intent/Audit/收据；密钥丢失不能恢复 Token，须让旧 Intent 过期后重新创建。|

## DEC-20260925-102

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-102|
|Date|2026-09-25|
|WBS|DOC-03-A04-A03-P01 Content 文件名契约前置|
|Decision|按 CR-DOC-005 修正 UploadIntent：既有 Document 升版也由创建请求提供 `original_display_name`，只作本次上传文件名，不改 Document 身份；旧缺名意图不自动回填、不可进入 Content。|
|Reason|冻结 API-02 要求升版也声明 display name，现有 `0023` 约束错误禁止，无法验证扩展名或形成可信 FileObject 名称。|
|Impact|Document ORM/增量 Migration、创建命令验证、合成验证与版本记录；无公开 API Breaking Change。|
|Rollback|降级仅在不存在新形态记录时允许，绝不删除有历史记录；旧缺名记录保持可追溯并按期限终止。|

## DEC-20260925-103

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-103|
|Date|2026-09-25|
|WBS|DOC-03-A04-A03-P02 有界流式 Content 校验与受控暂存|
|Decision|先在 Document Storage Adapter 构建与授权无关的单次暂存证明：调用方显式传入已受权的内部 FileObject ID/Scope 和格式允许清单，独占创建受控 Locator；对流式 Chunk 做长度/上限/SHA-256 校验，并以文件特征和容器结构复核类型。失败仅在文件身份仍为本次创建的普通单链接文件时删除暂存；成功返回不含绝对路径的内容证明。数据库 Intent/STAGED 登记、Token/Session 检查、重传/崩溃清理留独立 P03。|
|Reason|冻结上传次序要求先受控临时区校验，再建立 FileObject/STAGED；单纯信任扩展名、客户端 MIME 或一次性读入内存均不满足大小与类型底线。|
|Impact|仅 Document 基础设施与本地合成测试；不改 Schema、公开 API、技术栈或生产组合。允许格式仍由后续用途/部署配置注入，未列明或未实现的格式失败关闭。|
|Rollback|不装配暂存器即可停止新写入；已生成未登记的临时内容由后续 TTL 恢复/清理机制处理，不自动删除未知历史或业务版本。|

## DEC-20260925-104

|字段|内容|
|---|---|
|Decision ID|DEC-20260925-104|
|Date|2026-09-25|
|WBS|DOC-03-A04-A03-P03-A01 内部 Content STAGED 登记|
|Decision|采用两次短事务：流前受权并查 Intent/Token/数据库时间，事务外有界流式暂存；流后重新受权并按 Project→Document→Intent 行锁复核，随后同事务写 FileObject(STAGED)、初始状态事件、Intent(CONTENT_READY) 与 Audit。FileObject ID 固定使用本次 upload_id，避免重复请求在不同随机暂存路径产生多个候选。数据库结果不确定时不自动删暂存文件，交由后续受控恢复/TTL 清理；重复 PUT 先失败关闭，独立 P04 完成安全重传。|
|Reason|长流不能持有数据库事务；单次前置检查无法防上传中归档、过期、权限变化或终止。确定性暂存身份加后置行锁使重复写入不会覆盖原字节。|
|Impact|Document 内部 Service/Repository、合成 PostgreSQL/文件测试；无 Schema/API/依赖变更。正式 Session/License/CSRF 授权适配、重传恢复与公开 HTTP 尚未完成。|
|Rollback|入口未装配，可停止新写入；失败事务回滚 STAGED/Event/Intent/Audit。事务外孤儿文件不可作为业务版本读取，后续按固定 ID/TTL 受控清理；不删除有记录或未知状态文件。|

## DEC-20260926-105

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-105|
|Date|2026-09-26|
|WBS|DOC-03-A04-A03-P03-A02-P01 已登记 Content 安全重传|
|Decision|仅在 UploadIntent 为 CONTENT_READY 且 FileObject 仍为同 Scope/Project 的 STAGED、确定性暂存 Locator、元数据与声明一致时允许重传。重传必须完整读取并校验请求正文，再校验暂存文件 Hash/Size，最后在短事务重新授权、锁定并复核两条记录；不新增文件、状态事件或 Audit。未登记孤儿恢复与 TTL 清理拆为 P02/P03，必须先具备活跃写入的停写/租约证明。|
|Reason|仅按声明 Header 返回 200 会接受不同正文；仅凭孤儿文件现存无法区分崩溃完整文件与仍在写入的文件。|
|Impact|Document 内部 Service/Repository 和合成验证；不变更冻结 API、Schema、权限模型或依赖。|
|Rollback|入口未公开；停止装配即可禁止重传。已有 STAGED 数据保持不变，故障继续失败关闭。|

## DEC-20260926-106

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-106|
|Date|2026-09-26|
|WBS|DOC-03-A04-A03-P03-A02-P02 未登记 Content 孤儿恢复|
|Decision|暂存写入从创建起持有 OS 排他文件锁，完成类型/Hash 与 fsync 后关闭；重传若发现未登记同 ID 文件，必须在非阻塞取得同一锁后才可验证其文件身份、Hash、长度和类型，并在持锁期间重新授权、按既有锁顺序登记 FileObject/Intent/Event/Audit。请求正文也须独立完整校验。锁不可得/格式不符/状态改变均失败关闭；不覆盖或删除未知文件。|
|Reason|只看文件存在、大小或 mtime 不能排除活跃写入；进程崩溃时 OS 文件锁自动释放，能区分仍在写入与可检查的孤儿。仍通过数据库行锁处理双请求并发。|
|Impact|Document Storage/Spool/Service 与合成验证；无 Schema、公开 API、技术栈或依赖变更。Windows 11 与目标 OS 的锁行为需分别实测，未验证平台不宣称 PASS。|
|Rollback|未公开的内部入口可停止装配；原有暂存/数据库记录保留，未知文件由后续受控 TTL 策略处理，不执行自动删除。|

## DEC-20260926-107

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-107|
|Date|2026-09-26|
|WBS|DOC-03-A04-A03-P03-A02-P03-P01 单候选 TTL 清理|
|Decision|按冻结 R7-TEMP 的七天保留阈值，仅对受控 Locator 的普通单链接暂存文件执行逐个候选清理。先获同上传写锁并核对文件年龄/身份，再在事务中检查维护授权、UploadIntent 已失效且无文件关联及 FileObject 不存在，持久追加清理请求 Audit；随后复核原文件身份与年龄并删除，再写完成 Audit。Windows 不能在持锁句柄打开时 unlink，因此放锁后只对私有根内重新核对的同一 inode 执行删除，未知/变化对象失败关闭。目录扫描与调度独立实施。|
|Reason|删除文件与提交数据库审计无法原子化；先持久记录请求可避免删除成功而完全无审计。七天阈值来自冻结数据保留矩阵，不按失败暂存的 24 小时规则误删未登记内容。|
|Impact|Document 内部 Storage/Application/Repository、合成文件/隔离数据库验证；不改 Schema、公开 API 或依赖。|
|Rollback|内部入口未装配时不执行清理；已产生的不可变 Audit 保留。清理后的临时正文不可恢复，只允许在无 FileObject/业务引用且满七天时执行；恢复仍依赖备份，不允许操作正式文件。|

## DEC-20260926-108

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-108|
|Date|2026-09-26|
|WBS|DOC-03-A04-A03-P03-A02-P03-P02 受控扫描与中断对账|
|Decision|扫描仅遍历 temp/global/objects 和 temp/projects/{UUID}/objects 的固定层级，限制检查条目数，只返回规范 UUID Locator；未知、符号链接、重解析点及结构异常计数但不跟随/删除。批处理逐候选复用 P01 的授权/DB/文件身份检查，缺 Intent 或已有 FileObject 的候选保持不动。对已持久记录清理请求而物理文件缺失、没有完成 Audit 的对象，重新检查 DB/授权后只写 `DOCUMENT_ORPHAN_CLEANUP_ABSENT` 观察事件，不伪称由本进程完成删除。|
|Reason|文件目录遍历不能直接成为删除授权；PostgreSQL 与本地文件系统非原子，中断窗口只可陈述已观察到的状态。|
|Impact|Document Storage/维护 Service/Repository 与隔离文件/数据库测试；无 Schema、公开 API、新依赖。生产定时调度和目标账户路径权限仍属部署接线。|
|Rollback|维护入口未装配时不执行；已写的 Audit 保留，未知文件原样保留。不以扫描结果自动删除客户文件。|

## DEC-20260926-109

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-109|
|Date|2026-09-26|
|WBS|DOC-03-A04-A03-P04-P01 上传身份与角色授权适配|
|Decision|以请求级适配器连接已有 Auth Session/CSRF、DeploymentAdmin 与 Project 当前成员事实，项目上传创建只允许 ProjectManager/ImplementationMember/CustomerManager，Content 额外核验 UploadIntent 创建者。上传前和流结束后的事务均重新检查，不持有跨流数据库锁；License Guard 与 HTTP 由 P02 单独装配。|
|Reason|冻结 API-02 区分创建与 Content 权限；既有内部上传命令仅有合成授权 Port，不能把它直接公开。跨流 Session/成员状态可能变化，必须重新检查。|
|Impact|Document Application 授权适配与 UploadIntent 创建者只读查询；无冻结 Schema/API 变更。|
|Rollback|未接公开路由，移除该适配器即可恢复此前内部状态；无数据迁移。P02 装配前不得把本项称为生产授权通过。|

## DEC-20260926-110

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-110|
|Date|2026-09-26|
|WBS|DOC-03-A04-A03-P04-P02-A01 可选 UploadIntent 创建 HTTP|
|Decision|冻结 API-02 的可选 supersedes_version_id 仅作为创建意图时对既有 Document 最新版本的乐观前置条件；提供时纳入幂等请求指纹，未提供时保留旧指纹以兼容已发收据；创建和重放时都核对，不写入 UploadIntent，因为正式提交仍必须独立携带父 Document If-Match。HTTP 先以显式注入方式提供 GLOBAL/PROJECT 固定路径，默认与生产组合继续关闭；License Guard 和请求级 Session/CSRF 缺一不可。|
|Reason|不忽略已声明的父版本，也不把创建阶段的预检误当作提交阶段并发保护；复用既有 Document 最新指针，无需新增 Schema。|
|Impact|Document 创建命令/Repository/可选 API 与契约测试；无冻结 API/Schema 破坏、新依赖或生产密钥供给。|
|Rollback|不注入 Router 即恢复 404；内部可选预检字段不改变既有 Intent。已创建测试记录仅留合成库。正式平台装配和 Content/Commit 留后续验证。|

## DEC-20260926-111

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-111|
|Date|2026-09-26|
|WBS|DOC-03-A04-A03-P04-P02-A02 上传 Token 独立 Windows 密钥来源|
|Decision|为 Document Upload Token 使用独立 `document-upload-token-v1` 当前账户 Windows Credential Manager 引用，启动时仅只读校验 32 字节密钥；运行时重新解析，缺失则失败关闭。供给和离线加密备份沿用既有交互式 Secret Key Lifecycle，不生成或提交真实密钥。|
|Reason|Upload Token 必须跨进程重放稳定，不能复用 License、可信时间、Secret 主密钥或列表游标签名密钥；无备份的临时 Key 会使未过期意图失效。|
|Impact|Document Windows 入口适配与独立合成密钥备份恢复测试；无 Schema/API/技术栈变化。|
|Rollback|不装配上传 Router 即停止签发；撤下专用引用后旧 Token 失败关闭，可由独立备份恢复。正式发行时须由目标账户和操作员完成供给仪式。|

## DEC-20260926-112

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-112|
|Date|2026-09-26|
|WBS|DOC-03-A04-A03-P04-P02-A03 Windows 显式上传创建组合|
|Decision|仅在现有 Windows `--platform-write` 模式装入 UploadIntent 创建 Router；启动时要求独立上传 Token Key 与既有 License/Secret/游标信任源全部就绪，任一缺失回滚整个应用构造。每次请求新建 DocumentUploadAccess，使用 Auth 所有的 Session/CSRF、DeploymentAdmin 和 Project 当前成员事实，复用 PostgreSQL 收据与 Audit；登录/只读模式不开放。|
|Reason|冻结 API-02 要求上传创建的 Session、License、CSRF、幂等和审计，用户不可通过已认证的其他写路由绕过上传专用密钥前置。|
|Impact|Windows 组合根与生产模式契约；无 Schema/Breaking API/新依赖。|
|Rollback|撤下该显式 Router，上传路径恢复 404；已持久化意图按过期/终止流程处理，不删除其他数据。正式目标账户材料和 Content/Commit 仍须另行验证。|

## DEC-20260926-113

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-113|
|Date|2026-09-26|
|WBS|DOC-03-A04-A03-P04-P03 流式 Content HTTP|
|Decision|Content PUT 仅在显式 Windows 写模式挂载；要求固定 Scope 路径、可信 Origin、Session/CSRF、专用 Upload Token、严格 Content-Length 与 SHA-256 声明。HTTP 异步请求流通过 AnyIO 线程桥逐段供给现有同步 Content Service，单段最多 1 MiB，不在 HTTP 层整体缓存正文。服务在流前/流后分别校验 License Guard 与当前 Session/项目角色/创建者。|
|Reason|内部 Content 已具备暂存、类型/Hash/长度和数据库原子登记，但直接读取整份 HTTP 正文将突破有界内存目标；只在流前检查许可会让长传输后的状态变化失效。|
|Impact|Document 可选 API、Content Service 授权时序、Windows 组合与测试；无 Schema/冻结 API 破坏。|
|Rollback|撤下 Content Router，已创建意图自然过期；孤儿暂存依已有受控恢复/TTL 清理流程，不执行任意文件删除。|
## DEC-20260926-114

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-114|
|Date|2026-09-26|
|WBS|DOC-03-A04-A04-P02 Job Lease/fencing 事务命令|
|Decision|Job Owner 使用数据库 `statement_timestamp()`、单行 `FOR UPDATE SKIP LOCKED` 与短事务领取；每次领取增加单调 fencing token，同时追加 Attempt/Lease，过期租约在同一事务标记 EXPIRED；心跳与终态提交必须再次核对 Job 状态、token、worker、活动 Lease 和数据库过期时间。完成和重试只改变内部 Job/Lease/Attempt，不在 Worker 事务中执行外部解析。|
|Reason|ADR-007 的至少一次与崩溃回收必须阻止旧 Worker 在租约失效后覆盖新结果，单靠内存锁或任务状态不足。|
|Impact|仅 jobs 内部 Application/Repository 与合成测试；不增加 API、迁移、依赖或外部副作用。|
|Rollback|停用 Worker 调度并回退内部命令；已产生的 Job/Attempt/Lease 历史保留，不能删除重建 fencing token。|
## DEC-20260926-115

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-115|
|Date|2026-09-26|
|WBS|DOC-03-A04-A04-P03 Outbox 投递/消费去重|
|Decision|Outbox Owner 使用 `FOR UPDATE SKIP LOCKED` 与数据库时间在短事务领取到期事件；过期 `DELIVERING` 以单调 token 接管。确认投递要求当前 owner/token/未过期，并将目标数据库消费回调、`(event_id, consumer_id)` 去重记录和 DELIVERED 状态放在同一事务；回调不能在事务内进行外部 I/O。失败按有界次数进入 RETRY_WAIT 或 DEAD。|
|Reason|现有状态字段不能防止崩溃后旧投递者确认；至少一次语义要求目标消费和确认有明确事务边界与幂等键。|
|Impact|`CR-DOC-007` 的 ORM/迁移增量、jobs 内部 Application/Repository 和隔离 PostgreSQL 测试；无公开 API 或新依赖。|
|Rollback|停用 Outbox 调度，保留事件与 token 历史；若已有新语义历史，迁移降级失败关闭，不自动抹除。|
## DEC-20260926-116

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-116|
|Date|2026-09-26|
|WBS|DOC-03-A04-A04-P04 上传 Commit/Abort 编排|
|Decision|Document Commit 不调用现有会独立提交数据库事务的 FilePublishService；复用其受控 Storage 物理提升与事务内 FilePublishRepository、DocumentVersionRepository，并通过 Job Owner 的公开 Application Port 在同一调用方事务登记 DOCUMENT_PARSE Job 和最小引用 Outbox。先完成 Job Owner 的受限解析入队 Port，再接 Document 事务编排；接口不自行 commit。|
|Reason|冻结 DM-03 要求 FileObject AVAILABLE、DocumentVersion、Parse Job/Outbox、Audit 作为单一数据库提交。跨模块直接访问 jobs 内部表或复用独立事务 FilePublishService 均破坏该不变量。|
|Impact|jobs Application Port/Repository 与 Document Commit 实现、合成 PostgreSQL 回归；不改公开 API、数据模型或迁移。|
|Rollback|移除尚未挂载的 Commit 编排；已提交 Job/Outbox 不删除，需按受控取消/Dead 路径处理。原 FilePublishService 保留供独立恢复命令使用。|

## DEC-20260926-117

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-117|
|Date|2026-09-26|
|WBS|DOC-03-A04-A04-P04-P03-P01 上传 Abort 状态编排|
|Decision|Abort 仅在一个数据库事务内把 CREATED/CONTENT_READY 意图置为 ABORTED；有已登记暂存文件时按冻结状态图记录 STAGED→FAILED→CLEANUP_PENDING 两次状态事件，并同事务保存 Audit 与幂等收据。物理删除留给后续精确身份校验的清理命令，Abort 不在数据库事务内删除文件。|
|Reason|冻结 API 返回 cleanup-pending；文件系统与 PostgreSQL 不能原子提交，先删除再回滚会丢失已登记正文；Commit 可能在外部文件提升与数据库提交之间竞争，必须通过状态锁与后续恢复核查避免误删。|
|Impact|Document 内部 Application/Repository 与测试；无新 Schema、迁移、依赖或公开 API。CREATED 无文件时返回 cleanup_pending=false，CONTENT_READY 有文件时为 true。|
|Rollback|撤下未挂载的内部 Abort 入口；已标记 CLEANUP_PENDING 的记录保持可追溯，不恢复成可提交状态，也不自动删除物理文件。|

## DEC-20260926-118

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-118|
|Date|2026-09-26|
|WBS|DOC-03-A04-A04-P04-P04-A01 可选 Commit/Abort HTTP 契约|
|Decision|在现有 FastAPI 组合根增加默认不挂载的上传终结 Router。Commit/Abort 共用可信 Origin、当前 Session/CSRF、空请求体与 Idempotency-Key 边界；Commit 可选读取强 If-Match，新建无父版本，升版由内部服务要求父版本；服务复核创建者和 License。Abort 只返回数据库终止与 cleanup_pending，不在 HTTP 请求内做物理清理。|
|Reason|冻结 API-02 已规定两个操作及控制项；当前物理清理缺可信停写栅栏，不能把 HTTP 返回待清理解释为实际删除。可选挂载允许先验证合同且保持默认生产入口关闭。|
|Impact|仅 Document API 与通用应用可选 Router 参数、契约测试；不改 Schema、冻结路径、依赖或默认路由。|
|Rollback|不向应用注入该 Router，两个接口恢复默认 404；已通过内部 Commit/Abort 写入的历史仍保留。|

## DEC-20260926-119

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-119|
|Date|2026-09-26|
|WBS|DOC-03-A04-A04-P04-P04-A02 Windows 显式写模式上传终结组合|
|Decision|仅在既有 Windows `--platform-write` 组合中装配 Commit/Abort 可选 Router，使用同一请求级 DocumentUploadAccess、正式 PostgreSQL 收据/Audit、File Storage 与 Job Owner Parse 入队 Port；登录/只读模式保持 404，缺任何既有信任源则整个显式写模式失败关闭。Abort 不调用物理清理。|
|Reason|已有 Create/Content 在该显式模式验证，冻结 API-02 要求相同 Session/License/CSRF/Project Role/创建者边界；单独挂载无保护终结路由会绕过现有组合根。|
|Impact|Windows 组合根和隔离 PostgreSQL/临时文件验收；无 Schema、冻结 API、依赖或默认应用行为变化。|
|Rollback|撤下 Commit/Abort Router 注入，两个路径恢复 404；已提交 DocumentVersion/Job 与已终止 Intent 历史保留，不能回滚业务事实。|

## DEC-20260926-120

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-120|
|Date|2026-09-26|
|WBS|DOC-01-A02 内部受权 Document 元数据读取|
|Decision|Document 只查询本模块 DocumentRow；Auth Session、DeploymentAdmin 与 Project 当前成员/状态分别通过 Owner Port 在同一事务核验。内部按 document_id 稳定 keyset 读取 ACTIVE/ARCHIVED，RESTRICTED 默认不可见；GLOBAL 当前只放行 DeploymentAdmin，项目成员的正式引用/类别授权待引用模型具备后单独实施，不以类别或 ID 猜测放行。|
|Reason|冻结 API-02 要求 ProjectId 隔离与 GLOBAL 引用/类别联合策略；目前未有可核验的 GLOBAL→PROJECT 正式引用事实，直接放行标准类别会造成过度读取。Document 读层先建立可复用的 Owner 边界和分页事实。|
|Impact|Document 内部 Application/Repository、Port 组合与测试；不改 Schema、公开 API、依赖或冻结权限规则。后续 HTTP cursor 必须独立签名并绑定 Scope/Project/Session。|
|Rollback|不装配尚未公开的内部读 Service；Document 表和既有上传历史不变。|

## DEC-20260926-121

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-121|
|Date|2026-09-26|
|WBS|DOC-01-A03-P01 独立签名 Document 列表游标|
|Decision|Document 列表使用专用 `document-list-cursor-v1` Windows 当前账户密钥引用和 HMAC-SHA-256 完整性游标，绑定会话摘要、GLOBAL/PROJECT、ProjectId、page_size 与最后 document_id；不复用成员、部门、Secret 或上传令牌密钥。游标只承载键集位置，不承载未授权标题/路径。|
|Reason|冻结 API-01/02 要求不透明 keyset 分页；直接暴露 UUID 位置或跨会话/项目复用游标会扩大枚举面。现有目标账户安全密钥供给可复用生命周期而不新增技术栈。|
|Impact|Document API cursor codec、Windows 只读密钥适配与测试；无 Schema、冻结 API 路径或第三方依赖变化。正式目标账户密钥需独立供给/备份后才能挂载 Document 列表。|
|Rollback|不注入 Document 读 Router；旧游标失密时失败关闭，可用独立备份恢复，不用其他用途密钥替代。|

## DEC-20260926-122

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-122|
|Date|2026-09-26|
|WBS|DOC-01-A03-P02 可选 Document 元数据 GET|
|Decision|按冻结 API-02 展开 PROJECT/GLOBAL 明确路径，将已验证的内部受权 Document 读取与独立签名游标组合为可选只读 Router。项目和 GLOBAL 路径不共用用户可控 Scope；默认应用不装配。投影仅含业务元数据、版本引用、时间和 ETag，不返回存储 Locator、正文或文件系统路径。|
|Reason|先以可选边界验证 HTTP 契约与真实数据库读层；正式 Windows 组合仍需独立 Document 游标密钥和目标账户安全来源，不能因内部验证通过而提前开放。|
|Impact|Document API、应用可选路由入口、合同测试及版本/状态记录；无 Schema、冻结路径/权限变更或新依赖。GLOBAL 当前仅管理员，正式跨域引用授权另行设计验证。|
|Rollback|不向应用注入 `document_read_router` 即保持 404；已有 Document 数据及上传流程不受影响。|

## DEC-20260926-123

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-123|
|Date|2026-09-26|
|WBS|DOC-01-A03-P04 Windows 显式平台只读组合|
|Decision|在现有 `--platform` 与 `--platform-write` 显式模式接入 Document 读 Service/Router；普通登录模式继续不装配。两个显式模式均要求独立 `document-list-cursor-v1` 当前账户密钥，任何读取/验证失败使整个模式启动失败并释放数据库资源。|
|Reason|Document 页游标必须具备独立信任锚；仅 HTTP/数据库合成测试不足以授权在目标账户缺钥时降级运行。复用既有 License、Session、Project Owner Port，不增加第二权限体系。|
|Impact|Windows 组合入口、启动失败关闭与模式分离测试；无 Schema、冻结 API 或新依赖变化。正式账户密钥与发行公钥仍未供给，不能声明生产可用。|
|Rollback|撤下 Document Router 注入并保留独立游标入口；普通登录模式和现有 Document/上传数据不受影响。|

## DEC-20260926-124

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-124|
|Date|2026-09-26|
|WBS|DOC-01-A04-P01 内部 DocumentVersion 元数据读取|
|Decision|复用 DocumentReadService 的当前 Session/Scope/Project/License 授权与父 Document 可见性，在同一只读事务内读取不可变版本；按 version_no 降序做有界 keyset。普通版本读取仅投影 AVAILABLE 且引用 PERSISTENT/AVAILABLE、同 Scope/Project 且 Hash/Size/MIME 与版本快照一致的 FileObject；RESTRICTED/REVOKED 与异常文件状态不向普通读者暴露。只投影冻结 API-02 的版本元数据，不返回 file_object_id、storage_locator 或 source_metadata。|
|Reason|冻结 DM-03 要求 DocumentVersion→FileObject 的一致性与版本不可变，API-02 要求受权列表/详情和无文件路径投影。降序版本号让最新版本优先且已发布版本的编号稳定。|
|Impact|Document 内部 Application/Repository 与测试；不改变数据库、公开 API、冻结授权粒度或依赖。后续 HTTP 分页游标需独立完整性保护并绑定 Document/Scope/Session。|
|Rollback|不暴露版本读接口；保留原有文档元数据读取与数据库历史。|

## DEC-20260926-125

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-125|
|Date|2026-09-26|
|WBS|DOC-01-A04-P02 独立签名 DocumentVersion 列表游标|
|Decision|版本列表使用独立 `document-version-cursor-v1` Windows 当前账户密钥与 HMAC-SHA-256 游标，绑定当前 Session 摘要、Scope、ProjectId、父 DocumentId、page_size 和降序 `before_version_no`；不复用 Document 列表、成员、Secret 或上传令牌密钥。|
|Reason|版本号虽非机密，但明文或跨父文档复用分页位置会扩大枚举与状态推断面；冻结 API-01 分页采用不透明游标，现有 Windows 安全密钥供给/恢复模式可直接沿用。|
|Impact|Version cursor codec、Windows 只读密钥入口与单元测试；无 Schema、公开 API、依赖变化。正式目标账户密钥供给前不挂载版本列表。|
|Rollback|不注入版本列表 Router；失密时拒绝解码，可从该独立密钥备份恢复旧游标，不以其他用途密钥替代。|

## DEC-20260926-126

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-126|
|Date|2026-09-26|
|WBS|DOC-01-A04-P03 可选 DocumentVersion 元数据 HTTP GET|
|Decision|版本列表/详情以独立可选 Router 实现 PROJECT/GLOBAL 四条固定 GET 路径，复用 DocumentReadService 和专用版本游标；默认应用不装配。Page 返回 items/next_cursor/has_more，详情只返回冻结 VersionView 元数据，不含 FileObject ID、Locator、正文或 source_metadata。|
|Reason|冻结 API-02 已要求版本列表/详情；独立 Router 可在正式目标账户版本游标密钥缺失时与其他 Document 路由分离并失败关闭，避免默默共用旧游标。|
|Impact|Document API 与可选应用入口、合同测试；无 Schema、依赖、Breaking API 或权限粒度变化。Windows 显式组合留到同链路验证后单独实施。|
|Rollback|不向应用注入版本 Router 即保持 404；已有 Document 读与上传数据不变。|

## DEC-20260926-127

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-127|
|Date|2026-09-26|
|WBS|DOC-01-A04-P05 Windows 显式 DocumentVersion 读组合|
|Decision|仅在现有 `--platform`/`--platform-write` 显式模式装配 Version 读 Router；两个模式都必须从当前 Windows 账户解析独立 `document-version-cursor-v1` 密钥，缺钥或无效时整个模式失败关闭并释放数据库资源。普通登录模式继续 404。|
|Reason|版本 HTTP 已经完成隔离数据库同链路验证，但正式提供不透明分页前必须绑定目标账户独立密钥；不能复用 Document 列表密钥或回退未签名游标。|
|Impact|Windows 组合入口、缺钥合同与回归；无 Schema、API 路径/权限或依赖变化。正式发行信任源和目标账户供给仍待 Release 验证。|
|Rollback|撤下版本 Router 注入并保留原 Document 读组合，已有业务数据不变。|

## DEC-20260926-128

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-128|
|Date|2026-09-26|
|WBS|DOC-01-A05-P01 下载前验证快照|
|Decision|LocalFileStorage 新增仅内部使用的有界已验证快照：从规范 PERSISTENT locator 打开普通单链接文件，复制到数据根下的私有 `SpooledTemporaryFile`，在返回给调用者前完成 SHA-256/大小、源文件句柄及路径身份/时间检查；失败关闭并清理快照。成功快照与源文件脱钩，后续流式响应只读快照，最大字节数沿用 100 MB 上传限制。|
|Reason|先 verify 再重新打开原文件发送存在 TOCTOU；边验边发可能在末尾 Hash 失败时已经泄露不完整内容。快照在响应前完整校验且不把 locator/path 暴露给 HTTP。|
|Impact|Document 存储适配器与测试；不改变 Schema、冻结 API、文件格式或外部依赖。短时磁盘空间与并发容量需后续下载 Service/Release 策略限制，正式下载未开放。|
|Rollback|不调用快照方法；既有 verify/publish 行为不变。已关闭的临时快照由操作系统删除；不触碰登记 FileObject。|

## DEC-20260926-129

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-129|
|Date|2026-09-26|
|WBS|DOC-01-A05-P02 内部受权下载来源|
|Decision|DocumentReadService 在同一短事务复用 Session/License/Scope/父 Document 当前可见性，并由 Document Repository 对 AVAILABLE Version 与 PERSISTENT/AVAILABLE、同 Scope/Project、Hash/Size/MIME 一致的 FileObject 进行联结，返回仅内部消费的 `DocumentDownloadSource`（Locator 隐藏 repr，不进入 API）。普通读取不放行 RESTRICTED/REVOKED。|
|Reason|下载不能仅凭客户端 VersionId 或从公开 VersionView 推断物理地址；先建立可复用的授权来源事实，后续由下载 Service 执行文件快照、完整性事件与发送前复核。|
|Impact|Document Application/Repository 与隔离数据库验证；无 Schema、公开 API、新依赖或权限扩张。当前还不能直接下载。|
|Rollback|不调用下载来源方法；现有 Document 元数据读取与上传流程不变。|

## DEC-20260926-130

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-130|
|Date|2026-09-26|
|WBS|DOC-01-A05-P03 内部受权下载快照编排|
|Decision|下载 Service 先取得含当前受权 Actor 的内部来源，再创建已校验私有快照，并于向调用方交付前再次读取当前授权/Version/FileObject 来源且逐字段比较；失败关闭快照。源文件缺失/Hash/大小/身份不符时，在独立短事务写不可变 `DOCUMENT_DOWNLOAD_INTEGRITY_FAILED` Audit，目标为 FileObject 并关联 Version，失败分类不含路径/正文；不写 FileStateEvent、不擅自改 RESTRICTED/REMOVED 状态。Audit 写入失败也拒绝下载。|
|Reason|FileStateEvent 是状态沿革，原地记入同状态事件会误导后续追溯；Audit 的 FAILED 事件可记录本次观察且保留真实 Actor。文件外部 I/O 不能持有数据库长事务，二次核验减小状态变化窗口。|
|Impact|Document 内部读取 DTO、下载编排与审计/资源关闭测试；无 Schema、公开 API 或新依赖。并发容量与响应期间撤销语义留给 HTTP/Release 任务验证。|
|Rollback|不装配下载 Service；既有元数据 GET 和上传流程不变，已产生的失败 Audit 不删除。|

## DEC-20260926-131

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-131|
|Date|2026-09-26|
|WBS|DOC-01-A05-P04 可选受权流式下载 HTTP|
|Decision|按冻结 API-02 四条 PROJECT/GLOBAL 内容 GET 路径中的两种固定 Scope 路径实现可选 Router。请求先核验可信 Host/Session 且拒绝查询/Range；每 Router 默认最多四个并行快照/响应，单文件上限 100 MB。内部服务完整准备已验证快照后才返回 `StreamingResponse`；每次读取最多 1 MiB，设置长度、受控 MIME、nosniff、no-store 和不含用户文件名的附件名。流结束/中断/异常与响应后台均调用幂等关闭，释放快照和并发名额。|
|Reason|冻结合同要求受权流式内容且不暴露 locator；快照法在首字节前校验全部内容。并发限额将每进程临时快照上界限制到 4×100 MB，避免无限并发占满数据卷；后续 Release 须验证多进程/磁盘预算和实际中断行为。|
|Impact|可选 Document 下载 Router、应用入口与合同测试；无 Schema、第三方依赖或权限扩张。默认/当前 Windows 平台暂不装配，真实库/文件和目标账户验证后再开放。|
|Rollback|不注入下载 Router，维持 404；已存储文件/版本和 Audit 历史不变。|

## DEC-20260926-132

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-132|
|Date|2026-09-26|
|WBS|DOC-01-A05-P06 下载中断与部署容量边界|
|Decision|Windows 官方启动入口显式固定单工作进程，配合单 Router 四个并行、单文件 100 MB 上限，使此启动方式的下载快照理论上界为 400 MB；通过 ASGI 发送端中断模拟验证异常清理和名额释放。其他入口/多实例共享数据卷的容量不以此结论覆盖，Release 时需按实例数和同时运行任务重新评估。|
|Reason|现有并发锁是进程内的，若未限制官方入口工作进程，无法把单进程上界用于部署预算。断线应在发送异常时立即关闭私有快照。|
|Impact|Windows 启动配置与下载合同测试；无数据库、冻结 API 或外部依赖变化。此结论不替代现场磁盘空闲、故障及多实例验证。|
|Rollback|撤销单进程显式配置后应将部署容量重新标为未验证；下载 Router 仍可从平台入口移除以恢复 404。|

## DEC-20260926-133

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-133|
|Date|2026-09-26|
|WBS|CR-DOC-008/A03-P02-A01 已登记 Abort 文件单路径清理适配|
|Decision|文件适配器每次只清理一个已验证路径。`STAGE_ONLY` 清暂存，`FINAL_VERIFIED` 清最终文件；同一 inode 的 `LINKED_PAIR` 先清暂存，重试时以 `FINAL_VERIFIED` 清剩余最终文件。两个无关文件、重解析点、硬链接数异常、Hash/大小/身份不符均拒绝。`NONE` 只报告无文件，不直接改数据库。调用者必须已持同 upload_id 跨进程栅栏并完成数据库资格检查；适配器本身不推断业务授权。|
|Reason|两路径一次删除无法在崩溃中恢复步骤边界；逐路径操作使每个中断后的物理形态可重新识别，直到 `NONE` 才由后续数据库编排记录 `REMOVED`。|
|Impact|LocalFileStorage 内部受控方法及合成临时文件测试；无 Schema、公开 API、新依赖或生产装配。此单项不允许对实际已登记文件执行删除。|
|Rollback|不调用该内部方法；保留 `CLEANUP_PENDING` 和所有现有文件供后续受控恢复，不删除历史记录。|

## DEC-20260926-134

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-134|
|Date|2026-09-26|
|WBS|CR-DOC-008/A03-P02-A02 已登记 Abort 文件内部清理编排|
|Decision|仅内部维护命令在同 ID OS 栅栏内先验证当前数据库候选与全部物理形态，再于短事务记录一次清理请求 Audit；之后每步重读数据库资格并调用单路径清理，直到两路径均不存在。最后短事务行锁复核候选并原子写 `CLEANUP_PENDING → REMOVED` FileStateEvent 与完成/缺失对账 Audit。首次无文件且没有持久请求时拒绝；已有请求且文件缺失时按“观察到缺失”对账，不声称本次实际删除。|
|Reason|文件系统和 PostgreSQL 不具分布式事务；持久请求和可重复的单路径步骤允许在任意一步崩溃后保持 `CLEANUP_PENDING`，下次根据真实文件形态恢复，并区分实际删除与缺失对账。|
|Impact|Document 内部维护 Service、行锁 Repository、只读/清理 Storage 扩展及隔离库/临时文件验证；无 Schema、公开 API、新依赖或正式生产组合。维护身份授权由注入 Access Port 显式承担，生产来源未装配。|
|Rollback|停止调用内部维护命令；已 `REMOVED` 的合成测试文件不能靠回滚恢复，正式生产调用未授权；Audit/状态历史不删除。|

## DEC-20260926-135

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-135|
|Date|2026-09-26|
|WBS|EVD-01-A01 EvidenceLocator 类型化校验|
|Decision|在冻结的九种 `locator_type` 内提供纯领域校验器：DOCUMENT 无细节；PAGE 页号及可选归一化矩形；TEXT_RANGE 以页或节二选一定位，并持起止偏移与 64 位十六进制规范正文指纹；SECTION 为节路径；PARAGRAPH 为一基序号或稳定锚点；TABLE_CELL 为表锚点、行、列；SHEET_RANGE 为 Sheet 与 A1 起止单元格；SLIDE_SHAPE 为页号与 shape 身份及可选矩形；STRUCTURED_NODE 为 ParseRecord UUID、节点 ID 与非嵌套源定位。只接受各型白名单字段并返回规范副本。|
|Reason|冻结模型规定类型和最小语义，但未逐字段规定传输形状；先固定可测试的内部 DTO，后续 API/持久层复用同一校验，避免把模型摘要或任意 JSON 当成精确定位。选择不修改原 Gate 2 冻结内容。|
|Impact|仅 Evidence 领域模块和单元测试；无 Schema、公开 API、外部依赖或生产资格变更。实际解析/重新定位仍需 EVD 后续任务，不以字段校验代替证明。|
|Rollback|移除未对外装配的领域校验器；若后续 API/存储已引用，须先迁移持久定位器并保留历史固定版本，不可静默重解释。|

## DEC-20260926-136

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-136|
|Date|2026-09-26|
|WBS|EVD-01-A02 Evidence 固定版本持久模型|
|Decision|新增 `evd_evidence_records`，保存 Evidence 身份、Scope/Project、固定 Document/DocumentVersion 双引用、Locator 类型与 schema version 及 JSONB 细节、32-byte 内容指纹、受限显示字段、资格状态和乐观版本。FK 固定版本归属；插入触发器检查 DocumentVersion 当前 AVAILABLE 与 Scope/Project 一致，拒绝非 CANDIDATE 直接创建；更新触发器保护来源/Locator/指纹身份及保留历史。Locator 完整语义由 EVD-01-A01 校验与后续受权解析服务承担，不把 JSONB 字段合同冒称数据库已证明实际定位。|
|Reason|冻结 SC-01 允许 Locator 类型细节使用 JSONB，SC-02 要求核心类型/版本为列。GLOBAL 的空 ProjectId 使普通复合 FK 无法完整证明跨表 Scope，因此增加数据库插入触发器；DocumentVersion 原表不为 Evidence 增加可空复合键。|
|Impact|Evidence ORM、增量 Migration、隔离 PostgreSQL 验证与版本说明；不修改冻结 Gate 2 文件、不开放 API 或生产事实创建。后续 Eligibility/Viewer 必须有独立权限和有效来源校验。|
|Rollback|空表可降级；有 Evidence 历史时拒绝降级，先备份并走可追溯迁移，不自动删除证据。|

## DEC-20260926-137

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-137|
|Date|2026-09-26|
|WBS|EVD-01-A03-P01 Evidence 创建授权边界|
|Decision|EVD-01-A03 分为 P01 实时 Session/CSRF/角色授权、P02 固定 DocumentVersion 与真实 Locator 解析、P03 同事务候选创建/幂等/Audit。P01 仅允许项目 `PROJECT_MANAGER`、`IMPLEMENTATION_MEMBER`，GLOBAL 仅 `DeploymentAdmin`；任何创建在无 P02 来源证明与 P03 编排时不开放。|
|Reason|冻结 API-02 明确项目 PM/IM 与 GLOBAL Admin；现有 Document 读层提供版本/文件元数据，但九型 Locator 的实际解析证明尚无生产 Port。只凭 A01 字段校验或 A02 数据库触发器创建记录会允许无法点击定位的假证据。|
|Impact|仅 Evidence 应用授权适配、测试与任务时序；无 Schema/API/生产入口变更。后续 P02/P03 保持完整九型终态，不把当前分步实现替代最终可用要求。|
|Rollback|P01 未挂生产入口，停止注入该适配即可；历史冻结 API 权限矩阵不变。|

## DEC-20260926-138

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-138|
|Date|2026-09-26|
|WBS|EVD-01-A03-P02-A01 全文固定版本来源证明|
|Decision|Evidence 应用通过 DocumentService 现有受权 `PrepareDownloadService` 取得无路径、已全量 Hash 验证的私有快照；仅 `DOCUMENT` Locator 可由固定 DocumentVersion 全文 SHA-256 形成来源证明。流在成功/异常后均关闭；其余八类保持 `EVIDENCE_RESOLUTION_UNAVAILABLE`，直到格式解析器能给出实际位置和内容指纹，不以全文 Hash 假冒页/段精度。|
|Reason|ADR-008 禁止 Evidence 直读物理路径，且 Document 下载链已具状态/权限/完整性双查。Parser/结构定位尚未有生产 Port；现阶段只能对全文位置作可复验的真实性证明。|
|Impact|Evidence 内部来源证明服务、测试；无 Schema、公开 API、新依赖或生产候选创建入口。A03-P02 整体未完成，九类定位的终态不缩减。|
|Rollback|停止调用未挂生产的证明服务；不改动任何 Evidence/Document 历史记录。|

## DEC-20260926-139

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-139|
|Date|2026-09-26|
|WBS|DOC-04-A01 ParseRecord 持久基础|
|Decision|新增 `doc_parse_records` 每次解析 Attempt 独立 Root，固定 DocumentVersion、同 Scope/Project 的 `DOCUMENT_PARSE` Job、Profile/Version/递增 Attempt、状态/时间/脱敏错误与结果指纹；新增 `doc_parse_result_refs` 保存唯一受控相对结果 Locator、Schema Version、Hash/Size，并由 SUCCEEDED 记录通过触发器核对引用/指纹。PENDING→RUNNING→终态，终态不复活；删除拒绝，有历史不自动降级。|
|Reason|冻结 DM-03 与 SC-01 要求 ParseRecord 独立重试历史和受控结构化结果引用。真正 Parser/OCR Worker 在 Phase 3；Phase 2 先建立不可伪造成功形态、Job/版本归属和保留边界，以供后续结果发布/精确 Evidence 定位。|
|Impact|Document ORM、增量 Migration、隔离 PostgreSQL 测试；不引入解析依赖、公开 API 或 Worker，不把 PoC Parser 直接用作正式结果。结果 Locator 仅存受控相对标识，不返回给业务/UI。|
|Rollback|空表可降级；任何 ParseRecord/结果历史存在时拒绝降级，恢复须备份并走有记录的迁移计划。|

## DEC-20260926-140

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-140|
|Date|2026-09-26|
|WBS|DOC-04-A02 固定版本解析记录受权读取|
|Decision|复用 DocumentReadService 的 Session、License、GLOBAL 管理员/PROJECT 成员授权，在同一只读事务确认 Document 与 AVAILABLE 固定版本后读取 ParseRecord 历史。按 `(created_at, parse_record_id)` 降序 keyset 分页；安全视图仅含解析身份、状态、Job/不透明结果引用、脱敏错误与时间，不暴露结果物理 Locator、Hash 或异常堆栈。公开 HTTP 游标和 Worker 留给独立任务。|
|Reason|冻结 DOCUMENT_PARSE_LIST 需要固定版本受权历史；单独绕开 Document 授权或将受控存储路径投影到 UI 都不符合边界。|
|Impact|Document 内部读服务、仓储、测试；无 Schema、公开 API、新依赖或实际 Parser 运行。SUCCEEDED 仅代表数据库元数据状态，不证明结果文件完整。|
|Rollback|停止调用尚未挂载的内部读取方法；历史数据及已冻结接口不变。|

## DEC-20260926-141

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-141|
|Date|2026-09-26|
|WBS|DOC-04-A03 ParseRecord 列表可选 HTTP|
|Decision|按冻结 `DOCUMENT_PARSE_LIST` 提供 PROJECT/GLOBAL 两条显式 GET 路径，仅可选注入 Router；独立 HMAC 游标签名绑定 Session、Scope/Project、Document、固定 Version、页大小和 `(created_at, parse_record_id)` 位置。公开安全 ParseRecordView，不返回结构化结果路径/正文/Hash。生产 Windows 游标密钥供给及组合挂载另列 A04/A05。|
|Reason|复用既有 Document 认证与错误合同，同时防止游标跨用户、跨项目或跨版本重放；独立密钥避免与 Document/Version 游标混用。|
|Impact|Document HTTP/游标、可选应用挂载、合同测试；无 Schema、新依赖或默认公开入口。|
|Rollback|不注入可选 Router 即保持 404；不变更冻结 API 路径或历史数据。|

## DEC-20260926-142

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-142|
|Date|2026-09-26|
|WBS|DOC-04-A04 Windows Parse 游标专用密钥来源|
|Decision|采用现有 Windows 当前账户 Credential Manager 只读 SecretKeyProvider，使用独立引用 `document-parse-cursor-v1` 装配 ParseListCursorCodec；缺失或无效时失败关闭。以临时引用和合成口令验证加密备份、删除后恢复以及旧游标仍可验证；测试末删除临时凭据。|
|Reason|Parse 历史游标需独立密钥和可恢复性，不可复用 Document、Version 或其他资源族游标密钥，也不能把测试密钥内置于生产应用。|
|Impact|Windows 装配适配、单元/当前账户测试；无 Schema、API、依赖或正式密钥供给。|
|Rollback|不在生产组合调用该适配即可保持 Router 关闭；临时测试凭据测试后删除。|

## DEC-20260926-143

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-143|
|Date|2026-09-26|
|WBS|DOC-04-A05 Windows 显式平台组合 Parse 列表|
|Decision|只在 `--platform`/`--platform-write` 已有真实 Session、License 与 DocumentReadService 组合中装入 Parse 列表 Router；启动前读取独立 `document-parse-cursor-v1` 当前账户密钥，缺失则整个显式组合失败关闭，默认登录应用保持 404。隔离 PostgreSQL 验证固定版本、授权及真实 HTTP。|
|Reason|不扩大默认入口，避免仅合成 Router 被误用为生产可用；沿用 Document 读服务权限链及平台统一信任源要求。|
|Impact|Windows 组合与其测试；无 Schema、新依赖或冻结 API 变化。目标账户正式密钥与发行 License 信任锚仍由 Release 关闭。|
|Rollback|移除显式组合的 Router 注入即可恢复 404；不影响已有数据。|

## DEC-20260926-144

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-144|
|Date|2026-09-26|
|WBS|TRC-01-A01 TraceLink 版本引用与边形状|
|Decision|为 Trace 域建立冻结 SC-02 允许的具体 `(owner_module, object_type)` 白名单和固定 `object_id/version_id`、Scope/Project 值对象；边校验拒绝自环、PROJECT→GLOBAL、跨 PROJECT，并仅允许 GLOBAL→PROJECT 的 `DERIVED_FROM`/`REFERENCES_CAPABILITY`。关系只采用 DM-03 七种类型。输出标准化不可变值对象，不在该步骤判断目标存在性、正式状态、授权或图无环。|
|Reason|多态目标不能用通用 FK；应用层必须先限定类型和方向，但不能以形状合格替代 Owner Port 证明。参考对象、模板及未来业务版本仅可在后续受控写入时被验证。|
|Impact|新增 Trace 纯领域校验与单元测试；无 Schema、公开 API、数据外发或外部依赖。后续 Schema/TraceService 仍需目标 Owner Port、审计、持久幂等、无环和逐节点权限。|
|Rollback|停止调用尚未接生产的值对象工厂；不影响历史数据或冻结基线。|

## DEC-20260926-145

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-145|
|Date|2026-09-26|
|WBS|TRC-01-A02 TraceLink 不可变持久结构|
|Decision|新增 `trc_links`，保存双端固定 Object/Version Ref、Scope/Project 快照、七类关系、ACTIVE/SUPERSEDED/REVOKED、创建 Actor/Trace/时间及替代引用。数据库约束白名单、自环/跨项目/方向、活动边唯一；触发器只允许 ACTIVE→SUPERSEDED/REVOKED，禁止其他字段变更与删除。多态目标存在性、正式状态、权限、无环与 Audit 留给后续 TraceService/Owner Port，同步前不得公开写入口。|
|Reason|冻结 SC-01/02 要求多态边有受控 discriminator、保护引用、历史保留和活动边唯一；不创建全局 Object Registry，也不能将数据库形状当成目标事实证明。|
|Impact|Trace ORM、Alembic Migration `20260926_0029`、迁移/数据库验证与版本说明；无公开 API、新依赖或生产写路由。|
|Rollback|空表可降级；有任何 TraceLink 历史时拒绝降级，需备份和可追溯迁移方案。|

## DEC-20260926-146

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-146|
|Date|2026-09-26|
|WBS|TRC-01-A03 目标 Owner Port 与 DocumentVersion 证明|
|Decision|Trace 应用定义只返回匹配固定版本引用的 `TraceTargetProof` 和失败关闭的 Owner Port 调度；组合根适配既有 DocumentReadService 的受权 `get_version`，只支持 `document/DOC-02`。任何未注册类型、跨 Scope/Project、错误 DocumentVersion、无 Session/License/权限均拒绝，不返回路径、正文或文档元数据。通用 TraceLink 创建在所有目标 Owner Port、无环、幂等和 Audit 完成前仍关闭。|
|Reason|冻结架构禁止 Trace 直接跨模块读 ORM，多态目标需由 Owner Port 证明。DocumentVersion 读取已有真实授权链，适合先建立可验证的第一种端点；未来业务 Owner 必须逐类接入，不以合成数据放行。|
|Impact|Trace 应用合同、组合层 Document 适配、测试；无 Schema、公开 API、新依赖或生产写入口。|
|Rollback|不在生产组合注册该适配；数据库历史与冻结合同不变。|

## DEC-20260926-147

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-147|
|Date|2026-09-26|
|WBS|TRC-01-A04 受控关系写入期无环校验|
|Decision|为 `DERIVED_FROM` 与 `SUPERSEDES` 的合并受控子图建立仅事务内使用的 PostgreSQL Guard：按 Link Scope/Project 取得事务级 advisory lock，再对活动边作去重递归可达性查询；新增 `source→target` 前若 `target` 可达 `source` 则拒绝。GLOBAL→PROJECT 仍按相同 Scope 图观察；正常创建服务必须持同一事务与锁完成插入。无写入口前仅以独立合成验证测试 Guard，不声称 DB 禁止绕过 Guard 的直接插入。|
|Reason|冻结 DM-03 禁止受控关系成环，SC-02/03 明确无环留给 Application/transaction guard，不能以无上限触发器或仅单请求内检查代替并发写保护。|
|Impact|Trace 基础设施 Guard、单元/隔离 PostgreSQL 并发测试；无 Schema、API、新依赖或业务事实写入。|
|Rollback|停止调用尚未接生产写服务的 Guard；存量关系不变。|

## DEC-20260926-148

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-148|
|Date|2026-09-26|
|WBS|TRC-01-A05-P02 内部 TraceLink 创建|
|Decision|先实现与冻结 `TRACE_LINK_CREATE` 对齐的 PROJECT 用户路径：真实 Session/CSRF 与 ProjectManager/ImplementationMember 当前事实，在同一事务内证明双端固定版本、预留幂等收据、执行无环 Guard、插入活动边并追加 Audit。相同活动边由 PostgreSQL 唯一索引归一为原 LinkId，不产生第二条 Audit；同 Key 返回首次 LinkId。GLOBAL/Owner Service 自动写路径须在对应 Owner 身份合同具备后独立验收，不以测试伪造放行。|
|Reason|当前仅 DOC-02 Owner 具备事务内真实证明，冻结 API 项目用户角色明确；通用服务可由已注册 Owner 渐进接入，同时禁止未知 Owner 或无权路径。|
|Impact|Trace 应用/Repository 和测试；无 Schema、公开 API、外部依赖变化。内部 Project 用户路径完成不代表 Trace 全部 Owner 或生产 API 完成。|
|Rollback|不装配内部创建服务；原 TraceLink 历史保留，既有只读与无环 Guard 不变。|

## DEC-20260926-149

<!-- 后续配置决策见文末 DEC-20260926-150；此历史记录保留。 -->

|字段|内容|
|---|---|
|Decision ID|DEC-20260926-149|
|Date|2026-09-26|
|WBS|WFL-01-A01-P01 Workflow 定义形状|
|Decision|先建立不含默认业务内容的版本化 WorkflowDefinition 纯领域结构，只校验阶段/清单唯一键、有序阶段、非空 GatePolicy 引用与状态枚举；正式六阶段 key、每阶段 Checklist/Evidence/Review Policy 由后续可追溯业务配置设计确定，不在此任务硬编码或写库。|
|Reason|冻结 DM-02 给出了结构和不变量，但 API2-R04 明确正式 stage/checklist 配置尚未冻结。把合理推断的清单写进生产种子会误判 Gate。|
|Impact|workflow 领域模块和单元测试；无 Schema/API/依赖/正式业务数据变更。|
|Rollback|移除尚未被持久层使用的纯领域定义，不影响历史数据。|

## DEC-20260926-150

- Date：2026-09-26；WBS：WFL-01-A01-P02；Change Request：CR-WFL-001。
- Decision：以 Python 不可变纯配置发布六阶段 V1，每阶段两项核心必需清单，引用稳定 Evidence/Review/Gate 策略标识；具体语义与来源存版本化文档。不加载可变用户配置、不种库、不执行 Gate。
- Reason：冻结合同留下配置设计任务；最小配置可追溯，避免未经 Owner 事实验收就推进。
- Impact：新增内部目录配置和测试，无 Schema/API/依赖变化；真实项目事实与原冻结提交不变。
- Rollback：不装配配置；历史 V1 保留，未来修改发布新版本而非覆盖。

## DEC-20260926-151

- Date：2026-09-26；WBS：WFL-01-A02-P01。
- Decision：冻结状态用 StrEnum 表达，迁移校验只处理 ACTIVE Workflow 的相邻定义目标、非归档与锁版本一致，不接收客户端 Gate 布尔值，不产生新状态。最终完成/BLOCKED 恢复独立设计，不新增虚构阶段 key。
- Reason：冻结 API 只给目标 key 和 Gate 引用，真正证明必须从 Owner/Application Port 获取；纯校验不承担授权或事实证明。
- Impact：workflow 领域与单元测试，无数据库/API/依赖变更，结构成功不代表业务 Gate 已通过。
- Rollback：不装配该校验器；未持久化状态，无数据回滚需求。

## DEC-20260926-152

- Date：2026-09-26；WBS：WFL-01-A03-P02；CR-WFL-002。
- Decision：四表保留固定 V1 内容及 fingerprint，复合 FK/唯一约束防归属漂移；DEFERRABLE INITIALLY DEFERRED trigger 校验提交时完整性/状态指针，BEFORE trigger 防定义覆盖/删除/非法状态迁移。Migration 使用自包含快照，不引用会变动的 Domain；公开写路径仍不装配。
- Reason：初始化需要多行同事务插入，立即跨表完整性校验会误拒绝；只靠 ORM 无法防半套提交。数据库结构校验并不具备客户 Review/Gate 事实，因此不宣称正式阶段通过。
- Impact：Schema 增量 0030 与 ORM/测试，API/外部依赖不变；已有 Project 不回填进度。
- Rollback：空 Workflow 可 down 到 0029；有实例拒绝降级，回滚代码装配并保留历史。

## DEC-20260926-153

- Date：2026-09-26；WBS：WFL-01-A03-P03。
- Decision：初始化入口使用调用方事务，固定 V1 定义，唯一 project_id insert-on-conflict；仅新实例追加 Audit，不自行提交，不重置已有实例。入口不开放给请求/回填 CLI，真实 Project/License 授权由后续接线的应用调用方承担。
- Reason：Project 创建、幂等收据、Workflow 与 Audit 需要一事务提交；NOT_STARTED 初始化不需要虚构 StageTransition 或业务 Review 结果。唯一项目天然重试不能替代公开命令的请求幂等。
- Impact：Workflow 应用/Repository/测试，无 Schema/API/依赖变化，现有生产创建路径暂未改变。
- Rollback：不装配初始化服务；历史实例保留，不删除或回写进度。

## DEC-20260926-154

- Date：2026-09-26；WBS：WFL-01-A03-P04。
- Decision：ProjectCreateService 依公共 Protocol 调用 Workflow 同事务初始化，Windows 显式平台始终提供真实实现；Port 对旧隔离内部调用保留可选兼容，公开请求不能关闭。失败传播至调用方事务回滚，重放不重复 bootstrap。
- Reason：不让 Project Repository 直接写 Workflow 表；权限与 License 已由原 Project 创建服务验证，可复用原收据事务。跨模块修改仅为当前必要接线。
- Impact：应用 Port/组合与关联验证，无 Schema/API/外部依赖变化。已有 Project/未装配 Port 的内部路径仍需独立补齐，不据此声称全局恰一 Workflow。
- Rollback：回退组合装配，不删除已创建 Workflow，历史与初始状态保留；后续新项目未补齐须记录缺项。

## DEC-20260926-155

- Date：2026-09-26；WBS：WFL-01-A03-P05。
- Decision：既有项目初始化仅作为 PM 受权内部准备命令，引用冻结 WORKFLOW_START 的 PM/write 权限；先认证/License，再在写事务重新验证 Session 与锁定 Project/成员/部门，调用已验证 bootstrap。不得映射为 start HTTP 或自动按文档推断进度。
- Reason：初始化物理结构不等于业务启动；只读 GET 不得顺手写库，全局管理员也不能凭部署身份获得项目操作权限。
- Impact：应用命令及一个已有合同权限策略接线，无 Schema/API/依赖变化；无公开调用入口，无生产批量回填。
- Rollback：不装配内部命令；保留已初始化实例与 Audit，不重置或删除历史。

## DEC-20260926-156

- Date：2026-09-26；WBS：WFL-01-A04-P01。
- Decision：Workflow 投影仅由一个 SQL MVCC 快照构造不可变 DTO，校验固定 V1/完整阶段与清单/状态指针，不初始化缺项。WORKFLOW_GET 为四角色只读权限，读取时保持 Project/成员/部门事实锁直到返回，阻止授权与投影之间的撤权竞态；不把读操作改成 write，也不拒绝归档读。
- Reason：多次 SELECT 可能拼出不同时间的阶段状态；只有早先权限检查而不保持事实锁，会允许后续已撤销身份消费投影。
- Impact：Workflow 应用/Repository、一个内部权限策略锁标志及关联测试，无 Schema/API/依赖改变。事实锁现复用既有锁 Port，会串行同项目读取，性能另验，不宣称 P95 达标。
- Rollback：不装配读服务；保留实例与历史，不写库或清空进度。

## DEC-20260926-157

- Date：2026-09-26；WBS：WFL-01-A04-P02。
- Decision：WORKFLOW_GET 先 opt-in；HTTP 单独白名单投影并再次校验路径 ProjectId，成功回 trace/ETag/no-store，未知参数拒绝，错误复用已注册公共错误码。默认与生产组合本任务不挂载，不把缺实例读转换为写初始化。
- Reason：安全字段与应用对象分离，防内部字段意外暴露/错误 Project 投影；冻结 GET 不要求 CSRF 写令牌，但必须可信 Host/Session 和真实项目授权。
- Impact：可选 Router/create_app 注入及测试，无 Schema/依赖/Breaking API 变化。
- Rollback：不注入 Router，保持 404；实例/历史不变。

## DEC-20260926-158

- Date：2026-09-26；WBS：WFL-01-A04-P03。
- Decision：Windows 两种显式平台模式复用已验证只读服务与原信任源启动检查；默认/仅登录继续不挂载，无 Workflow 写接口。
- Reason：GET 组合不应创造另一套密钥/授权来源，缺信任源不允许降级。
- Impact：组合及隔离验证，无 Schema/依赖/Breaking API；正式信任源和实际 Gate 仍待。
- Rollback：撤销 Router 装配，保留所有实例和审计。

## DEC-20260926-159

- Date：2026-09-26；WBS：WFL-02-A01-P01。
- Decision：成功相邻迁移的 Gate 快照先作为不可变纯领域值对象；完整固定清单和 PASS/WAIVED 形状校验，所有 UUID 引用仍待 Owner 同事务证明。没有写服务或 Gate evaluator，不把对象构造成功当 Gate PASS。
- Reason：历史不能依可变当前 Checklist 重建；Waiver 需保留真实 actor/理由/影响/依据而不是改写 PASS。持久层和 START/完成语义独立设计，避免猜测 API。
- Impact：仅领域/测试/文档，无 Schema、依赖、Breaking API 或安全机制变更。
- Rollback：不使用新值对象；不改已有实例、审计或客户事实。

## DEC-20260926-160

- Date：2026-09-26；WBS：WFL-02-A01-P02；CR：CR-WFL-003。
- Decision：追加历史保留冻结 Transition/GateItem 两表，增加 typed refs owned 表；固定引用同时保存当时 Scope/状态/版本/摘要。Evidence 使用真实 FK，Review/例外缺目标表明确标前置，不虚构保护。root 创建事务标识由数据库强制写入，提交后禁止补写子项改变快照。
- Reason：Evidence eligibility 可变，只有 UUID 无法还原当时依据；JSON 数组也不足以提供查询/FK/项目结构约束。
- Impact：设计阶段，不创建 0031；无业务事实/API/依赖变化。Schema 增量与验证矩阵、缺 Owner 和 Checklist/START/完成前置见 CR。
- Rollback：设计可调整但保留历史版本；实施后有数据禁止破坏性 down，应用不装配并保留记录。

## DEC-20260926-161

- Date：2026-09-26；WBS：WFL-02-A01-P03；CR：CR-WFL-003。
- Decision：0031 新根先核对 ACTIVE/from/before，提交时核对 to/after/完整 Gate 项与当前结果/观测 Evidence；created_xid 由数据库强制写，子项只可在同事务追加。单次事务只推进一步。Review/例外缺目标表明确保留 Owner 前置，不把类型化 UUID 当实际批准。
- Reason：避免成功历史与实例状态脱节、事后补写快照，以及引用可变状态造成历史漂移。首次多表 trigger 字段错误经合法路径验证发现并修复，拒绝测试只接受预期约束错误。
- Impact：三表 Schema/ORM/metadata/验证，无公开 API/权限/依赖改变；真实业务 Gate 和 Checklist 历史尚缺。
- Rollback：空历史可 down；非空拒绝破坏性 down，不装配应用服务并保留事实。

## DEC-20260926-162

- Date：2026-09-26；WBS：WFL-01-A05-P01；CR：CR-WFL-004。
- Decision：Checklist 当前投影与每次不可变记录链分离；首次 PENDING，后续受控更正不退回 PENDING，保留 supersedes/依据与两个乐观锁序列。FAIL 可表达不足；PASS/WAIVED 服务端证明，豁免不改写质量通过。暂不用循环 latest FK，按唯一 Item 版本解析当前记录。
- Reason：覆盖当前值无法保留来源，更正又是补充资料/撤销依据后的必要闭环。旧非初态无可信链不能伪造回填。
- Impact：当前只设计；两表增量与 Gate→记录关联分步登记，公开 API 字段/架构/依赖不改变。
- Rollback：不装配记录命令，保留既有历史；未来非空 down 拒绝。

## DEC-20260926-163

- Date：2026-09-26；WBS：WFL-01-A05-P02；CR：CR-WFL-004。
- Decision：记录快照为纯 frozen 值对象，保留首次/更正父与两个独立锁序列；FAIL 不造理由或来源，正向结果最小依据形状不当事实证明。UUID/UTC/bigint 检查失败使用安全统一异常；实际链与 Scope/批准由未来受权同事务服务负责。
- Reason：在 ORM/写命令前固定不可变形状，不让错误版本或自引用进入持久层设计；不扩展冻结请求字段或把未注册 Owner 当可信。
- Impact：仅 Domain/测试/文档，无 Schema/API/依赖/权限改变。
- Rollback：不使用新对象，旧事实/历史不变。

## DEC-20260926-164

- Date：2026-09-26；WBS：WFL-01-A05-P03；CR：CR-WFL-004。
- Decision：0032 只添加 owned 记录/refs，当前投影按两个独立版本提交核对；数据库捕获 observed_stage_state，不在记录时自动恢复 BLOCKED。FAIL 可保存已证身份的未通过状态，但正向依据仍要求完整 ELIGIBLE/APPROVED。Unicode 空白显式检查，不依赖 locale。
- Reason：更正需保留当时依据、阻断状态不能被顺手消除；空白理由不能通过区域设置差异绕过。旧无链不虚构历史，Gate 固定记录关系与实际 Owner 留待独立任务。
- Impact：两表/0032/metadata/隔离验证，无 API/权限/依赖改变；结构与合成失败不是客户批准。
- Rollback：空历史可 down，非空拒绝；应用不装配写命令并保留历史。

## DEC-20260926-165

- Date：2026-09-26；WBS：WFL-01-A05-P04；CR：CR-WFL-004。
- Decision：内部当前记录 Port 使用调用方活动事务，Workflow→Item 同写方锁序和 Core 现值；按单 Item 全部不可变根验完整初次/更正链，只返回当前版本完整固定 refs。Workflow 版本允许后来增长；历史观测不重新投影为当下 Owner 事实。
- Reason：旧无链或过时 PASS 不能充当 Gate 依据；ORM identity map 可能滞后，双锁序列不同，跨项目/无链不自动回填。
- Impact：仅内部 Port/DTO/Repository；无 Migration/公开 API/依赖/权限改变，不装配不受权入口。完整链读取增长成本留待性能验证；受权 Owner/Gate 仍待。
- Rollback：不使用新 Port，保留当前表与历史，无数据回滚。

## DEC-20260926-166

- Date：2026-09-26；WBS：WFL-02-A01-P04/P05；CR：CR-WFL-004。
- Decision：GateItem 增加三 nullable 固定记录/版本/摘要字段与复合 FK；旧历史保持 NULL，新 INSERT 强制关联已提交的当前同项记录，保留 typed refs 精确集合和独立 Gate 重观测。
- Reason：直接返回 PASS 无法回溯具体更正记录；旧快照不可改写，不能由 nullable 漏洞创建新无链 Gate。记录操作者不等于例外批准人。
- Impact：拟独立 0033，原 0031/0032/冻结 API 不改，无新增业务 Scope/依赖。Schema 先验，实际批准 Owner/Gate 服务另做，不把结构当客户确认。
- Rollback：新关联非空拒绝 down；只有旧 NULL 关系允许删空字段，应用不装配新 Gate 命令。

## DEC-20260926-167

- Date：2026-09-26；WBS：RVW-01-A01/RVW-02-A01；CR：CR-RVW-001。
- Decision：统一 Review 先固定所有 Assignment 完成才汇总；任何 RETURN 在完整集合中使结果 RETURNED，未完成仍 IN_REVIEW/持锁。固定决定/主题观测与 owned 身份锁/事件分离，不覆盖历史，不跨模块更新主题正式状态。
- Reason：DM-01/DM-02/AF-02 明确完整集合规则，API 摘要不能被解释成提前终结；当前没有实际 Review，Gate 需要真实批准来源。
- Impact：设计八表（五既定+三个 owned 辅助）及纯 Domain；未有新 migration/API/依赖，不声明真实资格/Owner/Gate 已验。
- Rollback：不装配新模块，未来 owned 历史非空不允许破坏性 down，原冻结/0033 保留。

## DEC-20260926-168

- Date：2026-09-26；WBS：RVW-01-A02；CR：CR-RVW-001。
- Decision：0034 保持两 Aggregate/八 owned 表；Global 生成非空 Scope 键建立真实复合父键，完整 Round/决定/状态/事件/身份锁提交一致，终态不可改写。Trace 观测版本 0 明示无来源锁字段，以固定关系 tuple 摘要/当前状态重核替代虚构列。
- Reason：nullable Project 会跳过普通复合 FK，首条 RETURN 不能提前解锁，旧观测与新批准不同；现有 Trace 不具锁/摘要列，不能冒充存在。首次 CHECK/CASE/脚本失败修复重验。
- Impact：八表/0034/隔离验收，无冻结 API/角色/依赖变化；真实 Subject Owner/客户资格/审批服务仍未完成。
- Rollback：空表 down 至 0033，非空 owned 历史拒绝；关闭新应用入口并保留事实。

## DEC-20260926-169

- Date：2026-09-26；WBS：RVW-01-A03；CR：CR-RVW-001。
- Decision：内部查询只接受调用方活动事务/显式 Scope，以 Core mappings 和 Review→Round 共享锁读取；当前身份与固定历史轮次分开返回，历史来源观测不连接为当前状态。全轮计数/完整子记录/多人决定重新核对，缺值失败关闭。
- Reason：旧轮次结果不能随当前轮次变化；来源后来失效不应改写历史，也不能继续被当作当前有效批准。权限/License/真实 Owner 必须由后续受权应用独立验证。
- Impact：内部 Port/DTO/Repository 与测试，无数据库/API/权限/依赖变化。全历史读取成本未做性能验收；锁保护只针对遵循先锁 Review 的受控写方，不声称任意 SQL 无死锁。
- Rollback：不使用新 Port，保留 0034 历史；无数据回滚或公开路由变化。

## DEC-20260926-170

- Date：2026-09-26；WBS：RVW-01-A04。
- Decision：Project REVIEW_GET 只提供有效成员资格；主题 Owner 在同事务独立核验身份及固定旧版读取权。缺 Owner 默认拒绝，不创建恒真生产适配，不以历史批准/assigned 身份/部署管理员替代权限。
- Reason：冻结契约要求受权成员与真实固定 Subject；共享旧轮次意见不能绕过当前访问限制。
- Impact：设计内部读服务及 Project→Review→Owner→Round 相对锁序，不改 Schema/API/角色/依赖；真实 Owner 和跨模块并发验收仍待。
- Rollback：保持公开路由关闭，不使用新服务，保留历史。

## DEC-20260926-171

- Date：2026-09-26；WBS：RVW-01-A05。
- Decision：REVIEW_GET 同事务锁读四角色当前 Project 事实；内部服务独立要求 Owner 身份与固定旧版两次授权。先在已锁 Review 下定位不可变 Version，再 Owner 授权，最后读取完整 Round，避免先返回旧意见或改变既定相对锁序。
- Reason：未知 Owner/仅持 ID/旧决定不授予访问；服务凭据和身份不得由客户端证明替代。真实业务 Owner 未具备时不装配 HTTP。
- Impact：Project 新内部锁读策略、Review read service/Version 定位 Port 与单位/隔离测试；无数据库/API/角色/依赖变化。真实 Owner 锁及端到端授权未验证，License 合成拒绝不代表正式信任源通过。
- Rollback：停用内部服务/移除非公开策略，保留 0034 历史和冻结 API。

## DEC-20260926-172

- Date：2026-09-26；WBS：RVW-01-A06。
- Decision：内部 CREATE 只生成逻辑 DRAFT 根；Owner 验证固定输入与管理资格，服务器选择 policy，START 独立重验固定版本/确认人/身份锁。通用收据重放不可变 CreatedReviewRef，不把后来的 state/etag 当首次响应。
- Reason：冻结模型根绑定逻辑身份，轮次才绑定版本；目前通用收据不保存动态响应，根创建字段已不可变，可避免无必要的新 Schema。旧 Key 不能绕过现有授权，未知 Owner 不猜测。
- Impact：创建前置设计，无新代码/Migration/API/角色/依赖；真实 Owner 和创建服务仍待。保持现有每主题可有多 Review、活动 Subject 锁唯一语义，不擅自新增业务唯一性。
- Rollback：不装配创建服务，保留冻结版本/0034/历史。

## DEC-20260926-173

- Date：2026-09-26；WBS：RVW-01-A07。
- Decision：PROJECT 创建强制当前 PM/ACTIVE/Session/CSRF 与明确 Owner proof，DRAFT 根和 REVIEW_CREATED Audit/通用 receipt 同事务提交；重放由根不可变创建字段重建 Ref，并要求当前 Owner 访问权，不重验原版本待送审状态。
- Reason：身份创建不是送审，旧 Key 不能绕过撤权；原始创建 Ref 不含变化的 state/etag，可避免额外响应持久层。创建 version 只参与指纹，不误写为 Review 的 version Audit。
- Impact：内部命令/owned Repository/Project 策略/单位与隔离验收，无 Migration/公开 API/角色/依赖变化；Owner/License 合成，不能标实际批准或身份锁 PASS。
- Rollback：停用服务，保留 0034/不可变历史/审计/收据，禁止生产破坏性清理。

## DEC-20260926-174

- Date：2026-09-26；WBS：RVW-02-A02。
- Decision：先锁真实 reviewer ENABLED 账户再核对 Project 活动成员/部门及明确服务器角色子集；此为基础资格，不替代具体 Subject Owner 逐人资格。送审完整路径另用共享 User Session/CSRF 校验，不能沿用先 actor 排他锁/Project 再 reviewer 的倒序。
- Reason：数据库 FK/User 存在不等于有资格；冻结 Contract 不允许将 policy 字符串当授权，也不应静默限定全部 Review 为单一角色集合。账户与项目锁倒序可能引入死锁，须实际全链验收。
- Impact：前置/窄基础资格组件设计，不改冻结 Schema/API/角色；实际政策/Owner 身份锁/完整 start 未完成。
- Rollback：不装配新资格/start 服务，现有读/create 保持不变，历史保留。

## DEC-20260926-175

- Date：2026-09-26；WBS：RVW-02-A03。
- Decision：Auth owned 仅返回已共享锁 ENABLED reviewer IDs；Project owned 复用当前成员/部门事实 Repository 锁读，验证 ACTIVE Project 与受控角色子集，保留调用方 Assignment 顺序、实际锁账户按 UUID 排序。无用户名/敏感值输出，无自动 Assignment/commit。
- Reason：FK 或 User ID 不代表实时资格，成员/部门后来失效不能竞态逃过前置；此结果只证明必要资格，具体 Subject 资格另验。
- Impact：Auth 窄查询、Project 内部基础资格服务与真实隔离验证，无 Schema/API/角色/依赖变化；完整送审、真实 Owner 和生产政策注册未完成。
- Rollback：不调用新内部服务，保留既有 Project/Auth 与 Review 历史，无数据迁移。

## DEC-20260926-176

- Date：2026-09-26；WBS：RVW-02-A04。
- Decision：送审 Owner 结果完整绑定当前 Review/Actor/Project/逻辑主题/版本/新 Round/确认人集合，以窄准备 Port 与实际身份锁重核分离；无 bool/UUID/摘要即代表成功的默认适配。Sources 观测 scope/时序/唯一与完整人集合校验。
- Reason：纯 DTO 不证明真实业务权限或内容锁，旧准备结果不能复用到其他轮次/版本；实际 Owner 必须阻止编辑与替代 Draft，并同事务回滚。
- Impact：内部合同/6 项测试/文档，无 Migration/API/角色/依赖变化；真实 Owner/审批与完整 start 仍待。
- Rollback：不装配新 Port，保留原冻结/0034 历史；无数据动作。

## DEC-20260926-177

- Date：2026-09-26；WBS：RVW-02-A05-P01。
- Decision：完整 start 拆为可信调用方事务持久化/Owner 重核/Audit（P01）与真实 Session/CSRF/PM/账户资格/幂等入口（P02）；P01 不自提交或装配 HTTP，不能代替 P02 权限。
- Reason：先独立验完整八表原子与真实 Audit 回滚，避免在尚未完成统一锁序/授权入口时暴露不受权命令；原任务 Scope 与验收不删除。
- Impact：内部 owned Repository/事务编排/隔离测试，无 Migration/API/角色/依赖改变；真实 Owner 与完整受权入口仍待。
- Rollback：停用内部 Port，保留 0034 历史；无破坏性 down。

## DEC-20260926-178

- Date：2026-09-26；WBS：RVW-02-A05-P02。
- Decision：送审账户共享预锁与 Project 基础资格分两步，同事务暂存账户观测不作为授权证明；PM 检查先于对外资格错误。成功 receipt 重放只重验当前 Session/CSRF/License/PM/固定旧版 Owner 访问权，不重新要求历史 reviewers 仍可发起新审批；不重复写轮次/审计。
- Reason：提前锁定候选账户避免 Project→User 倒序；非 PM 不应从资格错误获知账户状态，历史重放不应被后来 reviewer 停用改写为新审批。reviewer 集合以 UUID 排序规范指纹，重排不改变请求语义。
- Impact：内部 Auth 共享 CSRF 校验、基础资格两步复用、受权 start/通用 receipt/稳定 Ref；无 Schema/API/角色/依赖改变，实际 Owner 仍未完成，不挂载 HTTP。
- Rollback：停用内部入口，保留原基础资格方法与 0034 历史/审计/收据。

## DEC-20260926-179

- Date：2026-09-26；WBS：RVW-02-A05-P02。
- Decision：基础设施只识别实际 DBAPI SQLSTATE 40P01；应用在整个 UOW 已 rollback/释放后最多三次执行同一命令/Key，不重试未知数据库或任意异常。稳定轮次 Ref 重放核对原始 Actor/Project/Review/Version/完整 Assignment 集合，忽略后来的状态/根版本但不绕过当前权限。
- Reason：新共享预锁不能使所有既有反序成员命令天然无死锁，实测确有循环；不能吞掉异常或局部重跑 INSERT。真实竞争验收证实第二次成功且只留一轮/一次 Audit。
- Impact：受控内部入口及窄死锁分类/重试，无 Schema/API/角色/依赖改变；原首轮验收错误码断言按版本检查顺序修正重验。完整 Owner/业务锁/HTTP 和其他旧写命令并发恢复仍待。
- Rollback：停用入口，原数据与不可变历史保留；不采用无限 retry 或 force 更新。

## DEC-20260926-180

- Date：2026-09-26；WBS：RVW-02-A06。
- Decision：固定单次决定/撤回交接合同绑定可信旧快照与完整新进度；同一事务通过 Owner Port 同步消费终态和释放实际身份锁，失败连最终决定 rollback。decide 不新增冻结未要求的 M 控制，withdraw 沿用根 ETag。真实 Owner 缺失不公开命令。
- Reason：Review owned 锁释放不等于业务锁正确释放，历史 Sources 观测不能代替当前批准事实；异步 best-effort 消费会留下不一致状态。
- Impact：内部合同/测试与前置文档，无本轮 Schema/API/角色/依赖变化。AF-02 reason 持久缺口另登记 CR-RVW-002，保留 0034 原文与未知旧历史。
- Rollback：不装配交接 Port，保留已有历史与送审路径；无数据动作。

## DEC-20260926-181

- Date：2026-09-26；WBS：RVW-02-A07 / CR-RVW-002。
- Decision：0035给不可变WITHDRAWN事件加nullable原因，其他事件只能NULL；保留0034原文和未知历史。down同事务ACCESS EXCLUSIVE表锁检查，含原因及offline down拒绝。ORM/固定读回随0035。
- Reason：冻结withdraw reason不得丢弃；无表锁EXISTS检查与删除列可能竞态丢失原因。
- Impact：Review owned Schema/查询，历史Schema unit显式叠加新delta，四个head verifier跟随0035；API/角色/依赖不变。
- Rollback：关闭未公开写入口；仅无原因库允许down，含历史保留新增列，禁止丢失回滚。

## DEC-20260926-182

- Date：2026-09-26；WBS：RVW-02-A08。
- Decision：先实现可信调用方事务 owned 决定/撤回、固定历史校验、实际 Audit 和终态 Owner Port 消费，不自建 UOW/commit/HTTP/收据或声称受权入口完成。Review 根独占锁持有后复用固定查询的 Round 共享锁，再调用 Owner；真实 Owner 装配前必须验交叉锁序，不能把合成 Port 当事实锁。
- Reason：先验完整结构与故障全回滚，再独立接当前 Session/权限/幂等；现有固定查询先读完整历史才能构造精确交接。所有 owned 更新仍以根为首锁；真正 Owner 交叉编辑路径尚不存在，不推断无死锁。
- Impact：新增内部编排/Repository/测试，无 Schema/API/角色/依赖变化；0035为前置。A06的抽象Owner-before-Round锁序在此内部实现读阶段具体化为根→Round共享读取→Owner，正式装配仍需核对或调整并记录，不开放路由。
- Rollback：不装配内部命令，保留全部历史与已有送审，无数据删除。

## DEC-20260926-183

- Date：2026-09-26；WBS：RVW-02-A09-P01（A09受权幂等入口前置）。
- Decision：首次结果Ref加入不可变round_event_id，以DECISION_RECORDED/WITHDRAWN事件作为通用receipt引用；重放从固定事件/轮次历史还原原Actor/状态/计数/时间，不读当前根状态当首次结果。先独立验证该前置，再A09-P02接权限与receipt，完整Scope保留。
- Reason：首次partial IN_REVIEW之后可终态甚至升版下一轮，根/轮次当前投影不是稳定首次响应。已有事件永久不可变，根首次计数可由round_no+前轮已封口lock_version之和+事件after_version还原，无需新快照表或改冻结HTTP。
- Impact：内部Ref/Repository与测试调整，无Schema/API/角色/依赖变更；旧内部对象未公开，外部收据尚未创建，不需数据迁移。非命令STARTED/COMPLETED事件拒作重放Ref，跨项目/Actor/轮次绑定在后续入口继续核验。
- Rollback：不装配受权入口，保留已提交事件和审计；无删除或原冻结内容覆盖。

## DEC-20260926-184

- Date：2026-09-26；WBS：RVW-02-A09-P02。
- Decision：Project增加REVIEW_DECIDE四成员必要权限与REVIEW_WITHDRAW PM写策略，assigned reviewer和实际Subject权另验；复用Auth共享Session/CSRF。PROJECT→Review根→固定轮次→receipt，完成指向不可变命令事件的200收据；重放重验当前固定旧版访问，不再次consume/Audit或要求根仍旧版本。只识别实际40P01整UOW最多三次，其他失败拒绝。
- Reason：角色不等于具体批准权，不能因旧receipt绕过撤权；首次结果不受后来终态/版本影响。恢复须在全部rollback后，不能只重跑INSERT。跨真实Owner锁序仍待，不以合成PASS声明全部路径无死锁。
- Impact：内部受权命令/窄重放Port/现有Policy实现，无Schema/API/新角色/依赖变化；未知Owner关闭，不装配HTTP。
- Rollback：不注册内部入口，保留事件/审计/receipt，关闭新操作但不删历史。

## DEC-20260926-185

- Date：2026-09-26；WBS：RVW-02-A10 / AUD-02-A01。
- Decision：真实Review Owner缺失，公开接线保持关闭，不用合成Actor/锁/批准通过Gate；转Phase2独立Audit受权内部读。项目Audit仅当前PM，部署Audit仅当前DeploymentAdmin且只DEPLOYMENT scope，License不免除；复用已有safe query，当前权限在同一事务保持。
- Reason：抽象AuditReadAccess和合成Review Owner不是生产身份事实，不能直接暴露已有Query或跨模块访问；Audit不依赖后续业务Owner，可继续实现批准Scope。
- Impact：Audit当前Session/Project授权服务、两项既有操作必要策略、测试；无Schema/API/角色/依赖或Phase变更。当前公开Review阻塞仍保留。
- Rollback：不装配新读服务，已有append/history保留；无数据写入。

## DEC-20260926-186

- Date：2026-09-26；WBS：AUD-02-A02。
- Decision：Audit专用32byte HMAC key/domain/family，绑定真实同事务读返回的Actor、Session digest、显式DEPLOYMENT或PROJECT、全部筛选/page_size和UTC窗口、(time,event_id)位置。strict decode用于显式日期；saved-window decode仅供未来日期未指定的HTTP使用，保留首窗，不忽略显式日期修改。
- Reason：当前默认时间每页重算会使查询指纹漂移；当前页权限必须另验，cursor绝不授予访问。独立签名域防他族复用，完整性不是加密或跨页MVCC快照。
- Impact：内部list_with_actor返回实际读上下文（不公开API），旧list保持原合同；新Codec/测试/设计，无Schema/API/权限/依赖变更。正式key来源/HTTP未接，不复用License、Secret或其他cursor key。
- Rollback：不装配新Codec/HTTP，保留原safe查询及审计历史，无数据动作。

## DEC-20260926-187

- Date：2026-09-26；WBS：AUD-02-A03-P01。
- Decision：Application接受内部搜索解析Port，在License/实际Session和当前Scope权限同事务检查后、repository读取前调用。API游标适配注入codec并使用实际Actor，禁止二次查身份或从客户端游标Actor信任；解析后的筛选/page_size不得改变，只有签名默认窗口和after允许补齐。响应上下文携带有效搜索窗口供续页签名。
- Reason：公开分页不能先信任客户端身份，也不应在独立事务取身份后查询；解码失败不触发仓库读取，当前授权先于游标格式错误。
- Impact：内部Port/API适配与验证，旧list/get不变，无Schema/公开API/角色/依赖变化。默认日期是否显式仍由后续HTTP决定，正式密钥供给未实现。
- Rollback：不装配解析适配，保留旧内部读取；无数据动作。

## DEC-20260926-188

- Date：2026-09-26；WBS：AUD-02-A03-P02。
- Decision：四个冻结Audit GET仅opt-in Router，Cookie/可信Host、当前受权service及独立codec显式注入。白名单start_at/end_at（同时提供或同时省略）、page_size/cursor/action/outcome/actor_id/target_object_type/target_object_id/trace_id；默认24h UTC，明确范围最大31天，默认续页保留签名首窗。仅安全Actor/对象引用/code状态投影，不返回ORM/hint/正文。GET只读无ETag可变状态或Audit追加。
- Reason：冻结合同已要求范围上限但未固定默认窗口；双端日期避免续页单边默认值漂移，service同事务实际Session/角色校验足够，不独立读取身份作为授权。普通默认应用不装配。
- Impact：可选HTTP、契约测试、增量接口实施说明；无Schema/Breaking API/角色/依赖变化。生产专用key供给和Windows组合后续验证。
- Rollback：不注入Router，四路径404；无数据动作。

## DEC-20260926-189

- Date：2026-09-26；WBS：AUD-02-A04。
- Decision：独立Audit游标签名key_ref为audit-list-cursor-v1，复用已验证Windows当前账户Credential Manager只读provider和加密离线备份生命周期。缺失/长度错误/provider异常统一拒绝启动，不自动生成、无环境变量/key明文文件fallback，不复用其他key。
- Reason：签名游标需持续稳定专用密钥；恢复须保持旧cursor可验证，重新生成不等于恢复。当前运行账户的临时Vault验证不代表正式部署账户或Server验证。
- Impact：新增entrypoint只读factory及unit/真实临时Vault恢复，无Schema/API/角色/依赖或安全算法变更。正式账户供给、口令独立保管和平台组合仍待。
- Rollback：不装配新factory，路由保持未启用；临时测试只清理own UUID引用，不操作正式key。

## DEC-20260926-190

- Date：2026-09-26；WBS：AUD-02-A05。
- Decision：Windows两种显式平台模式挂载四Audit GET，以同runtime的当前Session/部署Admin/Project授权与实际Audit repository接线；必须取得独立Audit cursor来源才能构建应用，异常dispose并统一关闭。默认/login-only不加载该key或挂载Audit。
- Reason：可选HTTP和当前账户来源已验证，正式组合仍需强制key前置，不能拿测试key或缺省生成继续运行。
- Impact：组合根和相关测试fixture增加显式合成Audit key，不改变业务Scope/数据库/冻结API/角色/依赖。正式账户/License供给仍缺，不据合成组合放行生产Gate。
- Rollback：回退组合根不挂载Audit；只读无数据变化。

## DEC-20260926-191

- Date：2026-09-26；WBS：AUD-03-A01。
- Decision：导出POST前置未满足，先记录设计和实际Schema差异。冻结DM-04 Job允许DEPLOYMENT，当前0035 Job/Outbox仅GLOBAL/PROJECT；下一项先CR-JOB-001修正实现遗漏，不将部署导出映射GLOBAL绕过Scope。快照与Job/受权结果交付分别实现，当前不开放POST。
- Reason：已有签名分页只是有界查询，不是跨页数据库快照；现有Job租约和Parse enqueue也不是审计导出受权入口或结果下载能力。
- Impact：只新增设计/隔离库前置证据，本轮无生产代码/Schema/API/权限或基线实施变化。完整导出范围保留，前置缺口不是免验收或删除Scope。
- Rollback：无生产变更；验证库只清理own UUID目标。后续CR必须保留原冻结版本并覆盖数据迁移/拒绝丢失的down/验证。

## DEC-20260926-192

- Date：2026-09-26；WBS：AUD-03-A03。
- Decision：导出内部Spec仅固定DEPLOYMENT/PROJECT、非零项目归属、明确UTC窗口/筛选、受控用途code、JSONL格式/安全投影/政策版本。用途不接受自由说明、字段列表、游标/路径/厂商外发或payload正文；按需由UI提供用途提示。指纹是请求一致性，不是授权/快照。Worker分CAPTURE/RENDER/PUBLISH阶段复验当前原Actor账户/角色/Scope，Port不能由DTO或bool证明替代。
- Reason：所有输入需固定供未来幂等与capture，Job只最小ExportRef。异步任务不持Session Token；登出本身不伪装取消Job，停用账户/撤角色/成员必须拦Worker发布，结果访问另须实时Session/License。
- Impact：仅内部请求/权限Port合同与unit/设计；实际Auth事实Port、Project导出维护策略与捕获/授权编排在后续实现，不对外挂载。本轮无Schema/API/角色/依赖/安全核心变更。
- Rollback：不装配未完成导出，保留已有查询；无数据动作。

## DEC-20260926-193

- Date：2026-09-26；WBS：AUD-03-A04-P03；依据CR-AUD-001。
- Decision：固定服务器AUDIT-EXPORT-POLICY-V1单集合最多100000成员，不接受客户端调大/字段列表/路径。实际capture单条带数据修改CTE的INSERT SELECT在READ COMMITTED statement snapshot按全部原Scope/窗口/筛选选取最多100001，超过上限抛错且不封口；调用方整事务回滚，不返回截断成功。上限是安全保护不是性能PASS，不减少导出需求；需要更大范围用户可调整窗口或后续新版本策略/实际性能评审。
- Reason：SQL string_agg封口及排序占O(n)空间，不能无限制占用数据库；时间/UUID分页不提供完整snapshot。首次已seal仅验证并返回原metadata，不重新选事件，Job retry/generation不替换集合。
- Impact：可信调用方事务Owner存储入口，不自建UOW/commit/鉴权/License/Lease；原Actor/Scope匹配是绑定不是权限证明。实际当前权限/幂等/Job在A05/A06，POST仍关闭。read-back检查版本/Spec指纹/原Source/顺序/count/hash/xid，未知版本或腐损拒绝。现有0001～0037/API/角色/依赖不变。
- Verification：真实隔离PostgreSQL验证single statement集合、晚提交/回填/新事件、两调用者重放同一seal、完整筛选/Scope/空集合、故障整UOW回滚。上限拒绝机制用测试小上限验证，100000行/20并发/P95实际性能另验，不虚报。
- Rollback：撤未装配存储入口不删历史；0037含历史仍拒绝down；无生产操作/客户数据外发。

## DEC-20260926-194

- Date：2026-09-26；WBS：AUD-03-A05-A01。
- Evidence：冻结API-02 AUDIT_EXPORT要求S/L/C/I/A、部署Admin/项目PM；DM-02明确归档允许受权审计/导出。现有Project政策只具AUDIT_PROJECT_LIST/GET，所有write一律拒归档；现有Parse enqueue只Document GLOBAL/PROJECT，不能假Document或GLOBAL绕过。
- Decision：先落实单一提交授权前置：新增AUDIT_PROJECT_EXPORT当前PM write政策，只有该明确维护操作允许ARCHIVED，仍锁实际Project/member/department；其他write保持归档拒绝。Audit调用方事务服务用现有Auth Session/CSRF锁核验及部署Admin proof、实际Project公共授权和License Guard，无匿名/历史Actor/DTO旁路。返回最小绑定metadata不能当跨事务凭据。
- Impact：补齐冻结权限/归档维护实现，不新增角色、Scope、API、安全机制或Schema；无新CR必要，原冻结不追写。Auth已有LicenseImportAccess只复用Session/CSRF/Admin事实，Audit服务始终另要求L，绝不复用License恢复面豁免。现有Job缺Audit专用enqueue公共Port与首次Ref读回，A02补齐后A03才能受权幂等/Audit/Job原子；不提前POST或创建未受权Job。
- Verification：四角色×操作矩阵、归档仅export write例外、真实Session/CSRF/License拒绝、跨项目/部署Admin非成员拒绝、当前member/department/user/role撤销、五类事实锁保持到调用方UOW结束及授权服务不写任何Export/Job/receipt/Audit。
- Rollback：撤未装配前置并移除新增operation，不影响历史/其他操作；无迁移/生产/客户外发。

## DEC-20260926-195

- Date：2026-09-26；WBS：AUD-03-A05-A02。
- Decision：Jobs owned AuditExportJobQueue公共合同仅固定ExportRef、原Actor、PROJECT/DEPLOYMENT、ProjectRef、原TraceRef、V1政策；Job payload只有export_id/policy_version，Outbox另加job_id。不读取Audit/Document内部表，不接受Session/Secret/路径/任意payload，不创建UOW/commit/鉴权/发布。Audit实际受权调用方须先绑定自己的不可变意图；Queue DTO不是真实存在/授权/许可或Lease证明。
- Replay：ExportRef唯一逻辑请求，内部对域分隔SHA-256的64-bit键取PostgreSQL事务级advisory lock，串行同Export首次空行竞争；跨Scope也用同Export锁。锁碰撞仅额外串行，不授予权限/合并身份，实际唯一键/全字段仍核对。Job与Outbox都存在且固定原Actor/Scope/Project/Trace/政策/aggregate/refs一致才返回原Ref；单边缺失/异载荷/改绑定拒绝，不自动修复。不复活终态或重写Worker mutable状态。首次Trace来自持久Export，不是重放请求的新HTTP trace。
- Impact：既有0037/Job Schema、公开API/角色/依赖不变；max_attempts固定Job3、Outbox5只是投递技术策略，不重复模型调用。A03主命令须授权→receipt→Audit根→Queue锁/行，并全UOW原子。Worker持Job锁再取Owner/当前权限的反序风险A06另验并使用整UOW有限重试，不宣称已有全链无死锁。
- Verification：真实PG双Scope、最小引用/原Trace、并发首次同Ref、失败Outbox全UOW回滚、调用方不commit、终态重放不复活、错Actor/Scope/Project/Trace/policy/缺一行拒绝、只读lookup不创建，已有Parse范围及Job租约回归。Queue本项不以可信调用方测试冒充客户权限/Worker/HTTP。
- Rollback：撤未装配公共Port不删已有Job/Outbox，无数据库升级/生产变更；普通导出POST仍关闭。

## DEC-20260926-196

- Date：2026-09-26；WBS：AUD-03-A05-A03-P02；输入CR-AUD-001/0038。
- Decision：完整内部提交使用A01当前许可/Session/CSRF/PM或Admin、通用receipt、Audit own Root/0038首次结果和A02 Jobs公共Queue，在同UOW受理并202。receipt按实际Actor/Project/版本化Scope操作/key digest隔离，指纹用完整规范Spec，HTTP trace与凭据不参加业务载荷指纹或落Job。请求Audit目标是确实创建的jobs/JOB-01，reason仅受控purpose，Root/Queue原Trace固定，不把Export伪装AUD-01。
- Replay：每次先当前权限/License再receipt；加载原不可变Root与acceptance，核对原Spec/Actor/Scope及Jobs公开lookup精确原Job/Event ID。缺受理记录/缺Job或被替换拒绝，不创建/修补历史，不用enqueue做replay。新HTTP trace不会改写首次结果，终态原Job不复活。
- Atomicity：授权→receipt→Root→Queue→请求Audit→acceptance→receipt complete→commit。任一异常全UOW退出回滚。只有实际DBAPIError sqlstate40P01（含安全包装因果链）最多3次完整新UOW重试，每次重验当前权限/许可；不凭error字符串/一般503重试，不重试未知commit或网络异常。原User/Project与receipt/Root/Queue锁序在此检查；Worker反序需A06另验。
- Impact：无新Schema/角色/Scope/公开API/依赖变化，不自动capture或运行Worker，不声明文件产出/任务完成。现有0038保留原引用；未装配内部命令，导出POST仍关闭。实际正式信任材料/质量/性能/Gate/完整可用包仍待。
- Verification：真实双Scope首次全记录、同key新trace原结果且全表不变、同key异Spec拒绝、不同Actor/Scope namespace、归档PM/部署无项目旁路/撤权/CSRF/许可拒绝、并发单组受理、每阶段故障全回滚、真实40P01限次整UOW恢复及耗尽拒绝、缺历史/替换Job拒绝。
- Rollback：撤未装配服务不删除/更改任何历史，0038含历史拒绝down，无生产/客户数据操作。

## DEC-20260926-197

- Date：2026-09-26；WBS：AUD-03-A06-A01 当前Worker权限。
- Precode：Phase2；输入冻结API-02/DM-02与A03当前授权Port、A05实际受理；前置满足。模块Auth/Audit，仅Auth公共当前User事实与Audit应用授权，无新实体/Schema/API/依赖。验收真实当前事实锁、撤权/范围/归档维护/许可拒绝、无业务写；风险坐标伪造及锁序，Owner仍须先绑定持久Root与真实Job租约，本项不是完整Worker。
- Decision：Auth提供非Session的当前enabled User/部署角色事实公共Port，在调用方事务锁User；Audit每次CAPTURE/RENDER/PUBLISH调用重新检查License与当前User及Project公开AUDIT_PROJECT_EXPORT权限。部署Admin不旁路项目成员。原Session注销/自然到期不自动取消已受理任务；原始凭据不持久化，真实当前身份禁用/撤权阻止执行。许可检查trace使用Export UUID仅为技术关联，不制造审计业务事实。
- Impact：结果None不构造可跨事务复用权限证书；原request仅坐标，持久Export/acceptance绑定与Job Lease/fencing/取消由后续Owner编排实施，不能以本项放行HTTP/文件发布。User→Project/member/department锁持至调用方事务结束；Job锁反序仍须实际整UOW验证。
- Verification：真实隔离库各stage/两Scope、disabled/非Admin/nonPM/member/department/跨项目/归档、Session注销仍当前权限有效、四事实锁与无业务写；License合成明确标注。单元错误映射/输入/绑定/无默认许可。
- Rollback：撤未装配Port，无数据迁移、不删除历史、不操作生产。正式信任源/性能/三平台及Gate仍待。

## DEC-20260926-198

- Date：2026-09-26；WBS：AUD-03-A06-A02-P01。
- Precode：Phase2；输入DM-04/API-03既有租约fencing与A06-A01；前置满足。模块Jobs；实体既有Job/Lease/Attempt；无公开API/Schema/角色/依赖变化。只解决caller事务内当前Lease检查，不实现取消命令或发布。
- Decision：新增Jobs公共JobLeaseCheckpoint，精确nonzero UUID/positive int64 token/worker校验，调用owned repository锁Job→Lease→Attempt，当前RUNNING/对应worker/token/未完成attempt/一致attempt_no及到期时点/未到期才返回现存ClaimedJob。取消中及所有非RUNNING状态拒绝，不heartbeat/finish/commit，不提供跨事务凭据。Caller必须短事务，长I/O不得持锁，后续发布重新检查。
- Verification：真实当前成功且全表不变、竞争三事实锁、错worker/token/ID、到期/实际接管、取消中及终态、篡改期限/attempt编号、caller故障回滚及原租约回归。取消状态用测试设置只证明拒绝，不冒充真实取消流程。Audit Root/actor/scope/acceptance绑定及锁反序由后续编排另验。
- Risk/rollback：Lease不是业务授权；保留A01当前权限。锁内到期仍须发布时重验，不能声称初次检查永久有效。撤未装配入口无迁移/历史删除/生产操作；POST保持关闭。

## DEC-20260926-199

- Date：2026-09-26；WBS：AUD-03-A06-A02-P02-A01。
- Precode：Phase2；输入冻结DM-04/API-03、A02-P01、CR-JOB-002；Job协作取消信息缺失已代码核查，先补必要Schema。模块Jobs，实体Job，新增三nullable字段，无API/权限授予/依赖。验收空/旧数据up/down/parity、不可猜回填/不可变取消信息/历史保护/并发降级锁。
- Decision：0039沿CR-JOB-002补齐首次申请人/原因/UTC时点，首值固定、取消态不可复活/删除、有历史禁止truncate/down。旧全NULL保持，元数据不代表实际授权；完整取消Port在下一分项，不用Schema替代Worker/HTTP。
- Risk/rollback：增量DDL锁需备份维护；含取消信息不可down，无信息可撤列；无生产迁移/自动删历史。错误与未知内容不公开原理由，Secret文本识别不能仅靠CHECK。正式Scope/Gate保持。

## DEC-20260926-200

- Date：2026-09-26；WBS：AUD-03-A06-A02-P02-A02。
- Precode：Phase2；输入DM-04/API-03/0039/CR-JOB-002/A02-P01；前置满足。模块Jobs，既有Job/Lease/Attempt和AuditExport Queue公共坐标；无Schema/API/权限授予/依赖。一个问题：可信Owner caller-UOW实际取消请求/协作确认/到期恢复及完成竞争。
- Decision：每次核对原Export Queue pair与精确首次Job/Event refs，不猜修复缺边或替换。PENDING/RETRY_WAIT在同事务REQUESTED→CANCELLED；RUNNING登记REQUESTED保留租约，当前未过期Worker/token可确认；失联后仅真实到期恢复EXPIRED，保留历史。首次申请信息不重写；已成功/失败返回原终态，不能伪装回滚，旧取消历史无来源失败关闭。
- Authority：坐标/申请人FK/Worker不是业务权限。Owner必须先锁自己的持久Root/acceptance，重新当前授权；本项只Jobs公共Port，不自建UOW/commit/许可或Session鉴权。申请原因不回到结果/payload/Audit自由正文；拒空白/未规范/控制字符/超长，但不能保证合法文本不含Secret。失败映射固定code。
- Locks/verification：Queue事务advisory→Job→Outbox，再Lease→Attempt；与finish Job锁串行，实际先取消拒发布、先完成拒伪回滚、同请求并发首次一次、确认/到期恢复竞争、故障全回滚/原数据/当前Worker/过期及缺来源验证。Worker短事务锁反序及完整Audit幂等/审计仍另验。
- Rollback：撤未装配入口不删历史；0039含信息拒绝down；无生产操作/公开API，正式信任/性能/完整Worker/包仍待。

## DEC-20260926-201

- Date：2026-09-26；WBS：AUD-03-A06-A03。
- Precode：Phase2；输入A05真实受理/0038、A06当前权限/租约/取消与A04真实capture；前置满足。Audit聚合+Jobs/Auth/Project公共Port；无新Schema/API/角色/依赖。只完成真实已受理Worker capture原子事务，非文件发布。
- Decision：Worker仅输入Export ID/原Job ID/worker/token。先无锁peek不可变Root作为内部查找线索，不授予权限，再User→Project/member/department→Root精确重读→原acceptance→Queue原pair→Lease/Attempt，核对真实Job Scope/Type/Trace/原payload/原ID，执行capture。完成后再当前许可/权限及Lease核验，commit只固定集合，不finish/heartbeat/发文件。迟到Worker/取消/缺源/替换/撤权失败回滚；已有seal只按原集合重放，不换snapshot。
- Atomicity：只有实际因果链DBAPI40P01最多3次整UOW新事务重新授权，不凭错误文本或一般存储失败重试。peek不锁Auth反序；后续publish Job-first反序另验。原不可变数据不因重试改变。
- Verification：真实受权提交→Job claim→Worker当前权限/原acceptance/pair/Lease→capture两Scope；重复/新事件不进旧seal，当前撤权/原Session注销/归档维护/取消/到期接管、故障及after-check失效全回滚；实际死锁与限次恢复，旧Worker不得成功。License合成须标注，无正式文件或性能承诺。
- Rollback/risk：撤未装配Worker不删历史，0037/38/39历史down保护保留。capture可能长于Lease/空间策略，末次检查拒绝到期；性能待验，不宣称短耗时P95达标。普通导出POST关闭，正式信任/Gate/全Scope仍待。

## DEC-20260926-202

- Date：2026-09-26；WBS：AUD-03-A06-A04-P01。
- Precode：Phase2；输入JSONL_V1/AUDIT-EVENT-SAFE-V1/CAPTURE-MEMBERSHIP-V1与已验A03实际seal；Audit owned安全渲染，前置满足；无新实体/Schema/API/权限/依赖。只解决固定来源安全字节与manifest，不接文件发布。
- Decision：JSONL文件只含逐条显式白名单事件，UTF8无BOM、canonical排序key/紧凑JSON/LF，UTC微秒，独立manifest含固定意图/Scope/窗口/筛选/版本/来源count/hash/文件size/hash，不含路径/worker/session/hint/free正文。来源只按固定member.position流入，逐项序号/Scope/全Spec/安全codes重核，再同原规范计算成员摘要；不得重查live集合。大小上限128MiB、单行16KiB，失败不返回manifest、不声称截断完整。
- Authority：纯renderer和owned source Port不鉴权、不建UOW/commit、不授予文件交付；Owner须先实际权限/Root/原Job/Lease，再受控临时产物，完成发布前重新授权。失败可能已写部分字节，必须保持临时且不可下载/清理，不伪装文件I/O回滚。
- Verification：规范向量/空集合/UTF8/LF/确定性、文件与成员hash区分、安全投影/筛选/范围、缺失/多项/重复/错序/错版本、短写/异常/超限、真实固定member源与新事件排除。摘要去重O(n)UUID内存保留，批量DB读取不声称常量内存或性能通过。
- Rollback：撤未装配代码无历史变更；无Migration/API/Scope/依赖，正式Artifact/当前渲染权限/发布/下载/Gate/包仍待。
## DEC-20260926-205 — P03-A01编码前检查

- 当前Phase/WBS：Phase2 / AUD-03-A06-A04-P03-A01；输入CR-AUD-002/ADR010、0039、DM03/04/API02，P02实际不兼容与P03设计已完成。
- 涉及模块/实体：Document FileObject、DocumentVersion/Upload引用保护；Audit仅后续来源，不跨模块写表。无新API/角色/依赖/生产操作。
- 验收：0040与ORM parity，旧DOCUMENT完整保留；专用文件用途/归属/内容身份固定，禁止普通DocumentVersion/Upload误绑，即使同PROJECT；空/有数据up/down/reup、实际并发降级锁和专用历史拒绝down。
- 实现选择：新增用途/owner CHECK及独立触发器，不改写0022/0023已有函数。用途/owner对所有FileObject immutable；专用Audit文件固定Hash/Size/MIME/Locator/Scope/Actor，初态STAGED/PERSISTENT，AVAILABLE后仅限制且不可复活；保留失败/取消文件历史，不物理delete/truncate。实际Export根与Worker权限不由UUID/Schema证明，后续公共Port独立验。
- 风险/回滚：含任一AUDIT_EXPORT历史拒绝0040降级；仅临时DB运行，离线down关闭；DDL停写/备份与正式文件/存储/Lease/HTTP/Gate/性能仍待。

- 同问题入口隔离补充：FileState/Publish通用Repository只加载DOCUMENT/NULL owner，防同PROJECT审计文件被旧状态/发布入口处理；实际公共Port独立验证仍待。

## DEC-20260926-204

- Date：2026-09-26；WBS：AUD-03-A06-A04-P03变更设计。
- Input：完整正式总控V1.1/实施方案V2.1、ADR007/008、冻结DM03/04/API02和P02实际拒绝。当前Phase2，前置核查已完；Audit/Document/Jobs内部文件归属与结果，公开API仍关闭。
- Decision：实施前建立CR-AUD-002与ADR010，仅内部FileObject扩用途/DEPLOYMENT、Audit own尝试/结果；不伪造文档或插件、不重标Scope、不修改普通Upload/Parse/Output规则。Schema/锁序/迁移/历史down保护/存储恢复/实际权限/Lease/取消/下载验收逐项记录后实施。
- Result/risk：本项是设计记录，尚无代码/Migration或运行验收，不标完整导出PASS；新路径/用途和旧链路误绑防护须真实DB+文件验证，含历史拒绝降级，正式信任/质量/目标账户/Gate仍待。

## DEC-20260926-208 — P03-A03-P01编码前检查

- Phase/WBS：Phase2/P03-A03-P01；前置0040及Document字节/元数据Port已验；输入CR-AUD-002/ADR010/0037～0038原源。Audit render attempt子记录/ORM/0041；无新HTTP/权限/依赖/生产操作。
- Decision：实施前CR精化每Job/fencing单文件计划、固定capture摘要/原accepted Job与安全Worker坐标。DB仅证明own来源/形状/不可变，实际Job存在/当前权与Lease公共Port留P02；不跨模块读取表、计划file_id不伪造已存在的FileObject或成功结果。
- Acceptance：空/旧accepted sealed历史up/down/re-up/ORM parity、双Scope来源绑定/缺capture或acceptance拒绝、UUID/token/worker/源/时点/唯一/immutability、真实并发同代单计划与down锁/有计划历史拒绝。无磁盘/真正Worker/下载证明。
- Risk/rollback：不回填/删旧来源，任何计划历史拒绝down，离线危险down禁用；待结果Schema与完整权限/Lease/发布回归，Gate/完整包仍待。

## DEC-20260926-207 — P03-A02-P02编码前检查

- Phase/WBS：Phase2/P03-A02-P02；输入0040/CR-AUD-002/ADR010/P01真实存储，前置满足。Document owned FileObject/StateEvent公共caller-UOW元数据Port；无Schema/API/依赖/权限变化。
- Decision：精确export/原User/Scope/File/content坐标登记STAGED与首次StateEvent，INSERT冲突后锁原行完整重核、重放不改来源。只由Document生成私有final Locator；AVAILABLE核对原身份/Hash/MIME/Size/初态版本并登记状态来源，同UOW不commit、不做长I/O。已可用只返回原事件，RESTRICTED/FAILED等不得复活。
- Authority：坐标/DTO/Hash不是Export根/当前权限/Lease/字节证明。Owner先核实际Root/acceptance/pair/capture/授权/Lease，事务外验证实际文件，再调用此Port且同事务追加真实Audit/Job结果。本项不自鉴权/伪造SystemActor；不单独开放HTTP。模拟caller用真实Audit/文件/临时DB验证同事务失败全回滚，不冒充完整Worker。
- Acceptance：两个Scope真实staging→字节Hash→元数据→提升→AVAILABLE，重复/并发单首次事件、不同owner/actor/scope/hash/size/普通用途/无来源历史拒绝、回滚包括Audit、原创建trace保持、已限制不复活；旧链路回归。正式信任/并发发布/下载/包仍待。

## DEC-20260926-206 — P03-A02-P01编码前检查

- Phase/WBS：Phase2 / AUD-03-A06-A04-P03-A02-P01；前置0040内部归属已验，输入CR-AUD-002/ADR010/P01安全字节。Document owned受控物理文件Application Port与Adapter；无新Schema/API/角色/依赖。
- Decision：本分项只实现PROJECT/DEPLOYMENT独立generated/audit存储，通过精确内部file_id/Scope/project坐标生成Locator，不接客户端路径。复用原路径检查/排他reserve/hash/同卷不覆盖提升/恢复原语；普通locators和上传扫描保持原范围。bounded sink只允许bytes写入，正常结束flush/fsync关闭再独立Hash读回；异常保留私有部分文件，不自动删除/覆盖。
- Acceptance：真实临时文件双Scope/空文件/上限/短写/模拟磁盘不足/路径污染/扫描隔离/不覆盖/新ID/实际linked与final恢复及损坏拒绝；坐标/Hash不是授权，不开下载或DB发布。旧Storage回归；目标账户ACL/实际磁盘满/128MiB性能/Server2025/Debian未验。
- Risks/rollback：下一分项才接caller-UOW元数据及Audit持久尝试/结果/当前权限/Lease；文件提升后仍不可见。撤未装配入口不删除专用历史；没有清理删除Port，不放宽生产删除授权。

## DEC-20260926-203

- Date：2026-09-26；WBS：AUD-03-A06-A04-P02。
- Precode：Phase2；前置P01安全渲染已验；输入冻结DM-03/04/API-02与0039；涉及Audit/Document/Jobs FileObject/结果归属；无新API/权限/Migration。只做实际入口只读探测与兼容核查，不实施范围变更。
- Decision：核验GLOBAL/PROJECT入口保持支持、DEPLOYMENT存储/发布实际拒绝、ORM范围；普通OutputArtifact的项目/Plugin/DocumentVersion来源不能伪造。登记独立进度证据；下一任务先专项CR再内部DEPLOYMENT FileObject/Audit自有结果契约，保持普通Document/Upload/Parse范围。
- Risk/rollback：探测不访问客户文件或修改数据库；不存在生产回滚。不得用拒绝探测PASS宣称导出交付PASS；没有实际文件/公开POST/发行验收。
## DEC-20260927-335

- Executed：1430项tests无失败/2既有跳过，实际Windows多工厂同一reset/change预算、容量冲突/绕过类型拒绝、dispose一次与九表不变、原HTTP/模式/故障/发布回归和wheel753290通过。混合HTTP/性能未验，A05继续；原FAIL与CR OPEN，无Migration/API/依赖/生产升级，完整包未完成。

- Phase2 / AUT-04-A12-P06-A04-P03-A04；前置A03内部共享容量已验证，输入CR-AUT-008/0049/冻结64cdf09。编码前检查见对应progress。
- 在Windows写组合根注入进程唯一reset/change容量，非敏感Bootstrap默认4/严格1..16；不同配置必须重启，不新建第二预算。无API/Schema/权限/算法/依赖变化。
- 风险、回滚与验收先记录；性能FAIL保持，实际Windows混合HTTP尚待验证，不冒充全Auth或跨进程限额。

## DEC-20260930-521 — Parser 独立进程调度层

- Phase/WBS：Phase2 / PAR-01-A05-P01-P05-A02-P02；编码前检查见 `docs/progress/par-01-a05-p01-p05-worker-process.md`。前置 A02-P01 已验；不改 Schema/API/权限/技术栈。
- 决策：单循环每轮先最多恢复一条已过期取消、再最多执行一个 Parser Job，避免扫表永久压住正常领取。停止信号仅设置本地标志，待当前单步/心跳退出后收敛；静止检查要求调度和执行锁均空闲。既有 Worker Step 负责失败分类/租约，循环不猜测事务结果。
- 风险/回滚：长耗时 OCR 不保证即时停止，不使用强杀或释放活跃资源；无新持久状态，回滚为停用未装配入口。单元并发、停止、计数、异常验证通过后接真实 Windows 进程组合。

## DEC-20260930-522 — Parser Worker 显式组合根

- Phase/WBS：Phase2 / PAR-01-A05-P01-P05-A02-P03-A01；编码前检查见进程进度文档。前置已验，但正式维护停写栅栏缺失，因此把组合根与发行级进程验收拆开，不改 Gate2 基线。
- 决策：仅以明确注入的 PG18 Worker runtime、Project/License/动态 SystemActor、数据根与离线 OCR 引擎装配既有 Parser Ports；启动前核数据库当前 Migration/身份/License。禁止从环境变量或命令行隐式取 Secret 或模型，缺受控源即失败关闭。
- 风险/回滚/验证：工厂本身不证明正式账户、维护模式、信号或断网 OCR；先用隔离 PG/已提交合成上传验证真实调用链，后续独立接 Windows CLI 与维护栅栏。无数据迁移，回滚为停用未接入工厂。

## DEC-20260930-523 — Parser Windows 离线 OCR 进程配置

- Phase/WBS：Phase2 / PAR-01-A05-P01-P05-A02-P03-A02。非敏感 Bootstrap 新增三项可选模型坐标供独立 Parser Worker 使用，API/Audit Worker 既有配置保持可启动。Parser Worker 必须三项齐备、指纹通过真实模型校验，禁止无模型隐式降级或在线下载。
- Windows 进程只从当前账户数据库凭据、正式 License/SystemActor Vault Port 装配；命令行只接 Bootstrap 文件路径与可选 `--once`。信号回调不做数据库或磁盘工作，由桥接线程请求停止，静止后才 dispose；不实现强杀假承诺。
- 此项不提供 API 级维护停写栅栏。维护模式的跨 API/Worker 栅栏需另立前置任务并验证，不能凭 CLI 正常停止关闭 Gate。无 Schema/API/权限变更，回滚为停用 CLI/移除可选非敏感配置，已提交 Job/Audit 保留。

## DEC-20260930-524 — 维护停写栅栏专项前置

- Phase/WBS：Phase2 / PLT-MAINT-01-A01。2026-09-30 核查现有按 UploadId 的本地锁与 Audit/Parser 协作停止均不足以阻止所有生产 API 新写；原 DOC-03 生产停写阻塞继续有效。
- 决策：先按 `CR-PLT-004` 设计会话级 PostgreSQL 共享/排他 admission 与持久维护状态，分步覆盖 Schema、Platform Port、生产 API、两类 Worker 和独立维护命令。未实现并验证全覆盖前禁止据此进行生产物理清理/升级或关闭 Gate。
- 风险：长 I/O 持有专用连接增加容量要求；旧进程混跑会绕过新门禁。迁移/回滚和真实跨进程验收条件详见 CR。

## DEC-20260930-525 — 维护状态0051编码前决定

- Phase/WBS：Phase2 / PLT-MAINT-01-A02；前置 `CR-PLT-004` A01 已登记，编码前检查见对应 progress。仅新增 Platform 单行状态 ORM/Migration，不提前接 API/Worker 或声明停写。
- 选型：`state_id=1` 固定行、RUNNING/MAINTENANCE、单调 lock_version 与数据库变更时间；触发器拒绝 DELETE/TRUNCATE 与跳版/同态更新。首次升级插入 RUNNING/v0，不回填业务表。只有无维护历史时允许 down。
- 验收/回滚：隔离 PG18 空/有数据 up/down/re-up、约束与 ORM parity；有历史 down 拒绝。生产迁移前人工备份/停写；正式 admission 全覆盖未实现前，表状态不是并发安全证明。

## DEC-20260930-526 — 维护准入锁与静止证明分离

- Phase/WBS：Phase2 / PLT-MAINT-01-A03-P01；编码前检查见对应 progress。CR-PLT-004 补记连接丢失窗口：会话锁释放不能证明仍运行的 OCR/上传进程已退出，禁止把取得排他锁当作备份许可。
- 本项只实现共享准入与状态读取，专用 PG18 会话持锁覆盖调用者窗口，状态 MAINTENANCE/缺失/DB 错误失败关闭；状态切换/正式 API 与 Worker 接线、OS 进程退出证明另做。无 API/Schema/权限变化。
- 风险：连接池容量及意外失联仍须真实并发验证，后续维护命令必须附加进程清单/退出证据。当前 Port 不等于可用维护模式。

## DEC-20260930-527 — 排他状态转换只作内部 Port

- Phase/WBS：Phase2 / PLT-MAINT-01-A03-P02；编码前检查见 progress。排他状态切换与 Audit USER 成功事件同事务，沿用 DB0051 和 AuditService，不开放普通用户 API/CLI。
- 入口须在后续 WBS 独立验证操作员身份及部署权限；此 Port 的 UUID 参数不构成认证。共享准入、全部生产进程和 OS 退出证明未完成时，即使状态成功切换亦禁止备份/迁移或宣称静止。
- 使用有限锁等待、失败关闭；维护状态可恢复但历史不删除，版本持续递增。无新 Schema/API/依赖；旧版进程仍是发行阻塞。

## DEC-20260930-528 — 维护转换操作员必须在同事务证明

- Phase/WBS：Phase2 / PLT-MAINT-01-A03-P03-P01；编码前检查见 progress。A03-P02 的 UUID 输入不足以证明操作员授权，禁止生产装配。复用 Auth 当前 Session+CSRF+DeploymentAdmin 校验，在排他锁下、状态/Audit 同一事务内解析 actor，不接受调用方自称 UUID。
- 该证明不等于 OS 部署账户限制或进程静止；CLI/服务权限和完整停写仍分步验收。无 API/Schema/依赖变化。

## DEC-20260930-529 — 本机维护工具双重信任来源

- Phase/WBS：Phase2 / PLT-MAINT-01-A03-P03-P02；编码前检查见 progress。Windows 工具只从当前 OS 登录账户 Credential Manager 取现有 DB URL，要求交互式终端和应用管理员隐藏口令，复用生产 Auth 限流/Session 证明；不把数据库 URL 或凭据放在命令行/环境变量。
- 状态仍由内部排他 Port 同事务重核 Admin，Session 使用短时限且操作后撤销。账号专属 Vault 配置与服务账户 ACL 必须在目标系统验证；工具输出不宣称 OS 进程已静止，未接生产全入口前禁止备份/迁移。
- 影响：增加运维 CLI，不改公开 API/Schema/依赖；失败时保留可审计的状态/Audit，按版本重新读取判断，不自动回滚生产数据。

## DEC-20260930-530 — 写请求在 ASGI 外层持共享准入

- Phase/WBS：Phase2 / PLT-MAINT-01-A04-P01；编码前检查见 progress。选择可选纯 ASGI middleware 包住非安全方法完整请求生命周期，包括上传正文 receive 与响应后台工作结束；Trace 外层保证拒绝响应仍有 trace_id。默认开发 app 不注入，正式组合接线另验。
- 失败返回固定 503 `SYSTEM_UNAVAILABLE`，不泄露维护状态/数据库错误；GET/HEAD/OPTIONS 暂按只读处理，后续需审计实际路由副作用。此中间件不代替业务权限或 OS 进程退出证据。
- 无 Schema/冻结 API 路由/依赖变更；引入独立 PG 连接容量和同步短时开销，性能和目标环境须验收；回滚移除可选注入。

## DEC-20260930-531 — 有错误路径写入的 GET 下载同样准入

- Phase/WBS：Phase2 / PLT-MAINT-01-A04-P02；`CR-PLT-004` 补充 GET 副作用。Document 版本正文和 Audit Export 正文四个 GET 路由在错误路径可提交 Audit，不能作为无锁只读请求。
- 选择精确路径族准入，覆盖完整响应流及后台收口；其余 GET/健康仍可用。现有公开 GET 合同不变；需真实 PG 路由拒绝和下载路径回归，生产组合尚未装配时不宣称全覆盖。

## DEC-20260930-532 — Audit Worker 单步窗口持共享锁

- Phase/WBS：Phase2 / PLT-MAINT-01-A05-P01；编码前检查见 progress。向 Audit Worker Loop 注入可选 admission 协议，覆盖一次 `step()` 的扫尾/领取/执行和现有 heartbeat 同步收口；idle sleep 不持锁。Audit 模块不直接依赖 Platform 具体 PG Adapter。
- Windows 正式组合接线与真实 PG18 跨进程验收后续单独完成；本项不改变 Audit Owner、Lease、权限或公开 API。连接失联非静止证明，仍需 OS 进程退出和发布前复核。

## DEC-20260930-533 — Worker runtime 显式拥有独立准入 Engine

- Phase/WBS：Phase2 / PLT-MAINT-01-A05-P02；编码前检查见 progress。WorkerDatabaseRuntime 仅在显式开启时创建一个独立 PG18 admission Engine，并与业务 runtime 同属 Worker 资源，静止退出/启动失败一起释放。Windows Audit Worker 从同一次当前账户 Vault URL 构造，传给 A05-P01 Loop；默认 Worker runtime/测试保持不启用。
- 连接池最多1个专用准入连接，单 Worker 一轮串行；Heartbeat 使用现有业务连接。无新 Schema/API/依赖；目标 OS 账户/Server2025 和失联静止证明继续保留。

## DEC-20260930-534 — Parser 每轮扫描与执行同锁准入

- Phase/WBS：Phase2 / PLT-MAINT-01-A05-P03；编码前检查见 progress。Parser Loop 注入可选 admission 协议，把一次 expired-cancel 扫描、领取及 OCR 执行放在同一共享锁窗口；idle sleep 在锁外，停止和异常自动释放。Parser 业务模块不直接依赖 PG Adapter。
- Windows 进程显式接线和真实 OCR/失联验证后续独立 WBS；不改变既有 Document/Jobs/Audit 事务与权限，连接丢失非 OS 静止证明。

## DEC-20260930-535 — Windows Parser 复用 Worker 专用准入资源

- Phase/WBS：Phase2 / PLT-MAINT-01-A05-P04；编码前检查见 progress。Windows Parser 从当前账户 Vault URL 创建显式 Worker runtime 专用准入 Engine，复用 A05-P03 Loop Port；由既有进程生命周期在静止后统一释放。
- 不更改现有 OCR/Job/Document Owner 与外部合同；正式账户/Server2025、连接失联后的进程退出与恢复演练保留为后续验收。

## DEC-20260930-536 — OS 进程只读候选盘点不作静止结论

- Phase/WBS：Phase2 / PLT-MAINT-01-A06-P02-P01。以 Windows CIM 读取 PID、拥有者 SID、可执行路径和命令行，仅在进程内分类；对外只给候选 PID/理由及不可见计数，绝不打印命令行/Secret。部署账户 SID、运行目录及已知模块任一匹配即候选。
- 未能读取拥有者/命令行、旧版进程移址及未知服务定义均不能由零候选反推安全。当前结果固定 `DIAGNOSTIC_ONLY`，不自动执行停服/备份/迁移；正式 SCM/版本/句柄证据另验。无新依赖/API/Schema，回滚独立诊断入口。
- 实测修正：逐进程 CIM `GetOwnerSid` 在本机约 379 进程时超过 30 秒，改为 CIM 一次读取进程元数据、Windows 原生只读 Token API 获取 SID；输出契约及安全边界不变。首轮超时明确失败关闭，不作为 PASS。

## DEC-20260930-537 — 运行时进程标记仅作交叉核验

- Phase/WBS：Phase2 / PLT-MAINT-01-A06-P02-P02-P01；编码前检查见 progress。Windows API 在配置验证后、Uvicorn 应用工厂运行前，Audit/Parser 在组合成功后，于受控 data_root 的独立运行目录写一次性 JSON：角色、PID、登记 UTC、包版本、运行代码树摘要、当前 SID/可执行路径；正常静止退出只移除本进程标记。仅用标准库与现有配置，不写数据库或公开 API。
- 标记不是安全边界：陈旧文件、运行中代码替换和具写权限的同账户进程均可能误导。OS PID/创建时间、SCM 服务身份/启动路径、数据目录 ACL、DB会话/文件句柄仍须外部核验。无法登记时拒绝启动；回滚停用组合，保留崩溃标记人工对账。

## DEC-20260930-538 — 标记与 OS 快照只读交叉核验

- Phase/WBS：Phase2 / PLT-MAINT-01-A06-P02-P02-P02。采用独立只读核验器，复用现有 OS CIM/Token 快照；严格限界读取受控 data_root 下的标记，不以标记存在或缺失推断进程安全。仅报告无 Secret 的状态、PID/角色与未知计数；任何冲突不自动终止进程或授权备份/迁移。
- 理由：自报标记独立于 OS 进程状态，必须核对真实 PID/SID/可执行文件、入口命令行及当前包版本/摘要；快照仍非原子，旧版/改名进程和同账户伪造仍需 SCM/ACL/句柄证据。影响限 Platform 诊断；无 Schema/API/依赖。回滚移除核验器与入口，不清理既有标记。

## DEC-20260930-539 — Windows 三角色采用待验证原生 SCM 宿主

- Phase/WBS：Phase2 / PLT-MAINT-01-A06-P02-P03。直接 `sc.exe create` 指向普通 Python CLI 不满足 SCM 协议；外部 WinSW/NSSM 增加供应链/许可与父子 PID 对账。选择 Python3.13 标准库 `ctypes` 的单角色独立进程宿主路线，先做可注入状态机及 Windows11 实机 PoC，再处理三角色与安装器。详细比较、服务账户/错误/回滚见 ADR-013 与 CR-PLT-004。
- 影响：无新依赖、Schema、API 或技术栈变更；服务宿主运行就绪与 STOPPED 必须由真实 SCM/PID/资源退出验证，设计不是 PASS。当前会话非管理员，不能安装或删除服务；失败回滚为不启用新宿主，旧 CLI/标记/审计保留。

## DEC-20260930-540 — API 服务仅在 Uvicorn 实际监听后就绪

- Phase/WBS：Phase2 / PLT-MAINT-01-A06-P02-P03-P02-A01。`service_windows` API 角色复用既有 bootstrap 与完整 Windows platform-write 工厂，延后重依赖导入到 SCM ServiceMain；使用 Uvicorn `Server.serve()` 的监听完成状态触发显式 ready，SCM stop event 请求正常 shutdown/lifespan 清理，标记覆盖该完整运行窗口。未知角色暂拒绝，不把 Audit/Parser 伪装为已接线。
- 理由：只在工厂创建时报告 RUNNING 会误判 socket 绑定失败；现有 `uvicorn.run` 信号 CLI 与 SCM STOP 生命周期不同。影响仅 Windows 入口，无 API/Schema/新依赖；回滚禁用服务入口保留旧 CLI。真实 SCM/目标账户/长流收敛仍待验。

## DEC-20260930-541 — Audit 服务停止窗口保持 SCM 待停心跳

- Phase/WBS：Phase2 / PLT-MAINT-01-A06-P02-P03-P02-A02。Audit SCM runner 使用既有 Windows 组合、运行标记、Loop `request_stop`/`run`/`quiescent`；停止桥只发送协作请求，长时间导出由非 daemon 状态线程每 10 秒更新 `STOP_PENDING` checkpoint。仅 `STOPPED` 结果且准入/heartbeat 静止、DB 已释放后返回；不强杀或以 DB 断线猜静止。
- 理由：原状态机只报一次 30 秒 wait hint，长导出可超时；原 CLI 信号桥依赖主线程，不可在 SCM ServiceMain 复用。影响限服务宿主内部，无 Schema/API/新依赖；回滚不启用 Audit 服务入口，保留原 CLI。SCM 实机/目标账户与故障注入仍待验。

## DEC-20260930-542 — Parser 服务拒绝活 heartbeat 静止误判

- Phase/WBS：Phase2 / PLT-MAINT-01-A06-P02-P03-P02-A03。Parser Step 续租线程改非 daemon，记住当前线程并在 `quiescent()` 中拒绝活线程；SCM runner 复用原 Windows Parser 组合和离线模型，STOP 协作等待解析/续租/DB 释放。未知 OCR 下层子进程不据此宣布已静止。
- 理由：原 `close()` 超时后 Step 锁可释放，但续租线程仍活，锁单独不是完整退出证据。影响限 Worker 安全关闭及 Windows 服务入口，无 Schema/API/新依赖；回滚不启用新服务入口，保留 CLI，不能移除安全检查后继续宣称静止。真实 SCM/目标账户/长 OCR/Server2025 待验。

## DEC-20260930-543 — SCM 实机受权限阻塞时先生成只读精确命令计划

- Phase/WBS：Phase2 / PLT-MAINT-01-A06-P02-P03-P03-A01。当前 Windows11 会话为中完整性级别、管理员组仅 deny-only，未见三款 PLM 服务，因此不尝试创建/修改 SCM。先用独立只读工具生成三固定服务的 `service_windows` 启动命令计划，严格校验解释器/配置路径并显式标记非安装、非停写证据。
- 理由：直接在无权限会话尝试真实安装无法取得 P03 验收证据，也不应把现有服务或账户误改。影响限发行准备，不改变业务/API/Schema/依赖；回滚删除未执行的计划工具即可。P03 实机安装、目标账户和资源静止继续待验。

## DEC-20260930-544 — Windows 服务安装使用原生 CreateServiceW 与显式账户

- Phase/WBS：Phase2 / PLT-MAINT-01-A06-P02-P03-P03-A02-P01。只允许三个固定角色、P03-A01 校验的本地绝对路径和显式非内置部署账户；调用 OpenSCManagerW/CreateServiceW 创建独立进程、手动启动服务。密码仅交互读取并以 API 参数传递，不进入 argv/env/`sc.exe` 命令行；失败不覆盖或自动删除服务，不自动启动。
- 理由：`sc.exe create` 把账户密码放在命令行会增加泄露风险；原生 API 可直接传账户凭据并明确 access/start/type。影响限安装入口，无业务/API/Schema/依赖；未运行时撤入口即可回滚，真实创建后的回退需核对精确服务归属/状态由受控管理员操作。当前非管理员会话只做模拟验证，正式 SCM/账户/ACL/启停仍待。

## DEC-20260930-545 — SCM 查询与资源静止许可分离

- Phase/WBS：Phase2 / PLT-MAINT-01-A06-P02-P03-P03-A02-P02-A01。只读 Win32 API 查询固定服务名的配置和状态，输出脱敏摘要。`RUNNING` 以外状态的 `dwProcessId` 不作可信 PID；STOPPED 不当作资源静止。该快照不授予备份/迁移，后续须同次 OS 进程/标记、句柄与 DB 会话收敛证据。
- 理由：Microsoft QueryServiceStatusEx 文档明确 STOP_PENDING PID 可能无效、STOPPED PID 永远无效，QueryServiceConfigW 返回的是保存配置而非运行中配置的强保证。影响仅诊断工具，无 Schema/API/依赖；回滚撤只读工具即可。真实服务/目标账户/Server2025 待验。

## DEC-20260930-546 — 用系统已安装服务验证私有 SCM 查询内核

- 日期/Phase/WBS：2026-09-30 / Phase2 / PLT-MAINT-01-A06-P02-P03-P03-A02-P02-A01-R1。公开 `read_service_observation` 继续只允许三个固定 PLM 角色；内部提取 `_read_name`，仅在测试中对系统 EventLog 服务执行只读配置/状态查询，不把它纳入产品清单或诊断许可。
- 理由：本机 PLM 服务均不存在，先前原生测试只能验证 OpenServiceW 的缺失路径，无法验证 QueryServiceConfigW/QueryServiceStatusEx 成功绑定。影响限内部适配和测试，无 Schema/API/依赖/服务修改；回滚撤提取/测试，保留公开固定角色查询。系统服务正向结果不证明 PLM 目标账户、PID 归属或资源静止。

## DEC-20260930-547 — 服务配置对账采取全字段精确失败关闭

- 日期/Phase/WBS：2026-09-30 / Phase2 / PLT-MAINT-01-A06-P02-P03-P03-A02-P02-A02。由只读命令计划产生期望 binary path，以明确目标账户和固定 own-process/manual-start/normal-error 参数比较 SCM 保存配置；任何缺失或差异均给固定原因码，不输出命令行、账户或路径，不把配置匹配当作运行时/静止证明。
- 理由：[Microsoft QUERY_SERVICE_CONFIGW](https://learn.microsoft.com/en-us/windows/win32/api/winsvc/ns-winsvc-query_service_configw) 列出这些保存配置字段；它们可用于安装定义对账，但不证明当前进程。大小写或账户名称规范化不猜测等价，首次采用严格字节级相等以避免错误放行；合法但表示不同的配置须受控调查。影响限只读 Platform 诊断，无 Schema/API/依赖/SCM 写入；可撤对账工具回滚，原服务和数据不变。

## DEC-20260930-548 — 现行后端 Windows 离线 wheel 集合只接受二进制依赖

- 日期/Phase/WBS：2026-09-30 / Phase2 / PLT-PKG-01-A01。沿 POC-01 已验证的 Windows Python3.13 方法，构建当前后端 wheel、解析其已锁版本依赖并仅下载 wheel，不允许源包现场编译；产物及 SHA-256 留在被 Git 忽略的本地构建目录，版本库仅记录脚本和脱敏验证摘要。以全新虚拟环境执行 `--no-index` 安装、`pip check`、最小导入与元数据版本检查。
- 理由：POC-01 的 109 文件 wheelhouse 证明当时输入，但当前 `apps/backend/pyproject.toml` 已有新依赖，不能直接当现版本完整发行集合。影响限打包前置，无架构/Schema/API/依赖版本变化；失败时保留诊断、不可标离线 PASS；回滚撤脚本和新生成的忽略产物，不触碰已安装系统或生产数据。此次 Windows11 成功也不代表物理断网、Server2025/Debian13 或完整发行 Gate 通过。

## DEC-20260930-549 — 前端离线构建使用冻结 lockfile 与独立 pnpm store

- 日期/Phase/WBS：2026-09-30 / Phase2 / PLT-PKG-01-A02。以 `git archive HEAD` 取当前已提交前端源，在新目录在线 `pnpm install --frozen-lockfile` 填充独立 store；另一份无 node_modules 的新源目录执行 `pnpm install --offline --frozen-lockfile`、测试、类型检查和构建。检查 lockfile 前后 Hash 与 dist Hash 清单；不复用当前开发 `node_modules`。
- 理由：现有开发目录构建通过不能证明依赖可从可搬运 store 重建；独立两阶段避免已安装依赖掩盖缺包。影响限打包前置和本地忽略制品，无业务/API/Schema/技术栈或依赖变更；失败不得称离线构建通过。回滚撤脚本与本次新建目录，当前前端工作树/历史文件不动。`--offline` 不等于物理断网，也不代表 Server2025/Debian13、静态站点部署或完整发行验收。

## DEC-20260930-550 — 候选载荷仅组装可校验开发制品并列出发行缺项

- 日期/Phase/WBS：2026-09-30 / Phase2 / PLT-PKG-01-A03。只把已验证 SHA-256 的当前 Windows11 后端 wheelhouse、前端 dist 和非 Secret bootstrap 示例复制到新建候选目录，生成逐文件 Hash 清单及 `release_eligible=false` 阻断列表；不加入本地 Secret/客户资料/开发者私钥/测试 License，不触发安装或 Migration。
- 理由：A01/A02 分别证明当前后端/前端依赖可由本机离线包管理器重建，但二者尚未合并，正式公钥、Python 运行时、PostgreSQL/pgvector、OCR 系统组件/模型、HTTPS 宿主/安装升级工具与三平台验收仍缺。先建立防篡改和缺项可见的载荷基础，避免误发半成品。影响限打包工具及忽略制品，无 Schema/API/技术栈变化；可撤脚本/候选目录回滚，不能将候选标记为正式交付。

## DEC-20261001-551 — Windows 私有 Python 运行时候选采用官方嵌入式发行包

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A05。选择 Python 官方 3.13.15 AMD64 embeddable ZIP 作为 Windows 私有运行时候选，固定发布页 SHA-256 并保留许可/版权通知；不复制开发机 Python 安装、不把第三方 wheel 直接当作嵌入式解释器可运行证明。
- 理由：嵌入式包为官方针对应用随附的发行形式，但不含 pip/Microsoft C Runtime；第三方包需由应用安装器旁装并验证。与 A04 已有 venv 安装不同，后续要单独证明 vendored 包、原生扩展和服务启动。仅内部打包形式选择，无冻结架构/Schema/API/技术栈变化；回滚撤未发行候选工具和忽略产物。未通过第三方许可清单、目标系统实测、完整安装/升级前不改变 `release_eligible=false`。

## DEC-20261001-552 — 非发行归档仅含运行所需文件且许可清单保持待审

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A07。新建独立候选 ZIP，只纳入 A06 私有 runtime（排除运行后生成的 `__pycache__` 与构建机 `packages/bin`）、A02 dist 和非 Secret bootstrap；生成逐文件 SHA-256、完整归档回读与从 ZIP 全新解包导入。第三方元数据清单对全部 93 项固定 `REVIEW_REQUIRED`，不凭 `License-Expression` 或许可证文件存在推定法律合规。
- 理由：旧 A03 候选缺 Python runtime，新 A06 已证明本机私有导入；旧/新来源仍非同一正式发行检查点，第三方/前端许可证及系统组件还缺。影响仅发行准备工具和 Git 忽略二进制，不改业务/API/Schema/技术栈；回滚可撤新工具与经确认路径的实验归档，不触碰旧 A03。正式发行需重建同源制品、逐项许可审查和三平台完整验收。

## DEC-20261001-553 — TIFF 升级预检先锁维护态并核 FileObject 字节

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A08-P09-P05-P03-A07-P03-P04。只读预检使用与 Platform 维护转换相同的 PostgreSQL advisory 排他锁，确认 `plt_maintenance_state=MAINTENANCE` 后，遍历全部登记的 `DOCUMENT` FileObject；采用已有 LocalFileStorage 的 Hash/大小校验快照，随后只读 TIFF 元数据。输出只含汇总计数与阻断状态，不导出客户路径/正文。
- 理由：单独指定 TIFF 文件容易漏掉改扩展名或多页文件，也不能证明存量覆盖；DB 登记清单与存储校验须一致，维护锁在扫描期间阻止正常 Admission 与状态切换。该锁仍不能证明所有非受管进程已停写，正式升级须另有服务/进程静止及人工备份证据。影响仅离线预检工具，无 Schema/API/正式 Parser 变化；回滚撤工具，不改 FileObject 或数据。

## DEC-20261001-554 — 升级恢复先在完整 Schema 隔离副本证明四类备份

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A08-P09-P05-P03-A07-P03-P04-P02-A01。以空库迁移至0051的本机独立PG18和纯合成 FileObject，分别保存 PostgreSQL dump、data、config、license 占位文件并逐件 Hash；JBIG 命中后不做升级动作，另在全新数据库/目录演练恢复与受损副本对照。
- 理由：单看预检返回阻断，无法验证发生升级故障时备份是否可读、业务元数据与本地文件是否一致。此项只证明隔离副本可恢复，不能替代正式人工备份、目标账户/进程静止、原机恢复及完整升级工具。影响仅测试脚本/忽略合成输出，无 Schema/API/正式安装变化；回滚撤脚本和验证输出，不影响既有程序与数据。

## DEC-20261001-555 — 升级从扫描至变更保持同一维护排他会话锁

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A08-P09-P05-P03-A07-P03-P04-P02-A02-P01。将现有只读 `audit()` 的锁生命周期抽为可复用的维护窗口对象；扫描仍在只读Repeatable Read事务中，但外层会话排他锁在扫描返回后持续持有，供后续升级门禁在复制/Migration前重复核维护状态和版本。旧一次性CLI行为保持。
- 理由：如果扫描结束就释放锁，后来服务可重新取得共享准入或状态被切回 RUNNING，扫描结果无法约束后续写操作。连续会话锁缩小此竞态；仍需独立验证服务/旧进程静止、备份和目标账户，不能单靠DB锁授权Migration。无 Schema/API/技术栈变化；异常时必须释放/使连接失效，回滚禁用尚未接入发行的升级窗口封装。

## DEC-20261001-556 — 目标服务未安装时不以诊断快照放行升级，转做完整候选合包

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A08-P09-P05-P03-A07-P03-P04-P02-A02-P02。当前本机无C:\PLMTool与三项固定PLM服务，现有进程/SCM入口明确为诊断级；因此不伪造正式备份/停写/Migration PASS。保持升级放行关闭，按持续执行规则转向独立的Windows11非发行端到端候选组装，统一93项旧候选与106项OCR运行时及固定原生组件/模型。
- 理由：一个无真实服务/目标账户的“已停写”布尔输入不构成可验证升级门禁；旧候选运行时缺13项OCR联合依赖，也无法作为可用包直接交付。影响仅任务排序与新非发行产物，原候选/冻结Schema/API/正式安装均不变。回滚保留旧候选与升级阻断，弃用新合包试验产物即可；License/NOTICE、真实质量、签名、目标平台与Gate仍不得假定通过。

## DEC-20261001-557 — 统一候选只复用旧包已核实的前端/配置/许可材料，替换运行时和Tesseract

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P01。固定五类本地输入及哈希；新包沿用旧候选的前端、示例配置和既有许可文件，不沿用93项运行时及顶层清单；以106项OCR运行时替换，旧OCR原生ZIP只取Ghostscript和tessdata，以34项无JBIG PE替换其旧Tesseract，其余模型来自固定模型ZIP。理由是旧Tesseract带JBIG依赖且旧Python少13项；混装或沿用旧manifest会使声明与实际字节不符。仅产生新非发行产物，历史候选不覆盖；逐件Hash/清洁解包失败即放弃新产物，许可/源码义务仍单独开放。

## DEC-20261001-558 — 当前Windows统一候选需ASCII安装路径，非ASCII路径不冒充可用

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P03。同一候选在中文仓库路径下Tesseract语言列举因字符转换退出3，ASCII新解包路径下四份合成PDF/A-2b/deskew均5/5通过；因此当前候选安装/升级流程应显式限制路径为ASCII，现行建议`C:\PLMTool`不受此限制。理由：仅修改Python输出编码无法解决原生Tesseract filesystem路径转换；无正式安装器可修改，先记录兼容限制并在后续入口失败关闭。若未来采用可核源的新Tesseract修复，须复跑四版面与非ASCII路径；不改冻结API/Schema，旧候选不覆盖，`release_eligible=false`。

## DEC-20261001-559 — 第三方证据先做精确字节差异，不以包内许可证文本替代法律复核

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P08。将93→106项Python及34项无JBIG原生、Ghostscript和模型证据写成固定输入Hash的机读差异清单；仅证明包内文本/来源矩阵位置及缺口，不自动生成“合规通过”。理由：嵌入式`.dist-info`的文本与元数据不等于独立NOTICE、对应源码或最终组合许可结论；旧93项侧载也不能代表新增13项。原冻结技术方案及候选不变，撤新审计工具/报告可回滚；需进一步产出精确侧载/源码交付材料和有资质复核，发行仍保持关闭。

## DEC-20261001-560 — 不把含PoC测试缓存的历史PG bundle直接升格为客户包

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P11。复用POC-02精确来源、PostgreSQL18.6/pgvector0.8.6运行文件和Server2025断网功能证据作为输入，但旧外层bundle含PoC源码及5项`__pycache__`/`.pyc`；选择重建最小非发行运行包，而非重命名旧bundle。理由：历史功能验证范围与客户发行清单/许可/正式账户不同，直接复用会混入测试产物并虚报完整交付。旧bundle保留历史，新包若失败可弃用；不改Schema/API/现网实例，发行门禁仍关闭。

## DEC-20261001-561 — PG运行旁包只选最小服务端目录和原始许可文本

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P12。按P11已核输入重建非发行 `bin/lib/share` 加三份服务器/命令行/pgvector许可文本的独立ZIP；旧PoC bundle、GUI、头文件、文档、数据和日志不进入运行旁包。理由：旧 bundle 含测试缓存，整套PG安装目录又含不需随服务端部署的GUI/构建部分，均不宜直接作为客户运行清单。每件Hash和新目录清洁解包是继续功能验证的前置，不代表许可发行批准或正式安装。若后续发现功能/许可缺件，保持现包历史，另建修订候选及差异；回滚弃用此Git忽略ZIP，无Schema/API/数据库改变。

## DEC-20261001-562 — PG隔离烟测不得捕获会被Windows子进程继承的启动管道

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P13。首次 `pg_ctl start` 已在 loopback 成功启动，但 Python 捕获的管道被后代进程继承而等待超时；正常停机/清理后，启动阶段使用空设备输出及单独日志检查，其他SQL步骤仍捕获结果。理由：保留 Windows 服务子进程生命周期可控和失败诊断，同时避免假性超时；仅改变非发行隔离测试脚本。若以后正式安装器复用该流程，须独立验证目标账户/SCM和失败恢复，不将测试入口结论当生产通过；回滚撤新脚本即可。

## DEC-20261001-563 — 统一候选与PG旁包先核零冲突，再新建组合候选

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P14。两个固定来源共21,103件逐字节核验后，大小写不敏感目标路径零冲突；PG只进入独立 `payload/pgsql/` 和许可前缀。选择新建非发行组合ZIP、重建顶层清单，而非将PG目录覆盖旧统一候选或继承其中“缺PG”声明。理由：来源、数量、许可和开放Gate均会变化，直接覆盖会失去可追溯性。此项仅只读计划，合包后仍需ZIP/清洁解包及真实产品链验证；回滚可放弃新候选，不改旧包/API/Schema/现有数据库。

## DEC-20261001-564 — 新组合包仅替换顶层声明，不继承旧候选“缺PG”语义

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P15。把P10/P12的21,103件原载荷保留，重建manifest与双来源许可库存，明确已有PG18运行字节但尚未正式安装/服务/许可发行。理由：沿用P10旧manifest中的“缺PG”会与新内容矛盾，直接删除所有缺口又会虚报发行完成。源ZIP/计划/新ZIP各固定Hash，新包仅非发行；若清单或门禁需调整，保留本版并另建修订包，回滚弃新候选，不改旧候选/Schema/API/既有DB。

## DEC-20261001-565 — 离线候选到Windows安装目录使用显式逐族映射

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P17。候选根含 `runtime/pgsql/frontend/ocr/config/third-party-licenses`，而Windows服务配置模板引用 `C:\PLMTool\app\models`；选择明确映射：Python→`runtime/python`、PG→`runtime/pgsql`、前端→`app/frontend`、OCR模型→`app/models`、Tesseract/Ghostscript→`app/ocr`、配置→`config`、许可文本→`app/third-party-licenses`。先仅在新ASCII Temp目录复制并按原载荷逐件Hash；只生成纯合成 `bootstrap.rehearsal.yaml` 验证服务命令计划，不改 `C:\PLMTool`、SCM、数据库或正式License。理由：直接原样解包无法满足模型配置目录，隐式搬运会使安装清单无法追踪。影响仅非发行装配验证；正式安装器须复用已验映射并另行核ACL/账户/签名。回滚弃用新临时装配目录及工具，历史ZIP/冻结Schema/API保持不变。

## DEC-20261001-566 — HTTPS同源边界候选须独立于三个PLM应用服务

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P18-A03；正式差异见`CR-PKG-005`。P18-A02证明静态文件和默认API在两loopback端口各自可用，但前端相对API路径与同源Cookie、冻结HTTPS边界在当前包内没有共同入口。选择先验证跨平台Caddy作为**独立Web边界候选**，保留API回环和三个PLM应用服务角色；不把Vite开发代理或标准库HTTP服务器当正式部署。理由：避免破坏现有Auth Host/Origin与安全监听边界；新增依赖/第四项外部服务的版本、许可、证书/ACL和离线三平台验收须单独完成。回滚弃用未投产PoC与新候选，不修改P15历史、冻结API/Schema；任何生产操作另需备份/服务静止。

## DEC-20261001-567 — Caddy先固定官方完整离线证据而不立即入包

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P19；依`CR-PKG-005`。固定官方`v2.11.4` Windows AMD64 ZIP/SBOM、buildable source及checksums四资产，核对发布 SHA-256 与逐件 SHA-512，并检查 EXE/许可/SBOM/源码对应；Windows输入审计已PASS。选择下一步先隔离HTTPS同源PoC、再做完整NOTICE/目标账户/三平台发行审查，不重写旧P15非发行ZIP。理由：字节可信不能代替路由/安全/法律与客户证书验证；可撤回候选而保留原冻结架构/API/Schema。具体结果见P19记录。

## DEC-20261001-568 — 错误Host使用同端口兜底站点显式421

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P21-A01；依`CR-PKG-005`。P20只看到错误Host状态200，最小Host回显确认空正文、不是首页；Caddy单主站无匹配时未提供拒绝状态。选择保留限定主站，并在同一HTTPS端口增加无主机名兜底站点，只返回421。合成回环真Caddy及固定随包重验：正常站点/路由不变、错误Host421、重复Host400。避免把静态泄漏误报为已发生，也避免把空200视为安全拒绝。回滚撤销非发行兜底配置即可，历史P15/API/Schema不变；生产登录与三平台仍独立验收。

## DEC-20261001-569 — HTTPS认证验收复用原真实PG/Vault断言并替换传输层

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P21-A02。为避免另写一个缩小版“登录成功”探针，保留`AUT-03-A07-P03`原有数据库/凭据/Session/审计断言，只把`TestClient`替成真正的Caddy HTTPS→回环Uvicorn传输，且PG使用新临时集群及唯一Vault目标。加错误Host/Origin/缺CSRF/Cookie标志与清理回读；结果仅合成Win11，非正式服务账户/客户证书/Gate。回滚撤销验证脚本，不改产品API/Schema或历史候选包。

## DEC-20261001-570 — Caddy进入新非发行全量候选而不改P15

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P22，依`CR-PKG-005`。从固定P15的21,103项逐件原字节复制，在新ZIP追加七项已固定Caddy二进制/许可/README/SBOM/checksums/buildable source及非敏感模板，重建顶层Hash/库存/非发行manifest。选择全量新候选便于后续清洁解包/安装映射验收，旧P15保持可追溯；不把整包Hash PASS升级为法律/安装/正式证书/Gate PASS。回滚弃用新候选，原冻结架构/API/Schema不改。

## DEC-20261001-571 — bce许可证通用正文仅作为复用审阅候选

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P43-A08。固定bce-python-sdk 0.9.79原wheel/sdist、P43候选及P33/P22谱系后，元数据声明Apache License 2.0，原wheel/sdist与候选均无bce独立通知；候选中Caddy侧载的通用Apache-2.0正文与官方正文同SHA-256。选择记录“现有正文可复用审阅”而不复制同字节文件或静默修改固定候选。理由：正文相同只证明文本可用，不证明bce版权归属、专属通知或组合发行义务。风险/回滚：只增只读审计及文档，可撤工具，历史包不变；合格法律复核/最终NOTICE、正式信任源和Gate仍开放，`release_eligible=false`。

## DEC-20261001-572 — 许可表达式空项按材料位置分类而不自动定性

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P43-A09。先固定P43/P33/P22与原生矩阵，再逐一核对60项空 `license_expression` 的名称/版本、精确包内 `METADATA`、嵌入通知及独立侧载；把材料分为 `EMBEDDED`、`SIDECAR_ONLY`、`NO_DISTRIBUTION_NOTICE`，若两类材料同时存在以嵌入类记录并仍保留侧载路径。理由：空元数据字段不能直接等同缺许可证，文本存在也不能等同许可义务完成。影响/回滚：只读工具和审阅清单可撤，固定候选/API/Schema/生产安装不变；所有行继续 `REVIEW_REQUIRED`，法律复核和最终NOTICE仍阻断发行。

## DEC-20261001-573 — 45项声明逐字匹配并与60项合并为105项审阅输入

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P43-A10。P43/P33/P22谱系和矩阵先验后，逐包比较45项库存 `license_expression` 与精确 `METADATA` 的 `License-Expression`，并要求每个 `License-File` 头映射到候选内真实嵌入文件；与既有60项合并，按名称/版本证明105项无重漏。选择保留原样 `AND`/`OR` 表达式和所有材料路径，不自动合并许可证、补写归属或将技术映射标为法律PASS。理由：文本声明、位置和组合分发义务是不同层次。影响/回滚：只增只读工具、测试与清单，固定包/API/Schema/生产安装不变；撤新材料不影响历史，法律复核与最终NOTICE仍阻断发行。

## DEC-20261001-574 — Server 2025宿主NAT地址偏差先登记再修复

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P44-A01。VMware Tools 可得来宾NAT地址，但3389/5985/5986/445不可达；宿主VMnet8实际为169.254/16，而DHCP/NAT配置要求192.168.27.1/24，当前令牌非管理员。选择先保留目标VM关机与所有既有宿主配置，登记`CR-ENV-001`，不尝试无权限网卡写入或把端口失败直接归咎来宾。理由：先恢复宿主路由前置，再区分来宾监听/防火墙问题，避免影响其他VM且避免假验收。影响/回滚：本项仅只读诊断，VM已正常关机至原状态；未来网络修复需记录其他VM影响及原配置回滚，Server 2025安装验收仍未通过。

## DEC-20261001-575 — 原生PE来源矩阵与包内许可通知分开审计

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P45-A01。P43/P33/P22和矩阵先验后核对34项包内原生PE字节SHA，再将61条矩阵许可文本哈希与候选内327条名称可识别的通知路径对照；仅3条在其他Python组件材料中出现相同正文，原生专属路径为0。选择先输出逐项证据及缺口，不从本机矩阵推断候选随包通知已足，也不修改固定ZIP或把`NO`升为已审结。理由：来源文本、同字节共享正文、特定组件归属和法律适用是不同证据层级。影响/回滚：只读工具和清单可撤，API/Schema/安装根/发行包不变；法律复核与最终NOTICE继续阻断发行。

## DEC-20261001-576 — 原生许可侧载只从固定归档成员取字节

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P45-A02。先重验P43候选与34项原生矩阵，再固定33项MSYS2二进制包来源和1项libtiff上游构建来源；61条矩阵许可记录必须从精确包成员或经归档Hash核对的上游tar直接读回相同SHA，包内文本还与本地已解包副本比较。结果为53包成员、7历史上游回退、1libtiff上游成员，42个不同正文Hash/34个固定归档。选择下一项只在新非发行候选按组件建立侧载，不覆盖旧P43，也不据此推断许可证适用或法律放行。理由：历史CSV路径或同名本地文件不能替代原压缩包字节证明。影响/回滚：只增只读核验/清单，API/Schema/现有候选不变；法律NOTICE和原生义务仍未审结。

## DEC-20261001-577 — 原生OCR正文去重侧载与逐PE映射并存

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P45-A03。依`CR-PKG-007`选择在新`NOT-FOR-RELEASE`候选内按正文SHA去重保存42份原始文本，同时保留61条逐二进制/来源映射和审阅说明；原P43 21,114项逐件不变。新ZIP SHA `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`，独立核验全量载荷/谱系/门禁通过。理由：字节共享不能替代具体组件归属，候选自带材料便于离线审阅，而不推定法律适用。影响/回滚：弃用新候选即可回到固定P43；无API/Schema/SCM/正式安装变化，`release_eligible=false`，法律NOTICE仍开放。

## DEC-20261001-578 — 新通知候选只在隔离Temp做清洁解包

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P45-A04。选择复用既有全量解包/Hash验证边界，仅为新候选kind增加白名单，并要求全新直接ASCII Temp目标。首轮预检因比较集合时丢失原名大小写而误拒绝，独立核对ZIP本身无缺漏；保留失败证据，修正预检并在另一全新目标重跑21,158载荷＋3元数据及61映射/42文本读回，真实退出0。理由：不得绕过来源、全集或Hash门禁，也不得在误拒绝后把同一临时目录当作清洁环境。影响/回滚：隔离目录可弃用，原P43与新ZIP均未修改；正式安装、法律与发行状态仍未通过。

## DEC-20261001-579 — 原生通知映射随隔离布局逐项核验

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P45-A05。沿用固定候选的全量映射及Windows目标大小写冲突检查，同时明确验证新增原生许可正文、审阅映射和README的目标路径；61条记录指向42份正文，再对目标文本逐一Hash。全新Temp布局21,161件Hash/全集/运行组件版本/合成Caddy模板均通过，映射SHA `9397c9891ea16840b163b8e88f5d3ef0b4aad22c2d502a0e2384667fb7d49784`。理由：ZIP中有材料不等于安装布局中可检索，且共享正文不代表各组件法律义务已审结。影响/回滚：仅隔离布局与工具，弃用布局即可；不触及正式根/SCM/DB/API/Schema，`release_eligible=false`、法律审阅仍开放。

## DEC-20261001-580 — 新通知候选网络读链复用隔离 HTTPS 边界

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P45-A06。选择先对新候选及隔离暂存/布局做全量来源、映射与Hash验证，再复用既有包内API＋Caddy回环合成HTTPS读链；不为审阅侧载新增公开路由，也不把合成证书写入候选。真实网络结果为首页/2资源、健康200、默认项目API404、SPA200、错误Host421，进程清理完成。理由：新增许可材料不得破坏原读链，但原生许可证据不应变成无需授权的公开内容。影响/回滚：仅临时进程/证书，终止即回退；无API/Schema/SCM/正式安装改动，`release_eligible=false`、法律审结仍待。

## DEC-20261001-581 — 随包登录验收保留原安全边界并注入新布局核验

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P45-A07。将P42合成登录验收器的布局核验与重建改为可选回调，默认仍执行原P33验证；新候选包装器注入P45完整谱系/21,161件验证和新布局重建，随后才创建合成公钥、临时PG/Vault和HTTPS子进程。真实登录/Session200、无License Project403、清理断言PASS，候选未修改。理由：源码级或默认404读链不足以证明新包内生产写模式实际能启动；同时不应复制另一套易偏离的凭据清理流程。影响/回滚：可撤销新包装器并恢复原P42默认调用，正式根/SCM/现有DB/API/Schema未动，法律/正式信任源仍阻断发行。

## DEC-20261001-582 — 暂停重复合成包验证并转向发行阻断关闭

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P46-A01。只读核对P45候选SHA/manifest及仓库发行证据后，确认候选仍缺产品级LICENSE/NOTICE、正式信任和目标平台/质量/Gate验收；`payload/runtime/LICENSE.txt`不能作为产品许可文件。选择先以当前候选整理产品级NOTICE审阅输入及逐门禁证据，而非继续增加同等合成冒烟次数。理由：P45-A03～A07已证明技术完整性与Windows11隔离启动，重复相同范围不能消除发行阻断。影响/回滚：仅审计文档/优先级，不改候选、API、Schema、SCM或正式环境；如新证据推翻分类，更新登记而不追写既有验证，`release_eligible=false`。

## DEC-20261001-583 — 原生 OCR 许可原字节另行同步为审阅输入

- 日期/Phase/WBS：2026-10-01 / Phase2 / PLT-PKG-01-A09-P46-A02。固定P45候选及祖先谱系先验后，将其原生OCR 42份文本、61条映射和README的精确字节导出到受版本控制的审阅目录，另写P45专属草案；P43历史NOTICE草案不改其固定基准。理由：仅存在于本机Git忽略区的大ZIP无法供远端审阅，且原文共享不能丢掉逐PE归属。影响/回滚：审阅源字节44项/354,131字节可从Git撤销但不改候选；无API/Schema/SCM/正式安装变化，所有`NO`/`REVIEW_REQUIRED`与`release_eligible=false`保持，法律签核仍待。

## DEC-20261001-584 — 新质量留出集保持原配额并失败关闭

- 日期/Phase/WBS：2026-10-01 / Phase2 / POC-03-R12-A01。新来源锁同时排除旧50条的ChunkId、正文指纹和同文档定位；真实本地预检合同0/7、技术协议1/8，不写新锁、不降低33/7/8/2配额，也不将方案库文件伪作合同或调研记录。理由：已有50条参与质量分析，复用旧证据或临时调整来源类型会破坏独立验收；机械排重亦不证明语义独立。影响/回滚：仅PoC工具和Git忽略的运行报告，无生产API/Schema/发行包变化；待补新材料后重跑，期间推进独立Evidence任务，Gate3与`release_eligible=false`不变。

## DEC-20261001-585 — 精确定位任务重入并更正旧任务指针

- 日期/Phase/WBS：2026-10-01 / Phase2 / EVD-01-A03-P02-A02。复核发现 PAR-01-A02 已完成，旧 EVD 精确定位前置中“无正式 Parser 结果”也已过时；选择下一项先建立 Document 所有的受权固定 ParseResult 读取 Port，再按真实节点类型逐项证明，不让 Evidence 直读物理路径或复用整文档 Hash 冒充精确位置。理由：现有 Parser/Document 已有成功结果和带定位节点，但 Evidence 仍只证明 DOCUMENT；SECTION/STRUCTURED_NODE 不能由已存在节点自动推定。影响/回滚：本次只读核查与任务指针修正，无代码/API/Schema/环境变化，旧结论当时的证据保留，Gate3不变。

## DEC-20261001-586 — Document 内部固定解析结果双重受权读取

- 日期/Phase/WBS：2026-10-01 / Phase2 / EVD-01-A03-P02-A02-P01。编码前选择在 Document 内部建立独立读取 Port：现有 DocumentReadService 先验当前用户/Scope/固定版本，Document 私有仓储只返回成功 ParseRecord 与精确 ResultRef 元数据；私有存储按 Hash/大小回读后，再复核用户授权、来源元数据和结果元数据是否相同。结果字节不经公开 API、不给物理路径，不让 Evidence 直接读 Document 表。理由：单靠 ParseRecord 成功状态或裸结果路径无法防止撤权、跨项目、版本漂移及结果篡改。影响/回滚：无 Schema/Migration/API/权限扩张，仅内部 Port；未装配时可撤代码，既有 ParseRecord 不改。验证计划为成功/伪造/篡改/撤权/漂移单元、实际 PG18 元数据查询与后端回归；未执行项不得记 PASS。

- 执行修正：原计划只复核 Document 元数据不能证明源文件真实字节，最终改为在结果读取前后调用现有 `PrepareDownloadService` 受权且完整性已验快照；Document 私有仓储和结果文件校验边界不变。定向7、隔离PG18成功/失败记录与真实私有结果篡改、后端1736（3既有跳过）及wheel通过。集成授权快照仍为合成 Port，未宣称真实生产账户组合或Evidence精确定位PASS；撤销新Port即可回滚，Schema/API不变。

## DEC-20261001-587 — Evidence 节点位置只按受权结果精确匹配

- 日期/Phase/WBS：2026-10-01 / Phase2 / EVD-01-A03-P02-A02-P02。选择由 Evidence Application 调用 Document 固定结果 Port，在结构化结果内找到且仅找到一条与请求 Locator 完全匹配的真实节点；STRUCTURED_NODE 还必须绑定当前 ParseRecordId 和 NodeId。正文指纹只取被证实节点原文，不沿用整文档 Hash；Parser 未产出的 SECTION 不降级为段落或文档。理由：类型合法不代表位置真实，多个节点复用同一位置会使引用歧义。影响/回滚：仅独立内部证明 Port，无公开 API/Schema/权限扩张；未装配时可撤代码。验证计划覆盖节点类型映射、错误、歧义、跨版本及上游授权失败；真实格式与完整 Gate 另验。

- 执行结果：定向7项、隔离PG18中Parser规范合成节点→私有文件/成功记录→Document受权结果→Evidence精确证明、后端1743项（3既有跳过）和wheel均通过；错误/歧义/撤权/篡改失败关闭。真实格式、实际账户授权组合、SECTION及完整Gate尚无证据，不能据内部PASS上推。无Migration/API，撤销未装配服务即可回滚。

## DEC-20261001-588 — 文本与 CSV 实际来源位置逐项复验

- 日期/Phase/WBS：2026-10-01 / Phase2 / EVD-01-A03-P02-A02-P03-P01。输入 Parser 固定策略/文本与 CSV 真实字节解析、Document 结果 Port 和 Evidence 节点证明；只验证纯合成临时文件，不外发客户资料。前置 P01/P02 内部 PASS。涉及 Parser/Evidence 已有合同及验证脚本，不增公开 API、实体、权限、Schema/Migration 或依赖。验收为文本 UTF-8/BOM/CRLF 的字符区间可回切且指纹一致、CSV 引号跨行与 A1 单元格可回查、空单元格不能成为有效 Evidence 但不拖垮同表非空节点、来源 Hash/歧义失败关闭。风险：只覆盖两种格式，不代替 Office/PDF/OCR 的精度或真实业务授权；回滚为停用新增验证，既有历史不变。

- 执行结果：真实临时合成TXT/CSV文件经Parser实际读取并逐节点回查，中文BOM/CRLF、跨行CSV、空单元格、源文件改写拒绝通过。修复Evidence将空CSV节点错误扩散为整份不可用，并按Parser Profile限定节点类型；定向8、后端1744（3既有跳过）、wheel通过。只覆盖两格式，正式账户/Office/PDF/OCR/Gate仍待；无API/Schema/迁移。

## DEC-20261001-589 — Office 三格式从实际文件独立回查节点位置

- 日期/Phase/WBS：2026-10-01 / Phase2 / EVD-01-A03-P02-A02-P03-P02。输入现有 DOCX/PPTX/XLSX Parser、已验 Document→Evidence 内部节点证明及已冻结 Locator 合同；前置文本/CSV 局部格式验证通过。仅生成临时纯合成 Office 文件，用独立 Office 读取库按段落、表格、形状、工作表单元格回查 Parser 节点，再核 Evidence 直接/结构化位置，不用客户文件或外部服务。不改生产实体、API、权限、Schema/Migration、依赖；风险是库级打开不等于 Microsoft Office 实际 GUI/UAT，也不能推及 PDF/OCR 或正式账户。回滚为停用验证脚本，历史证据保留。

- 执行结果：三份临时Office文件真实落盘/Parser读取后，DOCX段落/表格、PPTX形状/单元格、XLSX中文工作表/公式位置分别用独立库回查并经Evidence定位证明；脚本exit0、Office定向6/6。仅合成Python库范围，不据此记Microsoft Office GUI、真实客户文档或Gate3通过；无程序/Schema/API变更。

## DEC-20261001-590 — Evidence 候选创建同事务与重放原响应

- 日期/Phase/WBS：2026-10-01 / Phase2 / EVD-01-A03-P03-A02。输入 Gate2 冻结 Evidence Candidate、API-02 EVIDENCE_CREATE、现有 Document 固定版本/来源证明、Evidence 表、通用幂等收据及 Audit。编码前核对这些前置均存在；本次只完成内部 Service/Repository，不挂公开 HTTP。
- 决策：先在受权读取中证明整文档或解析节点，再于写事务重验当前 Session/CSRF/角色和固定 AVAILABLE 版本；整文档比较版本 SHA，节点证明另携带源文件 SHA 并比较。收据 reserve、Evidence insert、Audit append、收据 complete 同一事务提交。重放重新验证权限/来源，只返回同一 ID 与固定首次 `CANDIDATE` 响应；标签/摘录/位置/指纹须与原记录一致，后续资格状态不能污染原创建响应。不增加新 Schema 或改冻结 API。
- 理由/影响：防止证明与写入之间来源或权限漂移、重复 Evidence/Audit 及后续状态影响重放。仅 Evidence Application/Repository 与内部解析节点证明 DTO 增源 SHA；无 Migration、公开 API、架构或外部依赖变更。回滚为停用未装配的内部创建服务/仓储，已写历史 Evidence 不物理删除。
- 验证：单元 5 项覆盖创建/重放、撤权、Audit 回滚、节点源摘要漂移和输入拒绝；隔离 PostgreSQL 18 实际插入/收据/Audit 重放与失败回滚通过，临时库停止清理；全后端 1,751 项（3 既有跳过）通过。真实 Session/CSRF 组合、公开 HTTP、目标账户/三平台、Gate3 仍待，不得由合成 Access 推定生产授权通过。

## DEC-20261001-591 — Evidence 创建 HTTP 只作为可选装配

- 日期/Phase/WBS：2026-10-01 / Phase2 / EVD-01-A03-P03-A03。输入冻结 API-02 项目/全局 `EVIDENCE_CREATE`、S/L/C/I/A 控制、内部候选创建 PASS。选择两条明确路径的可选 FastAPI 路由，沿用现有可信 Origin、Session/CSRF、Idempotency-Key、严格 JSON 与安全响应；默认应用不挂载，生产组合根不接线。请求字段只含固定 Document/Version、typed locator、显示标签/可选摘录、可选 ParseRecord，不接收 actor/scope/eligibility 由客户端伪造。新增冻结错误码的运行映射；来源 SHA 漂移对外使用 `EVIDENCE_FINGERPRINT_MISMATCH`。
- 理由/影响：先验证 HTTP 合同与数据库写链，避免在正式信任源缺失时开放生产入口。仅可选路由、入口注入点、错误码与上一步内部来源漂移码校正；无 Schema/Migration、新依赖或冻结 API Breaking Change。回滚为撤销可选装配，默认 404 与既有历史记录不变。
- 验证：HTTP 合同 4 项覆盖默认关闭、项目/全局 201、Origin/Session/CSRF/Key、畸形/权限/License 映射；隔离 PostgreSQL18 合成 Session/Access 下的 HTTP→Service→Evidence/Receipt/Audit 创建/重放、撤权 404 和审计失败回滚；后端 1,755 项（3 既有跳过）通过。正式真实 Session/Document 来源组合、Windows Server 2025/Debian、正式 License 信任源及 Gate3 未验。

## DEC-20261001-592 — Evidence 只在 Windows 显式写组合挂载

- 日期/Phase/WBS：2026-10-01 / Phase2 / EVD-01-A03-P03-A04。输入 A02 内部候选创建、A03 可选 HTTP 及现有 DocumentRead/PrepareDownload/固定ParseResult私有存储、Auth Session/项目角色、License Guard、Audit/收据。选择仅在 `--platform-write` 的受信任组合中装配 Evidence 创建；默认登录专用与 `--platform` 只读不挂载。Document 文件和 Parser 私有结果都经 Document 所有的应用 Port 获取，Evidence 不直连 Document 表或路径。没有新环境变量、Secret 提供方式、Schema/API/依赖变化。
- 原因/影响/回滚：复用已有生产组合信任门禁，避免半装配入口；若目标账户密钥/License/数据根不可用，原组合根仍按既有失败关闭。回滚仅撤销新路由装配并保留历史 Evidence/Audit；不物理删除业务数据。
- 验证：全新隔离 PostgreSQL18 合成用户、真实 Session/CSRF 数据、PROJECT PM/外部用户、真实磁盘 Document、成功 ParseRecord/私有 Parser 结果、合成 License/Windows Vault 游标源；显式写模式整文档与真实节点 201、同 Key 重放、单条 Audit、外部用户和降权后重放404、License403，默认/只读404。临时库/文件/进程停止清理。仅 Windows11 合成信任源；正式目标账户凭据、公钥/可信时间、Server2025/Debian、性能与 Gate3 未验。

## DEC-20261001-593 — Evidence 元数据读取与来源 Viewer 分离

- 日期/Phase/WBS：2026-10-01 / Phase2 / EVD-01-A03-P04-A01。输入冻结 EVIDENCE_LIST/GET/VIEWER、DM-03 Evidence 历史保留、现有 Evidence 表与 Auth/Project/License 读取 Port；A02～A04 已完成候选创建。
- 决策：本项只建 Evidence 所有的受权元数据列表/详情 Port，按当前 Session、GLOBAL DeploymentAdmin 或 PROJECT 当前成员、License 和资源 Scope/ProjectId 过滤；分页以 `(created_at,evidence_id)` 稳定 keyset。列表/详情保留历史 Evidence 元数据（包括来源版本已撤销的可解释记录），不返回物理路径、正文或直接宣称来源可打开。Viewer 另项重新验证固定 DocumentVersion/定位指纹后才给受权 descriptor。
- 理由/影响/回滚/验证计划：历史 Evidence 不能被来源撤销抹去，但只持 ID 不等于有读取权限。仅内部读取服务/仓储，不改 Schema、冻结 API 或生产组合；可撤销未挂载 Port 回滚。验证项目隔离、全局角色、分页同时间戳、License 与异常失败关闭，并用隔离 PostgreSQL18 真实记录复验。未执行结果不记 PASS。

- 执行结果：内部 Service/Repository 已按当前 Session、Scope、PROJECT 四类成员/GLOBAL 管理员与 License 过滤，`(created_at,evidence_id)` keyset 读取，历史 Evidence 不因来源版本状态被元数据接口抹除；不输出文件路径/正文。定向 5 项、隔离 PostgreSQL18 真实 Session 与 3 个同时间戳记录逐页、跨项目/非成员/License 失败关闭通过；临时库停机清理。公开 HTTP/签名 cursor/Viewer 尚未完成，Gate3 不变。

## DEC-20261001-594 — Evidence 列表游标采用独立签名密钥

- 日期/Phase/WBS：2026-10-01 / Phase2 / EVD-01-A03-P04-A02-P01。输入 Evidence 元数据 keyset PASS、冻结 API 分页/Scope/Session 控制和现有 Document 游标设计。
- 决策：游标保存版本、Evidence 专属 family、Scope/Project、Session 摘要、查询页大小摘要及 `(created_at,evidence_id)`，以 Evidence 专用 32 字节 HMAC-SHA256 密钥签名；编码为无路径/正文/明文 Session 的 URL-safe token。当前账户密钥引用另项供给与备份验证，不复用 Document/其他游标密钥；生产路由接线前必须可解析，否则失败关闭。
- 理由/影响/回滚/验证计划：防止跨会话、跨项目和改页大小重放，且同一时间戳分页不漏/不重。仅 Evidence API 内部 Codec，无 Schema/Migration、冻结 API Breaking Change 或第三方依赖；未挂载可移除回滚。验证合法往返、逐字段篡改、跨会话/Scope/页大小、非规范编码及UTC位置；未执行不记 PASS。

- 执行结果：独立 HMAC-SHA256 Codec 已实现，位置时间规范化为 UTC 微秒，解码时重算规范 token 并拒绝篡改/跨会话、项目、Scope、页大小或密钥。定向 3 项通过；当前账户密钥引用、公开 GET/生产装配和 Gate3 均未完成。无 Migration/公开 API 变化。

## DEC-20261001-595 — Evidence 元数据 GET 采用可选挂载和最小投影

- 日期/Phase/WBS：2026-10-01 / Phase2 / EVD-01-A03-P04-A02-P02。输入冻结 EVIDENCE_LIST/GET、A01 受权元数据 Port 和 P01 独立签名游标；前置 PASS。
- 决策：新增项目/全局两组明确 GET 路由，严格 Host、Session、License/项目权限、查询参数和游标绑定；列表返回受限显示摘录，详情仅返回必要 EvidenceView 字段，不返回物理路径/正文。路由只可选注入 `create_app`，正式 Windows 组合须等待专用密钥目标账户来源和独立验收后再装配。
- 理由/影响/回滚/验证计划：避免未供给专用密钥时默认打开读取路径；非 Breaking 实现冻结 API，无 Schema/Migration/新依赖。可撤可选路由并保留历史记录回滚；验证默认 404、项目/全局权限、分页及恶意游标/未知参数、License 失败和隔离 PostgreSQL 真实记录。未执行不记 PASS。

- 执行结果：两组明确列表/详情路由已作为可选注入，列表短摘录、详情最小字段与强 ETag，默认应用仍404。HTTP合同4项覆盖双页、默认关闭、全局路径、Session/篡改/未知查询、License/资源错误；隔离PG18真实Evidence记录和底层真实Session/Project权限、合成HTTP Session边界的分页/跨项目/License链路通过。正式当前账户密钥与生产组合未接线；Gate3不变。

## DEC-20261001-596 — Evidence 游标密钥只读当前账户来源

- 日期/Phase/WBS：2026-10-01 / Phase2 / EVD-01-A03-P04-A02-P03。输入 P01 专用HMAC游标、现有 Windows 当前账户 SecretKeyProvider 与独立备份恢复工具。
- 决策：固定生产引用 `evidence-list-cursor-v1`，只读解析32字节 Vault 材料；无缺省硬编码、环境变量回退、自动生成或覆盖。测试恢复仅使用随机临时引用与独立临时备份，不操作正式引用。缺失/长度错误/访问失败使工厂启动拒绝，正式目标账户供给和恢复演练仍由 Release 安全任务验证。
- 理由/影响/回滚/验证计划：保持游标签名密钥独立并防止未供给时悄然开放 GET。仅新 Windows 工厂/测试，不改 Schema、冻结 API 或第三方依赖；撤销未装配工厂可回滚。验证固定引用选择、缺钥失败、临时 Vault 丢失与备份恢复后旧 token 解码；未执行不记 PASS。

- 执行结果：固定引用只读工厂已实现；定向2项含 Windows 当前账户临时随机目标的加密备份、删除、恢复与原 cursor 解码，测试目标最终删除。未读取、创建或覆盖正式 `evidence-list-cursor-v1`；正式目标账户备份/恢复未验，生产接线仍待。

## DEC-20261001-597 — Evidence 读取组合缺独立密钥时仅关闭该路由

- 日期/Phase/WBS：2026-10-01 / Phase2 / EVD-01-A03-P04-A02-P04。输入 Evidence 可选 GET、Windows 独立密钥工厂与现有显式平台组合；正式 Evidence 固定引用尚未供给。
- 决策：在 Windows `--platform`/`--platform-write` 组合中尝试解析 Evidence 独立游标签名密钥；可用时挂载受权列表/详情，不可用时 Evidence GET 保持404，不影响既有 Document/Project 等路由启动。此为单能力 fail-closed；不得复用其他密钥或自动生成测试材料。默认登录专用模式仍不尝试挂载。
- 理由/影响/回滚/验证计划：直接使整个已部署平台因新增 Evidence 功能缺钥而无法启动会破坏既有能力；仅关闭未完成密钥供给的新能力更符合逐模块交付和安全边界。无 Schema/Migration/API Breaking Change；回滚撤 Evidence 注入，历史记录保留。隔离PG18合成密钥下验真实Session/项目权限与分页；缺钥时 GET404、旧路由不退化。正式目标账户密钥和恢复依旧 Release 阻断，不据合成验收放行Gate3。

- 执行结果：Windows 显式平台读/写模式在 Evidence 密钥可解析时挂载 GET，缺钥仅该 GET404，Document GET200 保持；登录专用模式不挂。隔离PG18合成当前账户密钥、真实Session/Project和Evidence写后读取、CustomerMember降权保留读取、外部用户/License拒绝通过。因只读模式已存在同路径GET，未挂POST时返回标准405而非旧404；方法仍关闭，冻结API明确GET/POST分别受控。临时库/文件停止清理；正式目标账户密钥、Server2025/Debian/Gate3仍未验。
# DEC-20261001-598：Viewer 必须固定创建时的 ParseRecord

- 来源：`EVD-01-A03-P04-A03-P01` 前置核查；正式偏差见 [CR-EVD-002](../changes/CR-EVD-002-fixed-parse-provenance.md)。
- 证据：非 `DOCUMENT` 创建需要 `parse_record_id` 并证明，但 Evidence 表未保存；同一 DocumentVersion 允许多次成功解析，最新结果无法作为旧证据的唯一来源。
- 决定：新增内部 nullable 固定来源列；新非整文档证据同事务持久化，Viewer 只复验该来源；旧无确定来源记录失败关闭，绝不猜测回填。公开冻结 locator/API 不变。
- 状态：决策已记录，Schema/代码/测试尚未完成；Gate 3 不变。

# DEC-20261001-599：模板 Evidence 首版资格必须按来源用途保守处理

- 来源：`EVD-01-A04-P01` 编码前核查；正式偏差见 [CR-EVD-003](../changes/CR-EVD-003-template-eligibility-context.md)。
- 证据：冻结模型禁止模板独立成为客户事实，冻结资格 API 却没有 Binding 用途；当前 Evidence 事务也缺受权 Document 类别/固定版本 Port。
- 决定：先补 Document 同事务来源事实 Port。首版模板只保留候选/结构参考或判为不合格，不允许直接升为 ELIGIBLE；非模板资格必须复验当前来源、权限与固定版本。原冻结提交不追写，后续实现和验收分别登记。
- 影响/回滚：不变更公开 API 或现有行；后续若有历史模板 ELIGIBLE，只读清点并人工复核，不自动改写。可关闭尚未开放的资格路由，保留审计历史。当前仅完成决策，Gate 3 不变。

# DEC-20261001-600：资格未知回执采用原操作者收据回查

- Date/WBS：2026-10-01 / EVD-01-A04-P03-A08-P06；CR：[CR-EVD-004](../changes/CR-EVD-004-eligibility-operation-lookup.md)。
- Decision：以请求体中的原操作号，在当前 Session/CSRF/License/角色/Evidence Scope 复验后只读查询同 actor/project/operation 的已完成收据；未见收据只能返回 `UNCONFIRMED`。不扩大 CustomerManager 审计权限，不在浏览器持久化理由或自动重发。
- Reason/Impact：现有 Audit 无操作号，当前 Evidence 状态不是首次回执；新路径是 V1 非 Breaking API Scope 增量，原冻结提交不变。
- Rollback/Verification：关闭可选路由并保留历史；按 CR 验收只读、权限、并发、事务、HTTP/平台/前端及真实浏览器。当前仅设计登记，不标实现 PASS。

# DEC-20261002-601：复用非发行包 HTTPS 生命周期做持证 Workflow 网络验收

- Date/WBS：2026-10-02 / `WFL-01-A08-P07`。
- Decision：在既有固定候选双隔离布局、包内 Python/PG18/Caddy/Vault 生命周期脚本上增加**仅测试用的可选回调**。回调在进程内瞬时签发合成 License 文档，测试脚本删除私钥引用后才进入运行链；基础烟测默认路径保持不变。持证回调只在一次性数据库种入合成 License/Project/Workflow，随后经外部 HTTPS 调用 GET/START 并核 DB Audit/收据。
- Reason：复制整个安装/凭据/进程/清理逻辑会产生第二套不一致的安全边界；调用既有纯测试扩展点使固定候选不变，仍能隔离客观网络链路。合成签名不构成正式发行信任或客户业务事实。
- Impact/Rollback：仅测试工具、验证脚本及记录；不改变产品 API、Schema、依赖、包或正式账户。可关闭可选回调并保留基础脚本；无数据迁移。回调输入/返回值不得记录私钥、密码、客户数据。
- Verification：错误候选/缺回调/回调返回畸形拒绝；完整 ZIP SHA/布局哈希、HTTPS 初态/首启/同 Key 重放/权限与 CSRF 拒绝、单份 Audit/收据、无 StageTransition，合成 Vault/进程/目录清理。若合成信任或测试环境失败，不宣称 Gate/浏览器通过。
- Result：成对回调/畸形签名拒绝单元与原基础防护共 5/5；固定当前 ZIP 的双布局/包内 Python、PG18、Caddy 及合成 License 经外部 HTTPS 完成 Workflow GET 初态、START、同 Key 重放、CSRF/新 Key 拒绝和单 Audit/收据，清理标志及事后目录/进程复查 PASS。仅合成 Windows 11；正式信任/浏览器/Gate 均未验，详见 `docs/progress/wfl-01-a08-p07-packaged-licensed-https.md`。

# DEC-20261002-602：ParseRecord 固定来源采用调用方事务共享锁

- Date/WBS：2026-10-02 / `WFL-01-A07-P03-A01`；来源 `CR-WFL-005`。
- Decision：在 Document-owned `SqlAlchemyParseResultReadRepository` 增加与普通 `get` 分离的 `get_for_trace`。复用同一 Scope/Project/DocumentVersion/成功 ParseRecord 与 ResultRef 完整条件，但在**调用方已开启的事务**对两行执行 PostgreSQL `FOR SHARE OF`，并强制刷新 ORM 已加载对象。只返回最小固定元数据，绝不输出存储路径到 Workflow/API。
- Reason：现有 `get` 是普通只读，独立事务无法阻止固定来源在 Workflow 记录提交前变化；把仓储锁入口单独命名能避免普通列表读意外加锁，同时为后续 Document 应用 Port 提供可组合事实。
- Impact/Rollback：无 Schema、公开 API、依赖或既有 `get` 行为变化；未接 Workflow。可撤独立入口并维持 Checklist 写路由关闭。验证 SQL 锁形、项目/状态范围、无活跃事务拒绝及实际 PG18 并发阻断；后续应用 Port 仍需真实文件/解析内容哈希和权限重验，本任务不宣称完整 Owner。
- Result：新单元 2/2、隔离 PG18 对 ParseRecord 与 ResultRef 的第二连接 `FOR UPDATE NOWAIT` 均返回 55P03；原解析结果完整性/撤权/篡改矩阵回归退出 0，后端全量 1832 通过/3 跳过，本地 wheel PASS。仅仓储锁入口，应用 Owner 仍待接。

# DEC-20261002-603：Document 固定来源证明组合受锁事实与物理字节复验

- Date/WBS：2026-10-02 / `WFL-01-A07-P03-A02`；来源 `CR-WFL-005`。
- Decision：Document Application Port 先在调用方事务获取受权 Document/Version/File 事实及可选 ParseRecord/ResultRef 共享锁，再调用既有受权物理快照/解析结果读取复验；所有固定 ID、Scope/Project、源与结果摘要、解析器元数据必须与受锁事实一致。内部结果只返回最小来源事实和隐藏 repr 的解析字节，不返回文件路径。无 ParseRecord 时仍验证实际文件；有 ParseRecord 时复用现有解析读取对文件、解析 JSON 和结果字节的双读/哈希校验。
- Reason：避免在 Workflow 跨模块复制 Document 授权/存储校验；锁定数据库事实直到调用方提交，独立物理读取的结果只能在同一锁定事实下被接受。文件系统无法参与数据库锁，此 Port 表示读取时通过哈希的物理快照，不承诺提交后的文件永不变化。
- Impact/Rollback：只新增内部 Document Port 与测试，无公开 API、Schema 或数据迁移；可不装配后续 Evidence Owner，Checklist/Gate 写入口保持关闭。GLOBAL 项目经理窄标准引用授权、Evidence 资格/locator 和 Review/例外 Owner 均另行实现，本任务不宣称完整端到端 PASS。
- Verification：单元覆盖同事务调用/权限失败/版本或解析元数据漂移/物理文件或解析字节篡改/无解析情形，隔离 PG18 验证真实源锁与组合结果，后端全量回归和 wheel 构建。若任一复验失败，返回稳定错误码且不泄露正文或路径。
- Result：内部组合 Port 定向 6/6（含原读取回归共 16/16）；隔离 PG18 对五张来源表的第二连接 NOWAIT 均 55P03，实际本地文件/解析 JSON 哈希、错误 Scope/失败记录、撤权与篡改拒绝通过；后端全量 1838 通过/3 跳过，开发 wheel 构建 PASS。仅 Document Port，Evidence Owner 与窄 GLOBAL 策略未接，Checklist/Gate 写仍关闭。

# DEC-20261002-604：Evidence 当前可引用来源采用独立只读共享锁快照

- Date/WBS：2026-10-02 / `WFL-01-A07-P04-A01`；来源 `CR-WFL-005`。
- Decision：Evidence 模块增加单独的内部 `get_for_trace` 来源仓储入口，调用方事务对精确 Evidence 行执行 `FOR SHARE OF` 并刷新 ORM identity map；只接纳指定 Scope/Project 且当前 `ELIGIBLE` 的行，输出固定 Document/Version/ParseRecord、locator、fingerprint 与 lock version。普通 Evidence `get/list` 和资格状态变更入口不改，不在此处证明 locator 所指物理内容。
- Reason：现有 Eligibility `lock` 用于写决策且不含定位与固定解析来源；普通 Read 非事务锁。独立只读入口避免把创建时曾经 ELIGIBLE 或缓存中的旧事实当成 Workflow 提交时仍有效的来源，并减少对人工作业锁语义的影响。
- Impact/Rollback：内部 DTO/仓储增量，无 API、Schema、Migration、权限或数据迁移；不装配下游 Owner 即可回滚。下一任务仍须授权、Document 物理证明和 locator/fingerprint 比对，尤其窄 GLOBAL 标准引用；Checklist/Gate 写入口关闭。
- Verification：单元验证 SQL 共享锁、Scope/Project/ELIGIBLE 条件和非活动事务拒绝；隔离 PG18 验证当前资格、缓存刷新、第二连接 NOWAIT 冲突及事务释放后更新、错误范围/撤销拒绝；全量后端与 wheel。任何缺项不宣称完整 Owner PASS。
- Result：定向 2/2；隔离 PostgreSQL 18 中 Scope 错配/CANDIDATE/REVOKED 均不可读，已加载 ORM 旧实例刷新至新 lock_version，第二连接 `FOR UPDATE NOWAIT` 得到 55P03，事务释放后状态修改成功；后端全量 1840 通过/3 跳过，开发 wheel 构建 PASS。物理来源及项目经理窄 GLOBAL 权限仍在后续任务。

# DEC-20261002-605：PROJECT Evidence Owner 复用受锁 Document 结果并原位核对定位指纹

- Date/WBS：2026-10-02 / `WFL-01-A07-P04-A02`；来源 `CR-WFL-005`。
- Decision：Evidence Application 增加仅供调用方写事务使用的 PROJECT 来源 Owner。先用当前 Session 与 ProjectId 锁定 ACTIVE 项目经理，再读取同项目当前 ELIGIBLE Evidence 共享锁快照；调用 Document 固定来源 Port 在相同事务验证 DocumentVersion/File 与可选 ParseRecord/ResultRef 及物理字节。解析节点复用现有 Evidence locator/节点校验逻辑对 Document 已验证的结果字节做原位证明，不再独立打开一套来源；整文档只接收 `DOCUMENT` 且无 ParseRecord。比较最终 locator、指纹、固定版本与受锁记录，向下游仅返回最小观测事实。
- Reason：普通 Evidence Viewer 跨独立事务，不能作为 Checklist 提交时的来源凭证；重复读取 Parser 字节也可能脱离已锁事实。此组合维护模块边界：Document 证明物理来源，Evidence 验证定位器/指纹，Project/Session 提供当前调用者权限。
- Impact/Rollback：内部 Application Port 与既有解析节点校验复用，无 API、Schema、Migration 或普通读取授权变化；可不装配后续 Workflow。GLOBAL 标准引用另有窄授权任务，Review/例外 Owner 未齐前 Checklist/Gate 写继续关闭。
- Verification：单元覆盖全链正反例/隐私；隔离 PG18 的真实事务、真实私有文件及解析结果，撤权/篡改/并发拒绝；后端全量与 wheel。无客户或生产数据。
- Result：新增 Owner 单元 6/6、既有节点解析回归合计 15/15；隔离 PostgreSQL 18 合成 PROJECT 节点与整文档均通过，Owner 持 Evidence/Document/Version/File/ParseRecord/ResultRef 六行共享锁，跨项目、源文件/解析结果篡改与撤销拒绝；后端全量 1846 通过/3 跳过，开发 wheel PASS。会话/角色在单元与已检查假端口验证，尚未装配实际 Workflow/生产 Session；窄 GLOBAL 与 Review/例外 Owner 仍开放。

# DEC-20261002-606：GLOBAL 标准引用以独立内部 Port 验证而不放宽普通读取

- Date/WBS：2026-10-02 / `WFL-01-A07-P04-A03`；来源 `CR-WFL-005`。
- Decision：Document 模块新增只供受控业务引用的 GLOBAL 标准证明 Port，以当前 Session 和目标 ACTIVE 项目的 PROJECT_MANAGER 身份入调用方事务；仅查询并锁定 GLOBAL `STANDARD_CAPABILITY` 的 Document/Version/File 与可选 ParseRecord/ResultRef，校验实际私有文件和解析结果字节，输出不含路径的固定来源事实。Evidence 模块按同一项目经理身份锁定当前 GLOBAL ELIGIBLE 行、调用该 Document Port 并核 locator/fingerprint，最终返回目标 ProjectId 与 GLOBAL 来源的最小观测事实。普通 GLOBAL list/get/download 的 DeploymentAdmin 校验不改，不给 PM 通用文档正文。
- Reason：借用普通 GLOBAL 读取要求给项目经理部署管理员权限，会扩大信息边界；仅存 UUID 或仅验证 DB 元数据不足以证明来源完整。独立 Port 让来源证明在调用方事务内且不公开通用浏览能力。
- Impact/Rollback：内部 Application/DTO 增量，不改 API、Schema、数据或既有 GLOBAL 读取；若失败不装配 Workflow 并保持 Checklist/Gate 写关闭。只认 `STANDARD_CAPABILITY`，其他类别继续拒绝。验证合成 PG18/本地存储、权限及篡改，再处理真实 Workflow/Review/例外 Owner；正式信任和目标环境另验。
- Result：新单元 6/6，隔离 PostgreSQL 18 合成 GLOBAL 整文档及固定解析节点持六表共享锁、普通 GLOBAL 项目经理读取仍拒绝，跨项目/撤销/实际文件及解析字节篡改失败关闭；后端全量 1852 通过/3 跳过，开发 wheel PASS。仅内部来源证明，实际 Workflow 写链、Review/例外 Owner 与正式目标环境仍未验。

# DEC-20261002-607：Workflow Evidence 观测只接受实际 Owner 的显式 Scope 证明

- Date/WBS：2026-10-02 / `WFL-01-A07-P06`；P05 缺 Review/例外 Owner 保持阻塞。
- Decision：Workflow 内部适配按显式 PROJECT/GLOBAL 分别调用 P04 已验证 Owner，并在相同调用方事务核 EvidenceId、目标 ProjectId、Scope、ELIGIBLE、版本及指纹；只生成最小 `ChecklistBasisObservation`，不提交事务、不判 Review/例外/Gate。未知范围和异常失败关闭。
- Reason：避免 Workflow 复制跨模块文件/解析/授权逻辑，亦避免用历史 UUID 或客户端观测值充当事实。P05 缺真实业务 Owner，不能以临时实现开启 PASS/WAIVED。
- Impact/Rollback：内部接口/测试，无 API、Schema、依赖或数据迁移；不装配适配器即可回滚。后续真实写链必须重新验证 Session/License/CSRF、Review/例外、Audit/收据及并发；静态 Review 快照不代替客户确认。
- Verification：定向单元5/5、后端1857运行/3跳过、wheel构建PASS；本项无新的PG写事务/浏览器/目标平台验收。

# DEC-20261002-608：Trace 单跳读取在每条边的两端重新证明访问权

- Date/WBS：2026-10-02 / `TRC-01-A06-P01`；冻结 AF-02/DM-03/API-02 的 Trace 查询与逐节点授权。
- Decision：内部 PROJECT 单跳查询先验证当前 Session/License/项目成员及起点 Owner，随后在同一事务读取指定方向、指定项目的 ACTIVE 边；每条候选边两端逐一调用显式注册 Owner，缺失/无权边完全省略，内部故障整体失败关闭。用有界原始候选窗口与布尔 `truncated` 标记，不返回隐匿对象详情或数量；不装配外部 Graph API。
- Reason：Trace 行的 UUID 与 Scope 不能证明目标仍可访问；只验起点会泄露无权节点。后续完整多跳/游标仍可沿用同一逐边授权原则。
- Impact/Rollback：仅内部读取 Application/Repository 及项目只读操作策略，无 Schema/Migration/外部 API/依赖变更；不装配该服务即可回滚。旧边不迁移，历史继续保留。
- Verification Plan：单元覆盖起点/项目/License拒绝、两端撤权、跨项目、未注册 Owner、错误/异常、候选窗口；隔离 PG18 验证 ACTIVE/Scope/方向/上限与当前权限。全量后端和 wheel 后判内部任务结果；不声称多跳、HTTP、目标平台或 Gate 通过。
- Result：内部单跳单元6/6、隔离PG18真实会话/上下游/项目隔离/撤权隐藏/License拒绝及旧创建回归PASS；全量后端1863运行/3跳过、开发wheel PASS。首次全量旧策略总数断言失败，更新矩阵后重跑通过；未挂公开图API。

# DEC-20261002-609：Trace 多跳遍历采用同事务 BFS 与显式资源预算

- Date/WBS：2026-10-02 / `TRC-01-A06-P02-P01`；输入冻结 Trace Graph 最大深度/节点与逐节点授权、P01 单跳受权读取。
- Decision：在一次 Session/License/Project 授权事务里从已证明起点按广度优先遍历；每条候选边继续证明两端。节点去重防环；原始候选每节点最多 101 条、返回节点最多 500、返回边另设最多 2000 的安全预算，触及预算或过滤无权边均标 `truncated`。不返回无权节点身份/计数，异常不降级成空图。稳定游标/页作为 P02-P02 单独任务，在其完成前不挂公开图 API。
- Reason：跨事务拼接单跳结果会让授权与图状态漂移；无限广度/密图会耗尽数据库与响应资源。额外边预算属于内部安全上限，未改变冻结公开参数。
- Impact/Rollback：内部 Trace Application 增量，无公开 API/Schema/Migration/依赖及历史数据变更；不装配多跳服务即可回滚。此结果是有界部分图，不代替完整可续页图或客户业务事实。
- Verification Plan：单元验证多跳顺序、环、深度、节点与边上限、隐藏节点与根撤权、项目/License/Owner错误；隔离PG18验真实多跳/撤权。后端全量与wheel通过后只判内部遍历PASS。
- Result：定向7项、隔离PG18两跳/深度/撤权隐藏及旧创建回归PASS；边预算孤立节点缺陷已修复并重测；后端1870运行/3跳过、开发wheel PASS。稳定游标/公开图API仍未完成。

# DEC-20261002-610：Trace 有界图游标绑定查询与当前可见图指纹

- Date/WBS：2026-10-02 / `TRC-01-A06-P02-P02`；输入冻结图查询 `cursor/max_depth/max_nodes` 与 P02-P01 同事务逐节点受权结果。
- Decision：内部页服务每次以当前 Session/License/Project/Owner 重新计算同一有界可见图，再按固定 BFS 边序分页；专用 32 字节 AES-256-GCM 游标以 Session 摘要、Project/固定起点、方向、关系、深度、节点与页大小作 AAD，密文只含位置、可见图指纹和15分钟时效。下页图指纹不匹配则拒绝续页并要求重查，不能将过期授权快照继续输出。游标只覆盖本次预算内图；若基础图 `truncated=true`，最后一页仍保留截断标记，不暗示可续出全部边。
- Reason：裸 offset/客户端 BFS 状态既可篡改又会在边或权限变化时漏读/重复；持久化服务器快照将增加Schema/数据留存。对最多500节点/2000边的当前受权图重新计算并比较指纹可在无新表的条件下失败关闭。
- Impact/Rollback：内部 Trace Application/游标Codec 增量，无公开API/Schema/Migration/历史数据修改；不装配页服务即可回滚。生产独立密钥的目标账户供给/备份恢复在正式HTTP组合前另验，测试密钥不得当生产来源。图底层预算截断、不同Owner尚未注册、正式安全/性能/Gate仍开放。
- Verification Plan：单元覆盖正常续页、密钥/Session/Project/查询篡改、TTL、图/权限变化拒绝、页节点不泄露、截断语义；隔离PG18真实两页、撤权或状态变化后旧游标拒绝。全量后端与wheel后仅判内部可续页PASS。
- Result：定向6项、隔离PG18两页/撤权旧游标拒绝/新截断图及旧创建回归PASS，后端1876运行/3跳过、开发wheel PASS。仅内部合成密钥，正式目标账户密钥及公开图API未验。

# DEC-20261002-611：Trace 图游标使用独立 Windows 当前账户只读密钥引用

- Date/WBS：2026-10-02 / `TRC-01-A06-P03-P01`；输入 P02-P02 专用 AES-GCM 游标、既有 Windows SecretKeyProvider/交互供给和 CR-TRC-002 未开放HTTP的时序边界。
- Decision：新增固定 `trace-graph-cursor-v1` 引用的 Windows 只读组合入口；只从当前进程账户 Credential Manager 解析精确 32 字节，缺失、错形或Provider异常立即拒绝装配。不复用其他Cursor/Secret/License密钥，不在运行时生成或回退到环境变量/文件。实际正式账户的交互供给与离线备份/恢复留发行前置。
- Reason：测试合成 key 不能成为生产来源，Trace 游标与其他业务游标签名域须独立；复用受检的当前账户Vault生命周期避免引入新密钥存储方式。
- Impact/Rollback：仅组合入口和测试，无Schema/Migration/API/依赖/历史数据变更；不装配入口即可回滚。通用图HTTP仍因 CR-TRC-002 的Owner解析缺口关闭。
- Verification Plan：假Port精确引用/缺失/错长/异常单元，Windows11唯一临时Vault引用做加密备份、删失、错口令拒绝、恢复后旧游标可解；最后清理仅自己的测试凭据，不触碰正式引用。全量回归与wheel通过后只判本机来源PASS。
- Result：定向3/3、Windows11当前账户唯一临时Vault凭据供给/加密备份/删失/错口令拒绝/恢复旧游标/最终清理PASS；后端1879运行/3跳过、开发wheel PASS。正式KeyRef未供给，通用图HTTP未装配。

# DEC-20261002-612：DOC-02 三字段引用由 Document Owner 在同事务解析

- Date/WBS：2026-10-02 / `TRC-01-A06-P03-P03`；`P03-P02` 通用图HTTP前置核查BLOCKED，依据CR-TRC-002逐Owner实施。
- Decision：Document Owner 仅对冻结三字段DOC-02引用做内部解析：由Document自有仓储在调用方事务内只读定位真实Scope/Project，若PROJECT必须与路径ProjectId相等；随后沿现有当前Session/License/Document授权及固定Version/File受锁证明，返回内部完整TraceVersionRef。身份定位结果不对HTTP单独投影；未注册类型/失配/无权统一失败关闭。GLOBAL仍走原Document Admin授权，不把路径ProjectId推断为Scope。
- Reason：客户端没有Scope字段，不能靠猜测或添加冻结合同外必填字段；Trace模块不得直接查询Document私有表。此项只建立一个真实Owner，不宣称通用HTTP完成。
- Impact/Rollback：Document内部只读Port及Trace组合层增量，无公开API、Schema/Migration、依赖或历史数据改写；不装配解析Port即可回滚。未来其他Owner各自接线并验全套网络安全合同后方可开放通用HTTP。
- Verification Plan：单元验证同事务精确传参、PROJECT/GLOBAL授权、错误Scope/Project/Version/无权与异常掩码；隔离PG18验证真实Document/Version/File和当前Session权限，后端全量及wheel。正式目标账户密钥/三平台/性能/UAT/Gate另验。
- Result：新单元6项、Trace Owner定向总7及Document解析4均PASS；隔离PG18现有Trace创建/图验证扩展真实PROJECT/GLOBAL、跨项目/无权/不存在版本、受限File与过期License拒绝后PASS；后端全量1885运行/3跳过，开发wheel SHA-256 `84a2bbcf14532c70d15ac4d28dd321cec8b6775d97a8e783399cb6a8bc32ec9b`。通用HTTP仍关闭，其他Owner及正式密钥未验。

# DEC-20261002-613：TraceLink 状态强 ETag 使用数据库拥有的版本

- Date/WBS：2026-10-02 / `TRC-01-A07-P02`；输入 CR-TRC-003、冻结 API-01 If-Match/强ETag 与 Trace 原始状态触发器。
- Decision：新增`lock_version BIGINT NOT NULL`，ACTIVE=0、REVOKED/SUPERSEDED=1；独立数据库触发器拒绝调用方直接改版本并在唯一合法终态转换时加1，状态/版本组合由 CHECK 约束。历史终态回填只在独占表锁和同一迁移事务中暂时停用原守卫，随后恢复；原冻结0029迁移不追写。降级只允许全体ACTIVE/v0，已终态历史须保留并拒绝丢弃版本。
- Reason：显式版本列满足冻结通用协议，可由后续If-Match/CAS命令复用；独立触发器保留原不可变守卫，且原历史无信息丢失。
- Impact/Rollback：仅Trace ORM与0053 migration，无公开API/新依赖；空库/未转换数据可down，已有终态数据不做有损down，改走备份/正向修复。P02不开放撤销命令。
- Verification Plan：真实PG18空库head→0052→head、含ACTIVE+两种终态数据0052→head、触发器非法直改/重复转换拒绝、终态down拒绝、有ACTIVE数据down/up；全量后端与wheel。未测试生产迁移与三平台发行。
- Result：一次性PG18三库空库/ACTIVE/REVOKED/SUPERSEDED升降级及守卫PASS，Alembic ORM差异检查无新操作；首轮验证脚本误查public版本表，修正为plm后重跑通过。原迁移Head单元断言随0053更新后，后端全量1885运行/3跳过；开发wheel SHA-256 `70602728cb93c47ce4e37048c325e79e0876d13d1d19d2adf22ef8ec2083dbf2`。仅Schema，不判撤销/HTTP/发行通过。

# DEC-20261002-614：TraceLink 撤销允许当前项目经理清理项目关系

- Date/WBS：2026-10-02 / `TRC-01-A07-P03`；输入冻结API-02 ProjectManager撤销权限、0053资源版本及既有同事务收据/Audit。
- Decision：首个内部撤销命令只支持PROJECT关系和当前ProjectManager；先当前License、Session/CSRF、项目策略，再锁定精确ProjectId+TraceLinkId行。对已知项目关系，撤销是缩小图可见性的维护操作，不要求两端已失效资源仍可读取；仅返回LinkId与首次终态版本，不投影端点。持久收据在行归属核实后且版本/状态检查前预留，使同Key同载荷历史重放保持首次结果；新Key在旧版本/终态拒绝。状态/版本由数据库触发器一次转换，Audit/收据同事务提交；关系Owner路径和公开HTTP不装配。
- Reason：依赖当前端点再次可读会使已撤权/受限的历史边不可撤销；项目经理对本项目关系有冻结授权，但不能因此读取端点内容。先锁行并核当前PM可防跨项目枚举；收据在状态检查前重放保证未知结果可安全恢复。
- Impact/Rollback：内部Trace命令/Repository及Project操作策略增量，复用0053/通用收据，无新Schema/Migration或公开API。未装配命令即可回滚；已撤销边保留历史不可恢复为ACTIVE，只能以新边表达后续业务关系。
- Verification Plan：单元验证无权/跨项目/缺Key/错版本/终态、同Key与不同载荷、License/Session/CSRF；一次性PG18验证行锁并发、一次状态转换/一审计一收据、审计失败回滚及项目归属；后端全量/wheel。不以内部通过替代HTTP/UAT/Gate验收。
- Result：定向撤销单元4/4、项目授权策略7/7，原Trace自启动隔离PG18矩阵扩展受限端点PM清理、非经理/跨项目/CSRF/License/版本拒绝、同Key并发和Audit失败回滚PASS；后端全量1889运行/3跳过、开发wheel SHA-256 `36465601c896ab3d562e774d1acbac965dbc565e8b3b672475a817944fee4f32`。首轮全量原策略数量断言30失配，增新操作后更新为31并重跑通过。公开HTTP、关系Owner及正式目标环境未验。

# DEC-20261002-615：Trace撤销HTTP只做可选最小投影

- Date/WBS：2026-10-02 / `TRC-01-A07-P04`；输入冻结API-01/02、内部撤销P03与CR-TRC-003。
- Decision：仅新增可选`POST /api/v1/projects/{project_id}/trace-links/{trace_link_id}:revoke`，空体，现有Origin/Host、Cookie Session/CSRF、强If-Match、Idempotency-Key共用安全解析；内部命令仍二次复验授权。200只投影LinkId/`REVOKED`/强ETag`"v1"`，不投影两端或暗示当前端点可读。默认应用与Windows平台组合均不挂载，挂载另立任务/真实信任验证。
- Reason：冻结路径/控制明确，但其他业务Owner/通用Trace创建与图查询尚不完整；将路由做显式可选以便受控实测，同时避免把开发验证冒充生产可用。历史同Key返回首次结果，因REVOKED是不可逆终态，v1仍有效；新Key的旧版本拒绝。
- Impact/Rollback：Trace HTTP router与应用工厂可选参数，无Schema/Migration、新依赖、默认路由或旧数据改动；不传Router即可回滚。后续公开列表/创建/图Owner和平台装配需另验。
- Verification Plan：HTTP单元覆盖默认404、成功/ETag/最小字段、Origin/Session/CSRF/If-Match/Key/空体/查询、安全码；真实ASGI+PG18合成当前PM/非PM/跨项目/失效License/重放/单Audit/收据，后端全量和wheel。正式目标账户、Server2025/Debian与Gate不由本项判PASS。
- Result：HTTP合同3/3，原Trace自启动PG18脚本扩展真实Session的默认404/当前PM200/重放/非经理/CSRF/缺If-Match/非空体/查询/过期License及单一终态Audit/收据PASS；后端1892运行/3跳过，开发wheel SHA-256 `8ba0a2cb87a0250c582d7eec113057dd28929bb863ab973149b8c4a5a80033e2`。仅显式可选路由；Windows正式组合与关系Owner未装配。

# DEC-20261002-616：不从创建者推断 Trace 关系 Owner

- Date/WBS：2026-10-02 / `TRC-01-A07-P05`；输入冻结 API-02、TraceLink ORM/内部撤销、P04 可选 HTTP 与 Windows 正式组合。
- Decision：`created_by` 仅为创建审计事实，不能自动充当冻结合同的“关系 Owner”；现有仅 PM 路径不扩权。正式组合在独立 Owner 证明与目标账户真实信任材料齐备前继续不挂载撤销 Router，默认模式继续 404。转 `TRC-01-A08-P01` 的独立 PM 替换关系前置核查。
- Reason：端点 Document Owner 只证明资源版本，不证明边所有权；以创建者或合成 License 代替会扩大权限/虚报可用性。当前无可逆的真实关系 Owner/撤权规则。
- Impact/Rollback：仅记录前置，不改代码、Schema、API、运行配置或历史数据；无需升级/迁移，删除本记录即可恢复原文档状态。未来 Owner 扩展需先登记 CR/迁移与验证，正式装配需另验。
- Verification：API-02/ORM/服务/应用工厂/正式组合静态核查；未运行新业务测试，P04 原 PASS 不扩大到生产、Server2025/Debian、Gate 3 或发行。

# DEC-20261002-617：TraceLink 替换只接受本事务的新相关边

- Date/WBS：2026-10-02 / `TRC-01-A08-P01`；输入冻结 API-02、DM-03、0029/0053 守卫、已实现创建/撤销与 P05 授权边界。
- Decision：仅当前 PM 内部路径先行。锁旧 ACTIVE/v0 与当前项目，证明新边同项目且至少保留一个旧端点、形状真实且非原样；环检查后在同事务先插入全新 ACTIVE 边，再设旧边 `SUPERSEDED`/`superseded_by_ref`。拒绝复用其他已有 ACTIVE 边。Audit/持久收据原子完成，重放核旧边终态/替代 ID；关系 Owner 与公开/正式装配另验。
- Reason：0029 守卫要求替代边已存在且不早于旧边，ACTIVE 唯一索引禁止原样替换。无关边复用会把不相关事实冒充同一历史链，失败时必须整事务回滚。
- Impact/Rollback：设计决策不改冻结 API/Schema/数据；P02 仅增内部 Trace 代码和项目 PM 操作，不装配即停止新替换；已终态历史不反向改写。若未来放宽相关性需可追溯变更与迁移分析。
- Verification Plan：P02 单元/隔离 PG18 验同项目新边、强版本/状态、Owner 证明、环、同 Key 并发、其他 ACTIVE 冲突及 Audit/收据失败回滚，后端回归/wheel。P01 仅静态核查，未运行新业务测试。
- P02 Result：内部当前PM命令/Repository实施；Win11隔离PG18新边+旧边单事务、非经理/许可/错版本/同边、Audit回滚、同Key并发与预存ACTIVE目标拒绝及原Trace HTTP回归PASS。后端1895运行/3跳过，开发wheel SHA-256 `184cdb8db11efd305aff09c6f249d515f9f9316d0188ed329c2aabb855db0602`。公开/正式装配、关系Owner和Gate仍关闭。

# DEC-20261002-618：Trace supersede 不跨事务预解析公开引用

- Date/WBS：2026-10-02 / `TRC-01-A08-P03`；输入冻结 API-02 三字段 ResourceVersionRef、P02 内部已解析命令及 Document Owner 事务 Port。
- Decision：不将公开三字段客户端输入当作已解析 TraceEdgeShape，不在独立预解析事务后调用内部 supersede。可选 HTTP 继续关闭；先做 P04 同一命令事务内 Owner 解析和原始输入指纹，再做 P05 HTTP。
- Reason：独立预解析无法保证 Document/Project/Session 证明与替换提交为同一受锁事实；接受客户端内部 Scope/Owner 会改变冻结合同并扩大信任边界。
- Impact/Rollback：仅记录前置，无代码/API/Schema/数据变化，升级无迁移；P04/P05 分别验证后才可显式注入 Router，默认/正式组合仍关闭。
- Verification：冻结合同/Owner/Service 静态核查，无新业务测试，内部 P02 PASS 不扩大为 HTTP、Gate 或发行 PASS。
- P04 Result：仅注册DOC-02的原始三字段内部入口，在当前命令事务解析Owner Scope/Project；Receipt基于原始输入，重放重验当前身份/许可/旧边但不重新要求新端点可读。Win11隔离PG18来源变RESTRICTED后同Key安全重放与原Trace链PASS，后端1897运行/3跳过、开发wheel SHA-256 `29a227016ed0e5501e4f4cfec3741cbffa989353e146eadff47cbb85a0ce1fa0`。HTTP/正式装配/Gate仍关闭。

# DEC-20261002-619：Trace supersede HTTP只投影新边引用

- Date/WBS：2026-10-02 / `TRC-01-A08-P05`；输入冻结API-01/02、P04同事务三字段解析和P03前置。
- Decision：显式可选冻结POST路径，Body只含source/target三字段ResourceVersionRef及relation_type；禁止Owner/Scope/Project由客户端提供。严格Origin/Session/CSRF/强If-Match/Key/有界唯一JSON。201只投影新trace_link_id和新边ETag `"v0"`，不回显端点或旧边内部状态。默认与Windows正式组合不注入Router。
- Reason：冻结结果为replacement，替代边是新资源，旧边由数据库一次终态v1；新资源ETag不能误标旧边v1。最小投影避免以HTTP暴露未复验的端点内容。
- Impact/Rollback：仅可选Trace Router/应用工厂参数，无Schema/Migration/依赖变化；不注入即关闭，历史已替换状态不反写。正式装配及关系Owner另验。
- Verification Plan/Result：合同3覆盖201/新ETag/输入安全/默认404；Windows11隔离PG18真实ASGI/Session的PM、非经理、许可、版本、同Key重放与单替换收据PASS，后端1900运行/3跳过，开发wheel SHA-256 `4442f5503acecfaf616147ed3772fe7c59e3789696d0e46c623162b4dccf1fc1`。正式信任/三平台/Gate不判PASS。

# DEC-20261002-620：Trace 创建的原始引用与历史收据先于端点新证明

- Date/WBS：2026-10-02 / `TRC-01-A09-P01`；输入冻结 API-02、CR-TRC-002、内部创建 A05-P02 与三字段 Resolver A08-P04。
- Decision：通用创建 HTTP 继续关闭；P02 内部入口先当前 License/Session/CSRF/Project，再按原始三字段/关系预留持久收据。历史同 Key 只在当前授权与结果归属重验后返回原 LinkId，不要求失效端点重新可读；首次写入才同事务 Owner 解析/证明、验环、去重创建和 Audit。已解析内部命令保留并遵守相同重放顺序。
- Reason：客户端 Scope/Owner 不是冻结输入，独立预解析会失去提交时的受锁证明；当前收据前端点证明使未知结果重试在来源失效后不可恢复，移动顺序又要求显式 License 避免历史路径绕过。
- Impact/Rollback：P01 仅记录设计，无代码/API/Schema/数据修改。P02 仅内部 Trace/许可 Port 调整，不装配新入口即可停止；旧收据及关系历史保留。其他 Owner 与正式 HTTP 按 CR-TRC-002 后续验收。
- Verification Plan：P02 单元与隔离 PG18 首次/同Key端点变受限后重放、过期 License/撤权/跨项目拒绝、异载荷冲突、并发去重与 Audit 失败回滚；后端回归与 wheel。P01 仅静态核查，未运行新业务测试。
- P02 Result：内部原始三字段与已解析入口共用当前License/Session/Project→Receipt→仅首次Owner证明/创建顺序；PG18来源RESTRICTED、旧边REVOKED后原Key重放，许可/新Key拒绝及原Trace链PASS。后端1902运行/3跳过、开发wheel SHA-256 `939efcd3d2bcfce8413ddd9f19ad30621fc660d35f2c082098f82f37c2aeaad0`。通用创建HTTP/其他Owner及Gate不判PASS。

# DEC-20261002-621：Platform Core 真实 Owner 依赖解环

- Date/WBS：2026-10-02 / `PLT-CORE-DEPENDENCY-A01`；依据 V2.1 Phase 2～4、冻结 ADR-004/DM-04/API-03、RVW-02-A10/WFL-01-A07-P05 与现有 Owner 接线。
- Decision：按 CR-SEQ-001 前置不依赖业务 Owner 的 AI/RAG 基础 WBS；Phase 2 及 Gate 3 保持开放，后续真实业务 Owner 回接 Review/Trace/Workflow 并重做阶段验收。下一项 `AI-01-A01`。
- Reason：后续阶段才实现的固定业务 Subject 是 Phase 2 真实 Gate 所需，严格逐阶段全部关闭会造成依赖循环；合成 APPROVED 或观测引用不是业务事实。
- Impact/Rollback：仅排期拓扑/状态/文档，无运行代码、API、Schema、依赖或数据迁移。可停止前置编码并恢复排期；保留历史 CR 和证据。独立变更各自验证/回滚。
- Verification：静态检查正式阶段顺序、冻结合同、当前 Port/Owner/POC-03 阻塞；未运行新增业务测试，不判 Phase 2/3/Gate 3 PASS；逐次外发授权边界不变。

# DEC-20261002-622：AI Provider 配置形状不等于激活或外发授权

- Date/WBS：2026-10-02 / `AI-01-A01`；输入 ADR-004、DM-04、API-03、AIService 合同及 CR-SEQ-001。
- Decision：先实现不含 URL/Key/客户正文的不可变 Provider 配置形状，Secret 引用在 Domain 只持有 UUID；Platform SecretRef 用途与消费者由后续 AI Application 证明，Provider 真实连接、ACTIVE、调用和逐次外发另验。
- Reason：Domain 不反向依赖 Platform Application，也不能让“配置字段有效”越权成为许可证、目标端点、秘密读取或客户数据发送资格。
- Impact/Rollback：新增 AI Domain/测试，没有 Schema/Migration、API、依赖或外发；未接生产组合，可移除该未消费合同回滚。后续持久层须保留配置版本历史。
- Verification：定向5/5、Windows 11 后端1907运行/3跳过、开发 wheel SHA-256 `4383e7e4609a7f52afc1792a5e74ed2999fb75dc51c477f9749e53dc92e28825`；API/权限/真实数据库/质量/三平台未在本项验证。

# DEC-20261002-623：AIProvider 配置历史与当前指针分离

- Date/WBS：2026-10-02 / `AI-01-A02`；输入冻结 SC-01/02、DM-04 与先行 CR-AI-001。
- Decision：部署级根保留当前配置复合 FK 与状态/乐观版本，不可变子版本保留 SecretRecord 引用、地区和能力声明；空表可降级，已有历史安全拒绝。配置 FK 不承担 Secret 用途/有效性、许可或外发证明。
- Reason：避免跨 Provider 指针、无痕覆盖配置或丢失历史；将受权运行证明留给 AI Application，维持模块所有权。
- Impact/Rollback：ORM、迁移0054、隔离验证及固定迁移/表清单测试；不改 `/api/v1`、技术栈/依赖或客户数据。空表 downgrade 至0053；有历史须向前修复。
- Verification：Win11 隔离PG18空/有数据升级及空库降级、字段/FK/追加历史/非空降级、Alembic drift 0；后端1907运行/3跳过；wheel SHA-256 `856a4007c223058ed5035861d3bf45d69b2b364fa8c20ddcf3e8ece53384bc16`。正式迁移/Service/Gate/三平台未验。

# DEC-20261002-624：Provider 创建和配置追加分步验收

- Date/WBS：2026-10-02 / `AI-01-A03-P01`；依据冻结 API-03 CREATE/PATCH、DM-04 的配置版本和 A02 迁移。
- Decision：A03 拆 P01 首次 CONFIGURED 创建与 P02 现有 Provider 配置追加。P01 只在当前管理员/CSRF/License 下同事务证明 Secret 用途与有效版本，插入首版、Audit、持久收据；重放可返回历史 ID，但不证明现时 Secret 可用或激活。P02 单独处理强版本/状态/历史切换，ACTIVE 不能直接改当前配置。
- Reason：创建的初始身份/幂等与 PATCH 的状态锁和乐观并发不同，合并验收易把“可配置”误报为“可使用/已外发”。
- Impact/Rollback：内部 Application/AI Repository 和 Platform 自有 Secret 证明适配器，无 Schema/API/依赖变化；未公开装配即可停止。已提交的历史记录不物理回滚，纠正用后续版本。
- Verification：定向2、Win11隔离PG18权限/许可端口/Secret/并发收据/Audit失败回滚/停用后历史重放与角色撤销拒绝、后端1909运行/3跳过、wheel SHA-256 `e00d6490aa2d49ceac368892e843f4809e1e97ec7cd461d65e5f810dac956acd`。正式License/外发/HTTP/三平台/Gate未验。
## DEC-20261002-655 — Provider 激活 HTTP 只投影不可变首次状态

- Date/WBS：2026-10-02 / `AI-01-A05-P05-A03-P03`；依据冻结 API-03 和 P02 内部激活快照。
- Decision：新增显式 opt-in 的无请求体 POST 边界；强 If-Match、必填幂等 Key、可信 Origin/Host、当前 Session/CSRF 后调用内部受权命令。200 仅返回快照的 ProviderId、ACTIVE 与原始 ETag，不再次读取当前状态；默认应用不挂载。
- Reason：同 Key 重放可能发生于后续暂停/改版之后，当前行不能代表首次响应。最小状态投影符合冻结的 `200 ACTIVE`，且不泄露配置/Secret。
- Impact/Rollback：仅 AI API、应用可选路由、合同测试和增量文档；无 Schema、依赖、生产挂载或外发。移除可选路由可回退，历史激活/Audit/收据保留。
- Verification：合同4项；Win11 隔离 ASGI/PG18 许可拒绝、激活/Audit、暂停后原结果重放及新 Key 版本冲突 PASS；后端2001运行/3跳过、开发 wheel 通过。生产组合、正式信任与 Gate 3 未验。
# DEC-20261002-674：Prompt Schema 活动指针与不可变历史设计

- Date/WBS：2026-10-02 / `AI-03-A01`；依据冻结 DM AI-03、SC-01/02 与 API-03。
- Decision：Prompt 根/子表分离，以同模板复合 FK 管理活动版本；版本号在根行锁下单调分配，子版本历史由数据库拒绝原地更改/删除；非空降级拒绝。Schema 前置设计先固定验收矩阵，ORM/Migration 留给 `AI-03-A02`。
- Reason：防止跨模板激活、并发重号和历史 Invocation 无法解释；不将正文/Secret 放普通日志，也不把数据库约束误认为语义安全审查。
- Impact/Rollback：本项仅设计文档，无数据库/API/依赖变更，可由后续可追溯设计修订回退；后续迁移只能对空表降级，保留历史。
- Verification：冻结文档、迁移头和现有 AI ORM 静态核对；运行迁移/测试留待 A02，不标通过。

# DEC-20261002-675：Prompt 活动指针状态及数据库边界

- Date/WBS：2026-10-02 / `AI-03-A02`；依据冻结 DM/SC AI-03 与 A01 设计。
- Decision：DRAFT 指针为空，ACTIVE 指针必须同模板指向既存版本，RETIRED 可保留原活动指针。复合 FK 以可延迟约束处理根/子循环；版本正文和策略引用一经插入由触发器拒绝更新/删除/截断。正文哈希一致性、敏感内容、单调分配和业务状态转移不伪装成数据库 CHECK，交由后续受控命令。
- Reason：在不改变冻结模型/API 的情况下防跨模板激活与历史覆盖，同时保留退役后的解释链。
- Impact/Rollback：新增 ORM/Migration 0059 与 Schema 增量说明；无公开 API、依赖或外发。空表可降至 0058，有历史拒绝物理降级并向前修复。
- Verification：Win11 隔离 PG18 空/有旧数据迁移、drift、约束、历史触发器及非空拒降 PASS；后端回归与开发包见 A02 进度记录。正式账户/三平台未验。
# DEC-20261002-676：Prompt 创建与首版写入按冻结 API 拆分

- Date/WBS：2026-10-02 / `AI-03-A03`；依据冻结 API-03 的独立 `AI_PROMPT_CREATE` 与 `AI_PROMPT_CREATE_VERSION`、DM AI-03 和 Schema 0059。
- Decision：A03 仅创建 DEPLOYMENT/DRAFT PromptTemplate 身份，活动版本为空，不接收或写入 Prompt 正文；A04 独立追加不可变首版并实施正文/策略安全校验。修正先前 A02 进度中的“创建与首版同项”下一任务措辞，不改冻结 API 或表结构。
- Reason：冻结合同把模板创建和版本追加分成两个受控操作；Schema 允许无版本 DRAFT。合并实现会提前扩大创建入口的敏感内容边界并模糊幂等语义。
- Impact/Rollback：仅内部 AI Application/Repository 与合成验证；无公开 API、迁移、外发或生产路由。未装配时可停止；已产生的审计和 DRAFT 历史不物理删除。
- Verification：A03 Win11 隔离 PG18 当前管理员/CSRF/License、同事务收据/Audit、并发重放、退役后历史视图、审计回滚及撤权拒绝通过；后端2055运行/3跳过、开发 wheel 通过。A04 另验不可变正文写入；两项完成前不声称 Prompt 可调用。
# DEC-20261002-677：PromptVersion 内容准入失败关闭

- Date/WBS：2026-10-02 / `AI-03-A04-P01`；依据冻结 DM/API-03 PromptVersion 禁止真实 Key、固定客户资料、Golden 答案和绕过 Evidence/Review 指令，以及 Schema 0059。
- Decision：不可变增版先建立规范化内容/哈希与显式内容准入端口。普通语法/密钥特征检查只作前置拒绝，不能当作完整语义审查；准入证明须绑定模板、TaskType、规范化正文与策略引用的指纹，并在同一写入链重验。未提供可信准入来源时失败关闭，不能将合成测试端口装入生产。
- Reason：正则或 AI 自评不能证明任意自由文本不含客户固定副本、Golden 答案或绕过指令。冻结要求不能因为暂缺审查系统而被降格为“已自动验证”。
- Impact/Rollback：核对通用收据后先按 CR-AI-006 拆 P01 不可变首次结果 Schema，P02 再做内部原子增版/准入，P03 才做可信准入来源与公开装配；不改冻结 API 或引入外部服务。已有版本/结果历史不可物理回滚。
- Verification：P01 Win11 隔离 PG18 空/有历史迁移、约束/不可变及拒降通过；P02 固定 NFC/LF 规范化、明显密钥/控制字符先行拒绝，以纯合成正文和合成准入端口检验指纹绑定、权限/License、单调并发、Audit/收据回滚，后端2060运行/3跳过与开发 wheel 通过；不得据此宣称真实业务 Prompt 安全或 PromptRegistry 可用。P03 另验可信来源和真实模板审查。
# DEC-20261002-678：Prompt 准入按独立签名清单精确匹配

- Date/WBS：2026-10-02 / `AI-03-A04-P03-A01`；依据 CR-AI-007、冻结 PromptVersion 禁止内容规则与已完成 P02 准入端口。
- Decision：以独立 Ed25519 公钥和受信发行配置钉住的清单摘要验证结构化、无正文的批准指纹；签名载荷域分离，条目按模板/TaskType/指纹排序唯一。缺公钥/钉住摘要/清单、篡改、重复 JSON 键或不匹配均失败关闭。签名不代替实际内容审查。
- Reason：既保留经审查的动态版本能力，又避免只靠正则或易伪造的自我声明批准不可变正文；不复用 License 私钥。
- Impact/Rollback：新增只读 AI 适配器与合成验证，无 Schema/API/外发/新依赖。未装配即可撤回，正式密钥/清单仪式另验。
- Verification：Win11 临时密钥单元与隔离 PG18 签名清单增版/改正文拒绝通过；后端回归及开发包见进度记录。正式公钥和语义审查未验。

# DEC-20261002-679：工作台从完整候选计算签名指纹

- Date/WBS：2026-10-02 / `AI-03-A04-P03-A02-P01`；依据 CR-AI-007、DEC-678。
- Decision：离线签署工具接受完整候选而不接受自报指纹；要求交互式复核源文件 SHA-256，签名清单只保留作用域和规范化指纹，输出独占写仓库外。正式密钥仪式和发行装配分独立任务。
- Reason：避免人工/调用方给任意指纹贴上“已审”标签，防止正文或私钥意外入库；交互确认不代替实际内容审查。
- Impact/Rollback：新增工作台工具及测试，修复 Prompt 引用字段明显密钥样式拒绝。无 Schema/API/新依赖；工具可撤，Domain 安全增强不建议撤。
- Verification：合成加密临时密钥签署与运行时验签互通、错误摘要/口令/候选/覆盖拒绝共6项；后端2070运行/3跳过，开发wheel通过。正式审查/密钥/发行未验。

# DEC-20261002-680：Prompt 准入独立密钥只由工作台仪式生成

- Date/WBS：2026-10-02 / `AI-03-A04-P03-A02-P02-P01`；依据 CR-AI-007 和 License 私钥隔离边界。
- Decision：提供独立 Ed25519 加密私钥/公钥仪式及离线副本挑战核验工具，固定忽略的工作台私有目录，禁止覆盖和复用 License 身份；正式创建/口令及离线保管由实际操作员完成，不能把临时测试身份当生产锚。
- Reason：签署器须有独立可信来源；无正式操作证据时运行时继续失败关闭。
- Impact/Rollback：只增加工作台工具与测试，不改 DB/API/生产配置或依赖。工具可撤；已发行身份换钥必须重新签发清单和受信包，不覆盖原件。
- Verification：临时密钥定向3及签署回归6、后端2073运行/3跳过、开发wheel通过；正式仪式未执行。

# DEC-20261002-681：Prompt 准入从发行包读取公钥与钉住清单

- Date/WBS：2026-10-02 / `AI-03-A04-P03-A02-P03`；依据 CR-AI-007、DEC-678～680。
- Decision：运行时只读包内公钥/清单摘要/代际和签名清单，先严格校验再委托精确指纹准入；当前开发包不携正式材料，默认失败关闭，禁止环境/请求覆盖。
- Reason：签名清单不能自带其可信公钥或期望摘要；生产装配必须依赖受控发行来源，而非管理员随请求指定。
- Impact/Rollback：新增 AI 基础设施装载器和 package-data 声明，不改 DB/API/既有路由；缺材料或撤回装载器均保持关闭。正式签发与包完整性另验。
- Verification：合成正确/错密钥/摘要/代际/畸形/缺资源定向3、后端2076运行/3跳过与开发wheel通过；wheel ZIP 确认无正式信任文件，正式发行未验。

# DEC-20261002-682：发行摘要只从已验签清单派生

- Date/WBS：2026-10-02 / `AI-03-A04-P03-A02-P04`；依据 CR-AI-007、DEC-678～681。
- Decision：工作台发行生成器从独立仪式公钥元数据与已签清单验签后派生 SHA-256/代际，独占输出仓库外；不接受操作者自报摘要，不自动把产物复制进客户包。
- Reason：降低错配或拿未经签名的清单作为已审材料的风险；发行完整性与人工审查仍须单独证明。
- Impact/Rollback：仅工具/测试/文档，无数据库、API、运行时或包内容变化；可撤工具，已发行历史保留。
- Verification：合成生成→包内装载互通及错钥/篡改/覆盖拒绝定向3、后端2079运行/3跳过；正式发行未验。

# DEC-20261002-683：PromptVersion 写入口仅可选挂载并双重核对响应

- Date/WBS：2026-10-02 / `AI-03-A04-P03-A03-P01`；依据冻结 API-03 与 CR-AI-007。
- Decision：使用冻结 POST 路径建可选 Router，默认/当前生产不挂载；2 MiB 有界严格 JSON，Session/Origin/CSRF/幂等/强 ETag 前置；201 只回版本元数据/Hash，服务返回结果须与本次规范 Draft 指纹和引用完全一致。
- Reason：先验证 HTTP 合同，不把合成签名清单或缺正式信任锚的开发包装成生产可写；避免错配历史结果误投影。
- Impact/Rollback：不改 Schema/冻结 API/技术栈；移除可选注入即可恢复默认404。隔离PG及正式目标账户仍待。
- Verification：HTTP 合同3、后端2082运行/3跳过、开发wheel通过；真实 PG/正式信任未验。

# DEC-20261002-684：PromptVersion HTTP 整链合成通过后保持生产关闭

- Date/WBS：2026-10-02 / `AI-03-A04-P03-A03-P02`；依据 CR-AI-007 与冻结 Prompt 内容禁令。
- Decision：隔离 PG18/HTTP 仅注入临时签名材料验证事务和错误边界；正式 `A03-P03` 挂载在真实审查、独立密钥/离线备份、受控发行公钥/摘要及目标账户/包完整性通过前保持关闭，转向独立激活设计任务。
- Reason：合成准入可证明代码链路，不能证明审查事实或生产信任锚。默认不挂载防止自由正文写入不可变历史。
- Impact/Rollback：本项仅验证脚本与文档，无生产行为/Schema/API 变化；随机测试库已清理。
- Verification：Win11 隔离PG18默认/普通用户404、未列422零写、已列201/重放、冲突409、许可403及单版本/Audit/收据脚本exit0；正式生产未验。

# DEC-20261002-685：Prompt 激活以 AI 专属不可变结果承载原 200

- Date/WBS：2026-10-02 / `AI-03-A05-P01`；依据 CR-AI-008、冻结 API-03 与当前通用幂等收据形态。
- Decision：先设计 AI 所有的不可变激活首次响应结果 Schema0061，以 UUID 供通用收据引用；后续内部服务在同事务保存根状态、Audit、结果和收据。历史重放按结果投影而不读当前可变根，仍重验身份/License。
- Reason：通用收据无复合版本/ETag，Prompt 根可继续切换或退役，不能把现态冒充首次 200。
- Impact/Rollback：原冻结 `64cdf09` 不变；下一项需要 ORM/Migration0061，历史数据写入后 down 应拒绝。无本项代码/API变更。
- Verification：对照冻结 API、Prompt ORM/Schema0059/0060 与通用收据静态核查；新运行测试未执行，下一项隔离PG18验证。

# DEC-20261002-686：Prompt 激活结果只存首次最小快照

- Date/WBS：2026-10-02 / `AI-03-A05-P02`；依据 CR-AI-008。
- Decision：Schema0061 保存模板/版本复合归属、固定 ACTIVE 状态、操作者/Audit/Trace 与前后 lock_version，不复制 Prompt 正文或当前可变根；非空结果表拒绝 down，历史不可更新/删除/截断。
- Reason：足以由 UUID 收据恢复原 200/version/ETag，同时避免 Secret/客户正文重复落表；未来同一版本可再次激活，故不对 template/version 加唯一约束。
- Impact/Rollback：AI ORM/Alembic 增量，无 API 变化；有结果后只能前向修复或受控备份恢复。
- Verification：Win11 隔离 PG18 空/有历史升降与约束/不可变、drift=0；首轮2个旧版测试断言修正后全量2082运行/3跳过、开发wheel通过。内部服务未验。

# DEC-20261002-687：历史 PromptVersion 激活必须重新通过当前准入

- Date/WBS：2026-10-02 / `AI-03-A05-P03`；依据 CR-AI-008 实施前补充、CR-AI-007。
- Decision：内部服务从不可变版本重建规范指纹，对当前签名清单准入端口做精确核对后才允许切换；旧 Key 原结果重放仍重验当前身份/License，但不发起新激活。服务/仓储不挂生产路由。
- Reason：仅有版本存在或先前写入历史不能证明当前内容已被受信审查；强版本锁与同事务首次结果保留并发和历史响应语义。
- Impact/Rollback：复用0061，不改变冻结 API/Schema/依赖；关闭内部入口停止新激活，已写历史保留、向前修复。
- Verification：Win11 隔离PG18合成准入、未审版本零写/并发/重放/回滚/退役/撤权通过；后端2082运行/3跳过。正式信任/生产入口未验。

# DEC-20261002-688：Prompt 激活 HTTP 采用空对象和最小首次结果

- Date/WBS：2026-10-02 / `AI-03-A05-P04`；依据冻结 API-03 `AI_PROMPT_ACTIVATE_VERSION`、CR-AI-008。
- Decision：建立仅显式注入的可选 Router，POST 只接收有界严格 JSON 空对象 `{}`，URL 携带 Template/Version，强 If-Match/Session/CSRF/Origin/幂等键为前置；200 仅返回 Template、Version、ACTIVE、首次 ETag，不返回 Prompt 正文或当前可变根。默认/生产组合不挂载。
- Reason：冻结合同未定义额外激活参数，空对象避免未审选项；最小不可变结果允许旧 Key 精确重放，当前 trace 仍为本次请求。
- Impact/Rollback：无 Schema/依赖/路径/状态码变动；不注入 Router 即404，可撤路由，历史激活结果保留。
- Verification Plan：合同单测覆盖默认关闭、成功/重放、严格请求、权限/许可/冲突/准入错误映射与响应快照；隔离 PG18 实际 HTTP 链另验，不据此开启正式生产入口。
- Verification Result：合同3项、Win11隔离PG18临时签名清单实际HTTP整链、后端2085运行/3跳过、开发wheel通过；生产仍不挂载。

# DEC-20261002-689：Prompt 退役需独立不可变首次结果

- Date/WBS：2026-10-02 / `AI-03-A06-P01`；依据 CR-AI-009、冻结 `AI_PROMPT_RETIRE`。
- Decision：退役首次200由预定0062的 AI 专属不可变结果承载，通用收据仅指向结果 UUID；不复用固定 ACTIVE 的0061，也不从当前根重建历史响应。退役保留旧活动指针但不代表仍可调用。
- Reason：根锁版本/状态可变，通用收据不足以保存原 ETag/活动版本；独立快照可与 Audit/收据同事务审计。
- Impact/Rollback：先登记CR，下一项实现增量Schema；原冻结内容/API不改。非空结果须保留并向前修复。
- Verification：静态对照冻结 API、Prompt ORM/Schema0061和通用收据；运行验证待P02/P03。

# DEC-20261002-690：退役结果保留旧活动指针但不复制正文

- Date/WBS：2026-10-02 / `AI-03-A06-P02`；依据 CR-AI-009。
- Decision：0062只存首次状态/旧活动版本/锁版本/Audit等最小快照；旧活动版本非空时用复合FK限定同Template。DRAFT旧指针必须空，ACTIVE旧指针必须非空正数；不存正文。非空结果表禁止down。
- Reason：首次200可由收据UUID独立重放，历史版本仍可追溯；SQL CHECK 必须显式处理 NULL 三值逻辑，不能把 `>0` 的 UNKNOWN 当拒绝。
- Impact/Rollback：AI ORM/Alembic增量，无API/依赖变化；有历史时向前修复或受控备份恢复。
- Verification：Win11隔离PG18空/有历史升降、drift=0、FK/形态/历史保护/非空拒降；后端2085运行/3跳过、开发wheel通过。

# DEC-20261002-691：退役保留活动指针，仅状态阻断未来调用

- Date/WBS：2026-10-02 / `AI-03-A06-P03`；依据 CR-AI-009、冻结 PromptTemplate 状态。
- Decision：退役不清除历史 `active_version_no`，只将根状态设 RETIRED、锁版本加一并写不可变首次结果；新退役拒绝，旧Key可在当前身份/License有效时重放。AI Invocation 必须另按根状态拒绝，不以指针存在视作 ACTIVE。
- Reason：保留最后活动版本的追溯引用，同时避免重放从当前根推断原响应。
- Impact/Rollback：无新Schema/API/依赖；内部服务未装生产，已有退役历史不可删除，向前修复。
- Verification：Win11隔离PG18 DRAFT/ACTIVE、并发/重放/回滚/撤权 PASS；单元2、后端2087运行/3跳过，开发wheel通过。Invocation仍待独立验收。

# DEC-20261002-692：Prompt 退役 HTTP 只投影首次状态与 ETag

- Date/WBS：2026-10-02 / `AI-03-A06-P04`；依据冻结 `AI_PROMPT_RETIRE`、CR-AI-009。
- Decision：新增仅显式注入的可选 Router；POST 接受严格空 JSON 对象、强 If-Match、Session/Origin/CSRF/幂等键；200 `data` 只含模板 UUID、固定 RETIRED 和首次 ETag，不把保留的旧活动版本指针描述为仍 ACTIVE。默认/生产组合不挂载。
- Reason：冻结合同未定义额外退役参数；最小首次投影避免历史指针语义混淆，并能从0062不可变结果精确重放。
- Impact/Rollback：无Schema/依赖/冻结路径或状态码变化；撤可选Router即404，历史结果保留。
- Verification Plan：合同单测默认关闭/成功/重放/畸形请求/错误映射；Win11隔离PG18真实HTTP/Session/审计/收据链，正式信任另验。
- Verification Result：合同3项、Win11隔离PG18实际HTTP链、后端2090运行/3跳过、开发wheel通过；生产仍不挂载。

# DEC-20261002-693：安全退役不依赖 Prompt 内容签名清单

- Date/WBS：2026-10-02 / `AI-03-A06-P05`；依据 CR-AI-007/009 与冻结退役语义。
- Decision：退役只允许状态单向关闭且无新正文/激活，不以 Prompt 内容清单为前置；后续仅在 Windows 显式平台写模式装配，仍依赖平台 License/Session/CSRF/Schema0062及目标账户发行信任。增版/激活继续因 Prompt 清单缺失而关闭。
- Reason：把内容准入扩展到单向禁用会阻碍安全停用；但安全停用不等于允许新内容调用，也不能绕过平台信任。
- Impact/Rollback：本项只记录决策，无运行行为；下一项若组合失败保持默认404。无 Schema/API/依赖变化。
- Verification：只读核对 CR-AI-007、退役服务和 Windows 组合；实际组合与正式账户未验。

# DEC-20261002-694：退役仅进入显式平台写组合

- Date/WBS：2026-10-02 / `AI-03-A06-P06`；依据 CR-AI-009、DEC-693。
- Decision：仅在 Windows `--platform-write` 组合复用现有平台 UOW、License guard、Session/Origin/CSRF、幂等收据与 Audit 装配退役 Router。登录/只读默认404；增版/激活继续关闭。单向禁用无需 Prompt 内容签名准入，但仍依赖目标账户和正式平台信任。
- Reason：把安全退役限定在显式管理员写模式，不扩大 Prompt 内容写入/激活范围。
- Impact/Rollback：无新Schema/API/依赖；撤装配恢复404，0062退役历史不可删除，须向前修复。正式信任、生产迁移另验。
- Verification：Win11隔离PG18合成组合404/200/重放/权限/许可/缺密钥失败关闭及单根/Audit/结果/收据PASS；后端2090运行/3跳过、开发wheel通过。Server2025/Debian及真实账户未验。

# DEC-20261002-695：Prompt 元数据读取不投影退役历史指针或正文

- Date/WBS：2026-10-02 / `AI-03-A07-P02`；依据冻结 `AI_PROMPT_LIST/GET`、DM-04。
- Decision：独立 Prompt HMAC cursor，不复用 Model 密钥；只在 `ACTIVE` 状态联接不可变版本的 hash/schema/policy 元数据，永不选择 system/user 正文。`RETIRED` 根上保留的旧指针不进入读 DTO。
- Reason：避免把安全退役后的历史版本误标为仍可调用，并防止普通管理列表泄露模板正文或跨会话游标复用。
- Impact/Rollback：无 Schema/API/依赖变化；内部服务可停止装配，数据库不变。
- Verification：单元4、Win11隔离PG18三状态/分页/安全投影、后端2094运行/3跳过、开发wheel通过；公开HTTP和正式账户未验。

# DEC-20261002-696：Prompt 只读 HTTP 保持显式注入

- Date/WBS：2026-10-02 / `AI-03-A07-P03`；依据冻结 `AI_PROMPT_LIST/GET`、DEC-695。
- Decision：新增可选 LIST/GET Router，由组合根显式注入；默认应用与当前生产组合仍404。采用 Session/可信 Host/License、独立游标、最小元数据与详情强 ETag，不开放模板正文读取。
- Reason：先验证冻结接口的权限与投影，避免在缺正式游标签名密钥和发行信任时静默开放生产入口。
- Impact/Rollback：无Schema/依赖/Breaking API变化；撤Router恢复404，数据不变。
- Verification：合同3、Win11隔离PG18真实ASGI分页/ETag/三状态/权限/许可/撤销/无正文、后端2097运行/3跳过、开发wheel通过；正式组合尚未挂载。

# DEC-20261002-697：Prompt 只读组合要求专属 Vault 密钥

- Date/WBS：2026-10-02 / `AI-03-A07-P04`；依据冻结 `AI_PROMPT_LIST/GET`、DEC-696、现有 Windows 游标密钥机制。
- Decision：`--platform` 和 `--platform-write` 均显式装配 Prompt LIST/GET，并从当前账户 Vault 读取独立 `ai-prompt-list-cursor-v1`；缺失/损坏则拒绝显式平台服务启动，错误不泄露底层密钥信息。默认登录组合不装配。详情路由限定 UUID 以维持退役 POST 在只读模式404。
- Reason：防止跨资源游标密钥复用、不可恢复游标或默默降级；保持冻结动作路由语义。
- Impact/Rollback：新密钥是部署前置，不改Schema/依赖/冻结API；正式账户需受控供给及离线备份。撤只读装配可恢复原入口状态，不改数据。
- Verification：Win11临时Vault丢失/备份恢复、缺钥启动失败、隔离PG18平台读/写组合、退役/Model回归、后端2100运行/3跳过、开发wheel通过；正式账户/Server2025/Debian未验。

# DEC-20261002-698：AI-04 物理 Schema 按 Root/Input 与 Invocation/Snapshot 分切片

- Date/WBS：2026-10-02 / `AI-04-A02-P01`；依据冻结 DM-04、SC-01/02、API-03。
- Decision：0063 先建立 AITask R-SCP Root 与其不可变输入版本引用，包含 GLOBAL/PROJECT Scope、项目归属、TaskType、输入指纹、策略引用、状态/建议态、请求者、Job/Trace 与乐观锁；0064 再加入 Invocation、Context 与逐次外发授权快照及当前 Attempt 指针。冻结的四张 owned/Root 表均保留在最终范围；P01 不开放 API 或厂商调用。
- Reason：使数据库每步可独立验证，同时避免在尚无 Attempt 表时伪造当前 Invocation 外键或外发授权已可用。
- Impact/Rollback：0063 仅新增表，无已有列/API/依赖改变；空输入表可物理降级，已有 Task/输入历史拒绝降级并向前修复或受控备份恢复。P02 必须在 P01 之上补全冻结模型，不能据 P01 关闭 AI-04。
- Verification Plan：Win11隔离PG18空库及已有业务历史升级、drift、Scope/Project FK、输入引用同项目/不可变/序号约束、空表 down/re-up 与非空拒降；后端回归及开发wheel。正式账户、AI外发和Gate3另验。
- Verification Result：0063 ORM/Migration 已实施；Win11隔离PG18上述空/有数据与负例均 PASS，首轮全量回归因旧ORM/迁移头清单失败，更新后2100运行/3跳过PASS，开发wheel通过。Invocation/Context/外发快照仍未实现，正式环境与Gate3未验。

# DEC-20261002-699：每次 Invocation 固化外发授权与运行身份，不复制秘密或正文

- Date/WBS：2026-10-02 / `AI-04-A02-P02`；依据冻结 DM-04、SC-01/02、API-03 与 DEC-698。
- Decision：0064 为每次 AI Invocation 保存独立 Attempt、Provider/Config/Model/PromptVersion、输入/请求/响应与 Context 指纹、结构化输出验证状态和逐次外发授权快照；授权快照显式记录 Provider、区域、允许数据类别、审批人、授权时间窗与指纹，但只引用 SecretRecord 间接所在的 ProviderConfig，不复制 SecretRef、密钥、Prompt/Response 正文。无外发仅可显式记为 `NOT_APPLICABLE`，不得据此引入本地大模型。AITask 的当前 Invocation 采用同 Task 复合外键。
- Reason：冻结设计要求 Attempt 可追溯、重试不覆盖、外发逐次授权和敏感正文不落运行表；仅存可校验身份/指纹及受控载荷引用可满足审计而不扩大秘密面。
- Impact/Rollback：增量 Schema 0064，不改冻结 API、依赖或业务路由；新历史表非空时拒绝物理降级，使用向前修复或受控备份恢复。Provider/Prompt 退役仅阻止新 Invocation，历史引用仍保留。
- Verification Plan：Win11 隔离 PostgreSQL 18 验证空库与既有0063数据升级、Scope/Project与同Task引用、Provider/Config/Model/ACTIVE Prompt 准入、授权时间窗/类别、Attempt状态机与终态不可变、Context不可变、无正文列、空表回退/再升级、非空拒降、Alembic drift、后端回归和开发 wheel。
- Verification Result：Schema0064/ORM 已实施；Win11 隔离PG18上述升降、既有数据、drift与负例全部 PASS。首轮函数变量名与列名歧义，修正后完整重跑 PASS。首轮全量误用数据库最小环境导致12项缺 `pydantic-settings` 导入失败；改用完整Python3.13验证环境后2100运行/3跳过 PASS。开发wheel包含0064与ORM，SHA-256 `f6e46044844a1ad9fb2dbc99d429cca607a4185d6d544673edbbbb8a47295d3e`。无真实外发、API或生产迁移。

# DEC-20261002-700：缺 ObjectId 的0063输入只保留历史，不猜测补值

- Date/WBS：2026-10-02 / `AI-04-A03-P01`；依据 CR-AI-010、冻结 ResourceVersionRef 与历史不可变规则。
- Decision：0065增加 `ai_task_input_refs.object_id`；迁移前行允许保持NULL且永不更新，新INSERT必须非NULL。应用读取NULL时失败关闭，只有显式注册Owner在同事务证明ObjectId/VersionId/Scope/Project后才可建立新引用。
- Reason：VersionId不能替代业务ObjectId；猜测回填会制造不可追溯事实，而拒绝整个0063历史库升级又不满足兼容迁移。只读遗留+新写强约束同时保留历史和未来正确性。
- Impact/Rollback：不改冻结API/技术栈；新增列及守卫，下一项0065实施。有非NULL新引用时拒绝降级，既有NULL历史不阻止退回0064。内部创建/Owner注册在后续独立实现。
- Verification：本项静态对照冻结三字段引用、0063 ORM及Document Owner解析；运行验证待P02。
- Verification Result：0065已实施；Win11隔离PG18空库和0063遗留NULL历史兼容升降、drift、新写ObjectId强制/不可变/Scope及新历史拒降PASS；后端2100运行/3跳过、开发wheel SHA-256 `b0cd5c1288cb2ac278d755068124245b858270a2bd2a6cc53d06a864da7ab7ca`。Owner注册和内部创建仍待。

# DEC-20261002-701：AI输入先全组校验，再逐项调用显式Owner

- Date/WBS：2026-10-02 / `AI-04-A03-P03`；依据 CR-AI-010、冻结同项目固定版本与最小数据规则。
- Decision：AI输入Resolver仅接受显式注册的公开ResourceType；先对整组1～1000项完成形状与重复检查，之后才调用Owner。Owner必须返回精确同ObjectId/VersionId、合法内部Owner/ObjectType及同一PROJECT；当前只注册可复用既有授权读链的DocumentVersion桥接，其他类型保持失败关闭。
- Reason：边验证边调用会在后续重复/畸形引用时产生不必要的授权读取；预校验避免部分副作用。显式Owner避免AI模块猜测跨域表结构或绕过Owner权限。
- Impact/Rollback：无Schema/API/依赖变化；停止组合Resolver即可回滚。Project授权矩阵增加冻结已定义的AI_TASK_CREATE角色，不开放入口。
- Verification：定向13项和后端2106运行/3跳过PASS；wheel SHA-256 `895c2b4de673045ceb3db79e21edca79d850a61fcecdf2ad7f46c94f13991e46`。真实Task创建/外发未执行。

# DEC-20261002-702：AITask 作为幂等根反查唯一不可变 Job

- Date/WBS：2026-10-02 / `AI-04-A03-P04`；依据 CR-AI-011、冻结 `AI_TASK_CREATE`。
- Decision：通用幂等收据继续只指向 AITask；0066 为迁移后新 Task 强制唯一非空 JobRef 并纳入不可变守卫，从 Task 精确恢复首次 JobRef。旧 NULL 只保留历史，不猜测回填。
- Reason：避免改动全平台收据合同，同时满足 202 Task+Job 稳定重放与一对一关系。
- Impact/Rollback：增量 Schema0066，不改冻结API/依赖；有新绑定时拒绝降级。P05 已实施，P06 再组合内部创建。
- Verification：Win11隔离PG18.6空/旧NULL历史升降重升、drift、缺Job/错Owner/复用/换绑及拒降PASS；后端2106运行/3跳过，wheel `56e45841582d8e764b53a78426e9a43171f2924aa86cd509a0a61419e5cd658f`。

# DEC-20261002-703：外发授权只能由独立 Owner 产生快照

- Date/WBS：2026-10-02 / `AI-04-A03-P04`；依据 CR-AI-011、冻结 `EGRESS_*`。
- Decision：AITask 创建只接收 AuthorizationRef，由显式 EgressAuthorization Owner 在同事务内返回已批准、同 Scope/Project/用途、未过期未撤销的完整快照。请求 DTO、AI 输出和测试夹具不能代替 Owner；当前正式聚合未实现时失败关闭并保持公开路由404。
- Reason：批准主体、时间、数据边界与撤销状态是正式业务事实，不得由 AI 模块猜测或自我授权。
- Impact/Rollback：P06 可实现 Port/内部创建，但 Egress Owner 生产实现前不开放 API；无 Schema/API 冻结内容改写。
- Verification：静态搜索确认当前仅有0064 Task 内快照表，无 Egress Preview/Authorization 生产聚合或可组合 Owner。

# DEC-20261002-704：授权快照固定Model、源集合摘要与定量边界

- Date/WBS：2026-10-02 / `AI-04-A03-P06`；依据 CR-AI-012、冻结 `EgressAuthorization`。
- Decision：Schema0067在0064快照上增加Model、批准角色、preview payload/source refs指纹、载荷/Token/重试上限和捕获时AUTHORIZED状态。source refs明细由同Task不可变InputRef集合承载，不复制正文或第二份明细。
- Reason：0064现有列不足以证明Invocation未更换Model、源或扩大载荷；把边界放在Job JSON/日志或推迟到Invocation均无法作为完整批准证据。
- Impact/Rollback：新列兼容旧NULL历史，新行强制完整；不改冻结API/技术栈，有完整新快照拒绝降级。0067已实施。
- Verification：Win11隔离PG18.6空/遗留升降重升、drift、Model/角色/边界/不可变/拒降PASS；后端2106运行/3跳过，wheel `4550d75d6d8961ce493637a56b618e3c32132d4aee7caf5b58d4144146ce9589`。

# DEC-20261003-705：AITask首次创建以Task为幂等根原子写入七类记录

- Date/WBS：2026-10-03 / `AI-04-A03-P08`；依据 CR-AI-010～012、Schema0065～0067。
- Decision：先全组解析Input Owner，再由Egress Owner返回完整授权快照；源集合指纹精确一致后，同事务写Task/Job/Outbox/Input/Snapshot/Audit/Receipt。收据指向Task，重放从Task不可变JobRef恢复原202。
- Reason：防止部分入队、伪造授权、重放重复审计或返回新Job；也不扩展全平台单UUID收据合同。
- Impact/Rollback：新增内部Application/Repository，无Schema/API/依赖变化；未挂载组合根，可停止注入回退，已有历史保留。
- Verification：单元5，Win11隔离PG18.6真实原子链/重放/冲突/Audit失败回滚，后端2111运行/3跳过，wheel `d7978d74ee11f263ed25bd45fb8386cc178bfce4b14e8dbd75052e4dc88e0129`。

# DEC-20261003-706：Egress批准源与Task消费快照分离

- Date/WBS：2026-10-03 / `AI-04-A04-P01`；依据 CR-AI-013、冻结 `EGRESS_*`。
- Decision：新建 Preview Root+不可变SourceRef与Authorization Root/撤销历史；AITask只通过Owner读取当前有效授权并复制最小不可变快照。两者不共用可变行。
- Reason：先预览后批准、可撤销当前资格与不可改写的调用证据是不同责任；反向使用Task快照会伪造批准源。
- Impact/Rollback：新增0068/0069计划与Project权限Operation，不改冻结URL/DTO；空表可降，历史非空拒降。
- Verification：本项静态核对API-03、SC-01、0064～0067与现有代码，确认权威聚合缺失；无运行测试或外发。

# DEC-20261003-707：Egress Preview 以不可变根和语义去重来源固定授权边界

- Date/WBS：2026-10-03 / `AI-04-A04-P02`；依据 CR-AI-013、冻结 `EGRESS_PREVIEW_CREATE/GET`。
- Decision：Schema0068 将 Preview 和有序 SourceRef 均实施为只追加历史；数据类别/风险代码与来源语义键分别去重。Provider/Config/Region、AVAILABLE Model、Scope/Project和非零身份在数据库守卫中失败关闭。
- Reason：授权必须针对可重现的唯一来源集和确定厂商路由；重复条目会使数量/指纹语义不稳定，修改旧 Preview 会改写批准依据。
- Impact/Rollback：增量 Schema0068，不改冻结 API/依赖；空表可降0067，有历史时向前修复或受控备份恢复。未打开公开路由或外发。
- Verification：Win11隔离PG18.6 up/down/re-up、drift、Provider/Model/Region、集合/UUID、来源Scope/去重/不可变及非空拒降PASS；后端2111运行/3跳过，wheel `9f7f479e00258503511e43238d637662bc5ed772608798f183dc7d867c32c01e`。

# DEC-20261003-708：Egress批准与撤销首次结果必须成套原子落库

- Date/WBS：2026-10-03 / `AI-04-A04-P03`；依据 CR-AI-013、冻结 `EGRESS_AUTHORIZE/REVOKE`。
- Decision：Authorization Root 固化可缩小的 Preview 边界，只允许 `AUTHORIZED@0→REVOKED@1`；撤销事实和 Authorize/Revoke 首次响应各自使用不可变表。延迟约束触发器要求新Authorization必有AuthorizeResult，REVOKED必同时有唯一Revocation和RevokeResult。
- Reason：通用幂等收据只能指向一个 UUID，而可变 Root 无法重放首次 AUTHORIZED 响应；独立结果可保留原响应，延迟约束又防止只改状态或只写事件。
- Impact/Rollback：增量Schema0069，不改冻结API/依赖；空表可降0068，有历史时向前修复或受控恢复。当前角色/原批准者/部署策略由后续应用服务重验。
- Verification：Win11隔离PG18.6空库往返、已有0068升级、drift、越界/过期/角色/缺结果授权、不完整撤销、单向/不可变/拒降PASS；后端2111运行/3跳过，wheel `a9f4e426e9e132960da559d8e2a931493f6fb978742f234bde33304d99785700`。首轮迁移变量名和夹具引号缺陷已修正并全量重跑。

# DEC-20261003-709：Preview 按版本化策略固化边界并从不可变根重放

- Date/WBS：2026-10-03 / `AI-04-A04-P04`；依据 CR-AI-013、冻结 `EGRESS_PREVIEW_CREATE/GET`。
- Decision：Preview 创建必须在一个事务内通过当前 License、Session/CSRF、Project 角色、显式 Input Owner、当前 ACTIVE Provider/配置/AVAILABLE Model 和可注入的版本化最小外发策略，然后原子写 Root/Source/Audit/Receipt。类别集合排序后参与请求指纹；同 Key 从0068不可变根精确重放，不从当前可变路由重建历史。GET 只返同项目安全投影。
- Reason：策略引用与定量上限是授权候选边界，必须在发生批准前稳定、可审计；重放若重跑当前路由会将历史请求漂移到新配置。
- Impact/Rollback：复用0068/0069，无新Schema、依赖或Breaking API；停止后续组合即可回退入口，已有Preview/Audit/Receipt保留且不删除。公开HTTP及真实外发继续关闭。
- Verification：定向12项、Win11隔离PG18.6真实原子链/重放/冲突/回滚/项目隔离、后端2116运行/3跳过PASS；开发wheel SHA-256 `2160e09b852932c733add19ef0ee6e5bc2cad10749d0cb8848716ab89be03673`。

# DEC-20261003-710：Authorize 历史重放不从已撤销当前根重建

- Date/WBS：2026-10-03 / `AI-04-A04-P05`；依据 CR-AI-013、冻结 `EGRESS_AUTHORIZE/REVOKE`。
- Decision：Project Authorize 只接受 ProjectManager/CustomerManager 且必须通过强制注入的部署策略；只能缩小被锁定 Preview 边界。收据指向不可变 AuthorizeResult，重放时用该结果投影首次 `AUTHORIZED@0`，不从可变 Authorization Root 当前状态构造。Revoke 仅能在强版本0上执行一次。
- Reason：合法撤销会使当前根变为 `REVOKED@1`；如果原201重放读当前根，会改写已完成命令的历史响应。新Task/Invocation仍必须读当前根，不能因历史重放结果继续外发。
- Impact/Rollback：复用0069独立结果表，无新Schema、依赖或Breaking API；内部服务未挂公开入口，可停止后续组合，历史保留。
- Verification：定向17、Win11隔离PG18.6真实授权/策略拒绝/回滚/撤销/撤销后首次重放/跨项目隔离、后端2121运行/3跳过PASS；wheel `2b319bb6b3275317bd489aede16ed2e07041c6fdd41a2b42db4ed1e551afc1cd`。

# DEC-20261003-711：AITask 仅由锁定的当前 Authorization Owner 生成消费快照

- Date/WBS：2026-10-03 / `AI-04-A04-P06`；依据 CR-AI-010～013、DEC-703/705/710。
- Decision：Egress Owner 必须在AITask创建事务内锁定权威Authorization Root，同时验证`AUTHORIZED@0`、同Project、AI_TASK operation、有效期、SourceRef集合指纹、受信Task→Purpose映射以及当前ACTIVE Provider/当前Config/AVAILABLE Model。完整Authorization事实计算规范化指纹，再投影为Task不可变快照；消费端不接受客户端自报快照。
- Reason：批准历史结果只用于幂等响应，不代表当前还可外发；锁定当前根可使Task创建与并发撤销有明确顺序，Purpose映射防止用其他逻辑操作的授权创建Task。
- Impact/Rollback：新增内部Owner/仓储与错误契约，复用0067现有Task Snapshot，无新Schema/依赖/Breaking API；未挂公开入口，可停止组合，历史Task不删除。
- Verification：定向14、Win11隔离PG18.6当前投影/Purpose/Source/过期/撤销/Project/Task七类原子链与重放、后端2125运行/3跳过PASS；wheel `ad6e4a017f425c8a58bf6fc1643add7bf2a70c87998869548ae9a360f5ce687c`。

# DEC-20261003-712：Egress HTTP 仅显式注入并以双重版本条件授权

- Date/WBS：2026-10-03 / `AI-04-A04-P07`；依据冻结 API-03 与 CR-AI-013。
- Decision：四条 Egress 路径由一个可选 Router 显式注入，默认/当前生产组合保持404。Authorize必须同时提供强`If-Match: "v0"`和正文`expected_preview_fingerprint`：前者满足冻结资源版本前置，后者精确绑定不可变Preview内容；Revoke仅接受Authorization v0并返回v1。
- Reason：Preview本身只追加且没有可变lock_version，不能丢弃冻结合同的M控制，也不能用普通整数ETag替代完整内容指纹；双重条件兼顾统一HTTP并发合同和授权精确性。
- Impact/Rollback：无Schema/依赖/Breaking API变化；撤去可选Router注入即恢复404，既有Preview/Authorization历史不删除。未装入生产组合且不执行外发。
- Verification：合同5项覆盖默认关闭、四路径、安全投影/严格输入/权限前置/错误映射；后端2130运行/3跳过，wheel `e83a9586fe28193ccd4ca201e5665525e6c534bad0ec4f1c9afd1973e6209bd9`。

# DEC-20261003-713：Egress Windows 组合要求显式策略并分流读写 Session

- Date/WBS：2026-10-03 / `AI-04-A04-P08`；依据 CR-AI-013、冻结 EGRESS 控制标记。
- Decision：组合工厂不读取隐式默认策略，调用方必须同时注入Preview Policy与Approval Policy；GET使用无CSRF的项目读Session验证，三项写操作使用项目写Session+CSRF验证。当前生产组合在正式策略来源实现前继续不挂路由。
- Reason：一个仅支持CSRF的写适配器无法实现冻结GET合同；而把测试许可策略硬编码为生产默认会绕过逐次外发治理。显式依赖使缺项直接启动失败，读写分流保持各自锁和CSRF语义。
- Impact/Rollback：新增Auth适配器和Windows组合工厂，无Schema/依赖/Breaking API；停止调用工厂即回退，历史记录不变。P08还修复幂等HTTP投影不得要求首次业务trace等于当前请求trace。
- Verification：Win11/PG18.6真实Session/Project/Document Owner及六类Egress记录、三Audit/三Receipt链路，重放/隔离/撤销/许可拒绝PASS；合同5、后端2130运行/3跳过；wheel `d1533684503661409b357c5a567091bd01acab693b4da4b0f2645e75f2fff093`。

# DEC-20261003-714：Egress生产策略用非敏感Bootstrap快照并仅写平台挂载

- Date/WBS：2026-10-03 / `AI-04-A04-P09`；依据 CR-AI-013、DEC-713。
- Decision：以最多16条严格定型、版本化的Bootstrap非秘密策略作为Preview与Approval部署源；策略快照不包含URL/Key/正文。默认、登录和只读平台即使有配置也不挂载；显式Windows写平台无策略时仅对Egress保持404，有策略但组合失败时整体启动失败。
- Reason：Provider探针策略含endpoint且不表达逐次外发边界，不能复用；将测试放行策略写死在生产组合会绕过部署治理。显式策略快照可审查、可重启回滚且不泄露客户数据。
- Impact/Rollback：无Schema/依赖/Breaking API；受控修改Bootstrap并重启启用，移除配置并重启恢复404，既有不可变授权历史保留。
- Verification：单元6、生产组合合同32、Win11/PG18.6 Bootstrap策略真实Egress链、后端2136运行/3跳过PASS；wheel `7eeafd306f5d45efd283fdc3c1d9919090afa585ece13f4737bf99d1be6cfe5e`。

# DEC-20261003-715：AI Task提交必须锁定Prompt版本并使用分型最小参数

- Date/WBS：2026-10-03 / `AI-04-A05-P01`；依据冻结 API-03/DM-04与 CR-AI-014。
- Decision：不直接对现有三个字符串策略引用开放HTTP。先用0070固定PromptTemplate/PromptVersion和受Task Policy分型约束的最小参数及其SHA-256；新Task必须完整，旧NULL历史不回填且不可执行。
- Reason：Worker时再解析活动Prompt会使提交与执行版本漂移；任意JSON参数则可以绕过InputRef/Egress治理传递客户正文。
- Impact/Rollback：需CR-AI-014/Schema0070增量修订，原0063～0069和冻结提交保留；空新历史可降级，有新Task拒绝降级。本项仅记录，尚未实施Schema/API。
- Verification：静态对照冻结合同、AITask服务/ORM/Repository、Prompt和Egress Owner；未运行新测试。

# DEC-20261003-716：Schema0070以全空或完整快照实现分阶段兼容

- Date/WBS：2026-10-03 / `AI-04-A05-P02`；依据 CR-AI-014、DEC-715。
- Decision：0070先增加PromptTemplate/Version与有界参数快照，数据库仅接受四列全空或完整；完整快照必须引用当前ACTIVE版本并匹配Task类型、Output Schema与RAG Policy，且创建后不可改。旧行与尚未公开的旧内部链暂保留全NULL，P03负责让应用新写完整并拒绝执行NULL历史。
- Reason：直接将四列设为NOT NULL会破坏0069历史及当前原子创建链；在Task Policy/Prompt Owner尚未落地时猜测回填又会伪造业务事实。分片迁移可先建立可验证防线，同时不虚报入口已启用。
- Impact/Rollback：增量Schema0070、ORM和迁移合同；无公开API/依赖变化。无完整快照可降0069；有完整历史拒降并向前修复或受控恢复。
- Verification：Win11/PG18.6空库/历史库up-down-re-up、drift、Prompt/策略/JSON/摘要/不可变/拒降PASS；后端2136运行/3跳过，wheel `a6e14f401ffc911cf84091c685e932f76eff74d611ad97e8b484caa18af22c7a`。两次开发期验证分别发现变量歧义及JSON检查顺序并修正，最终全量重跑。

# DEC-20261003-717：Task Policy分型参数并由PostgreSQL形成Prompt提交摘要

- Date/WBS：2026-10-03 / `AI-04-A05-P03`；依据 CR-AI-014、Schema0070。
- Decision：部署注入的版本化Task Policy精确绑定task type、PromptTemplate、purpose、Output Schema、RAG policy和严格标量参数Schema；Prompt Owner在同一创建事务锁定当前ACTIVE版本。应用负责参数允许集，PostgreSQL负责JSONB规范化与SHA-256，最终快照随Task原子写入。Policy purpose必须等于当前Egress Authorization purpose。
- Reason：任意JSON会成为客户正文旁路；Python JSON编码与PostgreSQL `jsonb::text`不完全同构，不能由不同运行时各自声称同一摘要；提交后再解析活动Prompt则会造成版本漂移。
- Impact/Rollback：内部CreateAITask新增参数及强制Policy/Prompt Owner依赖，复用0070，无新迁移/公开API/依赖/外发。停止后续组合可回退应用，完整Task历史保留。
- Verification：定向16、Win11/PG18.6严格参数/锁定Prompt/数据库摘要/原子链/重放/退役和不匹配拒绝、后端2140运行/3跳过PASS；wheel `c214a8a277f9ef8521b68a62930b389053d105891c87bf68b4963fb2c1c215a8`。首轮双重JSON编码被数据库拒绝，修正Text→JSONB后从新库完整重跑。

# DEC-20261003-718：AI Task创建HTTP只接受最小七字段并保持可选注入

- Date/WBS：2026-10-03 / `AI-04-A05-P04`；依据冻结API-03、CR-AI-014。
- Decision：冻结POST路径严格接收task type、input refs、三类策略引用、最小标量参数及EgressAuthorizationRef；返回仅TaskRef+JobRef。Router继续可选注入，默认及生产组合在P05前保持404。策略/Prompt和Egress失败映射冻结安全码，不暴露Owner内部原因。
- Reason：P03已具备完整内部原子链，但直接全局挂载会在部署Task Policy/正式组合未完成时开放不完整能力；严格DTO也防止Key、endpoint、正文或任意Provider参数旁路。
- Impact/Rollback：新增Router/App工厂槽和两项冻结AI错误码；无Schema/依赖/外发。撤注入恢复404，历史不变。
- Verification：合同14项、后端2145运行/3跳过PASS；wheel `6f854dd6386108a0ad01c2f4b2aa8fe694af5bf0ec734be05d0f586889922ee7`。首轮缺Idempotency-Key状态断言按既有平台422语义修正并全量重跑。

# DEC-20261003-719：Task Policy版本必须随提交快照持久化并在执行前重验当前外发资格

- Date/WBS：2026-10-03 / `AI-04-A05-P05`；依据 CR-AI-014、Schema0070、DEC-717/718。
- Decision：用严格非敏感Bootstrap生成不可变Task Policy和Task→Purpose映射；仅显式Windows写平台有有效策略时挂载创建。新增0071保存 `prompt_policy_version`，新Task必须完整、旧NULL历史不可执行。执行前置除读取完整Task/Prompt/参数/Job/Egress快照外，还须通过当前Egress Owner重验未撤销授权及ACTIVE Provider/当前Config/AVAILABLE Model。
- Reason：P03已在内存解析策略版本但0070未保存，历史Task无法证明策略版本；仅依赖创建时授权快照又会允许撤销后的Task进入Worker。两者都不满足冻结追溯与逐次外发控制。
- Impact/Rollback：新增0071可空兼容列、部署策略源、Windows组合和内部执行前置；不改冻结URL/依赖且无外部调用。无版本化历史可降0070，有历史拒降并向前修复；移除配置重启恢复Task POST 404。
- Verification：Win11/PG18.6真实Egress+Task HTTP/PG链、202重放、版本不可变、执行准入/撤销拒绝PASS；定向50、后端2153运行/3跳过；wheel `32a3d4b414b2dec7bce36ea2b307f313833c7c62d6ebc9f795ccdc75bbb1b7e0`。

# DEC-20261003-720：Task GET按管理角色或创建人授权并只返回引用投影

- Date/WBS：2026-10-03 / `AI-04-A05-P06`；依据冻结 API-03、CR-AI-014、DEC-719。
- Decision：项目经理、客户经理可读取项目内Task；其他有效项目成员仅可读取自己提交的Task。未授权、普通成员读取他人Task、跨项目和不存在资源统一404。响应只包含冻结合同需要的状态、版本和资源引用，禁止Task参数、Prompt/Input正文、Provider原始载荷及Secret；未知Input Owner映射失败关闭。
- Reason：项目管理需要查看执行状态和追溯关系，但普通成员不应借Task ID浏览其他人的处理上下文；显式列投影比先加载完整实体再过滤更能控制敏感内容泄漏。
- Impact/Rollback：新增可选GET Router、读取服务/Repository、Windows组合和 `AI_TASK_GET` 项目读策略；无Schema、依赖、Breaking URL或外发。撤Router注入恢复404，历史不变。
- Verification：Win11/PG18.6真实HTTP/PG创建人及项目经理200、普通成员和跨项目404、Query拒绝与无参数/正文PASS；定向43、后端2157运行/3跳过，wheel `63315024faa0b1d4f5d7776579679b6af5030743257df2b4e0dd7cb2160c6c0e`。Worker最终payload/Invocation/发送前限制仍由A06继续验收。

# DEC-20261003-721：AI外发授权必须绑定服务端确定性最终载荷

- Date/WBS：2026-10-03 / `AI-04-A06-P01`；依据 ADR-004、DM-04、API-03、Schema0064、CR-AI-015。
- Decision：不接受客户端自报payload摘要作为AI Worker最终放行证据。采用服务端确定性 `AIExecutionEnvelope`，让AI_TASK Preview、Task创建复核和每次Invocation共用构建器；实际字节摘要、来源、Provider/config/model/region、数据类别、字节/Token/重试上限任一不符均在网络I/O前拒绝。旧记录无服务端计划证明时不可执行。
- Reason：客户端无权读取完整Prompt，也无法可靠复刻模板、编码和Provider序列化；逻辑引用摘要不能捕获正文或字节变化，发送后再记录则无法撤回外发。
- Impact/Rollback：P01仅文档，后续按CR-AI-015分片实现；不改现有Schema/API/依赖。撤未来Worker/路由组合恢复不消费，历史保留，不删除Invocation/Audit。真实Provider调用仍需明确数据范围授权。
- Verification：静态对照冻结合同、Schema0064、P05执行前置、Egress Owner和现有AI模块；确认无生产AIService/ModelRouter/ProviderAdapter、确定性载荷构建或Invocation发布服务。本项未运行新代码测试，不标Worker PASS。

# DEC-20261003-722：Execution Grant只承载完整元数据和无正文载荷证明

- Date/WBS：2026-10-03 / `AI-04-A06-P02`；依据 CR-AI-015、DEC-721。
- Decision：建立不可变 `AITaskExecutionGrant`，覆盖Task/Job/Attempt/Fencing、InputRef顺序、Prompt/Schema/Provider/Model/授权快照及所有定量上限；以规范化SHA-256形成Grant摘要。载荷构建器只返回无正文 `AITaskPayloadPlanProof`，必须精确匹配Grant/来源/批准payload并在记录数、字节、Token和有效期内。
- Reason：后续内容读取、Provider序列化和网络调用需要一个可复核但不会把正文/Secret扩散到Job或日志的边界；仅比较payload摘要会漏掉Claim代次、模型、Prompt或授权上限变化。
- Impact/Rollback：新增未装配内部合同与单测，无Schema/API/依赖/运行行为变化；撤模块即可。P03细分为当前Jobs Claim+PG投影和内容Envelope两步，避免AI模块把裸Job表当授权。
- Verification：定向4、后端2161运行/3跳过PASS；wheel `eea3cec629b1cf64060dfb6faf7fea5ca755aaf9e42cd58779808c705af06401`。首轮失败仅为测试在构造时即触发预期校验及把计数字段误判正文，修正测试后全量重跑。

# DEC-20261003-723：AI执行只能接受Jobs-owned当前Claim证明

- Date/WBS：2026-10-03 / `AI-04-A06-P03-P01-A01`；依据 CR-AI-015、Jobs Lease/Fencing基线。
- Decision：新增Jobs-owned `AITaskExecutionClaim`，携带Task/Project/原actor/Trace/Authorization/Input摘要和当前attempt/fencing/max-attempts；AI模块只在自己的短事务中调用Owner并复核请求Job/token，不直接把裸Job行或通用ClaimedJob当执行许可。
- Reason：通用Claim缺原actor与最大尝试数，不能证明AI Task、外发授权和原Outbox绑定；跨事务缓存Claim也会绕过Lease到期/fencing。
- Impact/Rollback：仅新增未装配内部DTO/Service与单测，无Schema/API/依赖；撤模块即可。A02补PostgreSQL Owner，A03再组合完整Grant。
- Verification：定向7、后端2164运行/3跳过PASS；wheel `ae993dc1a638c20c488df2d86e3eea4c04bc7417b58508e3c75f42778eab5e52`。本项不宣称实际PG Claim或Worker可用。

# DEC-20261003-724：AI Task Claim复用唯一Lease锁并绑定原始Outbox

- Date/WBS：2026-10-03 / `AI-04-A06-P03-P01-A02`；依据 CR-AI-015、DEC-723。
- Decision：Jobs Owner Repository先调用现有Lease Repository核当前worker/fencing/未过期ACTIVE Lease和Attempt，再验证严格AI Task三字段payload、原actor/Project/Trace/最大尝试及唯一 `AI_TASK_QUEUED` Outbox。AI模块不得自行重写Lease判断或从payload猜缺失事实。
- Reason：分别查询Job、Lease、Attempt或不核Outbox会产生代次漂移、伪造来源及任务/授权错配；复用同一事务当前锁保持Jobs为唯一Owner。
- Impact/Rollback：新增内部Repository和验证脚本，无Schema/API/依赖/生产装配；撤Repository保留历史。A03再组合完整Execution Grant。
- Verification：Win11/PG18.6真实claim及错误worker/token、额外payload、Outbox漂移拒绝PASS；定向8、后端2164运行/3跳过，wheel `fd96d52395a7e27fd228d90fcc197a3eed982704cbeb1b5472e0afc1caab46eb`。首轮仅验证脚本数据库工厂旧参数，修正后新库重跑。

# DEC-20261003-725：Execution Grant由Jobs Claim与AI Owner投影在同一短事务合成

- Date/WBS：2026-10-03 / `AI-04-A06-P03-P01-A03`；依据 CR-AI-015、DEC-722～724。
- Decision：AI执行Grant必须先通过Jobs-owned当前Claim，再由AI Repository锁定Task并投影顺序InputRef、当前ACTIVE Prompt/哈希、Schema/参数、AVAILABLE CHAT Model及Egress快照，最后调用Egress Owner重验当前授权和路由。AI Repository禁止把裸Job查询当成授权。Grant显式增加最小载荷策略和最大记录数，取自当前Authorization且由快照中的完整授权摘要绑定；License在事务内与边界后双检，发送前还须再检。
- Reason：单独的Task快照不能证明Worker仍持有当前attempt，单独的Job claim也不能证明Prompt/Model/Authorization未漂移；最大记录数和最小载荷策略若不进入Grant，后续Envelope构建器无法在无隐式配置的条件下确定边界。
- Impact/Rollback：仅内部合同、Issuer和Repository；无Schema、公开API、依赖、生产Worker或外发变化。撤未装配组件即可回退，已有Task/Job/授权历史不改。
- Verification：Win11/PG18.6完整链仅有效记录签发Grant；Prompt活动版本漂移、模型/批准payload快照漂移、撤销均拒绝，Invocation为0。定向15、后端2167运行/3跳过；wheel `87690d1d519bfd23bc0b8ca0e02881f989e67d07d66227a623c3bdc00215b16d`。两次夹具失败分别来自授权历史和当前Prompt数据库守卫，修正夹具后全新库PASS。

# DEC-20261003-726：业务Input与实际AI正文之间增加不可变Content Plan

- Date/WBS：2026-10-03 / `AI-04-A06-P03-P02-P01`；依据冻结DM-04/API-03、CR-AI-015/016。
- Decision：AITask继续绑定业务InputRef；AI_TASK Preview由服务端建立不可变 `AIExecutionContentPlan`，固定精确DocumentVersion+ParseRecord/Result hash、Prompt/参数、Context、编码和Estimator版本，Authorization/Task/Invocation绑定同一Plan。未知或尚未实现的RAG policy失败关闭；旧无Plan历史不回填且不可执行。
- Reason：DocumentVersion可对应多个解析结果，运行时选latest会造成批准载荷和重试漂移；客户端摘要、原文件字节或静默空Context均不能证明冻结合同要求的实际最小载荷。
- Impact/Rollback：P03-P02先增加未装配内部合同，P04再以追加Schema和兼容API语义持久化Plan；原冻结提交与旧历史保留。回滚撤Worker/Preview新组合并停止消费，不删除Plan/Authorization/Invocation历史。
- Verification：静态交叉核对AITask/Egress实现、Document固定来源证明、Prompt规范化、DM-04/API-03及RAG模块清单；本项无代码/Schema/API/依赖/外发，未运行新增测试。

# DEC-20261003-727：Content Plan只保存可复核身份且Context形态闭合

- Date/WBS：2026-10-03 / `AI-04-A06-P03-P02-A01`；依据 CR-AI-015/016、DEC-726。
- Decision：Content Plan只保存按序业务输入映射、精确Owner revision/object、producer/schema/policy、摘要/大小/计数、Prompt/Context/Model/编码/Estimator版本；禁止正文、参数值、locator和Secret。Context只能是字段全空且计数为零的NONE，或引用/摘要/计数全部完整的RAG_CONTEXT。Grant逐项核业务身份，内容结果变化由Plan fingerprint捕获并待P04持久绑定。
- Reason：把正文或动态Owner查询塞入Grant会扩大Job/日志泄漏面；允许半空Context或只比较业务Input则无法证明实际发送内容与授权一致。
- Impact/Rollback：新增未装配Application合同和单测，无Schema/API/依赖/运行行为；删除模块即可回退。旧无Plan历史仍不可执行。
- Verification：定向10、后端2173运行/3跳过PASS；wheel SHA-256 `1ccf1411c3eee3ebc438f8108213b6ecdab3a358cd81f199907d685cd48acf0c`。三轮开发期语法/版本规则/断言位置问题修复后均从修正状态重跑。

# DEC-20261003-728：Prompt渲染只允许三个字面占位符且插入内容不再解析

- Date/WBS：2026-10-03 / `AI-04-A06-P03-P02-A02`；依据 CR-AI-015/016、DEC-727。
- Decision：Prompt/Task参数必须由AI Owner按Grant精确投影；渲染策略 `strict-placeholders.v1` 仅接受 `{input}`、`{context}`、`{parameters}`，不实现表达式/属性/条件/动态模板。Input恰好一次，RAG Context和非空参数恰好一次；替换仅扫描原模板，插入正文中的大括号保持字面量。旧Prompt不兼容时创建新版本，不运行时猜测改写。
- Reason：通用模板引擎会扩大注入和非确定性面；重复替换会让客户正文被误解释为控制语法；静默忽略参数/Context会让批准计划与实际语义不一致。
- Impact/Rollback：新增未装配Owner/Repository/Renderer，无Schema/API/依赖/生产行为；撤组件即可。严格语法不回填旧Prompt，未准入版本继续不可执行。
- Verification：Win11/PG18.6精确投影/渲染及参数、活动Prompt漂移拒绝，Invocation=0；定向16、后端2179运行/3跳过PASS；wheel SHA-256 `c11a990c885c0c76ec93c83038da4ab62887ebffc1839a4f0b26c898518450b0`。首轮唯一失败为负例夹具未同步模板hash，修正后完整重跑。

# DEC-20261003-729：后台Document内容读取以原请求人当前Project权限和冻结解析结果双重约束

- Date/WBS：2026-10-03 / `AI-04-A06-P03-P02-A03`；依据 CR-AI-015/016、DEC-726～728。
- Decision：规划阶段由Document Owner确定一个具体成功ParseRecord/ParseResultRef；执行阶段只读取Content Plan冻结身份，不再选择latest。Worker不复用浏览器Session，新增内部 `AI_TASK_EXECUTE` Project操作，以Task原请求人身份在每次规划和读取时锁定并重验当前Project/Department/Member事实，仅ProjectManager/ImplementationMember且活动项目可继续。
- Reason：DocumentVersion并不唯一对应解析正文；运行时重新选latest会使批准载荷漂移。后台进程没有且不得持有用户Session，若只信Task创建时权限则成员暂停/移除或项目归档后仍可能外发。
- Impact/Rollback：新增内部Project策略、Document Owner/Repository、最小正文投影和AI反腐层；无Schema、公开API、依赖、生产装配或网络调用。撤新组件和策略项即可回滚，已有Document/Task/授权历史不变；旧无Plan记录不可执行。
- Verification：Win11/PG18.6/本地私有文件证明旧Plan不随新ParseRecord漂移、当前成员暂停和文件篡改拒绝、Invocation=0；定向19、后端2185运行/3跳过PASS；wheel SHA-256 `5bed8f10c02b9935de2224a227d68f3d410dbde1306b78293450d7ec9252800d`。

# DEC-20261003-730：Plan同时固定Owner原始结果与最小投影并以显式策略构建Envelope

- Date/WBS：2026-10-03 / `AI-04-A06-P03-P02-A04`；依据 CR-AI-015/016、DEC-726～729。
- Decision：Content Source在source/result hash之外增加 `projection_fingerprint`，由Owner规划时计算、执行时重算；Envelope只接收与Plan数量/顺序/身份/hash全匹配的projection，按 `provider-neutral-json.v1` 规范编码并由服务端计算payload fingerprint。Context仅允许Registry显式注册的NONE policy；RAG没有不可变Owner时关闭。Token estimator按ref/version/model绑定并可注入，内置UTF-8 byte upper-bound仅供已证明兼容的Adapter/模型绑定。
- Reason：ParseResult hash不能让通用Builder单独核派生projection bytes；调用者自带Context或隐式默认estimator会使批准内容、Token上限和实际语义漂移。Provider-neutral字节必须在网络Adapter前确定且可重复。
- Impact/Rollback：修改尚未持久化的内部Source合同，新增Envelope/Context/Estimator组件与验证；无Schema、公开API、依赖、生产装配或网络I/O。P04持久化前可整体撤回；持久化后须保留不可变hash历史并向前修复。
- Verification：Win11/Python3.13禁socket构建确定性Envelope，hash/顺序/Context/Estimator/限额负例PASS；A02/A03 Win11/PG18.6重跑，定向24、后端2191运行/3跳过；wheel SHA-256 `3e39c82a15758fc6521e0f74af8eb5c05da480db1fe02d931ed90e3862c52e1b`。首次字段放置错误导致6个构造TypeError，移至Identity后全部重跑通过。

# DEC-20261003-731：AI_TASK Preview必须携带计划输入并由服务端计算载荷证明

- Date/WBS：2026-10-03 / `AI-04-A06-P04-P01`；依据 CR-AI-016、DEC-726～730、Schema0068～0071。
- Decision：保持现有URL和响应；AI_TASK Preview请求新增必需 `ai_task_plan`，提前提交与Task Create相同的task type、Prompt/output/context policy和最小参数。AI_TASK不再接受客户端estimated record count/payload fingerprint，改由Owner+Prompt+Envelope服务端计算；非AI operation原合同不变。0072以Plan/Source新表反向一对一绑定Preview，并在Authorization、Task、授权快照、Invocation传播同一PlanRef。旧NULL历史不回填且不可执行。
- Reason：现有Preview发生在Task之前，缺Prompt/参数，客户端hash也无法证明ParseRecord/最小投影/服务端Prompt/Estimator；若Task创建后才生成Plan，审批没有覆盖实际内容。
- Impact/Rollback：这是尚未正式发行的AI_TASK请求体有意收紧，前后端原子升级并保留错误显式；非AI不变。Schema有新Plan历史后拒绝down，回滚应用时停止AI_TASK新建/消费并保留历史向前修复。
- Verification：静态交叉核对Preview、Authorization、Task、Invocation ORM/API和A01～A04合同；本项仅文档，无代码测试、Migration、API运行变化或外发。P02起按空/历史库和双操作类型验证。

# DEC-20261003-732：Schema0072以反向一对一Plan冻结Preview内容身份

- Date/WBS：2026-10-03 / `AI-04-A06-P04-P02`；依据 CR-AI-016、DEC-731、Schema0068～0071。
- Decision：新增无正文 `ai_execution_content_plans/sources`；Plan以唯一Preview外键反向一对一绑定，Source仅能在Plan创建事务内写入且必须匹配Preview Source。延迟完整性约束在提交时检查来源非空/连续/数量/记录数，Plan/Source与Plan后的Preview Source均冻结。四个下游根新增可空、不可变PlanRef，旧NULL历史不回填；有Plan历史拒降。
- Reason：正向在既有Preview加非空列会破坏历史，允许后续追加Source或跨事务补齐又会使已计算的Plan/hash可漂移。反向唯一绑定既保留旧行，又允许同一事务原子创建完整图。
- Impact/Rollback：Schema增量且旧行NULL；P04-P05前尚不强制新写链使用Plan。空Plan历史可降0071；出现Plan后停止新消费、保留历史并向前修复。无公开HTTP、正文、参数值、locator、Secret或网络外发。
- Verification：Win11/PG18.6空/历史/Plan三库up/down/re-up、ORM drift、AI/非AI兼容、完整性/身份/不可变/截断/敏感列/拒降负例PASS；后端2194运行/3跳过；wheel SHA-256 `eee89c4747111b62db83116621d22e010fa16751f314835e62ac417a40adb306`。首次触发器变量歧义与ORM清单漏登记均修正后全量重跑通过。

# DEC-20261003-733：Repository返回前强制校验完整Plan图且不持久化Envelope正文

- Date/WBS：2026-10-03 / `AI-04-A06-P04-P03`；依据 CR-AI-016、DEC-732、Schema0072。
- Decision：应用Owner接收短命Plan+Envelope，重验二者的Plan/source/encoding/estimator/context身份，仅把Plan身份和Envelope hash/计数交给Repository。Repository写根/来源并以schema限定名称即时触发0072延迟完整性，再恢复延迟模式；读取重建强类型Plan并重算Plan fingerprint。完全一致的PlanId+PreviewId重放返回原记录，证明漂移失败关闭。
- Reason：持久化canonical Envelope会扩大客户正文面；只在事务commit时发现图不完整会使调用方在返回后才失败；只信任数据库中的Plan hash又不能发现数据库映射或历史异常。
- Impact/Rollback：内部未装配组件，无HTTP/Schema/依赖/Invocation/外发变化。可撤Repository/Owner但保留0072历史。并发创建将在P04-P04写服务中以Preview幂等和唯一键收口。
- Verification：Win11/PG18.6真实写/提交/新事务读/精确重放/漂移拒绝/rollback、零Invocation通过；单元3、后端2197运行/3跳过；wheel SHA-256 `b7c2a8b7a088339cb3dc2b03d0af2e6431dcf7e016cc4ff117526394eb307c6a`。首次未限定schema的SET CONSTRAINTS失败，改为`plm.trg_*`后新库完整重跑通过。

# DEC-20261003-734：Preview规划使用独立Prompt内容而不伪造Task/Job身份

- Date/WBS：2026-10-03 / `AI-04-A06-P04-P04-A01`；依据 CR-AI-016、DEC-731～733。
- Decision：新增Preview专用Prompt规划投影和服务端Plan Builder；Builder用部署Task Policy、当前Prompt、显式Source Owner、Provider route、Context与Estimator构建Plan/Envelope。不得为复用执行期内容合同而生成虚假的TaskId/JobId/AuthorizationId。
- Reason：Preview发生在Task之前；伪身份会污染追溯语义，也会让执行期授权字段看似已经存在。独立最小合同可复用严格Renderer而不降低边界。
- Impact/Rollback：内部未装配合同，无Schema/API/依赖/持久化/外发；可整体撤回。后续A02～A06逐层接Owner、Preview事务、HTTP与Windows组合。
- Verification：Builder新增2项、Prompt/Envelope合计14项、后端2199运行/3跳过；wheel SHA-256 `da9d8cc92d8442955ceec44c01deecd9fc0c00494f5e50932b73bdb81bae81ce`。

# DEC-20261003-735：Preview Prompt读取锁定当前模板但允许活动版本正规推进

- Date/WBS：2026-10-03 / `AI-04-A06-P04-P04-A02`；依据 CR-AI-016、DEC-731～734。
- Decision：规划期Owner在调用方事务内以`FOR KEY SHARE`锁定DEPLOYMENT/ACTIVE PromptTemplate，读取其当前活动版本；精确匹配Task Policy固定的task type、template、output schema和context policy。Policy不固定活动版本号，正式激活的新版本用于后续新Preview；每个Plan仍固定实际version/hash。参数经PostgreSQL JSONB规范化并由数据库计算摘要。
- Reason：把活动版本号误当Policy常量会阻断正式Prompt升级；不锁模板则Preview规划期间活动指针可并发漂移。数据库端JSONB摘要与后续持久化语义保持一致。
- Impact/Rollback：新增内部Owner/Repository与验证，无Schema、公开API、依赖、生产装配、持久化或外发变化；不装配并删除组件即可回滚。
- Verification：单元2、相关定向10；Win11/PG18.6活动版本、JSONB摘要、行锁、敏感repr、漂移拒绝和零Invocation PASS；后端2201运行/3跳过；wheel SHA-256 `2fc1a8ef6d9216063715acd205e143cd678af01a8ff325b645d7ba189e14f2db`。首轮测试误把合法活动版本推进当漂移，修正验收边界后全部重跑通过。

# DEC-20261003-736：Document Preview规划与Task执行使用分离权限但共享精确投影算法

- Date/WBS：2026-10-03 / `AI-04-A06-P04-P04-A03`；依据 CR-AI-016、DEC-726～730/735。
- Decision：Document规划投影用`EGRESS_PREVIEW_CREATE`当前Project权限选择并锁定当前成功ParseRecord/Result；执行期精确读取继续用`AI_TASK_EXECUTE`。二者共享同一规范化、最小化、完整性和数据库前后复核算法，正式最小载荷引用统一为`minimum.document.text.v1`。
- Reason：CustomerManager按冻结策略可以创建/审批Preview但不能执行AI Task；复用执行权限会错误拒绝合法Preview，反向放宽执行权限则越权。两个阶段必须产生同一最小投影语义但不能混用授权。
- Impact/Rollback：新增内部Service/Adapter入口并修正未装配Builder测试别名；无Schema、公开API、依赖、持久化或网络变化。撤新入口即可回滚，执行期路径不变。
- Verification：单元新增1、Document/Builder合计9；Win11/PG18.6精确投影、CustomerManager权限分离、事务锁、敏感repr、零Plan/Invocation以及旧执行期PG回归PASS；后端2202运行/3跳过；wheel SHA-256 `2760da76b2fe311d5aabf5e3ef0222b3555497e7035a5354de17afc49a5f919a`。首轮验证仅临时目录创建顺序错误，修正后全新资源完整重跑。

# DEC-20261003-737：AI_TASK Preview先由服务端构建Envelope并与Plan原子持久化

- Date/WBS：2026-10-03 / `AI-04-A06-P04-P04-A04`；依据 CR-AI-016、DEC-731～736、Schema0072。
- Decision：带`ai_task_plan`的内部AI_TASK Preview必须省略客户端record count/payload fingerprint；同一事务解析Source、锁定Route/Prompt、构建Envelope、写Preview、唯一Plan/Source、Audit和Receipt。Preview展示的计数/hash来自Envelope。重放不重读可变Owner，但必须读取并复核原不可变Plan；Task参数属于幂等请求指纹。
- Reason：先写Preview再异步补Plan会留下已可审批但没有内容证明的窗口；重放重新读取Source会破坏幂等，而只返回Preview不核Plan又会掩盖历史损坏。Provider model key/revision必须来自锁定数据库Route，不能由客户端补齐。
- Impact/Rollback：扩展内部Command/Route与可选Service依赖，无Schema、公开HTTP、依赖或网络变化；旧内部路径保留到A05切换。回滚不装配Builder/Plan Owner并关闭新AI_TASK入口，已提交Plan历史保留。
- Verification：新增单元2、相关12；Win11/PG18.6真实Preview/Plan/Source/Audit/Receipt原子提交、重放、参数冲突、Audit全回滚、零Invocation和旧Preview PG回归PASS；后端2204运行/3跳过；wheel SHA-256 `3b4bae40ee433e65dcee8e43e52a72c40fe33834a1172de357e0b7ce0487ef99`。

# DEC-20261003-738：AI_TASK与非AI Preview使用互斥HTTP请求形态

- Date/WBS：2026-10-03 / `AI-04-A06-P04-P04-A05`；依据 CR-AI-016、DEC-731/737。
- Decision：AI_TASK请求必须提供五字段`ai_task_plan`且不得提供客户端派生record count/payload fingerprint；RETRIEVAL/INDEX请求保持旧派生字段且不得提供Task Plan。严格字段集合使旧AI_TASK明确400而非静默忽略。响应与URL不变。
- Reason：静默接受旧摘要会让调用方误以为它仍是授权依据，也给双重语义留下空间；非AI操作尚无本切片的Owner/Plan实现，不能误用AI Task合同。
- Impact/Rollback：已登记的`/api/v1`有意收紧，旧冻结提交保留；尚无正式发行依赖旧AI_TASK形态，前后端原子升级。回滚须同时撤客户端且保持AI_TASK关闭，不能恢复信任客户端摘要。
- Verification：HTTP合同6项、后端2205运行/3跳过PASS；wheel SHA-256 `e424ed47c2fc910205d5c0878741c89eee130ff86754b9c68fdbc9c37c895c0a`。无Schema/依赖/外发；真实Windows HTTP/PG组合留A06。

# DEC-20261003-739：Windows Egress仅在Task Policy完整时装配服务端Content Plan

- Date/WBS：2026-10-03 / `AI-04-A06-P04-P04-A06`；依据 CR-AI-016、DEC-731/737/738。
- Decision：Windows显式写组合在部署存在`ai_task_policies`时，同时注入统一`data_root`、Prompt规划Owner、Document最小内容Owner、Envelope/Plan Builder和Plan Repository。只有Egress Policy而没有Task Policy时不构造伪默认计划；AI_TASK失败关闭，非AI路径保持兼容。
- Reason：A05已禁止客户端派生摘要，若组合根未接实际Owner，合同虽存在却只能503；若以默认Prompt/正文或客户端值补齐则绕过部署准入、内容最小化和不可变证明。
- Impact/Rollback：无Schema、依赖、冻结URL/响应或Provider外发变化；生产配置需同时提供匹配Policy/Prompt/ParseResult。移除Task Policy并重启即可关闭AI_TASK规划，既有Plan历史保留。
- Verification：Windows11/PostgreSQL18.6真实ASGI Session/Project/Document/Prompt链完成201创建/重放、旧形态400、授权201、License403，Preview/Plan计数及指纹一致且Invocation=0；定向45、后端2206运行/3跳过PASS；wheel SHA-256 `38884673913bd55efc194680f35513dd7a8e0020f728688458523a03a8aa5ced`。首次证据Prompt夹具不兼容导致安全503，修正夹具后新库完整重跑。

# DEC-20261003-740：AI Task执行资格以同一不可变PlanRef贯穿授权、任务和Grant

- Date/WBS：2026-10-03 / `AI-04-A06-P04-P05`；依据 CR-AI-015/016、Schema0072、DEC-731/739。
- Decision：新AI_TASK Authorization必须继承Preview的非空Content Plan ID；Task与其授权快照原子保存同一引用；Preflight和Grant签发同时复核Task、快照、当前Authorization一致。Grant指纹包含Plan ID，内容加载要求精确ID相等。旧NULL历史继续可读/可撤销但不得创建新Task或执行。
- Reason：只比较payload/source fingerprint不能证明下游消费的是哪一个不可变Plan；允许NULL或各根引用分叉会使批准内容与实际执行内容失去可追溯闭环。
- Impact/Rollback：复用0072已有列，无Migration、公开响应、依赖或外发变化。应用回滚必须关闭新AI_TASK执行并保留历史，不得恢复信任客户端摘要。当前没有生产Invocation writer，本决定只把Plan身份送达Grant并为下一切片提供强前置。
- Verification：Win11/PG18.6真实Preview→Authorization→Task→Preflight链四处PlanRef一致、Task重放稳定、旧形态/License失败关闭且Invocation=0；定向33、后端2209运行/3跳过PASS；wheel SHA-256 `0500de4bb38f766103ae0980fa83c0232424a362ca4d6e588c4d2c0fc5bd6338`。

# DEC-20261003-741：Invocation写入前先补数据库Plan同源守卫

- Date/WBS：2026-10-03 / `AI-04-A06-P05-P01`；依据 CR-AI-015/016、Schema0064/0072、DEC-740。
- Decision：不直接以应用Repository创建Invocation。先追加Schema0073，在INSERT时要求新Invocation非空PlanRef，并与Task、授权快照及Content Plan的身份/载荷证明同源；旧NULL历史保留且不可执行。随后才实现同一短事务的PENDING Attempt与Task当前指针。
- Reason：0072的FK只能证明Plan存在，更新触发器只能证明引用不变，不能阻止新Invocation跨Task引用另一个合法Plan或写NULL。仅靠应用层检查无法提供数据库最终守卫。
- Impact/Rollback：P01仅文档。P02将是无新表/列的触发器增量；已有NULL历史不回填。产生新Invocation后拒绝降级，应用回滚关闭业务AI消费并保留历史。
- Verification：静态核对0064/0072 Migration、ORM、冻结DM/API与当前worker入口；确认生产代码中除ORM外没有AIInvocation写入，未运行新增测试、无网络外发。

# DEC-20261003-742：0073只证明不可变快照同源，当前授权与Lease继续由应用层重验

- Date/WBS：2026-10-03 / `AI-04-A06-P05-P02`；依据 CR-AI-015/016、DEC-741、Schema0064/0072。
- Decision：以独立BEFORE INSERT触发器核新Invocation、Task、授权快照和Content Plan的完整静态等价关系；不在数据库触发器中读取当前Authorization状态、License或Job Lease，也不替换0064状态机。
- Reason：静态历史一致性适合数据库最终守卫；当前授权/License/Lease会变化且涉及Owner边界，必须在调用方短事务和网络发送前检查。把二者混入触发器会造成隐式跨模块授权并仍无法覆盖事务提交后的网络窗口。
- Impact/Rollback：Schema头增至0073，无表/列/API/依赖/外发变化；旧NULL历史保留。无非空Invocation PlanRef可降级，有新历史时拒降并向前修复。
- Verification：Win11/PG18.6空库和旧NULL历史升降重升、drift=0；新NULL/跨Plan/payload漂移拒绝、精确PENDING插入和有新历史拒降PASS；后端2211运行/3跳过，wheel SHA-256 `d2301d828172e76fc2eec67d5c4ec5b8a7c79c1fe96f4c245f4754eb97f2ca46`。

# DEC-20261003-743：Invocation Begin提交前只写证明，提交后再验License且不跨网络持有事务

- Date/WBS：2026-10-03 / `AI-04-A06-P05-P03`；依据 CR-AI-015/016、DEC-742、Schema0073。
- Decision：Grant Issuer增加调用方事务内入口；Begin服务在同一短UoW内完成Claim/授权/License复核、PENDING Invocation插入及Task指针/状态推进，并显式commit。commit后再验License；任何Provider I/O必须发生在事务外且发送前再次检查。正文不进入Invocation。
- Reason：Grant与Invocation分事务会留下撤权/fencing竞争窗口；跨网络持锁又会放大锁时长且不能使外部副作用可回滚。PENDING先落证据、事务外调用是可追溯且失败关闭的边界。
- Impact/Rollback：内部应用/Repository增量，无Migration/API/依赖/生产装配/外发。未装配可撤代码；已提交PENDING及Task状态不能删除，须由后续终态/对账收敛。当前只支持NONE Context。
- Verification：Win11/PG18.6真实UoW原子Begin、重复拒绝、注入故障全回滚、零Provider I/O；定向9、后端2213运行/3跳过PASS；wheel SHA-256 `c6af40d3c0558987e475b1f0bc0c3a7528a48ff92190a99ea394ef4cbf815d0b`。首次证据遗漏显式commit，修正后新库完整重跑。

# DEC-20261003-744：Envelope先于Begin构建，Begin必须以重签Grant复核同一Proof

- Date/WBS：2026-10-03 / `AI-04-A06-P05-P04`；依据 CR-AI-015/016、DEC-740～743、Schema0073。
- Decision：在Task仍为QUEUED时，以实时Claim签发Grant，用短读事务从不可变Plan指定的Prompt/Document Owner构建Envelope和Proof；随后Begin短写事务重签Grant并以`require_payload_plan`复核该Proof，通过后才写PENDING/Task指针。正文只在短生命内存对象，不入Invocation/日志。
- Reason：Prompt内容Owner为防止Task并发漂移只允许QUEUED读取，Begin又必须原子将Task改为RUNNING；因此不能先Begin再构建载荷，也不能把内存正文持有在跨网络数据库事务中。两个短事务之间的竞争由重签Grant和Grant fingerprint绑定Proof关闭。
- Impact/Rollback：收紧未装配内部Begin签名，无Schema/API/依赖/外发变化。可停止新AI Task消费回滚应用；任何已提交Invocation/Task历史保留，不删除或倒写。
- Verification：Win11/PG18.6真实HTTP/Project/Document/Prompt/Plan/Job Claim链，错fencing、篡改Proof失败关闭，正确Envelope摘要与唯一PENDING Invocation一致；定向14、后端2216运行/3跳过PASS，wheel SHA-256 `e9679924e35e775446d2907523926a75073a5a4443e827abf77ec07de0df93b1`，零Provider I/O。首轮验证通用Claim取到Parse Job，仅调整合成夹具AI Job优先级后新资源重跑。

# DEC-20261003-745：业务 ProviderAdapter 与固定 Provider Probe 彻底分离

- Date/WBS：2026-10-03 / `AI-04-A06-P06-P01`；依据 ADR-004、CR-AI-002/015/016、P05-P04。
- Decision：保留 Provider Test 的固定`ping`/Probe Claim/Result边界；业务AI调用新建独立非秘密execution endpoint policy、ModelRouter、post-Begin pre-send Owner和ProviderAdapter。可复用SecretResolver及抽取的DNS/TLS安全原语，不复用固定探针运输接口。
- Reason：探针是无客户数据的连通性证明，无法携带已批准Envelope或返回受控业务结果；Grant Issuer又只接受QUEUED Task，Begin后必须以PENDING Invocation根做独立最后复核。
- Impact/Rollback：P01仅文档。后续是内部Port/非秘密Bootstrap增量，不改冻结URL；原Probe行为不变。回滚不装配业务Worker，PENDING历史保留待对账。
- Verification：静态核对run_provider_probe/probe_policy/provider_probe_transport、SecretResolver、Grant Repository与冻结AIService合同；未运行新代码测试、无网络外发，不标Adapter PASS。

# DEC-20261003-746：Provider发送证明同时绑定Invocation、Route与Envelope

- Date/WBS：2026-10-03 / `AI-04-A06-P06-P02`；依据 CR-AI-015/017、DEC-745。
- Decision：发送边界必须持有不含正文的`AIProviderSendProof`，将PENDING Invocation、Job generation、Grant、Authorization、Content Plan、实际Envelope和精确Provider Route/SecretVersion绑定；Adapter仅接受已复核的Route/Proof/Envelope。响应正文用可清零受控内存移交P07，不进repr/普通日志。
- Reason：单独payload hash不能防止路由、密钥版本或Invocation被替换；响应若使用普通bytes无法在下游消费后主动清零。
- Impact/Rollback：新增未装配内部合同，无Schema/API/依赖/外发。撤合同代码即可，历史不变。
- Verification：单元5、后端2221运行/3跳过PASS；wheel SHA-256 `38731f0ce54d2791e71f5f2b88f9aed04fd582e1270c89bbe5a3958fc1b6412b`；无Secret读取或网络I/O。

# DEC-20261003-747：Begin后以独立当前事实Owner关闭最终发送授权

- Date/WBS：2026-10-03 / `AI-04-A06-P06-P03`；依据 CR-AI-015/017、DEC-745/746、Schema0073。
- Decision：不复用只接受QUEUED Task的Grant Issuer；以PENDING Invocation为根，在一个短事务内组合Jobs Claim、Task/Invocation、当前Authorization、ACTIVE Provider/current Config、AVAILABLE CHAT Model和ACTIVE SecretVersion，并用只来自部署组合的execution policy解析endpoint与网络上限。事务内外双验License后生成SendProof；本Owner不解密Secret、不联网。
- Reason：Begin已将Task推进为RUNNING，原Issuer的QUEUED守卫是正确安全边界；放宽它会混淆创建前Grant与发送前当前事实。数据库只保存endpoint policy引用又不足以安全产生URL，因此URL/model allow-list/超时必须来自受信部署策略。
- Impact/Rollback：新增未装配application/infrastructure组件及默认关闭的验证回调，无Schema/API/依赖/Probe/历史修改。可停止消费并撤组件；已存在PENDING Invocation留待终态对账。
- Verification：单元4、相关定向12、Win11/PG18.6真实Claim→Envelope→Begin→pre-send组合、后端2225运行/3跳过PASS；wheel SHA-256 `efffd47597b53e6a83a06c660129db4b16793321a9d876fca2c1acae9dae7cbc`。Inactive Secret和暂停Model失败关闭；零Secret解密/Provider I/O。

# DEC-20261003-748：业务Adapter使用全候选global校验后的IP pinning

- Date/WBS：2026-10-03 / `AI-04-A06-P06-P04`；依据 CR-AI-017、DEC-745～747。
- Decision：OpenAI-compatible业务Adapter用隔离子进程解析DNS，只有全部1～16个候选均为global地址才连接；实际TCP连接使用已验证数字IP，TLS仍用Route hostname做SNI和证书校验。固定443、系统CA、TLS≥1.2、无代理、无重定向和有界Content-Length；不得放宽或复用Probe固定请求接口。
- Reason：普通高层HTTP客户端可能隐式读取代理、跟随重定向或在连接时再次DNS解析，破坏endpoint policy和SSRF边界；只检查首个DNS结果也允许混入私网候选。数字IP pinning同时保留hostname证书验证可关闭重绑定窗口。
- Impact/Rollback：新增未装配Infrastructure Adapter，无Schema/API/依赖/Probe变化；撤Adapter恢复不发送，历史PENDING Invocation保留待对账。测试连接器只在验证组合中显式注入，生产默认仍使用数字IP:443。
- Verification：单元5、相关定向14、Windows11本地合成TLS端到端和后端2230运行/3跳过PASS；wheel SHA-256 `0cf512ea16bb7082fcbf1d9e675b0d7c116501b20b7b34c90b6591d93bfb6b61`；无真实Provider/客户数据/真实Secret。

# DEC-20261003-749：发送开始窗口必须覆盖Adapter总时限

- Date/WBS：2026-10-03 / `AI-04-A06-P06-P05-P01`；依据 CR-AI-017、P06-P03/P04。
- Decision：在业务发送接线前，AI Task Claim须提供数据库观察时间和精确Lease截止；pre-send仅在剩余Lease大于Route总网络时限加安全余量时签发Proof，并将发送开始截止限制在`lease_expires_at-total_timeout-margin`。Secret解析后必须再次pre-send且Route/Grant/Invocation generation完全一致，随后立即发送。Probe专用Secret Audit不复用，另建Task身份作用域。
- Reason：检查瞬间Lease有效不等于最长120秒调用可在本generation内结束；Secret读取/解密/审计又位于首次检查与网络之间。只依赖Authorization有效期或静态fencing token会让过期Worker仍可能开始外发。
- Impact/Rollback：P01仅记录，后续为内部合同/Owner增量，无Schema/API/依赖；回滚为不装配业务Worker，不发送。安全余量及Lease窗口将在P02用行为测试固定。
- Verification：静态核对`SqlAlchemyJobLeaseRepository.check_current/_claim`、AI Claim/pre-send、SecretResolver/Store、Probe Secret Audit和Worker组合；确认Claim当前不返回Lease时间且Probe Audit拒绝非Probe snapshot。本项未运行新代码测试。

# DEC-20261003-750：SendProof截止表示最迟开始而非仅授权过期

- Date/WBS：2026-10-03 / `AI-04-A06-P06-P05-P02`；依据 CR-AI-017、DEC-749。
- Decision：`AIProviderSendProof.valid_until`按最迟允许开始网络调用解释，并取Authorization截止与`lease_expires_at-route.total_timeout-2秒`的较早值。Claim同时保存数据库观察时间，剩余Lease不严格大于总时限+余量时不签发Proof。
- Reason：Adapter已有绝对总时限；将该时限从Lease截止前倒推为开始截止，可在不持有数据库事务和不后台续租的情况下保证被批准的最坏网络窗口落在当前generation Lease内。2秒用于短生命Secret/审计/函数切换，不替代Worker合理Lease配置。
- Impact/Rollback：内部Claim/Proof语义收紧，无Schema/API/依赖/外发；未装配Worker。回滚为停止发送并撤内部字段，不修改历史。
- Verification：Claim/pre-send相关定向16、Win11/PG18.6 21秒窗口拒绝及120秒成功、后端2231运行/3跳过PASS；wheel SHA-256 `930d37c319def3c3cbf928738f80e535cac2b924f75ff4aec4ad5eda26a8fc74`；零Secret/网络。

# DEC-20261003-751：业务 Secret 审计只绑定最小 Task 发送身份

- Date/WBS：2026-10-03 / `AI-04-A06-P06-P05-P03`；依据 CR-AI-017、DEC-749/750。
- Decision：不复用 Provider Probe 的 Secret 审计。业务 AI 发送在已授权 Prepared Invocation/Route/SendProof 完全一致时，建立仅含 Project、原请求用户、Task、Invocation、Job generation、SecretRecord/Version 的 ContextVar；SecretResolver 的 GRANTED/DENIED 以受控 SYSTEM actor、原用户和精确 PLT-02 Version 写 Project 审计。Envelope、正文、Key、Response 和完整对象不得进入作用域。
- Reason：SecretResolver 的通用审计 Port 不携带业务 Task 身份；复用 Probe snapshot 会产生错误审计语义，而把 Envelope/Key 放入上下文会扩大敏感信息生命周期。最小绑定同时让错误 trace/consumer/Secret/proof 漂移在审计前失败关闭。
- Impact/Rollback：新增未装配内部审计适配器及默认关闭验证回调，无Schema/API/依赖/历史修改。回滚为停止业务消费并撤适配器；固定 Probe 不变。
- Verification：单元3项/8子用例、Win11/PG18.6真实 AuditService 持久化 SUCCESS/DENIED、错误Version解密前拒绝与明文清零、后端2231运行/3跳过PASS；wheel SHA-256 `5918f56a12390f5a2ed225fd2b0d02b37bc0bd6a557d3c76264e2f68b2e80f9e`；零真实Secret/Provider网络。

# DEC-20261003-752：Secret解析后必须以第二份当前证明立即发送

- Date/WBS：2026-10-03 / `AI-04-A06-P06-P05-P04`；依据 CR-AI-017、DEC-749～751。
- Decision：业务发送唯一入口执行首次pre-send，随后绑定Task审计/trace并按其精确SecretVersion进入SecretResolver；持有短生命Key时再做第二次pre-send。只有Route完全相同、SendProof除最新valid_until外的Invocation/Job generation/Grant/Authorization/Plan/route/payload身份完全相同才立即调用Adapter；Adapter使用第二份proof。一次调用最多调用一次Adapter。
- Reason：Secret加载/审计位于数据库授权与网络之间，期间可能发生密钥轮换、撤销、License或Lease变化。只做首次检查会发送旧Key，先做第二次再取Key又会在Key解析后留下同样竞态。双检查配合精确Version和Adapter内部proof复核把可控窗口收至最小。
- Impact/Rollback：新增未装配内部应用服务及验证注入，无Schema/API/依赖/历史修改。可停止业务消费并撤服务；PENDING历史留待后续终态/对账，不删除。该决定不承诺崩溃或超时下远端exactly-once。
- Verification：新单元4项/5子用例、相关定向17/23，Win11/PG18.6真实pre-send/Secret Store/Project Audit及合成Adapter顺序通过；后端2235运行/3跳过PASS，wheel SHA-256 `98575f61b942d999a86771d8e76ec6d40e64821eb784bc2462abd210dde38de7`；零真实Secret/Provider网络。

# DEC-20261003-753：网络前持久RUNNING栅栏，未知结果沿用FAILED安全错误

- Date/WBS：2026-10-03 / `AI-04-A06-P07-P01`；依据冻结 DM-04/API-03、Schema0064/0073、CR-AI-018。
- Decision：第二次pre-send和稳定性复核后、Adapter前，以当前Job fencing和精确proof原子把Invocation从PENDING推进RUNNING并写started_at；只有栅栏提交成功才可发送。崩溃/超时导致远端结果未知时，不新增冻结外UNKNOWN状态，使用`FAILED / AI_PROVIDER_OUTCOME_UNKNOWN / retryable=false`；只有显式受权Retry创建新attempt。
- Reason：PENDING在网络期间可被再次授权，无法阻止同一Invocation重复外发；数据库栅栏可令既有pre-send在重复执行时失败关闭。RUNNING可能在socket写前崩溃，因此它只证明“发送边界已越过”，不能证明远端收到。冻结状态已用安全error表达未知结果，无需Breaking enum。
- Impact/Rollback：P01仅文档。后续增加0074结果Owner及内部栅栏/发布服务，不改公开请求或状态枚举。发送栅栏装配后回滚只能停止消费并对账RUNNING记录，不得改回PENDING。
- Verification：静态核对0064状态/触发器、0073同源守卫、P06 pre-send/编排、冻结DM/API和Suggestion/Schema实现缺口；无新运行测试、Migration、外发或Secret访问，不标P07/P08 PASS。

# DEC-20261003-754：Suggestion只保存不可变非正式事实与类型化证据引用

- Date/WBS：2026-10-03 / `AI-04-A06-P07-P02`；依据 CR-AI-018、Schema0064/0074。
- Decision：SuggestionPayload必须唯一归属RUNNING且未发布的精确Task/Invocation，Schema/Scope/Project同源，载荷为有界规范JSON与SHA-256，事实状态恒为`NOT_FORMAL_FACT`；Evidence只保存Owner/Object/Version/内容指纹类型引用。Invocation以延迟复合FK在同一发布事务指向自己的Payload，发布后Payload/Evidence不可变。
- Reason：自由UUID、Provider wrapper或无Owner字符串不能构成可追溯结果；先写子记录再终态化需要延迟FK，而AI结构有效不等于客户确认事实。类型化引用避免复制正文并为后续Owner复核保留精确身份。
- Impact/Rollback：新增Schema0074/ORM，不改冻结API/状态枚举/依赖。旧NULL历史保留；空结果可降，有结果拒绝降级并须向前修复或受控恢复。多态Evidence存在性留给P04/P05受信Owner验证。
- Verification：Win11/PG18.6空/历史/绑定三库升降重升、ORM drift、负例、延迟FK/封存/拒降PASS；后端2238运行/3跳过，wheel SHA-256 `4ffcea6c91bf5a5ea1767ea1b11f68600d5424a04025a63872be9f7f379170f4`；零Provider/Secret/外发。

# DEC-20261003-755：只有已提交RUNNING栅栏的Invocation可进入Adapter

- Date/WBS：2026-10-03 / `AI-04-A06-P07-P03`；依据 CR-AI-018、DEC-753、P06-P05-P04。
- Decision：唯一发送编排在第二次pre-send及Route/Proof稳定性复核后，以当前Jobs Lease/fencing重新核对Task/Invocation/Plan/payload并原子提交`PENDING→RUNNING`、started_at和lock version；仅栅栏提交成功才调用Adapter。同一Invocation不能再次pre-send；栅栏后任何失败不得改回PENDING。
- Reason：进程内一次调用保护不能覆盖崩溃重启；持久状态转换能阻止同一Invocation重复外发。RUNNING可能在socket写前形成，因此仅表示越过发送边界，不作为远端收到或成功的证据。
- Impact/Rollback：新增内部Application/Repository并收紧发送服务依赖，无Schema/API/依赖/生产Worker/真实外发。可停止消费并撤组合；已RUNNING记录由P08对账，不能降级状态或删除。
- Verification：Win11/PG18.6真实Claim/Plan/Invocation/Secret/Audit与合成Adapter，数据库RUNNING先于一次Adapter、二次发送拒绝；定向12/11子用例、后端2241运行/3跳过；wheel SHA-256 `8e4cc572f2310f47aeaab4686722d9717ccfd4ad229073f031e00a76980d086c`。

# DEC-20261003-756：模型只引用授权来源序号，Evidence身份由Owner解析

- Date/WBS：2026-10-03 / `AI-04-A06-P07-P04`；依据 CR-AI-018、Schema0074。
- Decision：Output Schema采用代码内受信版本注册；`gap-output.v1@1`只接受四类非正式建议及本次Grant中存在的来源序号。模型不得提供formal fact、Owner、UUID或内容指纹；P05由受信内容Owner从不可变Content Plan解析Evidence。响应必须为单choice/STOP/纯JSON，并经过重复键、非有限数、深度/节点/文本/字段边界后才规范化和计算指纹。
- Reason：模型自报对象身份和指纹不可作为证据，通用宽松JSON或Markdown抽取会把歧义内容错误标为Schema VALID。来源序号可与已授权Plan稳定关联，同时把证据真实性留在服务端Owner边界。
- Impact/Rollback：新增内部registry/parser，无Schema/API/依赖/网络。兼容既有`gap-output.v1`和部署示例`gap-analysis-output.v1`；移除parser恢复不发布结果，不修改历史。
- Verification：单元4/8子用例，Windows11真实Prepared来源身份上的有效/无效合成响应，后端2245运行/3跳过；wheel SHA-256 `2fd6018406f032e0277531e3921dee8c0ded6ad8a6d581056b3ea347e3379a0d`；零真实Provider/Secret/外发。
