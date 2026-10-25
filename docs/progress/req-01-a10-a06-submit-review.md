# REQ-01-A10-A06：RequirementVersion 原子送审

日期：2026-10-08。结论：`REQ_01_A10_A06_SUBMIT_REVIEW_PASS`。下一项：
`REQ-01-A10-A07` RequirementRelation 四个冻结 HTTP。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A10-A06
输入基线：冻结API-01/API-04、REQ-01/REQ-03、CR-REQ-001、Migration0120
前置任务：A05 Version HTTP、Requirement Review Subject Owner均PASS
涉及模块：requirement application/api、project authorization/reviewer、统一PROJECT Review、Audit
涉及实体：RequirementVersion、Review、ReviewRound、SubjectSnapshot、IdempotencyReceipt、AuditEvent
涉及API：REQ_VERSION_SUBMIT_REVIEW
涉及权限：仅ProjectManager；Reviewer必须是当前合格项目成员
验收标准：固定策略、当前事实重验、Review create/start/bind/receipt/Audit同UOW、持久回放、默认关闭
风险：客户端串行两次Review调用；中间DRAFT泄露；来源漂移仍送审；回放绕过Subject访问重验
```

## 结果

- 新增 `RequirementReviewSubmissionService`，固定 `REQ-03 + REQUIREMENT_ALL_V1` 与
  `REQ_VERSION_SUBMIT_REVIEW` ProjectManager策略；Reviewer排序、锁定并按当前Project成员重验。
- Review create、Round start、RequirementVersion `IN_REVIEW`绑定、SubjectSnapshot、Audit及receipt
  在单一UOW内提交；提交前后均重验License，数据库死锁最多重试三次。
- 同key/同载荷从持久receipt读取首次Round并通过Requirement Subject重验访问；同key异载荷409，
  不创建第二个Review。当前来源失效时422且事务零落地。
- 新增opt-in冻结HTTP边界；请求精确包含reviewer_ids/policy_ref/due_at/submission_note，后二者V1
  必须显式为null，不静默丢弃。通用应用默认不注入仍404，Windows正式组合留A08。
- 定向application/API/authorization 13项通过；完整后端3060项通过、3项跳过。
- Windows 11/PostgreSQL 18.6真实来源撤销拒绝/恢复送审、原子Review链、回放/冲突、角色/
  License拒绝、Audit及Alembic drift通过。
- 开发wheel共1162项，SHA-256
  `4fab22cfcd1e5f8f3ecf52ca2464aefb01d5f61a19c684286ab50d18436ba64f`。
- 验收脚本首轮构造Version多传一个位置参数，次轮查询把正式表名误写为无`plt_`前缀；两次均
  作废，修正后以新临时库完整重跑。无Schema/Migration、依赖、Secret、客户数据或外发变化。
