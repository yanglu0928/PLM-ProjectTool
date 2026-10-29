# CR-EXEC-025：A17 PlanVersion 来源补齐显式 Outline Review

- 日期：2026-10-29
- 状态：已实施，待托管验收
- 来源与证据：GitHub hosted Windows 2025 run 40823849539 的全量后端测试、前端构建、PG18/pgvector、嵌入运行时、Windows 候选/父包组装及 PG lifecycle 均通过；A17 已输出 SOL_03_A06_P03_A05_P03_A05_P02_FULL_SOURCE_PG_PASS。随后 validation/plt-pkg-01-a09-p51-a17-planversion-packaged/verify.py 在 _outline_full 后检查 plm.sol_outlines.current_approved_version_ref，失败并报告 synthetic Approved Outline source fixture unavailable。日志显示 _outline_full 只创建/Validate Outline 并验证覆盖正反例，不执行 Review；下游 PlanVersion fixture 要求一个真正已批准 Outline。
- 问题：A17 将“Outline 验证通过”误当作已有“Approved Outline 来源”。当前一次性合成库中无已批准 Outline，因此正确的来源证明拒绝继续。
- 方案比较：A. 删除/放宽 approved-pointer 断言或直接写数据库状态；B. 复用既有验证 Owner 的 Review API helper，在当前 disposable PG 中为刚创建且验证通过的 Outline 建立合成 Review，通过实际提交/决策路由走完批准，再核对 current_approved_version_ref 指向同一个版本。选择 B，不跳过业务状态机、不直接改批准指针。
- 基线差异：只补充 A17 合成验证顺序；调用现有 plan-02-a04-p03-owner-transaction-pg _approve_current_outline Owner helper，将使用一次性合成客户成员 Session 和 Review API。此自动化决定仅为测试 fixture，不构成真实客户/用户确认；后续 PlanVersion Edge 的评审仍需保持 IN_REVIEW 且 decisions=0。不改产品 API、权限、Schema、License 或业务代码。
- 影响与风险：验证将真实通过 Outline Review/Terminal owner 的已批准来源约束；一旦 Review API/审批状态未完成立即失败。合成 reviewer 的 Session/Review/Decision 只存在于本轮 disposable database，并与正式事实明确隔离。Review fixture 的文档目录必须来自当前 D-drive hosted run temp，确保不产生 C 盘写入。
- 实施：A17 在 _outline_full 完成后构造同一 disposable PG 的 outline_context，临时将 Owner fixture 的连接解析器指向该数据库，再调用既有 _approve_current_outline helper；该 helper 通过实际 Review HTTP 完成提交和合成批准，并核对 Approved pointer 指向当前 version。连接覆盖在 finally 恢复；数据目录取自 fixture_db.data_root。\n- 回滚：移除本次 helper 调用；保留旧 Outline 创建/Validate 与 approved-pointer 检查。仅临时数据库数据随本次 runner lifecycle 清理。
- 验证计划：托管 Windows 2025 完整工作流；确认 Section 与 Requirement 来源、Outline Validate、Review API submit/approve 与固定版本指针、PlanVersion Edge/HTTPS、PG Version/WBS/Requirement/Validation/Audit/Receipt/Review/Round 且 decisions=0；核验所有子进程退出、D-drive 临时目录清理和候选哈希完整性。不得因本合成批准关闭 Gate 或宣称客户确认。
- 执行边界：仅 GitHub hosted runner 和合成数据；不在用户本机/C盘运行项目代码，不外发客户资料或 Secret。
