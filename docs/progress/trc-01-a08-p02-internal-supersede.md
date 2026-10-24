# TRC-01-A08-P02：PROJECT TraceLink 内部原子替换

日期：2026-10-02；Phase 2；结果：**当前项目经理内部命令/隔离 PG18 PASS，公开 HTTP 与关系 Owner 未实现**。输入冻结 API-02 `TRACE_LINK_SUPERSEDE`、DM-03、0029/0053、P01 前置与 DEC-20261002-617；Gate 2 原冻结提交不改。

内部命令先验证当前 License、真实 Session/CSRF 和当前 ACTIVE 项目的 ProjectManager，再锁旧 PROJECT 边并检查强版本/状态；收据在状态检查前预留以安全重放首次结果。新边必须同项目、与旧边不同且至少共享一个端点。Document Owner Port 在调用方事务中证明新边两端固定版本，受控关系验环；Trace 仓储仅接受本事务全新 ACTIVE 插入，不复用已有边。接着设置旧边 SUPERSEDED/替代引用，数据库守卫校同范围、时间、ACTIVE 目标并把旧边版本 v0→v1。两条 Audit（新边创建、旧边替代）与一条持久收据和关系更新同事务提交。旧边不删除，也不从端点自动推断关系 Owner。

验证：单元新增 3 项，项目策略定向 7 项；Windows 11 一次性 PostgreSQL 18 实际 Session/Document Owner/迁移 Head，覆盖非经理/跨项目/失效 License、强版本、同边拒绝、合成 Audit 失败整事务回滚、同 Key 并发重放一条旧终态/一新边/一替换 Audit/一收据、不同 Key 终态冲突、预先存在 ACTIVE 目标不被复用；原 Trace 创建/有界图/撤销 HTTP 同脚本回归 PASS。全后端 **1895 运行、3 跳过、无失败**；开发 wheel SHA-256 `184cdb8db11efd305aff09c6f249d515f9f9316d0188ed329c2aabb855db0602`。此 wheel 是开发构建，不是可使用发行包。

兼容/升级/回滚：仅内部 Trace Application/Repository 与 Project 操作策略增量，复用现有 0029/0053、通用收据和 Audit；无新 Migration、公开 API、依赖或旧数据改写。不装配此命令即可停止新替换；已替代历史不能反向改回 ACTIVE，纠正应保留旧事实并建立后续受权关系。公开合同路径、关系 Owner 身份/撤权、正式目标账户 License/密钥、Server2025/Debian、性能/UAT/Gate 3 与最终程序包仍未验。

Next：`TRC-01-A08-P03` 显式可选 supersede HTTP 的冻结请求/强 ETag/幂等/最小结果；默认和正式平台保持关闭，生产装配另行核查。
