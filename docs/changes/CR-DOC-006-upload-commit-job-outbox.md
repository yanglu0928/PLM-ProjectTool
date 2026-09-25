# CR-DOC-006：上传 Commit 的 Job/Outbox 持久化前置

日期：2026-09-26；状态：持续授权下实施中。原 Gate 2 冻结提交 `64cdf09` 保留，不倒写。

## 来源、差异与选择

冻结 API-02 的上传 Commit 必须返回 DocumentVersion 与 Parse Job，DM-03 要求文件发布后的 DocumentVersion、Job、Outbox、Audit 在短数据库事务中一致提交；ADR-007 要求 PostgreSQL Job/Outbox 至少一次、租约 fencing。当前迁移 head `20260925_0024` 尚无 Job/Outbox 表，已有 `DOC-02-A02-P01` 仅实现既有 Document 的内部版本提交，不能作为完整上传 Commit 宣称通过。

不选同步解析或仅在内存中排队：请求崩溃时任务会丢失，且破坏冻结契约。不选直接把解析任务塞入 Document 表：不能表达独立重试、租约与投递历史。选择在独立 `jobs` Owner 下增量建立 Job、Attempt、Lease、Outbox、Consumption 数据层，再由 Document Owner 以同一事务写版本、上传意图终态、Parse Job、最小引用 Outbox 和 Audit。后续独立接入受控 Worker；不引入 Redis/消息队列，不把文件正文或 Secret 放入任务载荷。

## 迁移、回滚与风险

增量 Alembic `20260926_0025` 与同构 ORM，不改变公开 `/api/v1` DTO。空表可降级；任一新表有记录时拒绝降级，先备份再升级。旧 Document/FileObject/UploadIntent 保留原值。文件提升与数据库提交之间的崩溃窗须由恢复命令处理，不能以该迁移消除；旧 Worker 的过期 fencing 必须在后续结果发布命令中再次校验。工作按 `DOC-03-A04-A04` 子任务分段验证，基础表完成不等于 Commit/Abort 或 Worker 已完成。

## 验证计划

验证空库及有数据升级、空表降级再升级、非空降级拒绝、ORM 差异为零、Scope/Project、幂等唯一键、状态、Lease token 与 Outbox 消费去重约束；随后做两 Worker 竞争、过期 fencing、崩溃恢复及公开接口端到端。每一段保留真实结果，不推断 Server 2025 或发行信任源已通过。
