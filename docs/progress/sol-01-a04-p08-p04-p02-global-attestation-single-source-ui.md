# SOL-01-A04-P08-P04-P02：GLOBAL 单来源人工脱敏核查页与原操作回查

日期：2026-10-09；结果：`SINGLE_SOURCE_UI_AND_RECOVERY_CONTRACT_PASS`，限单条 GLOBAL Evidence 所属固定 DocumentVersion 的交互机制、原操作号回查及合成 PG/前端测试。真实 Edge 点击、真实管理员业务判断和多来源编排未验，不能记为正式人工脱敏确认。

编码前检查：Phase 2；WBS P08-P04-P02；输入冻结 API-04、CR-SOL-009 与 P03-P05 显式组合。前置严格前端客户端/后端确认撤回链已通过。涉及 Solution 回查 Owner/Repository/API/Windows 组合与前端 Evidence→核查页、Auth 私有 CSRF；新增可选 `/api/v1/global` 只读回查操作。权限为当前 DeploymentAdmin、Session/CSRF、License、可信 Origin。验收为固定来源入口、逐项打开/显式勾选、预览漂移清空、超时保留原操作号且不盲目重试、受权收据与当前状态回查；风险是点击不等于真正阅读，合成测试不构成真人核查。

实现单来源页：从全局 Evidence 已受权 Viewer 进入，不要求手填 UUID；管理员填写分类与可选行业，Preview 返回当前 Document 根/版本及 Evidence 身份后显示固定原文链接和页/章节等定位提示。文档/证据各自打开后才能勾选核查，再勾选本人声明方可 Confirm；写时指纹栅栏仍由后端重验。确认与撤回的网络不确定结果将原 Key 存在当前 SessionStorage 并锁定新写入。复核发现仅凭本地勾选解除锁不够，先登记 CR-SOL-010，再加服务端只读回查：按当前管理员/操作种类/原 Key 查 Receipt，未见完成返回 `UNCONFIRMED` 并继续锁定；已完成返回最小确认 ID、首次码和现时 `CONFIRMED|REVOKED|EXPIRED|SUPERSEDED`，展示后才允许本人清除本地提醒。不同管理员或错误操作种类不能看到完成结果。页面没有 AI 自动勾选/自动提交。

验证：后端定向含许可拒绝与跨管理员边界、Win11 隔离 PG18.6/真实 Session/ASGI 下回查未见、Confirm 完成/撤回后状态、Revoke 收据、跨管理员与错操作种类均通过；后端全量 `3337 passed, 3 skipped, 4930 subtests passed`。前端定向含预览/声明/漂移/超时/回查，全量 `105 files / 1622 tests`、typecheck/build 通过（现有主包 >500kB 警告）；前端已验证在 `UNCONFIRMED` 不解除锁、`COMPLETED` 才展示当前状态。当前仅合成 UI 测试，不冒充真实管理员业务判断。

兼容/升级：CR-SOL-010 为新增可选只读 API；无 Schema/依赖变化，已有 Confirm/Revoke 合同和收据不改，无数据升级。回滚停用回查路由与 UI 恢复入口，保留确认/Audit/收据，页面对不确定写入继续锁定。已知限制：单 Evidence/单 DocumentVersion，不支持一次核查多来源；浏览器真实操作和正式目标账户/License/Server 2025、20 并发/Gate 3/发行未验，Debian 13 依用户指令跳过。TraceLink：CR-SOL-009 → P03-P05 → P04-P01 → CR-SOL-010 → P04-P02 Owner/API/PG/UI → 后续 Edge/多来源。
