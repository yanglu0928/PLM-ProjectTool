# DOC-03-A03-P01：FileObject 状态流转策略

- Phase/WBS：Phase 2 Platform Core / DOC-03-A03-P01。输入：冻结 DM-03 状态图、ADR-008、DOC-03-A01/A02；决策 DEC-20260925-089。
- 编码前检查：Document Domain；实体仅 FileObject；无公开 API/新权限入口。验收为精确许可 `STAGED→AVAILABLE/FAILED`、`FAILED→CLEANUP_PENDING`、`CLEANUP_PENDING→REMOVED`、`AVAILABLE→RESTRICTED`、仅 TEMPORARY `AVAILABLE→CLEANUP_PENDING`，其他流转失败关闭；同时指出内容、引用/保留及原因记录必须由后续事务命令验证。
- Changed/Files：`modules/document/domain/file_state.py` 内部纯策略与 `test_file_state_policy.py` 完整状态对单测。仅返回需要哪些证明，不接触数据库/文件，也不授权或执行状态变更。
- Migration/API/升级：无新 Migration、公开 API 或依赖；已有 `0020` 按 DOC-03-A01 要求升级。本项不改变现有数据，回滚为不接入策略。
- Tests/Result：Windows 11/Python 3.13 后端 451 项无失败（前项真实符号链接创建权限导致 2 项跳过）；开发 wheel PASS。状态图策略 PASS；真实状态命令、同事务审计和恢复器未实现。
- Known Issues：内容 Hash/Size/MIME、最终文件存在、Project 授权、expected_version、保护引用、Retention/Hold 及恢复幂等均不能由纯策略证明，必须在后续命令/集成验收中失败关闭。Windows Server 2025/Debian 13 未验证。
- Next：DOC-03-A03-P02 FileObject 同事务状态事件命令。
