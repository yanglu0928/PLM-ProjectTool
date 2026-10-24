# RVW-01-A04 Review 读取授权前置

2026-09-26；0.1.0.dev0；结果 DESIGN_COMPLETE / ACTUAL_OWNER_PRECONDITION_BLOCKED。

Phase 2；输入冻结 AF-02/DM-02/API-02、CR-RVW-001/0034/RVW-01-A03。检查实际 Project 策略目前没有 REVIEW_GET，已有读查询只是可信内部 Port；Review GET 需要有效成员与主题 Owner 访问权，不能由任意 UUID、旧决定或部署管理员替代。

完成 `docs/review/review-read-authorization-design-v1.md`：两层授权、同事务事实锁、旧固定版本独立权限、历史引用不授予源正文访问权、错误不泄露存在性，明确 Project→Review→Owner→Round 相对锁序。无代码/Migration/API/依赖改动，本设计任务没有运行新增程序验收；不声明真实业务权限或 API 通过。

【待确认】
问题：真实 Handover/Survey/Requirement 等 Subject Owner 尚未完成。
影响：无法证明当前主题/旧 Version 可读及送审身份锁。
当前可选方案：保持默认拒绝的窄 Owner Port，继续内部应用验收；或伪造恒真 Owner。
建议：只采用前者；后者违反冻结安全边界，禁止。
是否阻塞：阻塞真实公开 Review 接线，不阻塞 RVW-01-A05 内部受权协议实现；不需要用户再次决定。

Next：RVW-01-A05 内部 PROJECT Review 受权读服务；完整 Owner/审批/HTTP 留待真实前置，不跨 Phase 编造。
