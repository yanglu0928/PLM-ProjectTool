# CR-EXEC-028：Windows RUNNER_TEMP 盘符检查改为大小写不敏感

- 日期：2026-10-29
- 状态：D-drive guard 已通过 hosted run 40831017596；随后 PlanVersion Create succeeded，UI timing 问题另见 CR-EXEC-029
- 来源与证据：GitHub hosted Windows 2025 run 40829027692 的基础构建、测试、候选包、PG lifecycle、Section/Requirement/Outline Review 前置链均通过，随后仍在 A17 Edge 泛化 guard 失败。CR-EXEC-027 allowlist 与上游 smoke 源码确认的实际 origin https://localhost:<port> 一致。逐项检查 Node guard 后，最后条件比较 RUNNER_TEMP 是否以小写盘符 d: 开头；GitHub Windows runner 的实际路径示例为 D:/a/_temp，JavaScript startsWith 区分大小写，因此有效 D 盘路径被拒绝。
- 问题：安全路径校验把 Windows 盘符大小写当作路径身份的一部分，产生误拒绝。
- 方案比较：A. 移除 D 盘限制；B. 仅对盘符大小写不敏感，继续要求 RUNNER_TEMP 位于 D 盘、Edge profile 临时目录是 RUNNER_TEMP 的严格子目录。选择 B。
- 基线差异：仅修正 A17 Node 验证 harness 的本地路径谓词；不改产品路径、安全、TLS 或运行配置。
- 影响与风险：路径仍必须在非 C 盘的 D: runner temp 内；所有现有 child/identity/origin 检查保留。若根路径不在 D 盘则仍失败关闭。
- 实施：在 RUNNER_TEMP 规范化后的路径上先调用 toLowerCase()，再与小写 d: 根前缀比较；所有其它严格子路径判断保留。\n- 回滚：恢复原来的 lowercase startsWith；不影响产品实现。
- 验证计划：hosted Windows 2025 完整 workflow；确认 D: 与 d: 表示都被正确归一化，非 D 路径仍拒绝；继续检查 Edge Profile 位于本轮 RUNNER_TEMP 子目录、Edge 进程退出、PlanVersion Edge/HTTPS/PG assertions、临时目录清理、候选哈希完整性。
- 执行边界：仅 GitHub hosted runner 和合成数据；不在用户本机/C盘运行项目代码，不外发客户资料或 Secret。
