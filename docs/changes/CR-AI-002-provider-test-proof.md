# CR-AI-002：Provider 连通性测试的安全解析与持久证明

日期：2026-10-02；状态：部分实施（P01～P03、P04-A01～A05、P05-A01/A02/A03-P01～P03 与 P04-P01 已验证；Windows 激活组合、生产守护/真实外发未完成）；来源：`AI-01-A05` 前置核查；原冻结 Gate 2 提交 `64cdf09` 保留。

## 来源、冲突与证据

- 冻结 `API-03` 将 `AI_PROVIDER_TEST` 定为部署管理员 `POST /api/v1/admin/ai/providers/{provider_id}:test`，控制 S/L/C/I/M/A，返回 `202 JobRef`；探针必须固定、无客户数据、无业务 Prompt。DM-04 规定 ACTIVE 需要最小连通性证明，Job/Outbox 至少一次与 fencing。
- 现有 `20261002_0054` 只保存符号化 `endpoint_policy_ref`、SecretRef 和不可变配置版本；没有受控端点解析器、Provider Test 结果/版本绑定持久实体或 AI Provider Adapter。`JobRow` 支持 DEPLOYMENT/至少一次基础形状，但 Job 读取 Owner registry 目前只有 Audit Export 和 Document Parse，成功结果白名单也没有 Provider Test。
- 若直接在 HTTP 内同步访问厂商并返回 200，将破坏冻结的 202 JobRef 和 Job/Outbox 语义；若把客户端提供的 URL 当端点，将扩大 SSRF 与密钥外发面；若只凭 Job 成功状态激活，不能证明具体 Provider 配置版本、Secret 版本和端点策略的受控探针结果。

## 方案比较与所选方案

1. 同步 HTTP 调用或复用任意 URL：不选，违反冻结合同和安全边界。
2. 仅以通用 Job 行作激活证明：不选；Job 可重试、状态可变，且未固定配置/端点策略/Secret 版本，后续配置变更可能误用旧结果。
3. 选择分层增量：部署控制的端点策略解析和固定无客户探针合同；Provider Test 专用不可变配置/策略/Secret 版本绑定的结果证明；Job/Outbox 同事务提交与受权 Owner 投影；受限 Worker/Adapter 使用既有 SecretResolver，实际发送前重验许可、配置、策略和出站目标。真实对外调用另按逐次数据/密钥范围授权，先用本机合成端点验收。

首批目标仍为 DeepSeek；架构保留其他 Provider Adapter，不把尚未实现的适配器或正式外发标 PASS。端点策略不能由普通 Provider API 写入原始 URL。新增持久实体、约束及 Job Owner 投影前需单独实施和 Migration 验证，不追写原冻结 Schema。

## 影响、迁移与回滚

- 可能新增 Provider Test 结果表及普通增量 Migration；Job 通用表不以破坏性方式修改。端点策略解析可先由受控部署配置/Adapter registry 提供，不将 URL/密钥存入 Provider 配置版本或 Job payload。
- API 路径/角色/202 结果保持不变；Provider 激活必须检查与当前配置相同的成功测试证明，测试成功不代表 AI 质量通过。
- 新表空库及有数据升级验证、up/down、安全非空降级；有历史测试证明时不物理删除，撤开放路由/Worker 并向前修复。迁移前备份，生产迁移另行验收。
- 禁止将 API Key、响应正文、客户资料、原始异常写入 Job、Outbox、Audit、普通日志或 Git。未满足真实外发授权时，测试 Worker 保持关闭，内部合成验证可继续。

## 验证计划与剩余风险

按 `AI-01-A05-P01～P05` 分别验收：受控端点策略/固定探针合同；持久 TestRun 与 Migration；同事务异步提交/幂等/权限/Audit；Worker 的重验、超时/重定向/网络失败、fencing/原结果；Job 受权读取、激活证明与 Windows 显式组合。覆盖配置变化、Secret 轮换、License 过期、错误端点、重试并发和失败回滚。真实厂商连通、Server 2025/Debian、质量 Gate、UAT 与发行仍需独立证据。

