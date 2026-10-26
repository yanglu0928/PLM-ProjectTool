# A06-P05-P06-P09-P03 PlanVersion Validate 页面编码前核查

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P03`
- 结果：`PRECHECK_PASS`

## 编码前检查

```text
当前Phase：Phase 2 Platform Core
当前WBS：PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09-P03
输入基线：冻结API-04 PLAN_VERSION_VALIDATE；既有PlanVersionValidationService/HTTP/Windows显式写组合；PlanVersionWriteClient.validate严格响应Client；P09-P01固定版本只读详情页与P09-P02草稿创建页
前置任务：P06-P04 Validate HTTP及写组合、P06-P06 Validate Client、P09-P01固定快照读页面、P09-P02不可变Create与固定ID读回均完成
涉及模块：frontend PlanVersion固定版本详情/Validate页面；复用PlanVersionWriteClient；仅显式Windows写组合既有路由，无新后端组合
涉及实体：固定PlanVersion快照、ValidationReport(valid/blocking_issues/warnings/coverage_summary/checked_at)、幂等操作键；Validate不改变计划/版本状态
涉及API：仅冻结POST `/api/v1/projects/{project_id}/plans/{plan_id}/versions/{plan_version_id}:validate` 与现有固定版本GET；Validate为bodyless请求，不新增API/Schema/Migration
涉及权限：项目负责人/实施成员及有效Session/CSRF/License由现有Client/后端Owner约束；前端使用当前Session并不推断批准/项目资格；默认、只读模式不挂载写路由
验收标准：从固定版本详情显式进入Validate；展示验证开始/结果/失败状态，按严格合同展示valid、阻断问题、警告、需求/方案覆盖计数、检查时间；不自动提交、不自动送审；Validate不通过或后端拒绝时不显示PASS；响应不确定时保留原幂等键并只允许原操作重试；导航/身份变化时丢弃旧响应；路由变化/权限与会话边界、重复点击、异常和HTTP合同具备前端测试；定向/前端全量/typecheck/build，并复验现有Win11 PG18 Validate HTTP/Owner合同且只使用合成身份、来源与License
风险：Validate会写入不可变验证结果/Audit/幂等收据，不能把页面读取误作纯GET；报告证明特定快照/来源时点而非永久有效或业务批准；报告过时后须重新验证，review流程另行独立
```

## 实施边界

- 现有后端 Validate route 仅在显式 Windows write composition 下挂载；本任务消费既有 route 和 Client，不修改后端授权、评估、持久化或 API Contract。
- 页面明确报告 Validate 仅作快照核查，不替代客户确认或 Review；当前 `valid=true` 也不能称为批准或交付。
- 不做 Review UI、Reviewer选择、SubmitReview、候选来源编辑或历史版本改写。
- 本项属已授权Scope内L1前端实现，无CR/Schema/API变化；若核查发现合同或现有Windows实证不满足边界，先记录偏差后暂停相关编码并转独立检查。

## 输入检查结果

- 冻结合同 `docs/api-contract/api-04-implementation-business-chain-v1-candidate.md` 定义 PLAN_VERSION_VALIDATE 和 ValidationReport。
- HTTP要求可信Origin/Session/CSRF、幂等Key、canonical UUID、query/body为空；响应 `200`、no-store、固定字段报告。
- 现有 `PlanVersionWriteClient.validate` 已严格解析valid与阻断问题关系、排序、coverage非负整数及UTC检查时间；不可用时区分确定拒绝与不确定结果。
- 当前缺口为用户可操作Validate页面和固定快照上下文中的结果显示；不需要修改服务端。
