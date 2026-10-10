# DOC-03-A04-A04-P02：Job 租约与 fencing

日期：2026-09-26；版本：`0.1.0.dev0`；状态：内部事务命令 PASS，独立 Worker/Outbox/Parser 未完成。

按 ADR-007、`CR-DOC-006` 与 `DEC-20260926-114`，Job Owner 新增短事务领取、心跳、完成与有界重试。领取按优先级排序、`FOR UPDATE SKIP LOCKED` 行锁；每次领取追加 Attempt/Lease 并增加单调 fencing token；过期接管先终止旧 Lease 和 Attempt。心跳、结果完成及重试都核对当前 Worker、token、活动 Lease 与数据库时间。完成回调与 Job 终态处于同一事务，回调失败则回滚；回调只允许短数据库发布操作，不允许在事务内执行 OCR、模型或文件处理。

Windows 11/Python 3.13 后端 497 项无失败（2 项符号链接权限跳过）；隔离 PostgreSQL 18 两 Worker 竞争、过期接管、旧 Worker 拒绝、回调失败回滚、有界重试与成功完成验证 PASS；开发 wheel 构建 PASS。无新迁移、公开 API、依赖或生产库操作。

下一项：Outbox 领取/重试/消费去重的事务命令，然后接入 Document 上传 Commit/Abort 和独立 Parser Worker。当前不会对外运行解析，不代表 Gate 3 通过。
