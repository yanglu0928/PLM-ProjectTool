# DOC-03-A04-A04-P03：Outbox 投递与消费去重

日期：2026-09-26；版本：`0.1.0.dev0`；状态：内部事务命令 PASS，独立 Worker/真实消费者未接线。

按 `CR-DOC-007` 在现有 OutboxEvent 增加投递 Owner、过期时间、单调 token、有界尝试上限、终态时间和错误码（迁移 `20260926_0026`）；旧 `DELIVERING` 必须受控恢复后才准升级，已有新语义历史拒绝降级。Outbox Owner 使用短事务 `FOR UPDATE SKIP LOCKED` 领取；过期事件可接管，旧 owner/token 不能确认。消费回调、`(event_id, consumer_id)` 去重与 DELIVERED 状态同事务；外部副作用仍只能按至少一次/目标幂等处理，不承诺精确一次。

Windows 11/Python 3.13 后端 498 项无失败（2 项符号链接权限跳过）；隔离 PostgreSQL 18 旧数据升级/回滚、负向约束、双投递者竞争、过期接管、旧进程拒绝、消费异常回滚、重复消费跳过、错消费者拒绝、有界重试和不可安全降级保护 PASS；开发 wheel 构建 PASS。未操作生产库；正式 Worker、解析消费者、上传 Commit/Abort、Server 2025 与 Gate 3 未通过。
