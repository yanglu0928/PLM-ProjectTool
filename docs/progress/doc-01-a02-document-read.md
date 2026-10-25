# DOC-01-A02：内部受权 Document 元数据读取

日期：2026-09-26；版本：`0.1.0.dev0`；状态：内部 Application/Repository PASS，公开 HTTP 和完整 GLOBAL 引用策略未完成。

按冻结 DM-03、API-02 与 `DEC-20260926-120`，Document 模块新增只读 DocumentView/Page 和按 document_id 稳定 keyset 的内部列表/详情。一次短事务中由 Auth Owner Port 验当前 Session、Project Owner Port 验当前成员及项目状态，GLOBAL 由 Auth Owner Port 验 DeploymentAdmin，License Guard 拒绝无效许可。只投影 Scope、分类、标题/显示名、状态、版本引用、时间与强 ETag，不读取文件正文/Locator；ACTIVE/ARCHIVED 可见，RESTRICTED 默认失败关闭。跨项目、停用成员、无会话、非管理员 GLOBAL 均不泄露目标元数据。

Windows 11/Python 3.13 后端 508 项无失败（2 项符号链接权限跳过）；隔离 PostgreSQL 18 验证两页 keyset、客户成员、项目归档后读取、跨项目/受限隐藏、停用成员/无会话/License 拒绝、GLOBAL 管理员独读；开发 wheel PASS。无 Migration、公开 API 或新依赖。项目成员读取正式引用的 GLOBAL Version 所需引用/类别策略尚无可核验事实，此入口保持失败关闭，不能把 DOC-01 全部读取能力标 PASS。下一项为签名 Document 列表 cursor/正式 GET 与版本读取、下载；目标 Server 2025、生产信任源和 Gate 3 未验证。
