# CR-DOC-008/A03-P01：已登记 Abort 文件只读清理资格检查

- 日期：2026-09-26；结果：Windows 11/隔离 PostgreSQL 18.6 内部只读检查 PASS；未实现或执行已登记文件物理删除。
- 范围：对单个明确 `upload_id` 持有 A01 OS 栅栏后，在短事务读取 Abort Intent、FileObject，并核对同 Scope/Project/ID、`ABORTED`/`CLEANUP_PENDING`、PERSISTENT、`UPLOAD_ABORTED`、零 DocumentVersion、无保留时间、规范暂存 Locator 和 Hash/Size；只接受“仅暂存文件”形态，完整验证内容后在第二短事务重读全部候选字段。不返回路径给业务调用方；无候选/状态变化/最终文件/损坏均不得标为可清理。
- 验证：Windows 11/Python 3.13 单元覆盖二次核查、候选变化、损坏/仅最终文件及争用拒绝；隔离 PostgreSQL 18.6/临时文件验证已登记中止候选、无文件记录、保留时间拒绝及最终文件拒绝并保留物理文件。后端 553 项无失败（2 项既有符号链接环境跳过），开发 wheel PASS。测试临时库/文件已清理，PG 测试服务已停止。
- Migration/公开 API/新依赖：无；版本 `0.1.0.dev0`。此检查仅提供下一步决策输入；A03-P02 删除前还须验证物理身份/引用复查、外部删除与数据库状态/Audit 崩溃对账、旧版进程停写和目标账户。此项不能关闭原物理清理阻塞或 Gate 3。
