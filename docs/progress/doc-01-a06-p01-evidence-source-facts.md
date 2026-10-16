# DOC-01-A06-P01：Document 同事务 Evidence 来源事实 Port

日期：2026-10-01；Phase 2 Platform Core；结论：`INTERNAL_CODE_PASS / POSTGRESQL_PROOF_OPEN`。

输入为冻结 Evidence 资格规则、CR-EVD-003 和 Document 现有固定版本锁定读取。前置：DocumentReadService 的当前 Session、License、Project/Admin 授权与 `get_version_for_trace` 已存在。范围仅 Document 内部应用 Port，不新增 API、Schema、依赖或跨模块表查询。

实现 `get_source_facts_for_evidence(transaction, query, document_id, version_id)`：在调用方事务内复验当前授权并锁定项目及固定可用 DocumentVersion，再读取同一 Document 的当前类别/状态；仅返回资格所需的最小事实，不返回物理位置/正文。版本或文档不一致、撤销、跨项目、无权限均失败关闭。先锁定的 DocumentRow 读锁约束后续类别/状态更新时序；调用方不得另开事务。

验证：新增 3 项单元测试覆盖同一事务与锁、模板类别、伪造/撤销来源、移除成员和非法版本。后端全量 1779 项通过、3 项跳过；wheel 构建通过。当前本机未监听隔离 PostgreSQL 18 的 55432 端口，也没有 PostgreSQL 服务，实际 DB 事务/锁、撤销、跨项目证明待环境恢复后执行；不得称生产或 Gate 3 PASS。回滚为撤内部 Port，历史记录不变。下一项可独立实现 Evidence 资格策略，但正式数据库验收仍开放。
