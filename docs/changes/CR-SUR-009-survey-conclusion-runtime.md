# CR-SUR-009：SurveyConclusion 版本、来源与 Review 运行边界

日期：2026-10-07。状态：依据 `CR-EXEC-001` 持续授权批准实施。Gate 2 原冻结提交
`64cdf09` 保留；本 CR 细化 SRV-05 的运行映射，不修改冻结的五张表、五个 Operation、角色、
`/api/v1` 路径或“只有 Review 通过的 Conclusion 才能成为 Requirement 来源”的语义。

## 来源与差距

冻结 DM-05、SC-01/02/03 和 API-04 已确定：

- SRV-05 是 PROJECT 范围 V-PRJ；Root 为 `srv_conclusions`，owned tables 为
  `srv_department_conclusions`、`srv_module_conclusions`、`srv_conclusion_evidence_refs`、
  `srv_conclusion_open_issues`；
- Root 显式保存 `conclusion_series_id`、不可变版本身份、`version_no`、`supersedes_ref`、
  `survey_ref`、`round_refs`、`ai_task_refs`、状态和 Review subject；
- 结论只能引用 VALIDATED Response 或合格 PROJECT_RECORD；冲突、关键缺失或未关闭待办必须阻断，
  除非固定版本保存显式范围排除/受权风险接受，并由 Review 决定；
- API 固定为 LIST、CREATE、GET、VALIDATE、SUBMIT_REVIEW 五个 Operation。

当前 Migration head `20261006_0108` 尚无上述五表、Owner、Subject Owner、Router 或页面。冻结文档未固定
多态引用的物理列、Review policy code、无独立 identity Root 时的版本序列创建规则，也没有可生成
`APPROVED_EXCEPTION` 或风险接受的正式 Owner。若直接保存裸 UUID、动态 current/latest、客户端 PASS，
或把 AI 输出/模板当客户事实，将失去 Project、版本和授权证明；若虚构风险接受实体，则会绕过人工决定。

## 选择

### 1. 不可变版本与序列

- `survey_conclusion_id` 是单个不可变版本身份；`conclusion_series_id` 是稳定 Review subject 身份。
- CREATE 未给 `supersedes_ref` 时创建新 series 的 version 1；给出时只能从同项目、同 Survey、同 series
  的精确旧版本创建后继，服务器锁定 series 并分配连续 `version_no`。请求不得指定版本号或“latest”。
- 完整正文、引用集合和 `content_fingerprint` 创建后不可更新。状态只取
  `DRAFT / IN_REVIEW / APPROVED / RETURNED / SUPERSEDED`；RETURNED 修订必须新建版本。
- Review subject 固定为 `subject_type=SRV-05`、`subject_id=conclusion_series_id`、
  `subject_version_id=survey_conclusion_id`、`policy_code=SURVEY_CONCLUSION_ALL_V1`。

### 2. 五表物理映射

- `srv_conclusions` 保存 Project、series/version、Survey、规范化 `round_refs uuid[]`、
  `ai_task_refs uuid[]`、状态、内容指纹、Review 投影和创建元数据。数组排序、去重且非空；它们是固定
  身份快照，资格仍由 Owner 在创建、校验、送审和批准时重新证明。
- 部门/模块表保存有序结论项、稳定业务 key、标题、结论正文、结论分类与显式决定字段；正文不复制
  Evidence 原文。相同版本内 ordinal 与业务 key 唯一。
- Evidence 表以 `reference_role=SUPPORT/CONFLICT` 区分支持与冲突，保存固定 `evidence_id`、
  `evidence_version_id` 与创建时证明指纹；不得保存路径或大段原文。
- Open issue 表使用受控 `issue_owner_module + issue_object_type + issue_id + issue_version/state snapshot`。
  首版只开放已经有真实 Owner 的 `handover/HND-03`；不存在的 Survey 待办类型保持失败关闭，不以裸 UUID
  或备注代替。
