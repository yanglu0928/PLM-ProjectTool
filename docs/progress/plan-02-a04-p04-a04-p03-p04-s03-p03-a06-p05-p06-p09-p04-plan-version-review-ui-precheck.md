# A06-P05-P06-P09-P04 PlanVersion 原子送审页面编码前核查

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P04`
- 结果：`PRECHECK_PASS`

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P04
输入基线：冻结API-04 PLAN_VERSION_SUBMIT_REVIEW；既有PlanVersionReviewSubmissionService/HTTP/Windows写组合；PlanVersionWriteClient.submitReview严格合同Client；P09-P01固定只读、P09-P02草稿Create、P09-P03 Validate UI；既有ProjectMemberReadClient及Review用户路径
前置任务：P06-P04原子送审HTTP、P06-P06送审Client、P09-P01固定快照、P09-P02不可变Create、P09-P03明确Validate结果页均完成
涉及模块：frontend PlanVersion固定版本送审页面与Review回执；读取ProjectMemberReadClient；只消费现有送审Client/组合
涉及实体：固定DRAFT PlanVersion、活动客户评审成员、不可变ReviewSubmission回执（ReviewRef/RoundRef/IN_REVIEW）；不代替Review决定
涉及API：冻结POST `/api/v1/projects/{project_id}/plans/{plan_id}/versions/{plan_version_id}:submit-review`、冻结PlanVersion GET及既有Project Member分页GET；无新增API/Schema/Migration
涉及权限：仅ProjectManager可提交；候选仅当前项目ACTIVE的CUSTOMER_MANAGER/CUSTOMER_MEMBER；实施成员仅可读/Validate，不可送审；后端在同一事务重新核查固定DRAFT、当前来源/Validate readiness及客户评审人资格
验收标准：固定版本详情明确入口；按完整分页读取活动项目成员并过滤客户评审角色，分页异常/重复/超限失败关闭；仅当前DRAFT且无Review引用显示送审控件；至少选1人、至多32人并明确说明提交后进入IN_REVIEW而非批准；必须用户显式确认后提交；提交前持久化固定reviewer集合及幂等Key，不确定时只允许原集合原Key重试；同Key回执校验项目/计划/版本/提交人一致后展示Review与Round，不自动作决定；同Key/双击/会话与路由变化/客户成员变化/失败映射有测试；前端全量/typecheck/build，后端现有送审API/Owner/组合相关回归及复用同日Win11/PG18合成原子送审证据
风险：Review启动是写操作，可能创建Review/Round并把固定PlanVersion改为IN_REVIEW；不能只依据前端Validate缓存送审，服务端既有同事务readiness为权威；不能将回执或IN_REVIEW写成批准；评审人当前资格变化由服务端再次判定并要求刷新候选
```

## 基线核查

- 冻结合同明确只有ProjectManager可调用，载荷必须精确为 `reviewer_ids`、`policy_ref=PLAN_VERSION_ALL_V1`、`due_at=null`、`submission_note=null`。
- `PlanVersionWriteClient.submitReview` 已实现窄SessionClient桥接、reviewer UUID/数量/重复校验、排序、精确回执/ETag/提交人校验及确定/不确定错误分类。
- `PlanVersionReviewSubmissionService` 与 `PlanReviewSubjectOwner` 仅接受当前固定DRAFT，服务端交易内重新证明Plan readiness并只允许活动客户经理/客户成员作为评审人；Windows显式write组合已挂载。
- `ProjectMemberReadClient` 可读取成员分页；既有Survey/其他模块送审面板已验证“完整分页→按角色筛选→持久原请求→人工确认重试”路径可复用，但Plan版本入口必须独立并使用Plan固定版本DTO/策略。
- 本WBS是已批准Scope内前端接入；未发现需改API/Schema/后端Owner的冻结冲突。无客户数据外发或生产数据操作。
