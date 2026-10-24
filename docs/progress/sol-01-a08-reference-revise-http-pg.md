# SOL-01-A08：Reference Revise 可选 HTTP 与 Win11 PG

日期：2026-10-09。结果：`SOL_01_A08_REFERENCE_REVISE_HTTP_PG_PASS`；默认应用/Windows 生产组合仍不装载修订写路由。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-01-A08；输入冻结 API-04 `SOL_REFERENCE_REVISE`、CR-SOL-013、A07 内部 Owner/0150；前置满足。
- 模块/实体/API/权限：仅 Solution API 可选 PROJECT/GLOBAL POST 与 `create_app` 显式注入槽；受权角色/项目隔离沿用 A07，无 Schema/Migration/依赖/前端变化。
- 验收：真实 Session/可信 Origin/CSRF、强 `If-Match`、幂等键、有界严格 JSON；201 新版本/原结果重放、错误安全映射、默认 404、PROJECT/GLOBAL 真 PG；全量后端回归。
- 风险：后续根当前指针变化不能改变原 201；路由响应只投影不可变结果并用原版本号生成 ETag，不从当前根重建。公开路由需显式注入，避免默认打开写面。

## 实施与验证

新增 `reference_revise.py` 两个可选 POST 路由，路径与冻结 API-04 一致，使用既有安全读取器和 `parse_if_match`；请求仅允许来源版本 ID、来源分类及适用性，不接受客户端指定 scope/project/name/创建者。响应为新版本固定 ID、序号、前驱、DRAFT、首次时间和与本次修订相应的强 ETag；不回传指纹/脱敏证明正文，也不宣称该 ETag 一定是后来根当前 ETag。版本冲突映射 409，缺 If-Match 428，非法头/JSON 400，权限隐藏 404，License 403，来源不可用 503。默认 `create_app()` 两路均 404。

合同测试 3 项通过。Win11 一次性 PG18.6：PROJECT 真实 Session/文件/Document/Evidence/Owner 的第一次 201、重放、第二次修订、之后第一次重放、旧 ETag 新 Key 冲突、客户角色/Origin/弱 ETag 拒绝、结果/Audit 各两行通过；GLOBAL 真实 Session/脱敏确认绑定、首次重放、改变来源但旧确认无效及默认 404 通过。项目夹具首轮因测试幂等键不足 16 字符得 422，已修正后完整重跑退出 0；并非生产代码失败。后端全量 `3373 tests OK, skipped=3`。

## 升级/回滚与下一步

无新的迁移、依赖或冻结合同变更；移除可选 Router 注入即可停止公开写入口，不改已保存历史。TraceLink：Gate2 API-04 → CR-SOL-013 → A07/0150 → 本 A08 → A09 Windows 显式写组合 → UI/Eligibility。正式目标账户、公钥/Vault/HTTPS、20 并发、Server2025、Gate3/UAT/可用程序包未验；Debian13 实机按用户指令暂跳过。
