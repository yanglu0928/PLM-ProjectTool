# RVW-02-A02 送审前置

2026-09-26；0.1.0.dev0；DESIGN_COMPLETE / ACTUAL_OWNER_PRECONDITION_BLOCKED。

Phase 2；核对 AF-02/DM-02/API-02/0034 与现有 Auth 写、Project 授权代码。完成 `docs/review/review-start-preconditions-v1.md`：基础账户/成员资格与主题逐人资格分离、服务器角色子集而非任意请求政策、真实主题身份锁必须阻止内容和替代 Draft、固定 Source 观测、完整同事务 start/audit/receipt。

发现潜在 reviewer User 与 Project 锁倒序，设计先全部候选账户共享锁再 Project；完整 Session/CSRF/start 适配另做，不声明已验证整个流程无死锁。无新 Migration/API/角色/依赖；本设计自身未运行新增程序测试。

真实 Subject Owner/送审锁缺失阻塞公开送审，不需要用户再次批准；独立账户/项目资格可继续，Next RVW-02-A03。
