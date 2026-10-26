# CR-PLAN-011：补齐 PlanVersion 原子送审项目授权策略

- 日期：2026-10-26
- 状态：`AUTHORIZED_FOR_IMPLEMENTATION_BY_CR-EXEC-002`
- 来源 WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P05-A02`
- 基线：Gate 2 冻结 API-04 `PLAN_VERSION_SUBMIT_REVIEW`；P09-P04 送审 UI 编码前检查；既有送审服务与 HTTP 合同

## 差异证据（编码前）

- 首次真实 Windows 11 Edge→HTTP→PostgreSQL 闭环可完成真实 Session 登录、PlanVersion 创建与固定版本 GET、Validate（HTTP 200）、Review 页面读取；提交送审 POST 返回 `404 RESOURCE_NOT_FOUND`。
- 错误码符合隐藏未授权资源的安全约定。只读源码发现 `PlanVersionReviewSubmissionService.PROJECT_OPERATION` 使用 `PLAN_VERSION_SUBMIT_REVIEW`，但 `ProjectAuthorizationService.POLICIES` 未登记该冻结操作；故合法负责人也被安全失败关闭。
- 冻结合同及 P09-P04 编码前检查已明确仅 `PROJECT_MANAGER` 可提交。本修正不会新增角色、API、字段、表、Migration 或权限范围，只补齐既定角色映射。

## 方案、风险与回退

- 方案：在授权矩阵中将 `PLAN_VERSION_SUBMIT_REVIEW` 精确登记为仅 `PROJECT_MANAGER`、写操作；扩充授权矩阵单元测试，保持实施成员/客户角色拒绝。
- 风险：若错误增加角色会扩大写权限；因此验收固定检查角色集合恰为负责人，并验证非负责人被拒绝。跨项目/归档/License/来源/readiness仍由既有事务服务执行。
- 回退：移除新增策略和矩阵断言；无 Schema/API/数据迁移，不改变已有数据库事实。
- 验证计划：授权矩阵定向测试、送审服务/HTTP及权限回归、原 Edge→真实 HTTP→PG 浏览器闭环、前端全量/typecheck/build、完整后端测试、Secret/diff 检查；所有测试副作用仅限 D 盘隔离环境。

## 授权结论

依用户持续自主执行授权与 `CR-EXEC-002`，先记录差异后修复。Gate/Pilot/正式发行结论不因本 CR 改变；如真实 Edge/PG 闭环仍失败，保留失败并继续诊断。
