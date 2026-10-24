# SOL-03-A06-P01：OutlineVersion 正式 Review 链前置核查

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`PRECHECK_PASS`；本项仅确定真实缺口和实施顺序，不宣称 Outline 可送审或已批准。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-03-A06-P01`|
|输入基线|冻结 DM-05 `SOL-03`、API-04 `SOL_OUTLINE_VERSION_VALIDATE/SUBMIT_REVIEW`、统一 Review；PlanVersion Approved Solution 前置阻断|
|现有前置|OutlineVersion DRAFT 创建/读取/Windows/前端和真实浏览器已验；固定章节顺序、Approved RequirementVersion 与合格 ReferenceSolution 的创建时证明可复用|
|涉及模块|solution、review、trace、project、audit；本项只读合同与现有代码|
|API/权限|冻结 VALIDATE 允许 ProjectManager/ImplementationMember；SUBMIT_REVIEW 仅 ProjectManager；Reviewer 必须重验当前项目成员，GET/Session/License 按既有合同|
|验收标准|定位现时 order/source/coverage 检查、Subject 固定身份、原子送审/终态窄门、HTTP/Windows/前端/PG-浏览器独立分片|
|风险|把创建时来源证明或历史 VALIDATE 结果当成送审现时资格；Outline 批准误认为所有 Section 正文也批准；绕过统一 Review 或直接写批准指针|

## 核查结论

1. `SolutionOutlineVersionRow` 已存不可变的章节身份顺序、固定 RequirementVersion/ReferenceVersion、声明、内容摘要和 Review/Round 外键；状态列含 DRAFT/IN_REVIEW/APPROVED，但当前数据库 Owner Guard 只允许受控 DRAFT 创建，尚无合法 Review 状态窄门与回执。
2. 仓库无 `SOL_OUTLINE_VERSION_VALIDATE` 应用服务/路由，也无 Outline Version Review Subject Owner、原子送审服务或终态消费。创建时的 Approved Requirement 与 Reference 可用性证明是历史快照，不能替代送审/批准时同事务重新证明当前事实。
3. Outline Review 只确认固定结构；按照冻结数据模型，Outline 批准不等于 SectionVersion/StructuredSpec 正文批准。正式 Solution 输出及 Plan 输入仍需单独固定每个已批准的 SectionVersion/StructuredSpecVersion。
4. 复用统一 PROJECT Review 的 Subject/Round/Decision/Audit/幂等/终态消费；拟固定 Subject 为 `SOL-03 / solution_outline_id / solution_outline_version_id`，策略和状态转移在实现前用现有 Review Port/Schema 精确核对，不创建平行审批表。若发现冻结冲突，先登记 CR，再按持续授权实施。

## 独立实施顺序

- `SOL-03-A06-P02`：先定义 Outline 现时验证的报告/事实合同与纯评估边界；`order/source/coverage` 的未取得证明必须表达为 `UNAVAILABLE`，不默认 PASS。
- 后续独立任务：当前来源/Trace/覆盖证明 Owner；冻结 VALIDATE 的授权、幂等、Audit、HTTP/Windows 与真实 PG；统一 Review 生命周期 Schema 窄门/Subject Owner；原子送审、HTTP/Windows、前端与真实浏览器。每片编码前再核查其精确前置并独立验收。
- Section Version Review 是另一个 Subject，不由 Outline Review 自动替代。两者完成后才返回 PlanVersion 整体 Approved 输入与来源/Trace 一致性。

验证方式：冻结合同、迁移、ORM、应用/路由现状静态交叉核查；本项无程序、Schema、API、权限、License、Secret 或客户数据变化，未运行功能测试。Gate 3/Pilot/正式发行状态不变。
