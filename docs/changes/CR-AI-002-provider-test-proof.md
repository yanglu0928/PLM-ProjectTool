# CR-AI-002：Provider 连通性测试的安全解析与持久证明

日期：2026-10-02；状态：部分实施（P01、P02 验证）；来源：`AI-01-A05` 前置核查；原冻结 Gate 2 提交 `64cdf09` 保留。

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

2026-10-02 进度：P01 离线固定探针合同已验证；P02 按 `20261002_0055` 增量建立 append-only 结果与复合配置/Secret/Attempt/Lease/Job 归属，隔离 PG 空/有数据升级降级、ORM 无漂移和后端全量通过。P03～P05 及真实外发仍未实施，不提升整体 A05 或 Gate 状态。
