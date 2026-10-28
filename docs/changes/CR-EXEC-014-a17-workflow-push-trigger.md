# CR-EXEC-014：为 A17 云端验收启用包分支推送触发

- 日期：2026-10-28
- 状态：实施中
- 来源：PLT-PKG-01-A09-P51-A27 的 A17 包内 Edge/HTTPS/PG 验证无法由 PR #56 当前检查实际启动。
- 冲突证据：PR #56 的 GitHub Actions run 40639658480 虽 8/8 jobs 成功，但作业列表不含 A17 candidate assembly 或 packaged PlanVersion job；main 上 workflow 的 push.branches 未包含 feature/p51-embedded-runtime-cache。PR 事件采用的基线工作流版本仅运行旧作业集合。
- 目标：在主线工作流 push 过滤中加入现有 A27 feature 分支名。合并该触发规则后，向该分支推送后续的 A27 记录提交可触发分支上的完整 A17 job 定义；不新增产品行为，不降低验收标准。
- 方案：单独修改 workflow 触发过滤并通过独立 PR 合并；随后向 A27 分支提交仅用于触发的有效进度/证据文档更新，运行并检查 A17 的组装、Edge、HTTPS、PG 和清理验收。
- 基线差异：增加一个既有 feature 分支的 push trigger；触发范围仅限仓库自有 feature/p51-embedded-runtime-cache。原冻结架构/API/数据模型和产品依赖不变。
- 风险：工作流可能重跑后端、前端及多个 Windows hosted job，增加 GitHub Actions 时间；PR 合并前后的 workflow 内容差异可能令首轮只运行旧 job 集合。必须核验 job 名称与 head SHA，禁止把不含 A17 的旧结果记为 A17 通过。
- 回滚：移除此分支过滤项并提交后续 workflow 修订；不改写历史运行或候选 artifact。
- 验证计划：此 PR 检查当前 workflow/YAML 与既有 cloud suite；合并后在 A27 feature 分支产生新 commit，确认 Actions run 使用期望 head SHA 且实际包含 A17 candidate assembly 和 packaged PlanVersion jobs。逐 job 查看结果和证据 artifact；失败则记录并修复。
- 安全：仅仓库代码和合成数据；不在用户本机运行，不上传 Secret、客户资料或本机文件。
