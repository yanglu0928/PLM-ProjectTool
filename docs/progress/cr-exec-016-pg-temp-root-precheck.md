# CR-EXEC-016 编码前检查：A17 nested PostgreSQL 临时根

- 日期：2026-10-28
- 唯一问题：包内 PostgreSQL smoke 继承 P42 负向目录 ACL 夹具作为系统 temp，导致 initdb 不能创建数据目录。
- 证据：run 40650259852 的日志为 PLMToolTemp/plm-p42-platform-write-<随机>/pgdata Permission denied；所有路径映射、候选构建和父包 PG smoke 已通过。
- 实施方向：A17 上优先使用已验证的 PLM_P51_TEMP_ROOT，创建唯一命名的直接子目录作为 DB data root；其他调用 fallback 系统 temp。清理时沿用同一个显式选定 root 并确认对象归本次调用。
- 验收：路径选择单测与 hosted Windows A17 bundled initdb/migration/cleanup full flow。
- 回滚：移除 A17 root 覆写，恢复系统 temp，保留 A17 failed run。
- 数据：合成 PostgreSQL；不连接外部或现有数据库。

- 2026-10-28 云端 run 40652307366：新增 A17 temp-root 静态边界检查 PASS；后端 3849 项单测有 1 项既有并发测试 ready.wait(3) 偶发超时，其余基线组件 job 成功、打包/A17依赖任务跳过。已登记 CR-EXEC-016；完整重跑待证，不把该 run 记为通过。

- 2026-10-28 hosted run 40652933457：后端 3849/3849、前端、PG18/pgvector、embedded backend 与 parent candidate 构建通过。新增路径单测 fixture 使用默认 C 盘系统 temp，正确被边界规则拒绝；已记录为测试夹具错误，修改夹具使用 RUNNER_TEMP 的独立子目录后重跑。A17 full flow 因投影检查失败未运行。

- 2026-10-28 hosted run 40654144099：后端3849项、前端、运行时组装、父包和A17候选投影、父包PG smoke全部通过；A17真实链仍在 `smoke_packaged_platform_write_https.py` 的 PG initdb 失败。路径显示 temp_root 被 P42 负向 ACL 夹具设为 `plm-p42-platform-write-*`。已将 CR-EXEC-016 扩展至该嵌套 smoke：A17 优先用 PLM_P51_TEMP_ROOT，非 A17 保留 PLM_TEST_TEMP_ROOT fallback。不能记 PASS。

- 2026-10-28 hosted run 40656184670：CR 临时根选择单测、父包 PG smoke均通过，但 Platform Write nested smoke 仍把 PG `pgdata` 写在 P42 `plm-p42-platform-write-*` 目录并收到拒绝。扩展方案：独立创建 sibling PostgreSQL 临时目录，不与 P42 专用权限工作目录共用；重新执行 A17。
