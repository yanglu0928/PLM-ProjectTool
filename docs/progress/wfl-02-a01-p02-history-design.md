# WFL-02-A01-P02 追加历史持久层设计

日期 2026-09-26；结果 DESIGN_RECORDED / SCHEMA_NOT_IMPLEMENTED。

Phase 2；输入 DM-02/SC-01 WFL-02/API-02、CR-WFL-001/002 和已验证历史形状。前置为固定定义/0030 实例/读服务已完成。本任务只解决迁移快照的关系存储设计，不编码 ORM/SQL/API，不声明数据库 PASS。

核查结果：现有 Evidence 内容固定但 eligibility/lock 可变；Review Schema 尚不存在，UUID 不证明批准。按持续授权记录 CR-WFL-003，采用两张冻结表+owned typed refs，保留观测版本/状态/摘要；Checklist 追加历史与 START/最终完成仍须独立设计，原 Scope 不缩减。

Files：`docs/changes/CR-WFL-003-transition-gate-history.md`、`docs/workflow/transition-history-design-v1.md` 及状态/决策/版本记录。原冻结和 Migration 不修改。

验收：差异、方案比较、风险、迁移/回滚、引用归属/事实保护、追加与完整性、应用开放前置以及空/有数据/up/down/非空拒绝矩阵已记录。仅文件核查；本轮未运行 SQL、API、权限或程序测试，之前 649 项结果仅为上一任务证据，不能替代本次 Schema 验收。

下一任务 WFL-02-A01-P03：按 CR-WFL-003 实施三表 ORM/Migration 0031 与隔离 PostgreSQL 矩阵；如设计的事务追加保护不可实施，先记录差异再调整，不以省略约束取得 PASS。若需要 Review 真实 FK/运行放行，停止相关子任务并转 Review 独立前置。
