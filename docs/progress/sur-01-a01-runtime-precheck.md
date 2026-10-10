# SUR-01-A01：Survey 运行时与 Schema 前置核查

日期：2026-10-06
状态：`SUR_01_A01_RUNTIME_PRECHECK_PASS`
下一项：`SUR-01-A02` SRV-01/SRV-02 定义 Schema/ORM 基础

## 编码前检查

```text
当前Phase：Phase 2 Platform Core，Gate 3保持BLOCKED
当前WBS：SUR-01-A01
输入基线：DM-05、SC-01/02/03、API-01/04、模块边界、六阶段Workflow V1
前置任务：Handover正式版本/Action/资格、Workflow Checklist及HANDOVER→SURVEY闭环已完成
涉及模块：survey及project/document/evidence/handover/capability/review/trace/ai/audit/workflow边界
涉及实体：SRV-01 Survey、SRV-02 SurveyVersion、SRV-03 Round、SRV-04 Assignment、SRV-05 Conclusion
涉及API：API-04冻结29个Survey Operation；本项不挂载
涉及权限：PROJECT成员细分角色；DeploymentAdmin不自动获得项目正文
验收标准：核清Root/API/表/来源优先级/Owner/Review/Workflow差距并分解可验证任务
风险：模板或AI造客户事实、面对面记录冒充客户自填、动态latest、覆盖答复、空集合放行
```

## 核查结果

- 冻结范围为五个 Root、十七张 Root/owned table、二十九个 Operation；当前源码没有 Survey 模块、
  ORM、Migration、Owner、Router、前端或生产组合，运行实现为零。
- 当前 Migration head 为 `20261005_0102`。Audit 已允许 SRV-01～05，Trace 已允许 SRV-02/SRV-05，
  AI Task 已允许 survey target；这些只是白名单，不能证明资源存在、状态正式或当前用户有权访问。
- Workflow 已有 `SURVEY_ACTUAL_SOURCES` 与 `SURVEY_CONCLUSION` 两项定义，但尚无真实资格 Adapter；
  当前 Transition 只注册 `HANDOVER -> SURVEY`，不能继续推进到 REQUIREMENT。
- `srv_question_source_refs` 必须保存类型化固定来源，不能用路径、动态最新版、正文复制或无类型 UUID。
  TEMPLATE 可参与问题结构，不能独立形成 Answer、Conclusion 或 PASS Evidence。
- 面对面调研是首要真实路径：PROJECT_RECORD 固定版本/Evidence、`FACILITATED_RECORD`、录入人、时间和
  追加式 correction chain 必须保留。系统不要求客户维护业务表单，也不把表单空白项当缺失客户答复。
- Conclusion 只能消费 VALIDATED Response 或合格 PROJECT_RECORD；冲突/关键缺失须显式排除、风险 Review
  或继续待确认，AI Summary 与人工未确认建议不能转为正式 Requirement 来源。

## 决策与下一步

`CR-SUR-001` 保留冻结五 Root/十七表/二十九 Operation，仅补充物理来源映射和实施批次。下一项
`SUR-01-A02` 只建立 SRV-01/SRV-02 六表定义基础及 Migration `20261006_0103`，不导入用户资料、
不生成客户事实、不开放 HTTP。Round、Response、Conclusion、Review、UI 与 Workflow Owner 继续按独立
WBS 实现和验收。

本项为静态前置核查，没有代码、Schema、Migration、运行 API、依赖、网络或数据外发。已交叉检查
冻结模型、Schema/API/权限、Workflow 和当前源码；文档以 `git diff --check` 验收。
