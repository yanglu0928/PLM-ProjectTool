# SUR-06-A01：Survey Workflow 资格前置核查

日期：2026-10-07。结论：`SUR_06_A01_WORKFLOW_QUALIFICATION_PRECHECK_PASS`。下一项：
`SUR-06-A02` 通用资格合同、注册表与 Handover 兼容 adapter。

## 差距矩阵

|能力|现状|结论|
|---|---|---|
|六阶段定义|Survey 已固定 `SURVEY_ACTUAL_SOURCES`、`SURVEY_CONCLUSION`|存在，不代表运行资格|
|实际来源事实|CLOSED Round、VALIDATED Response、答复/PROJECT_RECORD Evidence Owner 已存在|可复用，必须当前重证|
|正式结论|不可变 Conclusion、Validate、SRV-05 Review 及 APPROVED 状态已存在|可复用，不能只信历史报告|
|Workflow basis|Schema 支持非空 ELIGIBLE Evidence 与 APPROVED ReviewRound|足够承载；无需先改 Schema|
|Checklist record|只接受 Handover key/DTO|缺 Survey 注册|
|资格 preview/HTTP|只接受 Handover，投影固定 analysis version|需兼容响应变体|
|Stage Transition|只实现 `HANDOVER → SURVEY` 并重证 Handover 两项|缺 `SURVEY → REQUIREMENT`|
|Windows 组合|只装配 Handover qualification Owner|缺 Survey Owner/registry|
|前端|写入、资格和 target 均硬编码 Handover|缺 Survey 交互|

## 结论与边界

- 已登记 `CR-SUR-012`，选择通用内部资格注册表；Handover 响应逐字段保持不变，Survey 使用独立严格
  响应变体。业务 identity 继续由服务端解析，冻结 Checklist request 不扩字段。
- 两个 Survey item 必须在同一事务指向同一个当前 APPROVED Conclusion 和 ReviewRound，并重新证明
  实际来源、Evidence、冲突与待办；模板、AI、历史 Validate 或客户端 PASS 均不成立。
- 本项纯设计/静态核查，无运行代码、Schema/API 路径、依赖、Secret 或外发变化；不声称资格、阶段推进、
  完整模拟项目、Gate 3、UAT 或发行通过。

## 验证证据

- 对账 Workflow catalog、record/preview/transition services、Windows composition、前端严格客户端与
  Survey Round/Response/Conclusion/Review Owner。
- 识别并登记五处 Handover 专用运行假设，形成 A02～A07 可独立验证拆分及回滚路径。
