# CR-AI-002：Provider 连通性测试的安全解析与持久证明

日期：2026-10-02；状态：部分实施（P01、P02、P03-A01 验证）；来源：`AI-01-A05` 前置核查；原冻结 Gate 2 提交 `64cdf09` 保留。

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
