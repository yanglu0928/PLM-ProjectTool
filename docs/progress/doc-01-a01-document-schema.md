# DOC-01-A01：Document 逻辑身份持久层

- Phase/WBS：Phase 2 Platform Core / DOC-01-A01。输入：Gate 2 冻结 DM-03、SC-01/02、API-02、CR-DOC-002、DEC-20260925-091，Project/User 表与 DOC-03 FileObject 已有。
- 编码前检查：Document Infrastructure；实体 Document；无公开 API/权限入口。验收为 Scope/Project、类别、标题/原名元数据、状态、并发版本和身份不可变的数据库约束；风险为 DocumentVersion 尚缺，指针不能自由写入。
- Changed/Files：`modules/document/infrastructure/orm.py` 新增 `DocumentRow`；Migration `20260925_0021` 新增 `doc_documents`、Project/User FK、类别/Scope/指针/版本约束及身份不可变触发器；更新 ORM/Migration 契约测试；`validation/doc-01-a01-document-schema/verify.py` 隔离库验收。
- Migration/API/升级：目标库先备份再由 `0020` 升至 `0021`；空表可降级至 `0020`，非空拒绝普通降级。无新公开 API/依赖。latest/effective 指针暂由数据库强制为 NULL，DOC-02 建版本表后须加入真实 FK/同 Document/Scope 保护并解除初态约束。
- Tests/Result：Windows 11/Python 3.13 后端 453 项无失败（2 项真实符号链接测试因账户权限跳过）；PostgreSQL 18 临时库有 FileObject 数据升级、空表 down/up、ORM 差异、合法 GLOBAL/PROJECT/OTHER/GENERATED 类别、非法 Scope/类别/标题/状态/指针/版本、绕过 ORM 改写身份拒绝、非空降级保护 PASS；开发 wheel PASS。临时库已删除，测试服务已停止。Document 元数据持久层 PASS，不代表 Document 功能可用。
- Known Issues：DocumentVersion、上传/下载、正式 Document 授权、Project Archived 写保护及版本指针最终 FK 尚未实现；Windows Server 2025/Debian 13 未验证，DOC-03 真实符号链接测试仍有 2 项跳过。
- Next：DOC-02-A01 不可变 DocumentVersion 持久层前置核查。
