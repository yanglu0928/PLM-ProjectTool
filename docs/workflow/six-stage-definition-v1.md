# 六阶段 Workflow 配置 V1

配置版本：1；程序版本：0.1.0.dev0；日期：2026-09-26；变更：CR-WFL-001。
配置入口：`workflow.domain.catalog_v1.six_stage_definition(1)`。不可变定义只表达要检查什么，不表达已检查或已批准；尚无运行 Gate evaluator、Owner 查询接线或数据库实例。

## 核心清单及来源

全部十二项 required=true。以下是阶段完成/推进的必要检查，不能代替进入阶段时的上游输入验证。每项均需固定版本、受权 Evidence 与相应人工 Review/决定。

|顺序/阶段|清单 key|必要业务事实；来源为冻结 DM-05 对应章节及 API-04 对应业务合同|
|---|---|---|
|1 HANDOVER 项目交接|HANDOVER_BASELINE|固定项目资料和 Approved CapabilityBaselineVersion 可访问；关键缺失已登记；交接版本经正式确认/批准|
|1 HANDOVER|HANDOVER_ISSUES|阻断的 NEED_CONFIRM/冲突/风险已处理；相关 ActionItem 验证/关闭并有依据，或具备明确受权风险接受/例外；SUBMITTED 不能当关闭|
|2 SURVEY 需求调研|SURVEY_ACTUAL_SOURCES|实际调研答复已 VALIDATED 或正式现场记录已确认；模板仅参考；结论的来源/Evidence/Trace 可定位|
|2 SURVEY|SURVEY_CONCLUSION|固定 SurveyConclusion 已批准；缺失/冲突已处理或有明确排除/风险 Review；AI 建议不算确认|
|3 REQUIREMENT 需求分析|REQUIREMENT_FORMAL_VERSIONS|实施范围固定 RequirementVersion 已批准，正式来源成立、分类和能力评估已确认；PENDING_CONFIRMATION 不得转正|
|3 REQUIREMENT|REQUIREMENT_ACCEPTANCE|每项正式需求有可验证验收条件、来源 Evidence 和反向 Trace；范围缺口有明确人工决定而非静默删除|
|4 PROTOTYPE 原型设计|PROTOTYPE_SCOPE_DECISIONS|固定 Approved RequirementVersion 全部有原型范围决定；NOT_REQUIRED 必须有理由、影响、受影响需求与真实确认/Review|
|4 PROTOTYPE|PROTOTYPE_COVERAGE|需要原型的需求由 Approved PrototypeVersion 覆盖，制品可访问/完整；缺口明确处理。全范围 NOT_REQUIRED 仅凭已验证决定满足，不能跳过阶段|
|5 SOLUTION 方案输出及评审|SOLUTION_APPROVED_SET|固定 Outline、所含 Section 与必要 StructuredSpec 分别批准、类型化校验通过；Outline 通过不代表 Section 通过；输出引用固定集合及完整制品|
|5 SOLUTION|SOLUTION_COVERAGE|每项 Approved Requirement 被 Section/Spec 覆盖或有明确排除/延期；IMPLEMENTS Trace 与 Section 快照一致；必要原型批准|
|6 PLAN 计划制定|PLAN_APPROVED_BASELINE|固定 Approved Solution 集合作为输入；负责人、日期、依赖、验收经人工确认；固定 PlanVersion 已批准，参考计划不算承诺|
|6 PLAN|PLAN_WBS_VALIDATION|层级 1..6、parent+1、FS 无环、日期工期合法；负责人/进入条件/验收/交付 Evidence 规则完整；需求/方案覆盖或明确排除延期|

## 策略引用语义

- `EVIDENCE_FIXED_PROJECT_V1`：由 Evidence 与资源 Owner 的公开 Port 验证固定引用存在、当前授权、所属项目及允许的 GLOBAL 标准引用、来源定位与制品完整性；拒绝 current/latest、其他项目、模板冒充事实、不可访问/受限引用。不得复制正文到 Workflow。
- `REVIEW_HANDOVER_V1`：交接固定版本确认/批准及阻断项的受权验证/风险决定。
- `REVIEW_SURVEY_V1`：实际来源的验证/确认和结论固定版本 Approved Review。
- `REVIEW_REQUIREMENT_V1`：固定需求及能力判断/范围决定的实际人工确认与 Approved Review。
- `REVIEW_PROTOTYPE_V1`：原型范围决定、NOT_REQUIRED 决定的确认/Review，所需原型固定版本 Approved Review。
- `REVIEW_SOLUTION_V1`：Outline、所含 Section/Spec 各自固定版本 Approved Review 和排除/延期决定。
- `REVIEW_PLAN_V1`：计划固定版本 Approved Review 与负责人/日期/依赖/验收的人工确认。
- `GATE_<阶段 key>_V1`：该阶段全部 required 项 PASS 或有已批准且受权的 Waiver，且固定 Evidence/Review 依据成立；只能顺序推进，不能因前端提交 PASS 就放行。Waiver 独立存理由、影响、actor、依据，不把失败改写成 PASS，不豁免项目开发质量 Gate。

引用均为内部稳定标识，尚不是可执行策略注册表。未来运行层对未注册策略、缺 Owner/Review/Evidence、空范围未经明确决定等一律失败关闭；不能凭空推定空集合通过。不能由 AI 自动创建客户确认或风险接受。

## 版本与兼容

顺序来自 V2.1 §1.20；状态/顺序推进/豁免来自 DM-02 Workflow；十二项细化依据 DM-05 和 API-04，经 CR-WFL-001 新增配置基线。API2-R04 的配置设计在本任务补齐，但运行行为尚未验收。
原冻结提交 `64cdf09` 不变；定义 V1 发布后保留。以后修改发布新版本及 CR，并评估实例迁移，禁止自动将已有项目切到 latest。本次没有实例、种子、Schema、API 或权限变更。
Windows 11 仅代码/打包验收；Windows Server 2025 未运行；Debian 13 按用户要求暂不验证。开发 Gate 3、UAT 和可用程序包仍未通过。
