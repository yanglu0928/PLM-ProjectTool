# SOL-05-A01：SolutionSectionVersion 正式开发前置核查

日期：2026-10-09。结论：`SECTION_VERSION_INPUT_PRECHECK_PASS / OWNER_NOT_READY`；仅允许先建无写入的输入合同，不把章节身份或目录 DRAFT 冒充正式章节版本。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase/WBS|Phase 2 Platform Core / SOL-05-A01|
|输入基线|Gate2 冻结 DM-05、SC-01/02、API-04；CR-SOL-003 的 0138 封闭 SectionVersion 基础；CR-SEQ-001 的 Solution 实施顺序|
|前置任务|SOL-04-A21 章节身份 Edge/PG 与 SOL-03 DRAFT 目录创建/历史读已验；0138 ORM/迁移已验，但 DML Guard 仍拒全部章节版本写入|
|涉及模块/实体|Solution 的 SectionVersion、固定 RequirementVersion/Evidence；DocumentVersion 只作受控正文引用，Artifact/StructuredSpec 尚无真实 Owner|
|涉及 API|冻结 `SOL_SECTION_VERSION_CREATE/GET/LIST/VALIDATE/SUBMIT_REVIEW`；本项不开放接口|
|涉及权限|创建限当前项目 PM/ImplementationMember；客户可读历史，正式 Review 须独立客户确认；本项不更改授权矩阵|
|验收标准|识别输入形状、当前来源证明与数据库闭锁边界，确定单一下一切片；不把结构校验、FK或 AI 建议当成来源/Review 事实|
|风险|无受控 Artifact Owner 时接受裸 Artifact UUID；DocumentVersion 仅靠 FK 而不验文件；跨项目 Evidence、旧 Requirement、未批准章节被误写成正式方案|

## 静态证据与顺序

`sol_section_versions` 和两类固定引用表由 0138 建立，正文要求 DocumentVersion 或 Artifact 二选一，标题/指纹/计数、同父前驱及 Review 配对已有 ORM/SQL 约束；`guard_solution_section_version_foundation()` 仍拒 DML。当前 Solution Application 无 SectionVersion CREATE/VALIDATE Owner，`SOL_OUTLINE_VERSION_VALIDATE` 也没有实现。目录 DRAFT 固定的是 Section *身份*，不能证明已批准 SectionVersion、内容或 Requirement 覆盖；因此不能直接完成目录 VALIDATE 的正式 coverage PASS。

先做 `SOL-05-A02-P01`：仅建立有界、可规范序列化的 SectionVersion DRAFT 输入合同和单元负例，固定项目/章节、受控正文引用二选一、Requirement 根/版本、Evidence ID、假设/排除声明和请求指纹；结构层不访问数据库，不表示 Document/Evidence 现时资格。Artifact 分支在后续 Owner 具备真实 OutputArtifact 证明前保持不开放。再分别建设项目授权、Section/Document/Requirement/Evidence 同事务证明、不可变首次结果与写 Guard、HTTP、Windows、UI/Edge、VALIDATE/Review/Trace。任何数据库闭锁修改须先补 CR-SOL-003 的迁移/历史回滚计划并独立验证，不能在输入合同中顺手解锁。

本前置仅静态核查，未运行新测试、无程序/API/Schema/数据变化；撤销本次排序可回滚记录，冻结历史保留。Server2025/正式信任、20并发、AI质量、Gate3/发行仍未通过。TraceLink：Gate2 DM-05/API-04 → CR-SOL-003/0138 → SOL-04/SOL-03 → 本项 → SOL-05-A02-P01 → SectionVersion Owner → Outline VALIDATE/Review → Gate3。
