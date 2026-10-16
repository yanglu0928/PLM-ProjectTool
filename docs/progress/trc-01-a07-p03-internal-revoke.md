# TRC-01-A07-P03：PROJECT TraceLink 内部撤销命令

日期：2026-10-02；Phase 2；状态：**当前ProjectManager内部命令PASS，公开HTTP/关系Owner未实现**。输入冻结 API-02、CR-TRC-003、已验证0053版本列、DEC-20261002-614；Gate 2原冻结提交保留。

新增内部命令先验当前License与Session/CSRF，再以Project操作策略要求当前ACTIVE项目的ProjectManager；Trace自有Repository在相同事务锁定精确PROJECT/ProjectId/LinkId，收据预留在状态检查之前保证同Key同载荷首次结果重放。新命令必须原强版本v0和ACTIVE；DB拥有触发器变为REVOKED/v1，Audit与持久收据同事务提交。返回仅LinkId/v1，不投影两端；已失效目标不会阻止PM清理既有项目边。关系Owner路径不注册。

验证：撤销单元4/4、项目策略7/7；Windows11自启动一次性PG18原Trace创建/图矩阵扩展非经理、跨项目、CSRF/License、错版本拒绝，受限端点PM清理、同Key并发一次状态转换/一份Audit/一份收据，Audit失败后ACTIVE/v0与零撤销收据；退出0且临时库/进程清理。后端全量1889运行/3跳过/无失败；开发wheel SHA-256 `36465601c896ab3d562e774d1acbac965dbc565e8b3b672475a817944fee4f32`。首轮全量原项目策略计数断言30失配，增加新操作后更新31并重跑通过。

兼容/升级/回滚：内部Trace Application/Repository与Project操作策略增量，复用0053和0015，无新Migration、公开API或依赖；不装配内部命令即可停止新撤销，已撤销历史不反向改回ACTIVE。后续可选HTTP须独立验证冻结路径/If-Match/幂等/错误合同并显式安全装配；关系Owner身份Port、正式License信任、Server2025/Debian、性能/UAT/Gate和可用发行包仍待。
