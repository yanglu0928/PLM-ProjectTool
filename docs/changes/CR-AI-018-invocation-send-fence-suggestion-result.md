# CR-AI-018：Invocation 发送栅栏与 Suggestion 结果归属缺口

日期：2026-10-03；状态：依 V1.1 持续授权登记，P07-P02/P03已实施、其余分片继续；关联 Gate 2 冻结 ADR-004/DM-04/API-03、CR-AI-015～017、Schema0064/0073/0074；原冻结提交 `64cdf09` 不改。WBS `AI-04-A06-P07～P08`。

## 冲突与证据

P06 已把一次进程内 Provider 调用收敛为双 pre-send、精确 SecretVersion 和有界 Adapter，但数据库中的 Invocation 在网络期间仍保持 `PENDING + started_at=NULL`。若进程在远端收到请求后、持久化结果前退出，当前 pre-send 仍可再次授权同一 Invocation，无法区分“未发送”与“远端结果未知”，违反冻结模型“不承诺外部精确一次、超时需明确错误”的要求。

Schema0064 虽有 `suggestion_payload_ref`、`response_fingerprint`、usage、latency 和错误字段，但仓库不存在 SuggestionPayload owned 表/ORM/FK，也没有受信 Output Schema 内容注册表或校验器。仅保存一个自由 UUID、把 Provider wrapper 当建议正文，或按 `output_schema_ref` 字符串自称 VALID 都不能满足 DM-04 的 `SUCCEEDED + schema VALID → AVAILABLE / NOT_FORMAL_FACT`。完整 Provider response 也不得写普通日志或无边界 JSON。

现有冻结 Invocation 状态为 `PENDING / RUNNING / SUCCEEDED / FAILED / CANCELLED`，没有 `UNKNOWN`。为表达远端副作用未知，无需破坏性新增状态枚举；使用 `FAILED` 与固定安全错误 `AI_PROVIDER_OUTCOME_UNKNOWN`、`retryable=false`。后续只有受权显式 Retry 才能创建新 Job/Invocation attempt，不得自动重发同一 attempt。

## 方案与决定

1. P07-P02：新增不可变 SuggestionPayload owned 表和0074增量，Project/Task/Invocation复合归属、schema ref/version、规范结构化 JSON、payload fingerprint、`NOT_FORMAL_FACT`、质量/Evidence最小字段；为 Invocation 的 `suggestion_payload_ref` 建真实FK。历史 NULL 保留，不猜测回填。
2. P07-P03：新增当前 Job/Invocation 发送栅栏。在第二次 pre-send 与稳定性复核后、Adapter 前，以短事务重新锁定当前 claim/proof，将 `PENDING→RUNNING`、写 `started_at` 并递增版本；只有本次事务成功才允许调用 Adapter。RUNNING 后原 pre-send 不再授权，防止同一 Invocation 被再次发送。
3. P07-P04：部署受信且版本化的 Output Schema registry/validator；只解析 Provider response 中最小 suggestion content，严格 JSON/大小/深度/键数/数值边界并按 Invocation 固定 schema 校验。未知 schema、非JSON或 INVALID 不产生 Suggestion。
4. P07-P05：成功结果在一个短事务写不可变 SuggestionPayload、Invocation SUCCEEDED/VALID、Task SUCCEEDED/AVAILABLE、Job/Attempt/Lease终态、Audit/结果引用；提交后关闭并清零 Provider response。
5. P08：失败、取消、`AI_PROVIDER_OUTCOME_UNKNOWN`、崩溃对账和显式新 attempt Retry；不得把运行中栅栏静默恢复为 PENDING，也不得把 UNKNOWN 自动标为可重试。

实施记录：P07-P02 已以 Schema0074落地不可变 SuggestionPayload/Evidence、RUNNING且未发布写入门禁、`NOT_FORMAL_FACT`约束及 Invocation 延迟复合FK；旧NULL历史保留，有结果历史拒绝物理降级。P07-P03 已在唯一发送编排中加入当前Job generation/Invocation的持久RUNNING栅栏，提交后同一Invocation不再满足pre-send；栅栏后失败保留RUNNING供P08收敛，不回退PENDING。Evidence实际Owner存在性与输出Schema内容校验仍由P04/P05承担，不把多态引用或JSON形状冒充已验证业务事实。

## 兼容、迁移与回滚

0074只追加 owned 结果表、FK和必要守卫，不改冻结 `/api/v1` 请求字段或既有枚举。升级前备份并停写至0074；既有 Invocation 的 NULL suggestion ref 保留。存在0074结果历史时物理降级必须拒绝，回滚采用停止 Worker/结果发布、向前修复或受控备份恢复。发送栅栏装配后不能回退到无栅栏发送；可停止新消费，已 RUNNING 的记录由P08对账，不能改回PENDING或删除。

## 风险与验收

- RUNNING 栅栏可能在实际 socket 写前因进程退出而形成保守 UNKNOWN；这是避免重复外发的安全取舍，不伪称已发送。
- Provider 已收到但客户端未收到响应时无法自动判定业务结果；若 Provider 将来提供可验证幂等请求标识，可作为新增策略能力，但V1不假设存在。
- schema VALID 只说明结构符合固定合同，不证明业务事实正确；Suggestion仍为 `NOT_FORMAL_FACT`，人工接受和 Review 链不变。
- 必须验证空库/历史库升级、FK/不可变/Scope、PENDING→RUNNING一次性竞争、崩溃/超时UNKNOWN、不自动重发、Schema VALID/INVALID、结果/Audit/Job原子回滚、响应/Key清零及Win11/PG18.6；Server 2025、Gate 3/UAT/发行包另验。
