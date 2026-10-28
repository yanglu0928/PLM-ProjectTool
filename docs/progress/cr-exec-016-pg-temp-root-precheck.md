# CR-EXEC-016 编码前检查：A17 nested PostgreSQL 临时根

- 日期：2026-10-28
- 唯一问题：包内 PostgreSQL smoke 继承 P42 负向目录 ACL 夹具作为系统 temp，导致 initdb 不能创建数据目录。
- 证据：run 40650259852 的日志为 PLMToolTemp/plm-p42-platform-write-<随机>/pgdata Permission denied；所有路径映射、候选构建和父包 PG smoke 已通过。
- 实施方向：A17 上优先使用已验证的 PLM_P51_TEMP_ROOT，创建唯一命名的直接子目录作为 DB data root；其他调用 fallback 系统 temp。清理时沿用同一个显式选定 root 并确认对象归本次调用。
- 验收：路径选择单测与 hosted Windows A17 bundled initdb/migration/cleanup full flow。
- 回滚：移除 A17 root 覆写，恢复系统 temp，保留 A17 failed run。
- 数据：合成 PostgreSQL；不连接外部或现有数据库。
