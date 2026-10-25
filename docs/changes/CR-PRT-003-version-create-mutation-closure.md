# CR-PRT-003：Prototype Version CREATE 根对象闭包修复

日期：2026-10-08。状态：依 CR-EXEC-001 持续授权实施；Gate 2 原冻结提交 `64cdf09` 不改写。

## 发现与影响

PRT-01-A10-A07 的 Windows 11 Edge → 生产 FastAPI → PostgreSQL 18.6 闭环中，`POST /api/v1/.../versions` 返回 503。数据库原始异常为 `Prototype mutation has no immutable result`。0131 迁移要求创建 Version 时递增 Prototype 根对象锁版本，而 0132 的递延根对象闭包仅识别身份命令、Scope 决策和 Review 状态结果，漏掉 Version CREATE 的不可变结果。现有单元模拟无法发现该生产组合；因此 Version CREATE 不能宣称通过，后续验证/送审也受阻。

## 决策与边界

采用 0135 前向修复：给 `prt_version_create_results` 增加仅内部使用的 `prototype_lock_version`，新结果必须记录本次根对象锁版本；旧历史行保留 NULL，不编造来源。以该列、根对象、Version 创建者及 DRAFT 状态共同校验结果，并把对应不可变结果纳入根对象的递延闭包。新增同根对象同锁版本唯一约束，防止重复占用。ORM 与仓储同步写入。既有 API、权限、License、项目隔离、业务状态和冻结载荷不变；不回写 0131/0132，也不增加依赖。

后续真实送审发现同一冻结输入的第二个缺口：创建时内容指纹包含 `expected_lock_version`，而当前事实复验重建载荷时漏掉该字段，稳定输入也被误判 `CONTENT_FINGERPRINT_MISMATCH`。0135 的不可变结果锁版本可还原创建时的期望值（结果锁版本减一）；内部读取投影与当前事实校验据此重建原载荷。旧 NULL 结果缺少可证明来源，维持失败关闭，不推断锁版本。

拒绝只放宽闭包或通过临时关闭触发器绕过：这会允许无结果的根对象变更。该修复不把一次 Edge 复验外推为 Windows Server 2025/Debian 13 已验证。

## 迁移、回滚与验证

升级为可空增量列及非空行唯一索引；现存行不修改。应用新写入必须非空，并与本次根锁及 Version 作者匹配。回滚仅在不存在新格式结果时允许，恢复原触发器及 Schema；若已有新格式结果，拒绝回滚，须先走业务数据迁移/保留历史方案，不删除不可变记录。先执行空库和有数据升级/降级检查，再以真实 PostgreSQL、后端回归和 Windows 11 Edge 闭环验证；失败不得关闭 Gate。所有结果记录在 STATUS、决策/版本说明并同步 GitHub。
