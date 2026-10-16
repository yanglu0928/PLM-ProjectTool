# PLT-PKG-01-A09-P47-A01：固定候选与当前源码新鲜度核查

日期：2026-10-02；结论：`STALE_NON_RELEASE_CANDIDATE / CR-PKG-008_RECORDED`。

输入为本地固定 P45 ZIP、当前已提交分支 `feature/license-runtime-guard` 的 `25106908`、当前前端构建与后端源码。核验 ZIP SHA-256 与 P45 一致；只读列举 manifest、前端 assets、Evidence 包、Migration 目录。P45 ZIP 中前端 JS `index-1aZZs5xp.js`，当前构建 `index-BwItlzAE.js`；ZIP 中缺资格操作回查 Router/Service 与 `0052` Migration。未解包、未修改 ZIP、未触碰正式安装根、数据库或 Vault，也未处理客户正文。

此证据足以否定“旧候选代表当前应用版本”，不足以证明新候选已可构建或任何 Release Gate 通过。差异与所选受控派生方案见 [CR-PKG-008](../changes/CR-PKG-008-current-app-delta-candidate.md)。下一项先实现逐件替换/来源哈希的非发行派生构建器与测试；正式发行仍由完整门禁约束。
