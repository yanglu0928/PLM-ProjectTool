# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P03-P03：PlanVersion Validate事务Owner

日期：2026-10-26。结果：PLAN_VERSION_VALIDATION_OWNER_INTERNAL_PASS；仅内部Owner与合成PG证据，不含HTTP/Gate/Pilot结论。

## 编码前检查与边界

- 按本WBS前置记录完成编码前检查；输入为冻结API-04 Validate报告合同、CR-PLAN-006与Migration 0189、A06-P02确定性报告评价器，以及现有Session/CSRF/License/Project授权、PlanVersion快照和Approved来源证明Owner。
- 单一问题：实现受权、只读PlanVersion Validate内部事务Owner；不新增HTTP路由，不改变PlanVersion状态，不引入新Schema/依赖/公开API。
- 版本根在事务内共享锁读取；当前Approved Solution/Requirement事实由服务端复证。客户端不能提供可信Coverage范围。
- 报告、Audit事件、0189不可变结果行与通用IdempotencyReceipt在一个UOW提交；同Key精确恢复首次报告，不重新执行可能已变化的来源证明。权限仍需当前有效，payload/目标不符拒绝。
- 来源不可用或来源覆盖不匹配映射为稳定阻断问题码，而不是将业务验证缺陷变成服务端成功事实；未经授权、许可失效、跨项目身份仍按拒绝路径处理。

## 实施结果

- 新增PlanVersionValidationService与PostgreSQL结果仓储，实现Session/CSRF、License、当前Project PLAN_VERSION_VALIDATE授权、固定快照校验、当前批准来源证明、确定性报告、Audit/结果快照/Receipt原子提交及重放读取。
- Project授权矩阵显式授予ProjectManager与ImplementationMember该写操作；其它角色不因此获得权限。
- Windows平台提供显式内部服务组合；未装入默认HTTP应用。无Migration、冻结API、License、安全依赖或业务事实变化。
- 独立验证脚本复用已有全批准来源合成夹具，在一次性Win11 PostgreSQL 18环境验证真实来源链、同Key报告完全一致重放、数据库记录唯一性及Audit失败整体回滚；不读写客户数据。

## 验收与限制

- 定向授权/Owner测试：15 passed, 859 subtests。
- 完整后端回归：4146 passed, 3 skipped, 6195 subtests passed。
- Win11隔离PostgreSQL 18合成事务验证：Owner正链/精确重放及失败原子性断言通过；结果标记PLAN_VERSION_VALIDATION_OWNER_POSTGRESQL_PASS。它不证明正式安装信任、真实客户审批、Pilot或Gate通过。
- compileall与差异空白检查通过；变更尚待Secret检查、远端同步及提交后复验。
- Known Issues：Validate HTTP合同/路由/Windows HTTP组合与浏览器验收尚未完成；没有可用户操作的Validate页面。Gate 3、Pilot、正式发行仍未通过。
- 下一项：PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P01，核查Validate HTTP接线的冻结请求/响应/错误Envelope、CSRF/Session/License/幂等头语义、端点挂载范围和Win11隔离PG验收计划；本次不提前挂载路由。
