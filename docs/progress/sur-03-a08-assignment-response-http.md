# SUR-03-A08：Assignment/Response HTTP 与 Windows 组合

日期：2026-10-06。结论：`SUR_03_A08_ASSIGNMENT_RESPONSE_HTTP_PASS`。七个冻结 Assignment/Response Operation 已接入 Windows 生产组合；下一项进入 `SUR-03-A09` 前端工作台与 Windows 11 真实浏览器闭环。

## 实现

- 新增默认关闭、显式注入的 Assignment 只读与命令 Router，覆盖 LIST、CREATE、GET、RESPONSE_RECORD、SUBMIT、VALIDATE、RETURN；严格执行 Origin/Session/CSRF、幂等键、强 ETag、规范 UUID、有界 JSON 和安全错误投影。
- 冻结 GET 要求返回 `Assignment/response projection`，因此在既有动态可见性 Owner 后增加 Survey 自有 Response/Answer/Evidence 最小详情投影；不复制 Document 正文、本地路径或跨模块私有标识。
- Assignment 列表 cursor 从既有 Survey cursor Secret 以固定 HMAC 标签派生，绑定 Session、Project、Round、页长和完整复合位置，不增加部署 Secret。
- Windows 生产组合始终开放只读边界；写边界只有在 Document 下载/解析证明依赖完整时才挂载，否则保持 404。Response、SUBMIT、VALIDATE 的 Evidence 重证均复用既有 Owner，不能因接入层缺依赖降级。

## 偏差、兼容与回滚

- A03 的既有 GET Owner 只返回 Assignment Root，但冻结 API 明确要求 Response projection；本项增加同一可见性事务内的详情投影，而非修改冻结 URL 或创建第二套读取权限。该兼容补充登记为 `DEC-20261006-953`。
- 只读与写 Router 被拆分，避免生产 App 同时挂载读写组合时重复注册 GET；缺完整 Evidence 依赖只关闭五个写 Operation，不影响两个只读 Operation。
- 无 Schema/Migration、冻结 URL、角色、生产依赖、Secret 数量或数据外发变化。应用回滚可撤 Assignment Router 注入并恢复 404；既有 Assignment/Response/Audit/receipt 历史不可删除。

## 验证与已知问题

- 契约/组合/Owner 定向 7 项与 2 个子测试通过；后端全量 `2907 passed / 3 skipped`、`4203` 个子测试通过。
- Windows 11/PostgreSQL 18.6 隔离库完成两次 CREATE、八次 RESPONSE_RECORD、两次 SUBMIT、VALIDATE、RETURN、列表分页、cursor 错绑定拒绝、详情四条 Response 投影、14 条 Audit 和 14 条持久幂等回执，Alembic drift 为零。
- 开发 wheel `1086` 项，SHA-256 `6c9d208d5cbb505bc342d87794b88ddf3e2694ed8ee622616761f503f4333b4f`；它只证明可构建性，不是最终交付安装包。
- Assignment/Response 前端和真实浏览器仍待 A09；Conclusion、完整模拟项目、Gate 3/UAT、Windows Server 2025 发行复验和可使用程序包仍待。Debian 13 实机按用户指令跳过，但仍保持正式兼容目标。
