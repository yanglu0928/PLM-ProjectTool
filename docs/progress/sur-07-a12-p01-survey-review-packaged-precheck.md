# SUR-07-A12-P01：Survey 校验/送审固定包验收前置核查

日期：2026-10-25；结果：`SUR_07_A12_P01_PACKAGE_PRECHECK_PASS / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SUR-07-A12-P01`；只核对最新 Survey A10/A11 前端与现有固定包验收链差异，不修改产品。|
|输入基线|CR-EXEC-002；冻结 Survey Version Validate、原子 Submit Review 与 `SURVEY_ALL_V1`；源码提交 `a5c1af7b`。|
|前置任务|`SUR-07-A08-P02` Survey DRAFT 包内创建；`SUR-07-A10` 校验报告 UI；`SUR-07-A11` 当前客户评审人原子送审 UI；`CAP-02-A05-P05-P04` License 自然失效包内负例。|
|涉及模块/实体/API|后续只扩展 Windows 非发行包验收脚本：`SurveyVersion`、`ProjectMember`、`ProjectReview`；`POST .../versions/{version}:validate` 与 `POST .../versions/{version}:submit-review`。本前置核查不改产品/API/ORM/Migration。|
|涉及权限|校验用户为项目经理或实施成员；送审必须为 `PROJECT_MANAGER`。候选 Reviewer 必须是当前 ACTIVE 客户经理/客户成员，服务端事务仍重验。测试需真实建立合成项目成员资格，不可仅靠 UI 隐藏或直接伪造业务 Review 结果。|
|验收标准|从当前干净提交构建不可发行 Windows 候选并清洁逐件校验；包内 Edge/HTTPS/PG18 从已验证的 Survey DRAFT 打开当前校验面板，得到匹配该版本的有效报告；由项目经理选择完整分页的当前客户评审人、显式确认并调用唯一原子送审命令；PostgreSQL 只有一个 Review/Round、评审人快照匹配、SurveyVersion=`IN_REVIEW`、单一成功 Audit/收据；送审回执只记 `IN_REVIEW`，不宣称 Reviewer 已批准。检查拒绝/回滚和临时资源清理。|
|风险|现存 A08 Edge 夹具以实施成员创建 DRAFT，不能直接复用其身份调用 ProjectManager-only 的送审命令；后续必须通过受控合成成员准备建立 PM 身份。Reviewer 只作合成候选，绝不表达客户事实。候选 `release_eligible=false`、`legal_clearance=false`；本 WBS 不关闭 Gate/Pilot。|

## 前置核查结论

只读核对确认：冻结 Validate/Submit Review API 与 Windows 显式组合已存在；A10/A11 前端实现已提交，分别有类型/构建和全量前端测试证据；A08 现有包内 Edge 验收止于 DRAFT 创建，没有驱动校验报告面板/客户评审选择/送审结果。A08 当前候选早于 A10/A11，不能重用其包 SHA 作为新 UI 验收证据。送审 Owner 明确要求 `PROJECT_MANAGER`，而 A08 浏览器 actor 是用于创建 DRAFT 的实施成员，因此 P02 需通过产品受权接口/既有项目流程准备单独的合成 PM，并确保该 PM 登录 Edge 后完成送审。

## 交付信息

- Changed：仅新增此 WBS 前置核查，明确 P02 的可执行范围及授权边界。
- Files：本记录、`STATUS.md`、`CHANGELOG.md`。
- Migration/API/依赖：无。
- Tests：只读对照 A08/A10/A11 验收记录、前端组件、Session Client 路由、冻结 API Owner 权限；未运行程序测试。
- Result：`SUR_07_A12_P01_PACKAGE_PRECHECK_PASS`。编码前置齐全，可继续 P02；未证明包内新 UI、真实客户评审或 Pilot。
- Next：`SUR-07-A12-P02`，干净提交重建当前 Windows 11 非发行候选，包内 Edge/HTTPS/PG18 实测 Validate→原子送审 `IN_REVIEW` 与评审人快照；正式信任、Pilot/Gate/Release 仍独立开放。
