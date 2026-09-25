# DOC-03-A03-P04-P03 异常文件隔离分类与恢复审计

日期：2026-09-25。版本：`0.1.0.dev0`。状态：内部命令合成验证 PASS；P04 整体及生产自动恢复未完成。

依据冻结 DM-03，新增明确指定 FileObject 的恢复隔离命令。调用者必须通过 Scope/Project 授权、预期版本与注入的“发布已停止”证明；前后两次检查文件形态且在最终检查时持有数据库行锁。只有无文件、仅暂存、独占最终文件摘要不符、两份互不相同的普通文件可分类为隔离原因；其 STAGED→FAILED、失败码、状态事件、Audit、幂等收据在同一 PostgreSQL 事务提交。文件不删除，FAILED 不逆转为 AVAILABLE，重传须创建新 FileObject。

最终文件完整、同一硬链接对可恢复，或存在重解析点/其他不安全形态时，本命令拒绝变更，继续 STAGED 供受控恢复或人工排查；不会以目录扫描或年龄猜测替代停写证明。现有生产运行时尚无可信 Quiescence Port，本命令没有公开 HTTP 或生产装配，不能声称自动恢复可用。

Windows 11/Python 3.13 后端 461 项无失败（2 项符号链接场景因当前账户权限跳过）；PostgreSQL 18 临时库合成停写证明、权限/跨项目、四类隔离、重放、拒绝与审计回滚 PASS；P01/P02 恢复及 P03 发布回归、开发 wheel PASS。无新 Migration、API 或依赖；目标库仍须既有 `20260925_0022`。Server 2025/Debian 13、真实停写/维护模式、TTL 清理、AVAILABLE 无 Version、版本损坏与 Parse Job 恢复未验证/未实现。

追溯：`DEC-20260925-096`、ADR-008、冻结 DM-03、`validation/doc-03-a03-p04-p03-file-quarantine/verify.py`。
