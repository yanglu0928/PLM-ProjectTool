# CR-EXEC-024：SOL-03-A06 nested fixture 兼容显式 NONE_REQUIRED Section

- 日期：2026-10-29
- 状态：已实施，待托管验收
- 来源与证据：GitHub hosted Windows 2025 run 40821508561 attempt 2 的全量后端测试、前端构建、PG18/pgvector、嵌入运行时、候选/父包组装与 PostgreSQL lifecycle 均通过。A17 已越过 Document、Section Review 和 nested RequirementVersion 授权，并输出 `P51_A17_SYNTHETIC_SECTION_OWNER_REVIEW_PASS`、`OUTLINE_QUALIFIED_REQUIREMENT_V2_PASS`。随后 `validation/sol-03-a06-p03-a05-p03-a05-p02-full-source-pg/verify.py:_approved_section_v2` 从当前项目选取 Approved Section 后，仅因 `old.spec_binding_state == "FIXED_REFS"` 断言失败而中止。
- 问题：SOL-03-A06 的既有验证夹具假设唯一 Approved Section 必须使用 `FIXED_REFS`。当前 A17 合成 Section 是普通标准功能，按现有 Section 合同可明确使用 `NONE_REQUIRED` 并提供不需要专用规格的理由；这是明确的合法状态。该断言把夹具历史形状误当成产品不变量。
- 方案比较：A. 在 A17 中额外伪造一个带固定规格引用的 Approved Section，以满足旧夹具；B. 修正 nested 验证夹具，仅接受合同允许且内部一致的 `FIXED_REFS` / `NONE_REQUIRED` 两类明确绑定状态，并对 `NONE_REQUIRED` 保持非空理由校验。选择 B，避免造与标准功能场景无关的规格数据，不改变产品权限或合同。
- 基线差异：仅修改 A27 所调用的 SOL-03-A06 disposable verification fixture 的前置状态断言；不改业务实现、API、Schema、ORM、License 或冻结基线。
- 影响与风险：测试夹具继续验证 Approved Section 与固定 Requirement 的 Outline/Plan 链路。兼容范围限定为有效的两种显式规格绑定状态；未声明状态、状态/理由不一致或其他未知枚举仍应失败。不得据此把任意 section 或未批准内容认定为正式事实。
- 回滚：恢复单独的 `FIXED_REFS` 断言即可；不迁移或改动业务数据。
- 实施：仅替换 SOL-03-A06 验证 fixture 的单一历史形状断言，允许 `FIXED_REFS` 或 `NONE_REQUIRED`；当为后者时仍断言 `spec_not_required_reason` 非空，当为前者时断言该理由为空。业务实现不变。
- 验证计划：hosted Windows 2025 完整工作流复跑。必须继续看到 Section Review、Requirement、Outline、PlanVersion Edge/HTTPS、PostgreSQL Version/Validation/Audit/Receipt/Review 且 Decision=0 的完整证据，同时完成进程退出、仅清理本轮临时资源和候选 Hash 完整性标记。任一缺失时 A27 不通过。
- 执行边界：只使用 GitHub hosted runner 与合成数据；不在用户本机/C盘运行项目代码，不外发客户数据或 Secret。