2026-10-02 进度：P01 离线固定探针合同已验证；P02 按 `20261002_0055` 增量建立 append-only 结果与复合配置/Secret/Attempt/Lease/Job 归属，隔离 PG 空/有数据升级降级、ORM 无漂移和后端全量通过。不提升整体 A05 或 Gate 状态。

2026-10-02 追加：P03 拆为 A01 内部 Job/Outbox 原子队列、A02 受权提交/收据/Audit、A03 可选 202 HTTP。A01 已在隔离 PG 验证成对/重放/并发/回滚，未开放入口或外发；A02/A03/P04/P05 仍待。

2026-10-02 追加：P03-A02 已按 DEC-20261002-642 实施。Windows 11 隔离 PostgreSQL 验证真实管理员与普通用户 Session、同 Key 双写、一对 Job/Outbox/收据/Audit、旧配置重放和审计失败回滚；只保存原始受控策略摘要与配置/Secret 版本引用。无新迁移或公开入口；A03/P04/P05、真实外发与发行仍待。

2026-10-02 追加：P03-A03 按 DEC-20261002-643 增加可选 202 HTTP 路由及默认关闭注入点。合成 HTTP 合同验证；不挂 Windows 平台组合、不触发 Worker/真实外发，HTTP+PG 端到端仍待 P05 装配验证。

2026-10-02 P04 实施拆分：按 DEC-20261002-644 先做 A01 专属领取/fencing，随后 A02 许可/当前配置/Secret/策略重验、A03 受限合成 Adapter、A04 不可变结果与终态发布。无技术栈/Schema/API 改动；期间 Worker 循环仍关闭，任何领取证据不代表实际连通。

2026-10-02 P04-A01 已在 Windows 11 隔离 PG 验证双 Worker 专属领取、非 AI Job 排除、过期租约与 fencing、回滚及畸形队列失败关闭。P04-A02～A04 和真实外发仍未实施，不能把 Job 领取报告为探针/许可通过。

2026-10-02 P04-A02 核查发现现有 SecretResolver 信封不携带 SecretVersionId。按 DEC-20261002-645，先实现不解密、不联网的当前版本/许可/策略/fencing 预检；A03 另实现版本绑定 Secret 使用及发送前重验，预检不授予外发权限。该调整在 CR-AI-002 既有范围内，无 Schema/API 变化。

2026-10-02 P04-A02 已在 Windows 11 隔离 PG 验证当前租约、License 拒绝、策略变化、Secret 停用/轮换、Provider 配置实际升版失败关闭；未产生结果或网络调用。版本绑定 Secret 使用和出站安全仍待 A03，不提前开放 Worker。

2026-10-02 A03 再拆 P01 版本绑定 SecretResolver、P02 受限 Adapter 与本机合成端点；按 DEC-20261002-646 先完成 P01。Internal Envelope 增量携带 SecretVersionId，预期版本不符时须在解密前拒绝；不改变既有调用默认行为，也不开放 Worker 或外发。

2026-10-02 P04-A03-P01 已在隔离 PG 验证真实 SecretVersion 轮换后旧 Job 版本在解密前拒绝、匹配版本可读取且退出清零；没有网络外发。A03-P02 的发送前再核验和目标安全仍待，不可由版本绑定单项推断可外发。

2026-10-02 A03-P02 按 DEC-20261002-647 选 Python 3.13 标准库受限 HTTPS：公网 DNS 全候选校验、钉住 IP、TLS 原域名验签、无代理/重定向、固定小探针和有界响应；本机合成 TLS 用测试专用覆盖，不挂生产组合。无新增依赖/Schema/API。风险：发送前元数据重验与网络请求之间仍存在短暂状态变化窗口；终态发布必须以当前 fencing/配置/Secret 再核验，真实厂商外发不由本机合成授权。

2026-10-02 A03-P02 已完成单次内部 Runner/Transport；本机临时 CA TLS、未受信 CA、固定请求、重定向/过大/非法/慢响应与 Key 缓冲清零 PASS，后端 1963 项运行/3 跳过。只返回安全观察值，不保存结果、未启用 Worker，也没有真实厂商外发；详细证据见 `docs/progress/ai-01-a05-p04-a03-p02-synthetic-tls.md`。下一项 A04 负责 fencing 后的不可变结果与终态原子发布。

