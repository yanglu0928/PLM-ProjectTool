# DOC-03-A03-P02：FileObject 失败/限制状态事务命令

- Phase/WBS：Phase 2 Platform Core / DOC-03-A03-P02。输入：冻结 DM-03、API-02、ADR-008，DOC-03-A01/A02/A03-P01、通用幂等 `0015`、FileObject `0020`；决策 DEC-20260925-090。
- 编码前检查：Document Application/Infrastructure；实体 FileObject、FileStateEvent；无公开 API。访问通过强制注入的内部 AccessPort，当前只在隔离测试中用合成实现；验收为 Scope/Project/版本锁、`STAGED→FAILED` 与 `AVAILABLE→RESTRICTED`、状态/事件/Audit/收据同事务、同键重放与回滚。风险为文件/数据库跨资源不原子、未接正式 Document 权限。
- Changed/Files：`change_file_state.py` 内部服务和安全输入/幂等/Audit；`file_state_repository.py` 行锁/状态事件；`test_file_state_command.py` 负向输入；`validation/doc-03-a03-p02-file-state/verify.py` 临时 PostgreSQL 事务、并发、授权与回滚验收。
- Migration/API/升级：无新 Migration、公开 API 或依赖；目标库须已升级至 `0015` 与 `0020`。服务未装配 HTTP，停用可移除内部接线；既有状态、事件、Audit 和收据作为历史保留。
- Tests/Result：Windows 11/Python 3.13 后端 453 项无失败，其中 2 项真实符号链接测试因账户权限跳过；PostgreSQL 18 临时库同键顺序/并发重放各仅一次状态、事件、Audit/收据，异载荷、旧版本、跨项目及合成未授权拒绝，审计失败回滚并用同键重试 PASS；开发 wheel PASS。临时数据库已删除，测试服务已停止。内部命令在合成授权范围 PASS，DOC-03 整体未完成。
- Known Issues：AccessPort 尚无正式 Document 授权适配；自动恢复需要受控 SYSTEM actor、完整性证明与恢复矩阵，不得直接以此命令宣称完成。AVAILABLE 发布和 CLEANUP_PENDING/REMOVED 仍关闭；原始文件/数据库原子性、Windows Server 2025/Debian 13 未验证，之前真实符号链接场景仍跳过。
- Next：先推进 DOC-01-A01 Document 持久层及后续不可变 DocumentVersion；再恢复 DOC-03 发布、清理与恢复协调任务。
