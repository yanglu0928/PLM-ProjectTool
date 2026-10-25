# DOC-03-A04-A04-P01：Job/Outbox 持久层前置

日期：2026-09-26；版本：`0.1.0.dev0`；状态：基础 Schema/ORM PASS，上传 Commit/Abort 未完成。

按 `CR-DOC-006` 新增 Job、Attempt、Lease、OutboxEvent、Consumption 五张私有表及增量 `20260926_0025`。Scope/Project、任务和事件幂等键、状态、尝试计数、活动 Lease 唯一性、fencing token、消费去重与领取索引由数据库约束；任务/事件只设计最小引用 JSONB，不存正文或 Secret。原冻结版本与历史迁移不改。

Windows 11/Python 3.13 后端 495 项无失败（2 项因当前账户符号链接权限跳过）；隔离 PostgreSQL 18 已验证旧数据升级、ORM 差异为零、任务/消费重复拒绝、有历史记录降级拒绝、清空后降级/再升级；开发 wheel 构建 PASS。临时验证库已删除。生产升级需先备份，再将目标库升级到 head；生产库未操作。

后续须完成 Job 领取/Lease 心跳/过期 fencing 的事务命令、受控 Outbox 投递与消费，以及 Document 上传 Commit/Abort 的同事务编排和故障注入。当前不可称解析 Worker、正式 HTTP Commit/Abort、Windows Server 2025 或最终可用程序包通过。
