# REQ-01-A12-A01：Requirement Workflow 资格前置核查

日期：2026-10-08。结论：`REQ_01_A12_A01_WORKFLOW_PRECHECK_PASS`。下一项：
`REQ-01-A12-A02` 多Subject资格集合合同与既有Owner兼容。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A12-A01
输入基线：六阶段Definition V1、冻结REQ-01～04、A02～A11运行证据、CR-EXEC-001
前置任务：Requirement Schema/Owner/Review/HTTP/UI/Windows Edge闭环已PASS
涉及模块：workflow qualification/checklist/transition、requirement current-fact owner、Windows组合、前端
涉及实体：项目内Requirement全量范围、Approved RequirementVersion、REQ-03 Review、决定与Evidence
涉及API：既有Workflow qualification/checklist/transition路径；不改冻结Requirement URL
涉及权限：ProjectManager写与当前Session/License；业务Owner在调用者事务内重证
验收标准：多正式版本全集、未决草稿阻断、决定缺口不静默、双item同集合、顺序推进与漂移失败关闭
风险：单Subject合同漏验范围；Package被误作Scope批准；直接归档绕过决定；历史Validate冒充当前事实
```

## 差距矩阵

|能力|现状|结论|
|---|---|---|
|六阶段定义|已固定Requirement两个required item|存在，不代表运行资格|
|正式需求事实|Root正式指针、不可变Version、A07当前验证、REQ-03 Review已存在|可复用，必须逐项当前重证|
|范围缺口|DEFER/REJECT有不可变决定+Evidence；ARCHIVE可不带决定|直接归档不得自动合格|
|通用资格合同|只支持一个subject/version/review|不能表达多Requirement项目|
|Checklist record|只注册Handover/Survey四项|缺Requirement两项与复数Review证明|
|资格Preview/HTTP|只序列化Handover/Survey响应|需新增Requirement集合变体|
|Stage Transition|已到`SURVEY → REQUIREMENT`|缺`REQUIREMENT → PROTOTYPE`|
|Windows组合|只装配Handover/Survey Owner|缺Requirement Owner/registry|
|前端|资格动作只识别Handover/Survey|缺Requirement集合确认与推进|

## 结论与拆分

- 已登记`CR-REQ-004`并采用多Subject资格集合；不制造合成Review，不选择单个需求代表项目，也不以
  RequirementPackage静默缩窄范围。
- A12拆分为：A02通用集合合同/兼容；A03 Requirement current-fact Owner；A04 Checklist/Preview/
  Transition/Windows接线；A05 Windows 11真实PG；A06前端；A07真实Edge完整三阶段推进。
- 本项纯设计和静态对账，无运行代码、Schema/Migration、公开路由、依赖、Secret、客户数据或外发变化；
  不声称Requirement资格、PROTOTYPE推进、Gate 3、UAT或发行通过。

