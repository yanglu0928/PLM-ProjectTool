# SOL-06-A09-P02：专项完整草案 Repository 与首次结果重建

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。TraceLink：Gate 2 SOL-06 → 0161～0164 → A07 固定草案/A08 现时来源 → 本项。Phase 2。
- Changed：新增 Solution 内部 SQLAlchemy Repository，在调用者事务内用与 0164 相同的 series advisory lock 选版/核对前驱，写 Root、类型化 payload、按顺序固定的 Requirement/Section/Evidence 引用；Artifact 非空拒绝。`first_result` 从不可变 Root+payload+有序子集重建最初 DRAFT 视图，核对项目、版本链、条数/顺序/唯一性、payload 语义与 SHA-256。结果只含初次创建的稳定字段，未来 Review 状态不能改变首次响应含义。
- 安全边界：Repository 不创建 Session/CSRF/License/Project 授权、不自行提交事务，不写 Audit 或持久幂等收据；只有后续受权 Service 可在同事务调用并提交。直接 SQL 合成版本不是客户业务事实；当前无公开入口、Windows 组合或 UI。
- Verification：Win11 可弃 PG18.6 真实 Auth/已批准合成 Requirement/固定最新 SectionVersion/Document/Evidence 来源 → 内部 Repository 完整 DRAFT v1、首次结果读回、同 series v2、旧前驱/跨项目拒绝及子行计数通过；底层 fixture 对来源撤回/篡改等负例继续通过。后端全量 3621 通过/3 跳过/5677 子例，开发 wheel 与新模块入包通过。无 Migration、冻结 API 或权限变化；未装配 Repository 可撤回，已插入历史不可清除。
- Next：`SOL-06-A09-P03` 在现有 Receipt/Audit/Project 授权边界安装正式内部创建 Service，验证同 Key 原响应/并发/审计失败回滚；之后独立 HTTP/Windows/UI、Trace/Review。Gate3/Pilot/正式发行未通过。
