# SOL-03-A06-P03-A01：OutlineVersion 固定顺序与当前来源重证

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：固定顺序与现时来源内部验收通过；coverage 仍未实现。

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-03-A06-P03-A01`|
|输入基线|冻结 API-04 `SOL_OUTLINE_VERSION_VALIDATE`、DM-05 SOL-03；A06-P02 三维失败关闭合同；既有 OutlineVersion 创建时来源证明|
|前置任务|固定版本历史 DTO、当前 Section 身份、Approved RequirementVersion 和合格 ReferenceVersion 的受权 Application Port 均已实现；SectionVersion Review/Trace 覆盖 Owner 尚未就绪|
|涉及模块/实体|solution.application 的固定版本当前事实评估；不变更 OutlineVersion、SectionVersion 或其他模块表|
|涉及 API/权限|本片不挂载 HTTP；后续 Owner 负责 Session、项目权限、License、Audit；当前来源证明沿用同一事务的上游 Application Port|
|验收标准|固定章节顺序结构验证；按固定旧版本号/前驱重算当前来源摘要；Section/Requirement/Reference 当前资格漂移失败关闭；coverage 不伪造 PASS；定向/全量回归|
|风险|把创建时来源快照当现时证明；用“最新版本号”重算旧版本而误报；有缺口声明却在无 SectionVersion/Trace 覆盖证明时放行|

实施边界：本片只生成 `order` 与 `source` 事实。`coverage` 必须继续 `UNAVAILABLE`；只有后续独立覆盖 Owner 能核对批准 SectionVersion、精确 RequirementVersion 和 TraceLink 时才可赋予 PASS。重证复用现有来源 Proof Service，注入固定版本身份而非读取动态下一版本号；完整 `content_fingerprint` 不相等是来源漂移 FAIL，证明端口不可用是 UNAVAILABLE。历史报告不能用于送审现时资格。

无 Schema/Migration、冻结 API、角色、License、依赖或客户数据变化；旧版本只读历史保留。若实际复用中发现输入摘要定义冲突，先记录 CR 后调整，不静默降低比较强度。

## 实施与验收

- 新增 `OutlineVersionCurrentFactsService`。固定历史 DTO 必须与命令的 Project/Outline/Version 完全一致；顺序维核查非空、上限、规范 UUID 和唯一章节。来源维将固定历史引用与声明重构为原创建输入，使用历史版本号和前驱而非动态下一版本号，复用既有 Section/Requirement/Reference 当前证明并比较完整内容指纹。
- 证明不可用或项目/资格不符时 `source=UNAVAILABLE`；当前来源可证明但完整指纹已漂移时 `source=FAIL`。本片始终返回 `coverage=UNAVAILABLE`，不因来源两维通过而产生 `ready_for_review=true`。
- 定向 42 项通过；Windows 11 后端完整回归 `3885 passed, 3 skipped, 6023 subtests passed`，退出码 0；`git diff --check`通过。
- 一次性 Windows 11/PostgreSQL 18.6 验证脚本退出码 0：真实创建固定 DRAFT OutlineVersion，历史反读后在同一事务重证得到 `PASS/PASS/UNAVAILABLE`；把 PROJECT Reference 当前资格改为 RESTRICTED 后，同版本重证得到 `PASS/UNAVAILABLE/UNAVAILABLE`。脚本使用合成项目/账户/来源，退出时停用并清理临时 PG；不代表正式客户或服务账户信任。

剩余：真实 SectionVersion/Requirement 精确 Trace 覆盖 Owner、授权/Audit/幂等 VALIDATE、Review 送审终态、HTTP/Windows/前端与正式信任均未在本片完成。