2026-10-02 A04 拆分 P01 成功原子发布与 P02 失败/重试处理。P01 按 DEC-20261002-648 在调用方 PostgreSQL 事务内重验当前租约、配置/策略/Secret；隔离库真实验证成功、旧 fencing、变化拒绝和终态失败回滚，复用既有 0055，不启用 Worker 或真实外发。P02 仍需完成错误结果、重试/最终失败和审计，不将 P01 视为 A04 整体完成。

2026-10-02 P02 实施前决策 DEC-20261002-649：原方案结果表每 Job 唯一，故可重试尝试只记 Attempt 与 Audit，最终失败才写不可变结果；成功路径补同事务 Audit。仅安全错误码与受控 SYSTEM 身份进入审计，原始异常/响应不落库。无 Schema/API/依赖变化，回滚为撤内部调用并保留历史；需隔离 PG 验证三次上限、错误分类、旧租约和审计失败回滚。

2026-10-02 P02 已在 Windows 11 临时 PG18 验证三轮领取/5 与 15 秒退避计划（测试时推进可用时间）、前两轮无最终结果、第三轮唯一 FAILED 证明、旧 fencing 拒绝、非重试错误立即终止以及 Audit 故障整笔回滚；成功路径补审计并回归。此为内部状态机验证，不等于 Worker 已运行。P04-A05 仍需单次 Worker 组合和合成端到端，P05 与真实外发独立验收。

2026-10-02 P04-A05 按 DEC-20261002-650 增加纯内部单次 Worker；Windows 11 临时 PG18 与本机合成 TLS 串起真实 Job/Outbox/SecretStore、预检、固定 POST、结果及 Audit，验证 IDLE、成功和重定向失败。测试端点与合成解密器只在 validation；没有进程守护、正式 Windows 装配或真实外发。P04 内部链可进入 P05，但整体 AI-01-A05 和 Gate 3 不标 PASS。

2026-10-02 P05-A01 按 DEC-20261002-651 扩展冻结 JobView 的内部 Owner 结果枚举与 Windows 组合。历史 SUCCEEDED 仅经当前管理员 Session/License 授权且 Job/Outbox/结果/配置版本/SecretVersion/策略/attempt/fencing 同事务核对后返回安全结果引用；失败与未完成不暴露证明内容。无 Schema/Breaking API/依赖变更，撤 Owner 注册可回滚且历史保留。Win11 隔离 PG18 与后端全量回归通过；该历史结果不是当前激活资格，P05-A02 和正式 HTTP/外发仍待。

2026-10-02 P05-A02 按 DEC-20261002-652 增加供未来激活命令在同一事务调用的当前资格证明。锁定当前 Provider，重验 License、ACTIVE SecretVersion、受控策略摘要，只接受该 Provider 最新终态结果为 SUCCEEDED 且原 Job/Outbox、配置与版本完整匹配；较新的失败不能被旧成功绕过。Windows 11 隔离 PG18 验证策略/配置/Secret 变动和新失败均拒绝；无 Schema/API/依赖变化，保留全部历史。后续 P05-A03 内部激活命令仍须实现管理员授权、并发版本、幂等、Audit、状态原子提交；本项不将 Provider 置 ACTIVE。

2026-10-02 P05-A03 前置差异：通用持久幂等收据不含 Provider 原始状态/ETag 版本；激活后若暂停或修改，再从当前行拼接同 Key 200 响应会失真。比较方案：仅返回当前行（不选，破坏重放）、扩充全局收据字段（不选，扩大跨模块 Schema）、AI Owner 增量不可变首次响应快照（选择）。按 DEC-20261002-653 拆 P01 Schema 与 P02 受权激活命令；原冻结提交保留。P01 增量表由收据通过 ref_id 引用，含 Provider/config/探针结果/actor/Audit/trace、请求与结果锁版本和固定 ACTIVE；加唯一与 FK、不可变保护，不存密钥或正文。备份后 0055→0056；空表可 down，有快照时拒绝降级；向前修复优先，撤入口保留历史。P02 必须同事务写 Provider 状态、Audit、快照、收据并验证并发/回滚；整体 A05/Gate 不因 P01 通过而关闭。

