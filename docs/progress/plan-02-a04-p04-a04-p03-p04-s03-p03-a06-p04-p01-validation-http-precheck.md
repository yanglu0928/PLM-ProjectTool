# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P01：Validate HTTP接线编码前核查

日期：2026-10-26。结果：`PRECHECK_COMPLETE`；仅静态合同核查，无路由/运行行为变化。

## 编码前检查

- 当前Phase：Phase 2 Platform Core。
- 当前WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P01`。
- 输入：冻结API-04的`PLAN_VERSION_VALIDATE`、A06-P02报告DTO、A06-P03-P02的0189不可变报告结果Schema、A06-P03-P03内部事务Owner与现有Solution Validate HTTP模式。
- 单一问题：确定冻结Validate operation到可选HTTP边界的请求/响应/安全/装配约束；本片不编码、不挂载端点。
- 公开合同：POST `/api/v1/projects/{project_id}/plans/{plan_id}/versions/{plan_version_id}:validate`；空请求体、禁止query；返回200 ValidationReport(valid, blocking_issues, warnings, coverage_summary, checked_at)，不改变PlanVersion状态。
- 权限与头：trusted Origin、Session Cookie、CSRF、License、当前Project PM/IM操作授权、Idempotency-Key与Audit；项目/版本身份仅取路径并在Owner内重核，不能从客户端提交来源/coverage。
- 安全错误：无效Session/CSRF和跨项目或隐藏资源依现有Envelope；明确映射幂等冲突、许可拒绝、Archived项目和畸形请求；未知内部错误统一SYSTEM_UNAVAILABLE，不泄露异常/来源细节。
- 响应：仅序列化冻结Report字段，时间UTC ISO-8601 Z；Cache-Control no-store；不要将内部Audit主键或snapshot fingerprint额外扩展成API字段。
- 接线：HTTP边界使用run_in_threadpool调用同步Owner；新增可选router参数并仅由显式Windows PlanVersion平台组合注入。普通默认应用不自动暴露该写端点。
- 验收：契约测试覆盖空体/query/UUID/头/Envelope/report/UTC/no-store/重复Key边界；后续隔离PG18组合验证正链、PM/IM授权、拒绝角色、许可/跨项目、同Key重放、来源变化时重放和Audit/Receipt原子性。浏览器和Pilot另列，不由HTTP合同PASS推定。

## 结论

- Solution Outline/Section Validate HTTP既有可信Origin、Session+CSRF前置校验、幂等头、空体/no-query及标准Envelope可作为边界范式；Plan仍调用其自身Owner和授权，不共享其他模块身份/报告。
- 冻结API已含本路由，无需CR或breaking change；本项不改数据库、依赖、License或默认路由集合。
- 无阻断。下一项：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P02`，实现可选Validate HTTP合同路由和定向契约测试，保持默认应用关闭；随后另做显式Windows HTTP/PG组合验证。
- Gate 3、Pilot、正式发行、Server 2025和Debian 13结论不变。
