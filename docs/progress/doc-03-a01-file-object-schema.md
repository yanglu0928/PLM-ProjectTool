# DOC-03-A01：FileObject 持久层

- Phase/WBS：Phase 2 Platform Core / DOC-03-A01。来源：Gate 2 冻结 DM-03、SC-01/02、API-02，CR-DOC-001；决策 DEC-20260925-087。
- Changed：新增 `doc_file_objects`、`doc_file_state_events` 的 Document-owned ORM/Migration；GLOBAL/PROJECT Scope 与 Project FK、相对 Locator 基础形状、Hash/Size/MIME、状态、actor/time/版本/Retention 及仅追加事件。正文仍在受控文件系统，未开放 HTTP。
- Migration：`20260925_0020`；目标库升级前备份并执行至 head；空表可降至 `0019`，已有文件元数据/事件时拒绝普通降级。无新增依赖。
- Tests：Windows 11/Python 3.13 后端 441/441 PASS；PostgreSQL 18 临时库有 Project 数据升级、空表 down/up、ORM 差异、Scope/Project/Locator/Hash/Size/AVAILABLE 形状、事件不可改写、FK 与非空降级保护 PASS；开发 wheel PASS。临时库已删除，测试服务已停止。
- Result：FileObject 持久层 PASS；Storage Adapter、真实文件写入/恢复、DocumentVersion、上传/下载及 Gate 3 未完成。
- Known Issues：数据库 Locator 约束不替代文件系统符号链接/重解析点与同卷原子操作验证；Server 2025/HTTPS、Debian 13 和正式信任材料未验证。
- Next：DOC-03-A02 受控本地 Storage Adapter。
