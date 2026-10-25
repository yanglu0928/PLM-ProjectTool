# SOL-01-A12-P03：PROJECT Reference Revise Win11 Edge/隔离 PG 验收

日期：2026-10-09。结果：`SOL_01_A12_P03_PROJECT_REVISE_EDGE_PG_PASS`；限合成用户/文件、开发机 Windows 11、临时 PostgreSQL 18.6 与真实 Edge，不等于正式目标账户或完整 UAT。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-01-A12-P03；输入 A12-P02 页面/路由、A11 客户端、A07～A09 真实 Owner/HTTP/Windows 组合，前置满足。
- 模块/实体/API/权限：仅验收脚本；PROJECT Reference 修订、受权 DocumentVersion、真实 Session/CSRF/Idempotency，PROJECT_MANAGER 可写、CUSTOMER_MANAGER 只读。无正式程序/Schema/Migration/API/依赖变化。
- 验收：真实浏览器选择固定文档版本；首次服务端 201 丢失后原 body/If-Match/Key 锁定、重新登录同键恢复；当前 GET 与历史回执分离；客户入口隐藏及直接 POST 拒绝；数据库单根第 2 版/单审计；临时 Edge profile、服务和 PG 清理。
- 风险：仅合成信任源与私有文件；不代表目标服务账户、正式发行信任/HTTPS、20 并发、Server2025、客户确认或真实 UAT。

## 实施与证据

新增一次性 `serve.py`/`run-edge-browser.mjs` 夹具，复用既有 PROJECT Reference 合成来源，增加真实 Scrypt 浏览器经理/客户账户和 Windows 写路由。Edge 从受权文档候选选择固定版本，逐项核查并 POST；DevTools 只丢弃第一次响应，服务端已返回 201。页面锁住新 Key，经整页重载与重新登录后显式同键重放，原请求 body、If-Match、Idempotency-Key 完全一致；回执显示第 2 版，重新 GET 当前根也为第 2 版。SQL 确认 `(version_no,lock_version)=(2,1)` 且仅一条 `SOL_REFERENCE_REVISED` 审计；客户只读详情不显示入口，直接 POST 为 404。

首次夹具运行因整页导航丢失前端内存身份而停在只读页；改为真实登录后同页返回。第二轮因等待“第 1 版”误命中当前版本文案，改为等待固定版本链接。最终整链退出 0，临时 Edge profile/HTTP server/PG 均由夹具清理。上述两次失败属于验收脚本时序，不记作产品 PASS；最终结果仅覆盖本夹具范围。

## 兼容/回滚/后续

仅增加验证夹具，可移除而不影响程序或历史；无 migration。TraceLink：API-04 → CR-SOL-013/015 → A07～A12-P02 → 本 P03 → A13 GLOBAL 整合 → A14 双 Scope 验收。PROJECT Evidence 可选 UI 的真实浏览器选择尚未跑（已有页面合同及服务端合成 PG 来源证明）；正式目标账户/20 并发/Server2025、Gate3/UAT/发行仍待；Debian13 实机依指令暂跳过。
