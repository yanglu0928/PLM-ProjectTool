# REQ-01-A05-A01：Requirement 固定来源证明前置核查

日期：2026-10-07。结论：`REQ_01_A05_A01_SOURCE_PROOF_PRECHECK_PASS`。下一项：
`REQ-01-A05-A02` SurveyConclusion 与 Handover 固定来源证明。

## 权威来源矩阵

|输入类型|权威身份|当前资格与锁定条件|边界|
|---|---|---|---|
|`APPROVED_SURVEY_CONCLUSION`|`survey_conclusion_id`|同项目 Conclusion 为 `APPROVED`，并与 `SRV-05 / SURVEY_CONCLUSION_ALL_V1` 的 APPROVED Review 与 Round 精确一致|不接受 DRAFT、未批准结论、动态 latest 或仅凭 Review 元数据|
|`CONFIRMED_HANDOVER`|`handover_analysis_id + handover_analysis_version_id`|同项目 ACTIVE Analysis 的 `current_approved_version_ref` 精确指向 APPROVED Version，并与 `HND-02 / HANDOVER_ALL_V1` 的 APPROVED Review 与 Round 一致|`source_object_id` 保存 Analysis，`source_version_ref` 固定 Version；不把单个 Item 状态冒充整份 Handover|
|`HUMAN_DECISION`|`RequirementStateDecision.decision_id`|不可变 DEFER/REJECT Decision、真实用户、同项目 Requirement、至少一条由 A03 Owner 固定的 Evidence 引用与首成功结果|现有正式载体只覆盖 DEFER/REJECT；尚不存在的范围排除、风险接受或通用例外 Owner 保持不可用|
|`PROJECT_EVIDENCE`|`evidence_id`|同项目 `PROJECT / ELIGIBLE` Evidence，在调用方事务内共享锁读取固定 Document/Version、指纹与 lock version|不接受 GLOBAL、CANDIDATE、INELIGIBLE、REVOKED 或其他项目 Evidence|
|Capability Assessment|`baseline_version_id + capability_item_id`|ACTIVE GLOBAL Baseline 的当前 APPROVED Version及 AVAILABLE Item|不接受动态 latest、旧 Version、非 AVAILABLE Item；PROJECT Evidence 支撑由 A04 提交闭包另行固定|

## 实施拆分与约束

- A02 实现 Survey/Handover 所属模块只读 proof adapters，并连同统一 Review 终态一起重证。
- A03 实现 Evidence/Capability 所属模块只读 proof adapters；不复制正文、路径、locator 或 Secret。
- A04 实现 Requirement-owned 人工决定 proof，并以真实 PostgreSQL 验证五类 proof 的同项目、当前状态、
  共享锁、撤销/漂移拒绝和零写；然后 A05 收口。
- 所有 adapter 仅使用调用方已经打开的事务，不自行 commit，不创建业务事实，不绕过 A06 Version Create
  的项目授权、License、幂等、Audit 与完整快照校验。

本项没有 Schema、Migration、公开 API、依赖、Secret、客户数据或外发变化；不声称 A05、Version Create、
Review、Workflow、Gate 3、UAT 或发行已通过。
