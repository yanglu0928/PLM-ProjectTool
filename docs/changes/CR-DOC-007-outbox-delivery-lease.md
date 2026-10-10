# CR-DOC-007：Outbox 投递租约与防旧投递者增量

日期：2026-09-26；状态：增量 `20260926_0026` 与内部事务命令已实施并验证；真正消费者/Worker 待后续。原 Gate 2 冻结提交 `64cdf09` 与已推送迁移 `20260926_0025` 均保留。

## 来源与证据

ADR-007 与冻结 SC-03 要求 Outbox 至少一次投递、`FOR UPDATE SKIP LOCKED` 领取、崩溃恢复与消费去重。现有 `job_outbox_events` 只有 `PENDING/DELIVERING/...` 状态、尝试次数和下一次时间，缺投递者身份、租约到期和单调 fencing token。若进程在 `DELIVERING` 后崩溃，事件无法安全接管；若仅按超时复位，旧进程可能在接管后确认同一事件。这是 `CR-DOC-006` 基础表的后续实现缺口，不能宣称基础表已提供完整 Outbox 运行语义。

## 方案比较与选择

- 不选无限期 `DELIVERING` 或人工复位：丢失自动恢复能力。
- 不选进程内锁或单靠 PostgreSQL Session 锁跨越投递：外部处理时不得保持长事务，进程异常也无法提供稳定 fencing。
- 选择增量 `20260926_0026`：在 OutboxEvent 添加投递 Owner、租约到期、单调 token、有界尝试上限与终态时间；仅 `DELIVERING` 可持有活动租约。短事务领取/过期接管、确认和重试都复核 owner/token/数据库时间。`(event_id, consumer_id)` 记录继续作为数据库内消费者去重依据；外部副作用仍需目标幂等，不能承诺精确一次。

## 影响、迁移、回滚

只改 jobs 内部 ORM/数据库和事务命令，不改 `/api/v1`、技术栈或公开 DTO。旧 `PENDING/RETRY_WAIT/DELIVERED/DEAD` 行无需回填；升级前若已存在旧 `DELIVERING` 行，则拒绝迁移并由受控恢复先处置，不伪造租约。降级仅在没有任何非空投递租约/非零 token 与新语义终态时允许；否则拒绝并保留历史。目标库先备份。工作流程先用隔离 PostgreSQL 18 验证空库、有数据升级、回滚、负向约束、并发与崩溃恢复，不操作生产库。

## 剩余风险

数据库消费者可将业务写入、Consumption 与 Outbox 确认放在同一短事务；外部服务可能在成功后、确认前断连，仍会至少一次重投。客户数据/Secret 不放进 Outbox 载荷；真正消费者、Parser Worker 与上传 Commit/Abort 属后续任务。Server 2025 与正式信任源不因本增量判定通过。

Windows 11/Python 3.13 后端 498 项无失败（2 项符号链接权限跳过）；隔离 PostgreSQL 18 已验证旧 `DELIVERING` 升级拒绝、旧 PENDING 行升级与空租约降级再升级、ORM 差异为零、无租约 DELIVERING 约束拒绝、并发领取、过期接管、旧 token/owner 拒绝、消费回滚/去重/错消费者拒绝、有界重试与有投递历史降级拒绝。目标生产库未操作。
