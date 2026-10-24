# SOL-06-A13-P01：结构化专项类型化验证前置核查

日期/版本：2026-10-16 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_VALIDATE_PRECHECK_PASS`；只完成边界设计，不表示 VALIDATE 已实现或专项可送审。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A13-P01`|
|输入基线|Gate 2 冻结 API-04 `SOL_SPEC_VALIDATE`，DM-05 StructuredSolutionSpec 四类约束，0161～0164 不可变完整快照，A06 payload 校验，A08 当前来源证明，A09～A12 创建/读取/列表/修订纵向链|
|前置任务|Gate 2、SOL-06 完整 DRAFT、Windows 11 创建/读取/修订闭环均有证据；可进入只读验证设计|
|涉及模块/实体|Solution / StructuredSolutionSpec；只读依赖 Requirement、Section、Evidence、Trace、OutputArtifact，写侧仅未来 Receipt/Audit|
|涉及 API / 权限|冻结 POST `/api/v1/projects/{project_id}/structured-solution-specs/{spec_id}:validate`；ProjectManager、ImplementationMember；S/L/C/I/A|
|验收标准|明确报告事实、类型检查、当前版本/来源重证、幂等/Audit、状态与 Review 分界；缺真实 Owner 必须显式 UNAVAILABLE|
|风险|把存储时结构校验误当真实业务验证；复用创建时快照冒充现时来源；历史版本或 DRAFT 被误报可送审；缺 Trace/Artifact Owner 被静默跳过|

## 现状证据

- 冻结 API 只规定“200 type-specific validation report”，未规定正文、报告字段和重放语义。沿用 SectionVersion 先例，成功 200 只能表示一次验证观察已审计，不代表 `valid=true`、批准或客户确认。
- `validate_structured_spec_payload` 能可靠重算四类结构与 payload fingerprint；A08 `StructuredSpecSourceProofService` 能证明完整 DRAFT 的当前 Requirement/Section/Evidence/Document 来源，但它是创建用的 fail-fast 合同，不能直接生成逐维 FAIL/UNAVAILABLE 报告，也不能复用历史创建证明代替新观察。
- 当前 Trace `IMPLEMENTS` Repository/Owner 只接受目标 `SOL-05` SectionVersion；Trace shape 虽允许 `SOL-06`，尚无 StructuredSpec 精确覆盖 Owner。OutputArtifact 也无正式当前事实 Owner；创建/修订因此仍拒绝非空 Artifact refs。两者不得默认 PASS。
- 0161～0164 全历史不可变；VALIDATE 不得修改 Spec 状态、Review 引用、当前指针或固定正文。`SOL_SPEC_SUBMIT_REVIEW` 是后续独立命令。

## 选定边界

1. 请求无 JSON 正文，路径绑定一个固定 SpecVersion，必须带当前 Session、CSRF、License、项目写角色和 Idempotency-Key。允许读取任一同项目固定版本以形成审计报告；只有系列最新的 DRAFT 才可能 `ready_for_review=true`。
2. 报告绑定 `audit_event_id`、首次 `observation_trace_id`、项目/版本/系列/类型、版本号/状态、content/payload fingerprint、四类引用计数、`observed_at`。共同 `facts` 固定为 `integrity`、`payload`、`requirements`、`sections`、`evidence`、`artifacts`、`trace`、`current_version`，值仅 `PASS/FAIL/UNAVAILABLE`，不可省略。
3. `type_checks` 按类型返回固定有序检查：流程至少覆盖图结构、角色与输入输出可追溯；接口覆盖边界/映射、责任与运行控制、认证控制；迁移覆盖范围/映射、试迁移、对账、回滚与验收证明；权限覆盖矩阵/default-deny、范围和职责冲突审查。现有纯结构校验只能令结构项 PASS；真实职责、端点、试迁移、恢复或冲突审查没有 Owner 时必须 UNAVAILABLE。
4. `valid` 仅表示不可变完整性、payload 结构及当前 Requirement/Section/Evidence 来源均 PASS；它不是可送审结论。`ready_for_review` 还要求版本为系列最新 DRAFT、全部必需 type checks、Artifact（无引用可 PASS，有引用须真实 Owner）和 Trace 精确覆盖均 PASS。任一缺项都输出确定的 `issue_codes`，不将未知折算为 FAIL 或 PASS。
5. 首次成功观察使用独立 `SOL_STRUCTURED_SPEC_VALIDATE` 策略、`V1_SOL_STRUCTURED_SPEC_VALIDATE` 持久收据和 `SOL_STRUCTURED_SPEC_VALIDATED` Audit，在同一 UOW 保存完整首次报告。Audit `SUCCESS` 表示命令完成，不表示业务通过。相同主体/项目/操作/Key 在重新鉴权后返回首次报告、观察 Trace 和时间，不重新采样；新 Key 才重证现时事实。
6. 存储结构损坏、指纹矛盾、报告/收据/Audit 绑定不一致属于系统不可信，失败关闭而非伪造业务 FAIL。正常的来源撤回、版本陈旧或 Owner 缺失应形成已审计的 FAIL/UNAVAILABLE 报告。VALIDATE 不创建 Review、不批准版本、不改历史。

## 兼容、回滚与后续

本项无产品代码、Migration、公开 API 行为、依赖或数据变化，不需要升级/回滚。上述字段是对冻结结果的向后兼容细化；P02 先形成纯应用报告合同与确定性派生规则，若实施发现必须增加持久表、修改冻结路径/角色或放宽 0164 闭锁，则先登记 Change Request，不静默变更。正式信任、Server 2025/Debian 13、性能、Gate 3、Pilot 与发行状态不变。

Next：`SOL-06-A13-P02` 实现并单元验证类型化报告值对象、八维事实/issue/`valid`/`ready_for_review` 派生和首次报告序列化合同；不接数据库、HTTP 或 Review。
