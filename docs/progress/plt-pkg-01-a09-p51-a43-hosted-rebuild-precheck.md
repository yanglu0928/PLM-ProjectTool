# PLT-PKG-01-A09-P51-A43：Windows 受控试用包云端重建（编码前检查）

- 日期：2026-11-02
- 状态：检查完成；复用既有 CR-EXEC-005 和云端构建工作流，不在本 WBS 修改产品代码或本机执行程序。

当前 Phase：Phase 2 Platform Core；Gate 3 未通过。
当前 WBS：PLT-PKG-01-A09-P51-A43。
输入基线：CR-EXEC-002、CR-EXEC-005、CR-PKG-012；STATUS.md 的 Pilot/正式Release阻断；A40～A42暂存与签名验证工具。
前置条件：GitHub Actions cloud-sandbox-validation 可由 PR #61 触发；固定公开来源构建流程已存在；本轮遵循用户“本机不运行、优先云端/沙箱”的约束。

## 单一任务与验收范围

核实当前 PR 源码能否在托管 Windows runner 上从固定公开输入重建一份新的非发行父包，并在同一 run 完成构建、清洁暂存/解包、临时 PostgreSQL/pgvector、A17 合成业务链和 A34 隔离替换/恢复验收。该任务只证明可重复云端构建路径和包内受限行为，不验收 Windows 11 新运行、不安装/启动真实产品，也不关闭 Pilot、Gate 或 Release。

## 编码前检查结论

- 本任务不新增或修改程序代码；消费 PR 自动运行的既有 workflow 结果。流程/范围按已记录 CR-EXEC-005 执行，不产生新的架构、API、数据库或安全基线变化。
- 运行提交由 PR event 表示：PR 分支 head 为 4cbf2c140a1515029e5823bba1bd6935a5c33399；GitHub 为该次 pull_request 生成的合并提交为 9713443955f7698a687c620ab3647971f8700847，其父提交包含分支 head 与当时 base。Artifact 文件名采用此合并提交，因此不是来源错配。
- 所有运行在 GitHub hosted Windows Server 2025 runner 的非 C 盘临时区；本机未执行程序。Windows Server 2025 托管环境不能替代 Windows 11 新环境结论。
- Secret 检查范围为本次新增/更新的追踪文档；不得写入密钥、密码、客户正文或运行日志。

验收边界：12 项 workflow job 全部成功才可给本 WBS 标记 PASS_LIMITED；任何成功均不得提升 release_eligible、legal_clearance、formal_startup_ready 或 pilot_ready。

风险/恢复：workflow/artifact 保留期有限；失败时保留历史 artifact/CR并在新 run 修复，不强制覆盖。该任务不触及用户磁盘、现有安装、SCM 服务、正式数据库或设备重启。