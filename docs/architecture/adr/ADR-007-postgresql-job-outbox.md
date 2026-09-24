# ADR-007：PostgreSQL Job/Outbox 与独立 Worker

## Status

`ACCEPTED_FROM_BASELINE / NOT_GATE_2_FROZEN`

## Date

2026-09-22

## Context

解析、OCR、Embedding、AI、文件转换和插件输出可能超过同步请求时限，并需要重试、取消和崩溃恢复。第一版是单服务器、低并发部署，新增 Redis、RabbitMQ、Kafka 或 Celery Broker 会显著增加离线安装、备份和运维成本。

## Decision

1. 长任务与需恢复事件统一写入 PostgreSQL Job/Outbox，由独立 Worker Process 领取执行。
2. Job/Outbox 提供至少一次交付，不承诺精确一次；所有可重试写操作必须携带 idempotency_key，并以 Job/Event 标识和业务版本去重。
3. API 在同一短事务中提交业务状态、Job/Outbox 与 Audit，不在请求事务内运行长任务或外部模型调用。
4. Worker 通过数据库原子租约领取任务，维护 owner、lease expiry 与 heartbeat 语义；崩溃后的过期租约可回收。
5. Job 只保存对象引用、版本、策略版本和最小参数，不保存文件正文、Prompt 全文、Cookie 或 Secret 明文。
6. RetryPolicy 区分可重试与不可重试错误，并使用有上限的次数、退避和抖动。越权、签名、Schema 和凭据配置错误不得盲目重试。
7. Worker 使用受控 SystemActor，但继承原始 actor_id、project_id、trace_id 和授权目的，并通过公开 Application Port 写入结果。
8. 取消是协作式；阶段输出完整校验后原子发布。维护模式停止接收新任务并收敛 Worker 后，才进入备份和 Migration。

## Consequences

- 不增加新的基础设施，Job、业务事务、Outbox 和备份使用同一 PostgreSQL 运维能力。
- 至少一次语义要求所有消费者幂等，不能用“任务只会跑一次”作为业务假设。
- PostgreSQL 同时承载业务与队列负载，需要索引、批量领取、保留/清理策略和容量监控。
- 单服务器 Worker 故障后可恢复，但 V1 不承诺多节点调度、跨区域容灾或极高吞吐。
- 长事务被禁止，降低锁竞争和任务重跑的不确定性。

## Rejected Alternatives

- 同步请求内执行：超时、断线和恢复能力不足。
- 仅内存队列：进程崩溃后任务丢失。
- Redis/Celery、RabbitMQ、Kafka：超出 V1 运维与技术基线。
- 精确一次承诺：跨数据库、文件和外部 Provider 无法可靠保证。

## Rollback / Change Rule

可在 PostgreSQL 方案内调整租约、批次和清理策略。引入消息队列、Redis 或多节点调度属于架构/技术栈变更，必须以容量和可靠性证据发起 L3 Change Request，并给出迁移、回退与离线部署方案。

## References

- `docs/architecture/security-file-job-runtime-boundaries-v1-candidate.md`
- `docs/architecture/application-contracts-v1-candidate.md`
- 《实施方案 V2.1》4.17
