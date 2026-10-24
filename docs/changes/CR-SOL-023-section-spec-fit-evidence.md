# CR-SOL-023：Section Spec 送审适配依据

日期：2026-10-23。状态：`APPROVED_FOR_IMPLEMENTATION`（依据用户 CR-EXEC-001 持续授权，逐片验收前不得称 PASS）。原 Gate 2 冻结提交 `64cdf09` 与 CR-SOL-022 均保留，不追写原版本。

## 来源、冲突与目标

Gate 2 API-04 的 Section VALIDATE 六维报告要求 Spec 维 PASS 才可标记 ready_for_review；CR-SOL-022/0180 已能固定当前批准 Spec，但 DEC-1204 明确“候选资格不等于新正文适配”。现有数据没有作者对新正文与每条固定专项设计的适配依据。若把固定引用或已批准 Review 直接当 `spec=PASS`，会把来源资格误写成业务判断；若一直 UNAVAILABLE，则 Section/Outline Review、Plan 和 Pilot 链路无法前进。

目标是在不伪造客户确认、不使用 AI 建议替代正式事实的条件下，得到可审计的“具备送审依据”判定。`spec=PASS` 只表示送审前资料与现时资格齐备，不保证语义正确；客户确认仍由统一 Review 处理。

## 方案比较与选择

- A（选择）：在每条 Section 固定 SpecRef 中增加可选、由当前授权创建者提交的有界适配依据 `fit_rationale`。新引用可固定依据；旧引用保持 NULL，不能静默补填。验证时重查现时 Spec/Review/Section 来源/共有固定需求与正文 DocumentVersion 当前资格，并要求每条引用均有规范化依据；齐全才可给 Spec 维送审准备 `PASS`。`NONE_REQUIRED` 只有显式规范化理由且零引用才可表示“无需专项”的送审准备 PASS；`UNDECLARED` 永不 PASS。最终客户 Review 独立完成。
- B（暂不选）：完全自动对自然语言正文与四类类型化 Spec payload 作确定性语义覆盖。不同文档格式和业务语义无可靠通用等价规则，易把不确定推断写成正式事实，耗时且无法支撑近期 Pilot；后续可作为 AI 建议，不代替作者/客户确认。
- C（拒绝）：只要引用的 Spec 仍 APPROVED 即直接判 PASS。缺新正文适配证据，违背 DEC-1204 与六维报告的可信要求。

## 与冻结基线的差异及边界

- 对冻结的 SectionVersionInput 增加可选引用级 `fit_rationale`，原 `/api/v1` 路径、角色、License、请求必需字段和首次 201 形状不变。旧请求仍可创建 DRAFT，但缺适配依据的固定引用在 Spec 维保持未通过，需创建后继 SectionVersion 以提交依据；不可原地补写。
- Spec 维 `PASS` 的确切含义为“已完成现时资格重证且有作者逐项送审依据”，不是程序验证自然语言等价、AI 判定、客户签署、Spec 自身批准或 Section Review 已通过。UI/报告必须说明这一边界。`NONE_REQUIRED` 的操作者理由同样只用于送审准备，不能自动批准方案。
- 客户正文/依据只保存在项目受权的本地系统和数据库，不发送外部模型；Audit 使用有界状态码，不复制依据正文。ProjectId 隔离、Trace、来源固定版本和原幂等语义不变。

## 迁移、回滚和验证

1. 0181 在 `sol_section_spec_refs` 增 nullable 有界 `fit_rationale`，旧行 NULL、不回填、不动原 Section 内容指纹/201；ORM 与新迁移同时落地。现有 0180 子集合事务封印和复合 FK 继续生效。空库、有数据升级及空新增依据降级重升、约束负例、head drift 必测。存在任何非空新增依据时拒绝降回 0180，不删历史；回滚关闭新入口并前滚修复。
2. 另片扩展可选请求/DTO、请求与内容指纹、同事务写入和受权历史反读。旧无依据请求/首响/同 Key 重放保持；同 Key 改依据为冲突，错项目/格式拒绝。
3. 另片安装 Section VALIDATE 的 Spec 维现时证明；`UNDECLARED`/缺依据/已替代或失效 Spec/来源变化/正文失效/端口异常负例，`NONE_REQUIRED` 和具备逐项依据的 FIXED_REFS 正例；原 Key 回放首次观察，新 Key 重采样。真实 Windows 11/PG/HTTP、权限/License/Review 边界和全量回归必测。前端提示作者维护何种依据、定位固定 Spec/正文，并明确等待客户评审。

## 剩余风险

作者依据可能写错，因此它只是待客户 Review 的可审计声明；正式输出还须固定客户批准的 Section/Spec、Trace 与 Outline，并独立验证。旧固定引用版本缺依据继续不能送审。Gate 3、Pilot 安装、正式信任与三平台 Release 不因本 CR 预先通过。
