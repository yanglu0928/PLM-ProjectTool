# EVD-01-A02：固定 DocumentVersion 的 Evidence 持久模型

- 日期：2026-09-26；Phase 2 Platform Core；输入：Gate 2 冻结 EVD-01/DM-03/SC-01/SC-02、DOC-02 DocumentVersion、`DEC-20260926-136`。
- Changed：新增 `plm.evd_evidence_records` ORM 和 `20260926_0027` Migration。记录固定 Document/DocumentVersion、Scope/Project、Locator 类型/schema version/JSONB、32-byte 内容指纹、受限显示字段、资格状态、创建主体与乐观版本。外键锁定版本归属；插入触发器核对来源 AVAILABLE、Scope/Project 一致和初态 CANDIDATE；更新保护固定来源/Locator/指纹，删除拒绝。已有 DocumentVersion 不修改、不复制正文或路径。
- Files：Evidence ORM、迁移、迁移元数据注册与单元合同、`validation/evd-01-a02-record-schema/verify.py`。公开 API、新依赖：无；版本 `0.1.0.dev0`。升级需先备份并执行新增 Migration；有 Evidence 历史时降级按设计拒绝，不能自动删证据。
- Tests：Windows 11/Python 3.13 后端 564 项无失败（2 项既有符号链接环境跳过）；开发 wheel PASS。隔离 PostgreSQL 18.6 完成旧版已有用户/Project/DocumentVersion 数据升级、空表 down/re-up、ORM drift=0、GLOBAL/PROJECT 正向插入、跨项目/错误 Document/Locator 类型/指纹/初态拒绝、来源不可变/版本防护/历史保留、来源 REVOKED 后新建拒绝与有记录降级拒绝。首次完整回归因元数据表集合断言未登记新表失败；已更新合同测试并完整重跑通过。测试库已删除，测试服务已关闭。
- Result：EVD-01-A02 持久模型及隔离数据库约束 PASS；EVD-01 整体、Gate 3 与可用程序包未通过。数据库只约束 Locator 类型/schema version 与 JSONB 基础形状，不能证明九型细节和文件内容真实可重定位；后续受权写服务必须先调用 A01 校验，再由 DocumentService 核实固定版本、真实内容与权限。AI Candidate 不得自动变为 ELIGIBLE，TEMPLATE 不得独立证明客户事实。
- Next：EVD-01-A03 内部受权候选创建与来源解析 Port；之后再做资格命令、Viewer、Binding。正式 Windows Server 2025 未运行本项；Debian 13 按用户当前指令暂不验证。
