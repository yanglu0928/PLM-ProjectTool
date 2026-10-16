# DOC-03-A04-A04-P04-P03-P01：上传 Abort 状态编排

日期：2026-09-26；版本：`0.1.0.dev0`；状态：内部数据库状态编排 PASS，物理清理与公开 Abort HTTP 未完成。

按冻结 API-02、DM-03 与 `DEC-20260926-117`，新增受当前 Session/项目角色/创建者 Port、License Guard、幂等 Key 保护的内部 Abort。CREATED 意图直接进入 ABORTED；CONTENT_READY 意图在同一短事务内把已登记 FileObject 依次 STAGED→FAILED→CLEANUP_PENDING，留下两次不可变状态事件，再将 Intent 置 ABORTED，并写 Audit/收据。重放只读原结果。项目、目标 Document、Intent、FileObject 采用与 Commit 一致的锁序。已提交意图与已正式引用文件不能终止；不在事务内删除物理正文。

Windows 11/Python 3.13 后端 503 项无失败（2 项符号链接权限跳过）；隔离 PostgreSQL 18/临时文件验证 CREATED/CONTENT_READY、同 Key 重放、创建者/License 拒绝、状态事件、Audit 失败整库回滚和物理文件未误删；开发 wheel PASS。无新迁移、公开 API 或依赖，需已有 `0026`。下项 P03-P02 实现已登记文件的精确身份清理及崩溃窗口对账，再接正式 Commit/Abort HTTP；Server 2025、生产信任源和 Gate 3 未通过。
