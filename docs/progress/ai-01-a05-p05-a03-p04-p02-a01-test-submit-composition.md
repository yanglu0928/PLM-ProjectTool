# AI-01-A05-P05-A03-P04-P02-A01 Windows Test 提交工厂

- 日期：2026-10-02；Phase 2；输入 CR-AI-002、P04-P01 受控策略来源、已有 Test 提交/202 HTTP/Job 队列。前置 PASS。
- Changed：新增 Windows 组合工厂，严格使用 Bootstrap 策略快照、真实 Session/License/Secret 证明与 PostgreSQL Job/Outbox/Audit/收据组件构建 Test Router；缺策略或依赖固定失败。未在 `production_login` 挂载，默认/当前 Windows 平台仍 404。
- Files：组合工厂、隔离 ASGI/PG18 验证、CR/决策/状态/版本记录。Migration：无，复用 0055/0056。API：冻结 202 JobRef 不变。Architecture：无变更，不运行 Worker 或网络探针。
- Tests：Win11 隔离 PG18/ASGI 默认404、缺策略失败、License403、202 Job/Outbox/Audit与同 Key 重放 PASS；后端全量2006运行/3跳过；开发 wheel SHA-256 `6414171596dd60e3c6b4fb2f112b95141da7209c2fdc029f19585579c4419f0e`。
- Result：本子项 PASS；P02/P04/Gate 3 未关闭。Known Issues：Windows Worker 工厂/进程生命周期、两侧策略同源验证及正式路由挂载未完成；目标账户信任/出站、质量、Server 2025/Debian/UAT/可用包待验。
- Next：`AI-01-A05-P05-A03-P04-P02-A02` Windows 同源单次 Worker 组合与安全运行边界。
