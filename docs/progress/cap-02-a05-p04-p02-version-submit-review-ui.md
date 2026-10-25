# CAP-02-A05-P04-P02：能力版本正式送审入口

日期：2026-10-24；状态：`FRONTEND_SUBMISSION_PASS / GLOBAL_REVIEW_DECISION_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `CAP-02-A05-P04-P02`；只解决 DRAFT 能力版本的正式送审用户入口。|
|基线/前置|冻结 API-04 `CAP_VERSION_SUBMIT_REVIEW`、现有 CR-CAP-003 请求增量、P04-P01 VALIDATE 入口、Capability Version DRAFT 读取及 Admin User 列表。|
|模块/接口|前端 Capability + Auth；既有 POST `:submit-review`，固定 `DEPLOYMENT_ALL_V1`、`due_at/submission_note=null`；无 Schema/Migration/后端合同变更。|
|权限与事实|仅当前 DeploymentAdmin、非强制改密、DRAFT 且无 Review 指针可发起；依据冻结 Capability Review Subject 决策，界面给出已启用用户候选，后端同事务重新核验 Session/License/来源/Reviewer。VALIDATE 报告和前端筛选不替代服务端验证。|
|幂等与验收|固定排序 Reviewer 集合及原 Key 保存在会话存储；未知结果要求核对历史后同内容同号重试；严格核对 201、no-store、强 ETag、`CAP-01`/身份/Reviewer/`IN_REVIEW` 回执，不把送审当批准。|

版本详情增“正式送审”，可从分页用户列表选择 1～32 名已启用用户，必须显式确认送审范围。普通用户不能发起送审或读取候选；受分配且当前已启用的用户可在后续 Review 路径作决定。成功后显示 Review/首轮 ID 和“尚未批准”，不提供不存在的 GLOBAL Review 详情跳转。若响应丢失，保留 Reviewer 集合和操作号；明确业务拒绝可清除原号，幂等冲突锁定并要求查审计。Admin User 安全投影增加已由后端验证的 `deployment_role`，不暴露内部其他用户字段。

验证：送审客户端 4 项、送审面板 3 项、用户列表既有 32 项；前端全量 177 文件、1938/1938，typecheck 和 Vite build 通过。Vite 大 chunk 警告仍在。没有真实浏览器/包内 Edge/PG 送审、GLOBAL Review 公开决定接口、真实管理员决定或批准版本证据；后续先建立可追溯 API 增量 CR 再做 P04-P03。Gate/Pilot/Release 未通过。

2026-10-24 纠偏：冻结决策仅要求 Reviewer 全部当前启用，而非全部为 DeploymentAdmin；原先前端候选筛选过窄。`CR-CAP-005` 实施前静态复核发现并改为已启用用户，后续结果以新的定向与全量回归为准；原 P02 验收与措辞保留在 Git 历史中。