2026-10-02 P05-A03-P01 已完成 Schema `20261002_0056`。Windows 11 隔离 PG18 空库升降级/重升、有既存两条探针结果升级、复合归属/唯一/不可变、非空拒降及 ORM 漂移 0；后端全量 1992 运行/3 跳过、开发 wheel 通过。首轮回归两项旧头/库存断言失败，修订测试后重跑通过。生产迁移与受权激活状态命令尚未执行；历史快照存在时只允许向前修复，不删除。

2026-10-02 P05-A03-P02 按 DEC-20261002-654 完成内部同事务受权激活。当前管理员/License/最新成功探针/强版本通过才由 CONFIGURED 或 SUSPENDED 更新 ACTIVE；USER Audit、0056 首次快照、通用收据与状态同事务提交。历史同 Key 重放只读首次快照，不再改当前状态，后续暂停仍返回原始 v1；不同 Key/version 不绕过冲突。Windows 11 隔离 PG18 双并发、普通用户、License/Secret 失效和 Audit 失败回滚通过，后端 1997 运行/3 跳过。无新 Schema/API/依赖；撤命令入口可回退而保留历史。公开 HTTP、正式组合与真实外发尚未验证。

2026-10-02 P05-A03-P03 按 DEC-20261002-655 新增可选 HTTP 激活边界，200 只投影不可变首次 ACTIVE/ETag，不重读现时行以免暂停后的历史重放失真。冻结 API-03 不变，无 Schema/依赖/外发；Windows 11 隔离 ASGI/PG18 许可拒绝、激活/Audit、暂停后重放和新 Key 冲突 PASS，后端 2001 运行/3 跳过。默认与当前 Windows 组合未挂载；下一项显式写模式接线，正式信任/Worker/质量/Gate 仍待。

2026-10-02 P05-A03-P04 前置核查：`production_login` 当前只有 Provider 创建/配置 PATCH，既无 `EndpointProbeRegistry` 的正式受控部署来源，亦无 Provider Test 正式提交/Worker 接线。激活服务若直接由空或合成策略注入，将永久拒绝或把测试策略误作生产资格。比较：硬编码供应商地址（不选，变更/出站治理失控）、复用验证脚本合成 registry（不选，测试信任误入生产）、先实现独立受控策略来源及缺失失败关闭，再按同一来源接 Test/Worker/Activate（选）。因此 P04 暂为 PRECONDITION_BLOCKED，入口保持 404；拆出 P04-P01 策略来源与回滚/安全验证，随后重检 P04，不改冻结 API/Schema，也不触发真实外发。正式目标账户策略文件/权限与生产出站仍须另验，不能以隔离来源代替。

2026-10-02 P05-A03-P04-P01 按 DEC-20261002-656 用现有 Bootstrap 非秘密 YAML 承载受控策略列表，并严格转为进程内不可变 Registry；没有配置或无效时工厂固定失败。Windows 11 实际 YAML/固定计划、重复/额外 Secret 字段、不安全 URL 和不支持类型测试 PASS，后端2006运行/3跳过。没有正式 Test/Worker/Activate 装配或真实外发；P04 保持阻塞，下一项同源组合。

2026-10-02 P05-A03-P04-P02 范围拆分：Windows 现有服务计划仅 Web、Audit Worker、Parser Worker；Provider Test 单次 Worker 只在隔离脚本内组合。直接公开 `:test` 会接受 Job 却没有正式消费者。按 DEC-20261002-657 拆 A01 受控策略 Test 提交工厂（不挂路由）、A02 同策略单次 Worker 工厂与安全运行边界、A03 在两者具备后装配/验收公开路由及生命周期。API-03 冻结 202 JobRef 不变，原 P04 激活路由继续关闭。失败关闭及历史 Job/结果保留；此拆分不授权真实厂商外发。

2026-10-02 P05-A03-P04-P02-A01 Windows 提交组合工厂已验证，但不向生产应用注入路由；受控 Bootstrap 策略缺失时固定失败，隔离 ASGI/PG18 真管理员/License、Job/Outbox/Audit/收据与历史重放通过。后端2006运行/3跳过。仍缺 Worker 的同源/目标账户网络和安全生命周期，不能据此开启 :test 或 :activate。
