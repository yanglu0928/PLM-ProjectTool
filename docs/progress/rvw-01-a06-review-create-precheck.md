# RVW-01-A06 Review identity 创建前置

2026-09-26；0.1.0.dev0；结果 DESIGN_COMPLETE / ACTUAL_OWNER_PRECONDITION_BLOCKED。

Phase 2；输入 AF-02/DM-02/API-02 REVIEW_CREATE/ResourceVersionRef、CR-RVW-001/0034/A04/A05。检查已有通用幂等收据可保存稳定创建 Ref，但不能返回后来变化的 state/etag 冒充首次响应；Review 根只绑定逻辑身份，CREATE 与 START_ROUND 必须分离。

完成 `docs/review/review-create-design-v1.md`：PM/ACTIVE/CSRF、Owner 绑定固定输入与服务器 policy、DRAFT 根创建、同事务 Audit/收据/故障回滚、撤权后拒绝重放、不可变 CreatedReviewRef、无新表/列和无隐含每主题唯一 Review 规则。

真实业务主题 Owner 尚未具备，阻塞真实公开接线，不阻塞窄内部命令/合成 Owner 协议验证；不需要用户重复批准。未编写新程序，未运行新增测试，无新 Migration/API/依赖，设计不等于实际创建/审批/Gate PASS。

Next：RVW-01-A07 内部 PM Review identity 创建/幂等与真实 Session/Project/Audit 验收，缺 Owner 继续失败关闭。
