# AUD-01-A01 AuditEvent 存储验收

- 日期：2026-09-24；结果：PASS；来源：Gate 2 冻结内容 `64cdf09` 的 DM-02/SC-01～03/API-02，以及 `DEC-20260924-072`。
- 变更：`plm.aud_events` ORM、Alembic `20260924_0005`、三组 SC-03 索引、Scope/Actor/65 Root 目标白名单/安全码约束；数据库触发器拒绝 UPDATE、DELETE、TRUNCATE。业务 API/服务端审计写入本任务不实施。
- 验收：Windows 11、Python 3.13 后端 89/89；本机 PostgreSQL 18.6 临时隔离库空库 up/down/re-up、有现存 PLT 数据升级、ORM drift=0、约束拒绝、只追加拒绝、非空 downgrade 拒绝、备份恢复 PASS。验证入口：`validation/aud-01-a01-audit-schema/verify.py`。
- 升级：先备份，执行 `upgrade head`；有事件时不得普通回退。未对 Windows Server 2025 或 Debian 13 做本任务发行验证。
- 遗留：真实 AuditService/同事务写入与授权、审计读取/导出、Retention/Legal Hold、DB 权限收紧尚未实现；Gate 3/UAT 未通过。下一任务为 `AUD-01-A02 AuditService append Port/Repository`。
