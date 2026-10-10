# SOL-01-A01：Solution 最小真实 Owner 前置核查

日期：2026-10-08。状态：`PRECHECK_PASS`；仅确认实施边界和依赖，不表示 Solution 业务 Owner、阶段资格或 Gate 3 已通过。

```text
Phase/WBS：Phase 2 依赖解环前置 / SOL-01-A01（依据 CR-SEQ-001 提前核查 Phase 8）
输入：V2.1 §6.10/Phase 8、冻结 DM-05、SC-01/02、API-04、六阶段定义、当前源码及迁移
前置：Prototype 已有隔离 PG/HTTP 合成资格，但正常生产路由关闭，20 并发性能未达标；
      不将该状态冒充正式 Solution 上游验收
模块：solution、requirement、prototype、document/evidence、review、trace、workflow、audit
实体：SOL-01～06；Approved RequirementVersion、必要时 Approved PrototypeVersion、
      DocumentVersion/Artifact、Review Subject、EvidenceBinding、TraceLink
API：冻结 SOL_REFERENCE_*、SOL_OUTLINE_*、SOL_SECTION_*、SOL_SPEC_*、SOL_COVERAGE_GET；
     当前尚未装配，不以临时端点替代
权限：项目 PM/ImplementationMember 可写草案；GLOBAL 参考仅 DeploymentAdmin 可写；
      Review 人工审批与 Workflow 资格均需独立受权证明
验收：固定版本、同项目来源、实际 Evidence 可定位、Section/Spec 独立审批、
      全部 Approved Requirement 覆盖或显式排除/延期、Section 快照与 IMPLEMENTS Trace 一致
风险：参考资料变客户承诺、目录批准冒充章节批准、AI 草案自动转正、
      缺失/漂移的正式需求和原型被静默忽略、空范围误判 PASS
```

## 静态核查

- 冻结架构已有 `solution` 模块边界与依赖白名单；冻结 SC-01/02 有 `sol_reference_*`、`sol_outline*`、`sol_section*`、`sol_structured_specs` 逻辑/物理映射和 M-SCP/M-PRJ/V-PRJ 类别；API-04 明确上述 `/api/v1` 资源与操作。无需为了最小 Owner 改动冻结产品 Scope 或原 Gate 2 提交。
- 当前 `apps/backend/src/plm_assistant/modules` 没有 `solution` 目录；迁移没有 `sol_*` 业务表，运行 OpenAPI 也未装配 Solution 操作。Trace/Audit 的 SOL 类型白名单与 Workflow 的两项 Solution Checklist 只是引用形状和配置，不是实体存在、正式 Owner 或资格 PASS 的证明。
- `SOLUTION_APPROVED_SET` 需要固定 Approved OutlineVersion 及其明确列出的 Approved SectionVersion/必要 StructuredSpecVersion；`SOLUTION_COVERAGE` 需要对每项当前 Approved RequirementVersion 覆盖或人工排除/延期、`IMPLEMENTS` Trace 与 Section 快照一致，必要 Prototype 亦须已批准。ReferenceSolution 只能是参考输入，不能单独满足任一 Checklist。
- 冻结模型明确 Outline 与 Section 分别逻辑身份/不可变版本，Spec 也是独立不可变版本；因此单一“方案文本”表、仅有目录、仅靠 AI 输出或假造 Review 都不能构成最小真实 Owner。

## 后续最小切片与验证顺序

1. `SOL-01-A02` 先按冻结 SC-01/02 核对并实现 Solution 身份/版本持久层的首个可独立验收切片；任何字段、约束或 API 与冻结合同不一致时先建专门 CR，含升降级、有数据升级与回滚。不得一次性把所有 Solution 功能标为 PASS。
2. 后续分别实现 ReferenceSolution 的 `REFERENCE_ONLY` 边界、Outline/Section/Spec 版本写读与类型校验、Evidence/Requirement/Prototype 固定输入证明、正式 Review 与 Trace；AI 只产草案，不能代客户确认。每项单独 WBS 验证权限、并发、跨项目/撤权/漂移负例。
3. 最后接入 Workflow 两项 Solution Checklist/资格预览/顺序推进，使用同事务真实 Owner 重证；Win11 隔离 PG/HTTP、完整模拟项目与性能另行验收。Server2025 实机资源满足后补证，Debian13 按用户指令暂跳过。

本项无程序、数据库、API、权限、配置、依赖或客户数据变更；兼容性和升级无动作，停止上述前置实施即可回退排序，但保留本追溯记录。核查方法为基线与源码/迁移静态对账；未运行新测试，不把静态结论称为运行验证。TraceLink：CR-SEQ-001 → DEC-20261008-1095 → SOL-01-A01 → DEC-20261008-1096 → SOL-01-A02。
