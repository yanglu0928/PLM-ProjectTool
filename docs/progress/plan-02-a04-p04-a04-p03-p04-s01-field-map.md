# PLAN-02-A04-P04-A04-P03-P04-S01：PlanVersion 快照字段映射

日期：2026-10-26。结果：`FIELD_MAP_DECIDED / READY_FOR_SCHEMA_SLICE`；无代码或数据变更。

|冻结语义|物理落点候选|约束/Owner规则|
|---|---|---|
|PlanVersion `calendar_ref`|`pln_plan_versions.calendar_ref` text|保存有界逻辑Calendar code，不存假 FK；写Owner需由受控 Calendar policy registry 解析，未识别则拒绝。|
|PlanVersion `exclusions`|`pln_version_exclusions` owned child rows|列固定为 `exclusion_id, plan_version_id, plan_id, project_id, ordinal, target_kind`、互斥的 Requirement/Outline/Section/StructuredSpec ID对、`reason, impact`；每种目标各用真实 `(version_id, source_id, project_id)` 复合FK，`target_kind` CHECK强制恰一目标；按ordinal去重。不得保存Evidence/Review原始UUID冒充批准。|
|WBS `category`|`pln_wbs_items.category_code` text|规范化大写标识；Owner必须匹配版本化类别白名单。具体业务允许集由Application registry持有，不扩充冻结API。|
|WBS `owner_ref`|`pln_wbs_items.owner_project_member_id` nullable UUID|复合FK `(project_member_id, project_id)`；创建时重新证明Member为ACTIVE，使用稳定成员身份而非裸user UUID。|
|WBS `support_role_refs`|`pln_wbs_support_roles` ordered owned rows|每条受控Project role code；有序、去重、不能为空值，角色集合由Owner白名单校验。|
|计划/实际日期、工期|`planned_start_date`, `planned_finish_date`, `actual_start_date`, `actual_finish_date` (date), `duration_minutes` integer|非负；成对日期形状和前后关系由CHECK；依据SC-02统一以分钟作持续时间。准确工作日换算必须依受控calendar_ref，不猜测。|
|`entry_conditions` / `acceptance_criteria`|`pln_wbs_conditions` ordered owned rows (`kind`, text)|严格有序、每项有界非空；kind限ENTRY/ACCEPTANCE；Send Review前由Plan Validator确认所需条件齐全。|
|WBS `risk` / `explicit_exclusion`|`pln_wbs_items.risk_summary`, `explicit_exclusion_reason` nullable text|分别为有界规范化短文本；不嵌套业务引用，不把AI风险建议自动转为客户接受事实。|
|WBS `output_refs`|暂不迁入Plan引用表|当前没有OutputArtifact表、ORM、Migration或Owner；非空引用由PlanVersion写Owner失败关闭，待OUT-02可证明的Owner后另起Schema变更。禁止裸UUID/FK虚构。|

## 验收边界

- 该映射是CR-PLAN-002内的首批字段设计，不增加API字段、不追写Gate 2冻结提交；新增revision追加在0185之后。
- `pln_version_exclusions` 目标类型固定为 `REQUIREMENT_VERSION` / `SOLUTION_OUTLINE_VERSION` / `SOLUTION_SECTION_VERSION` / `STRUCTURED_SPEC_VERSION`，并固定各自逻辑identity+version复合FK；不允许自由目标种类。
- S02 migration需明确 child table 具体固定目标种类、复合FK、不可变guard/down guard；空库、有Plan历史和新历史三类 PostgreSQL 18.6 验证，Migration drift为零。
- 新列均不默认业务承诺；旧PlanVersion（若有）为DRAFT前置身份历史，不可伪造分类/负责人/日期/验收。其历史形状使用nullable/空 child rows且不能送审，后续新版本由完整 Owner 建立。
- PlanVersion当前批准指针/Plan/WBS数据不可因Schema扩充改写；RLS不作主授权。
