# CR-DOC-008/A02-P02：Commit 全窗口栅栏

- 日期：2026-09-26；结果：Windows 11 Commit 同 ID 栅栏接入 PASS；Abort/清理尚未接入，物理清理仍关闭。
- 依据：`CR-DOC-008`。Commit Service 强制注入栅栏，规范参数校验后、首次许可/数据库预检前取得；跨越短事务预检、外部文件提升/恢复、最终 DocumentVersion/Parse Job/Audit/收据事务，直到结果返回才释放。争用失败在数据库预检前映射既有文件不可用安全错误，不暴露内部锁路径。
- Windows `--platform-write` 组合向 Content 与 Commit 注入同一数据根的栅栏实例；默认/只读模式写路由继续关闭。
- 验证：Windows 11/Python 3.13 单元验证取锁失败不进入事务；隔离 PostgreSQL 18.6/临时文件脚本通过新建/已有版本、父版本条件、重放、License/Actor 拒绝、原子回滚、仅最终文件恢复和损坏正文；后端 548 项无失败（2 项既有符号链接环境跳过），开发 wheel PASS。
- 无 Migration、新依赖或冻结 API 变更；版本 `0.1.0.dev0`。回滚须先停写；A02-P03 Abort 与完整交叉并发验证前不得执行已登记正文物理清理。
