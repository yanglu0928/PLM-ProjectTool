# DOC-02-A01：不可变 DocumentVersion 持久层

- Phase/WBS：Phase 2 Platform Core / DOC-02-A01。输入：Gate 2 冻结 DM-03、SC-01/02、API-02，DOC-01-A01/DOC-03-A01，CR-DOC-003、DEC-20260925-092。
- 编码前检查：Document Infrastructure；实体 DocumentVersion、VersionSourceRef，关联 Document/FileObject；无公开 API/权限入口。验收为同 Scope/Project、AVAILABLE 持久 FileObject、Hash/Size/MIME 快照、版本号/前驱链、latest/effective 指针、不可变历史及可逆空库升级。风险是数据库不能证明磁盘正文，也不能替代授权、Audit 和跨资源恢复。
- Changed/Files：`modules/document/infrastructure/orm.py` 新增两个 Root/来源映射并给 Document 指针加后建 FK；Migration `20260925_0022` 增加两表、基础 FK/唯一约束和事务触发器，解除 `0021` 暂时的 NULL 指针限制；更新 ORM/Migration 契约测试；`validation/doc-02-a01-version-schema/verify.py` 隔离库验收。
- Migration/API/升级：目标库先备份再从 `0021` 升至 `0022`；已有 Document 行的 NULL 指针保留。版本/来源表空且所有指针 NULL 时允许降级；存在版本/来源/指针则拒绝普通降级。无新公开 API/依赖。
- Tests/Result：Windows 11/Python 3.13 后端 453 项无失败（2 项真实符号链接测试因账户权限跳过）；PostgreSQL 18 临时库有 Document/FileObject 数据升级、空表 down/up、ORM 差异、GLOBAL/PROJECT、同范围可用文件、摘要/大小/MIME、连续版本与前驱链、文件一对一、归档项目拒绝、指针可用性、来源与内容不可改写、已发布文件元数据不可改写及非空降级保护 PASS；开发 wheel PASS。临时库已删除，测试服务已停止。持久层 PASS，不代表实际版本发布可用。
- Known Issues：磁盘文件存在与实际 SHA-256、发布命令的 expected_version/幂等/授权、Audit/Job/Outbox 与崩溃恢复仍需真实集成。已有 FileObject 状态可在内部受控命令中 RESTRICTED，读取端必须同时检查版本与文件状态；Server 2025/Debian 13 未验证。
- Next：DOC-03-A03-P03 文件完整性校验与受控 AVAILABLE 发布前置核查。
