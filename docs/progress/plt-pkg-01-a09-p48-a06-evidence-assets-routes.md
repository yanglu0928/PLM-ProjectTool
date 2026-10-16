# PLT-PKG-01-A09-P48-A06：当前候选 Evidence 前后端资产/路由一致性

日期：2026-10-02；Phase 2；结果：`CURRENT_APP_EVIDENCE_ASSET_ROUTE_CONTRACT_PASS / REAL_BROWSER_OPEN`。

编码前检查：当前 ZIP SHA 固定、P48-A05 包内 Evidence 合成后端链通过，前端源码及 dist 在同一已提交来源上。任务只读核包内前端资产与后端源码，不更改产品实体、API、权限或Migration；验收是重新构建资产逐件等于包内哈希、编译 JS 有项目/GLOBAL Evidence 入口和资格/回查标记、包内四处后端路由源码与当前源码同字节。风险是字符串存在不等于浏览器按钮可操作或角色可用，因此结果仅为合同一致性。

实际 `pnpm --dir apps/frontend test`：51文件/1,065项通过；`pnpm --dir apps/frontend build` 的 typecheck 和 Vite 构建通过，输出 `index-BwItlzAE.js`/`index-LTvnm9Te.css`。新只读工具 `tools/audit_current_app_evidence_asset_routes.py` 先核 ZIP SHA `eb2494be5de85b64a7ac64ce02112ed52454d0423d2a7e8406f120a126e14ed7`，再核 index/JS/CSS 三文件的重建/ZIP/manifest SHA 相同；编译 JS 中项目和 GLOBAL 路由、资格提交/原操作号回查及各自 pending 存储标记共6项存在；Evidence set/lookup、生产平台组合和通用应用路由四份后端源码与 ZIP 相同且具预期挂载语句。真实命令退出0，合成资产篡改拒绝单元1/1。

本项不是浏览器交互、端到端 HTTP 部署或真实角色/License 验收。此前 computer-use 初始化失败，尚未点击页面或验证断线/刷新后持久状态；Server2025/Debian、正式信任、法律、质量、UAT/Gate 仍开放。兼容性：仅审计工具；Migration/API：无变化；回滚：弃用审计工具。`real_browser_verified=false`、`release_eligible=false`。
