# WFL-01-A07-P04-A01：Evidence 当前固定记录共享锁

日期：2026-10-02；Phase 2；来源 `CR-WFL-005`、`DEC-20261002-604`。状态：**内部仓储 PASS，完整 Owner OPEN**。原 Gate 2 冻结提交 `64cdf09` 保留。

Evidence 新增内部 `LockedEvidenceSource` 和独立 `get_for_trace`：精确查当前 `ELIGIBLE`、Scope/Project 匹配的 Evidence 行，在调用方事务执行 `FOR SHARE OF evd_evidence_records` 并刷新 identity map。返回固定 Document/Version/ParseRecord、locator、fingerprint、lock_version；locator/fingerprint 不出现在对象 `repr`。普通元数据列表/详情和人工资格写锁不改。

验收：定向单元 2/2；一次性 PostgreSQL 18 中错误项目、CANDIDATE 与 REVOKED 拒绝，旧 ORM 缓存刷新到最新 lock_version，持锁期间第二连接 `FOR UPDATE NOWAIT` 返回 `55P03`，释放后可更新。后端全量 1840 通过/3 跳过；开发 wheel SHA-256 `075b82b711838eaf48540b819e68671cdd91a14f563d6a153cb46b2af32a7dda`。

兼容/回滚：无 API、Schema/Migration、依赖或数据迁移；可不装配后续 Owner。此仓储只能证明数据库当前资格和固定元数据，**尚未**证明调用者的项目经理权限、Document 物理文件、locator/node/fingerprint 或窄 GLOBAL 标准引用。`WFL-01-A07-P04-A02` 将处理 PROJECT 来源组合；Checklist/Gate 写、正式发行均继续关闭。
