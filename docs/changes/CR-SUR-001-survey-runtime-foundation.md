# CR-SUR-001：Survey 运行时基础与实际调研事实边界

日期：2026-10-06。状态：依据 `CR-EXEC-001` 持续授权批准分步实施。Gate 2 原冻结提交
`64cdf09` 保留；本 CR 不代表任何客户调研、客户确认、Survey Gate、Gate 3 或 UAT 已通过。

## 来源与当前差距

冻结 DM-05、SC-01/02/03 与 API-04 定义 SRV-01～SRV-05 五个 PROJECT Root、十七张
Root/owned table 和二十九个 `/api/v1` Operation。当前运行仓库没有 `survey` 模块、`srv_*`
表、Owner、Router、页面或生产组合；Audit、Trace 和 AI 中的 Survey 类型仅为允许列表，不能代替
业务 Owner、授权、正式 Review 或 Workflow 资格证明。

冻结基线只固定了 `srv_question_source_refs` 的逻辑用途，未固定 Handover Item、Capability Item、
TEMPLATE DocumentVersion 与人工来源在单表中的列和约束；也没有规定五个 Root 应在同一迁移还是
分批交付。若把动态 latest、目录路径、正文副本或无类型 UUID 写成来源，将失去版本、Scope、
ProjectId、授权和反向追溯。若一次迁移实现定义、轮次、答复和结论，又会跨越多个独立状态机与
事务边界，违反“一项 WBS 一个明确问题”。

## 选择

- 保持冻结的五个 Root、十七张表、二十九个 Operation、角色和 `/api/v1` 路径不变。
- `srv_question_source_refs` 使用受控 `source_kind` 和类型化引用；TEMPLATE 只能固定到明确的
  DocumentVersion 并用于问题结构，不能成为 Response、Answer、Conclusion 或 Gate 的客户事实。
- 实际面对面调研以 `PROJECT_RECORD` 的固定 DocumentVersion/Evidence 为来源；实施人员结构化录入时
  固定 `response_source=FACILITATED_RECORD`、记录人、原始 Evidence 和追加式更正链，不伪装成客户自填。
- AI 只能形成建议或 Draft。进入 SurveyVersion、Round 或 Conclusion 的业务内容仍需受权人员明确操作；
  Approved Review 之前不得成为正式 Requirement 来源或 Workflow PASS。
- 五个 Root 按定义版本、执行轮次、分派答复、结论版本分批物理化；跨模块只经公开 Owner Port，
  不允许 Survey 直写 Document、Evidence、Handover、Capability、Review、Trace、Workflow 或 AI 私有表。

## 实施拆分

1. `SUR-01-A02`：新增 SRV-01/SRV-02 六表定义基础与 Migration `20261006_0103`；只建立
   Survey identity、不可变 SurveyVersion、Question/Option/Source/TargetDepartment，Owner 未开放前关闭写入。
2. `SUR-01-A03`：实现 Survey identity、完整 Draft Version 创建与 Validate Owner；服务端计算内容指纹，
   对 Handover/Capability/TEMPLATE/人工来源执行类型和 Scope 证明，保留 Audit 与持久幂等。
3. `SUR-01-A04`：接统一 Review Subject/送审/终态消费；只有实际 APPROVED 版本更新正式指针。
4. `SUR-02`：独立物理化并实现 SRV-03 Round 与 `srv_round_source_records`，固定已批准 SurveyVersion、
   计划/开放/关闭/取消状态和正式现场记录。
5. `SUR-03`：独立物理化并实现 SRV-04 Assignment/Response/Answer/Evidence、更正链、提交/校验/退回；
   `CLOSED` Round 拒绝新答复，同 Round/部门/受访者使用冻结的 `NULLS NOT DISTINCT` 唯一语义。
6. `SUR-04`：独立物理化并实现 SRV-05 Conclusion、分部门/模块结论、Evidence/冲突/待办引用及 Review；
   只有 VALIDATED Response 或合格 PROJECT_RECORD 可成为结论来源。
7. `SUR-05`：按冻结 Operation 分批接只读/写 HTTP、Windows 显式组合、前端 Evidence 定位与输入提示。
8. `SUR-06`：接 `SURVEY_ACTUAL_SOURCES`、`SURVEY_CONCLUSION` 真实资格 Owner、Stage Transition 和
   PostgreSQL/浏览器闭环；不得以空集合、模板、AI 建议或客户端 PASS 放行。

## 迁移、回滚与验证

每个数据库增量同时提供 ORM、Alembic up/down、空库与有数据升级、drift、约束负例和历史拒降。
空历史可逐级降级；产生对应 Survey 历史后拒绝物理降级，改为向前修复或恢复备份。应用回滚可停止
Survey Router/Owner 注入，但不删除历史、Evidence、Review、Trace 或 Audit。

本 CR 只记录实现映射和顺序，不修改冻结业务语义；`SUR-01-A01` 仅完成静态核查。真实客户资料导入、
客户答复/确认、质量、性能、正式信任、Windows Server 2025、Gate 3、UAT 和发行需各自证据关闭。

## 实施记录

- 2026-10-06 / `SUR-01-A02`：完成六表定义基础与 Migration 0103。来源采用真实外键加受控类型，
  TEMPLATE 仅允许模板类别并继续不得作为客户事实；无冻结 API 或 Scope 变化。空历史可降级，存在
  Survey 历史时拒绝降级。Windows 11 / PostgreSQL 18.6、2783 项后端回归及 Wheel 内容检查通过。