- 显式范围排除/风险接受只能保存为类型化 `SourceDecisionRef`。当前没有 ApprovedException/风险接受
  Owner，因此首版可记录建议态但不得据此解除关键冲突或缺失；正式放行保持失败关闭。

### 3. 来源与跨模块边界

- Response 来源固定到同项目、所列 Round 下的当前链尾 Response，且 Assignment 必须是 VALIDATED；
  更正链旧节点、SUBMITTED/RETURNED Assignment、空答案均不合格。
- PROJECT_RECORD 来源只通过 Document/Evidence 公共 proof Port 固定 DocumentVersion、Locator 与内容指纹，
  不允许 Survey 直查 Document 私表。
- Evidence、Handover Action、AI Task、Review、Trace、Workflow 均通过公开 Owner Port；Survey 不直写或
  依赖其他模块私有 ORM。AI Task 只能作 provenance，不构成来源或批准事实。
- VALIDATE 只返回服务器权威 `ValidationReport`，不改变状态。送审与批准在调用方事务内重新证明所有
  来源、冲突、待办和权限；历史校验报告不能代替当前事实。

## 实施拆分

1. `SUR-04-A02`：五表 ORM 与 Migration `20261007_0109`，含 V-PRJ、类型化引用、不可变历史、
   up/down、空库/有数据升级和 drift 验证；Owner 未开放前关闭业务写入。
2. `SUR-04-A03`：实现 VALIDATED Response、PROJECT_RECORD、HND-03、AI Task 的最小 proof adapters；
   不新增客户事实或风险接受。
3. `SUR-04-A04`：实现 Conclusion create/list/get Owner、连续 series/version 与完整不可变快照。
4. `SUR-04-A05`：实现 source/conflict/completeness Validate Owner，关键缺口失败关闭。
5. `SUR-04-A06`：接 `SRV-05 + SURVEY_CONCLUSION_ALL_V1` Review Subject、原子送审和终态消费；
   APPROVED 时只取代同 series 旧批准版。
6. `SUR-05`：按冻结五个 Operation 接 HTTP、Windows 显式组合与前端 Evidence/open issue 定位；
   不在 SUR-04 提前扩大公开 API。
7. `SUR-06`：实现 `SURVEY_ACTUAL_SOURCES`、`SURVEY_CONCLUSION` 资格 Owner、Workflow 与完整模拟项目闭环。

## 风险、迁移与回滚

- 风险：跨 Owner 证明顺序可能产生锁竞争；固定锁序为 Conclusion series → Survey/Round/Assignment →
  Handover Action → Evidence/Document → AI Task → Review，并以并发测试验证。
- 风险：`uuid[]` 不能由普通 FK 逐项约束；数据库只保证规范形状，Application 每个关键命令逐项锁定和
  重证。若未来需要高基数反查，必须另走 CR 增加 owned bridge，不静默改表。
- 数据库降级：空历史可降至 0108；存在 Conclusion 或其 Review/Trace/Audit 依赖时拒绝物理降级，使用
  向前修复或恢复备份。应用回滚可撤 Owner/Router 注入，但保留全部历史。
- 本 CR 不证明客户确认、质量、性能、Windows Server 2025、Debian 13、Gate 3、UAT 或发行通过。

## 验证计划

- 静态：五表/五 Operation/Root manifest 对齐，运行实现初始为零，Migration head 为 0108。
- Schema：Windows 11 / PostgreSQL 18.6 空库直升、0108→0109、0109→0108→0109、有历史拒降、
  ORM/DB drift、约束和不可变负例。
- Owner：跨项目、错 Survey/Round、非链尾/非 VALIDATED Response、模板/AI 单独来源、Evidence 漂移、
  未关闭关键待办、并发版本号、Audit/Review 故障回滚。
- HTTP/UI：严格 DTO、cursor/ETag/幂等、安全头、Evidence Viewer 定位及 Windows 11 真实 Edge/PG 闭环。

