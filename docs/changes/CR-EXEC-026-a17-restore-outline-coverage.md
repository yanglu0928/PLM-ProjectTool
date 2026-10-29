# CR-EXEC-026：A17 Outline Review 前恢复合成 Requirement 覆盖 TraceLink

- 日期：2026-10-29
- 状态：已实施，待托管验收
- 来源与证据：GitHub hosted Windows 2025 run 40825554371 的基础构建/测试、候选包、PG lifecycle 与 Section/Requirement/Outline validation 均通过。CR-EXEC-025 追加 Outline Review API 提交时返回 BUSINESS_REVIEW_NOT_ELIGIBLE。SOL-03-A06 _outline_full 为覆盖负例，故意撤销 Requirement→Approved Section 的 IMPLEMENTS TraceLink 并确认 coverage=FAIL；之后 PlanVersion Owner 需要一个 coverage 完整的 Outline 才允许送审。
- 问题：Review 被业务 Gate 正确拒绝，因为 A17 没有在负向验证结束后恢复其 disposable synthetic coverage source。
- 方案比较：A. 放宽 Outline readiness 或直接改状态/TraceLink 表；B. 复用 plan-02 Owner 的 _restore_coverage_edge helper，通过 TraceLink Owner Service 在当前一次性 PG 中恢复正确 requirement/version 到 approved section/version 的 IMPLEMENTS link，再用现有 Review API 提交/审批。选择 B，维持真实 Gate/授权/审计和来源证明。
- 基线差异：只调整 A17 验证顺序；不改业务 API、Readiness、数据库、权限、License 或冻结基线。Link 和后续合成 Review/Decision 仅处于 disposable database，绝不代表真实客户确认。
- 影响与风险：需使用相同当前 project、Requirement 与 Approved Section 快照，并确保恢复步骤由授权 Manager Session 调用真实 TraceLink Owner。重复/已有 link 的行为需按 owner 幂等语义处理；若恢复或 Review 不满足条件，测试必须失败关闭。
- 实施：在 CR-EXEC-025 的 Owner connection 临时绑定区域内，先运行 _restore_coverage_edge(outline_context)，后运行 _approve_current_outline(outline_context, Path(fixture_db.data_root))；finally 恢复原 connection resolver。\n- 回滚：删除本次新增 helper 调用；仅一次性 PG 合成记录随 runner 清理，不影响正式数据。
- 验证计划：hosted Windows 2025 完整工作流；确认 coverage 负例仍返回 FAIL、TraceLink Owner 恢复后 Outline Review API 提交与合成批准通过且 Approved pointer 指向验证版本；随后 PlanVersion Edge/HTTPS、PG Version/WBS/Requirement/Validation/Audit/Receipt/Review/Round 且 decisions=0；完成子进程退出、D-drive临时目录清理及候选哈希检查。不得宣称真实客户审批或关闭 Gate。
- 执行边界：仅 GitHub hosted runner 与合成数据；不在用户本机/C盘运行项目代码，不外发客户数据或 Secret。
