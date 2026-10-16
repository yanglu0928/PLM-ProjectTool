# AI-01-A05-P05-A03-P03 Provider 激活可选 HTTP

- 日期：2026-10-02；Phase 2；输入 Gate 2 API-03、CR-AI-002、内部 P01/P02。前置 PASS。
- Changed：新增 opt-in 无请求体激活 Router，Session/CSRF/Origin、强版本/Key；从不可变首次快照投影 `200 ACTIVE` 与 ETag。默认应用不挂载，无生产调用或真实外发。
- Files：AI API、应用 Router 注入、合同与隔离 ASGI/PG18 验证、增量 API 文档、决策/状态/版本记录。Migration：无，复用 0056。Architecture：无变化。
- Tests：合同 4/4；Windows 11 隔离 PG18/ASGI 合成 License 拒绝、真实管理员激活/USER Audit、暂停后原结果重放、新 Key 版本冲突 PASS；后端全量 2001 运行/3 跳过；开发 wheel SHA-256 `a2886c9f248456184f810c1254df55e9df73f27cfba3678046cc805025c9bfff`。
- Result：此 WBS PASS；A05/Gate 3 不因此关闭。Known Issues：Windows 正式写组合未挂载；正式目标账户信任、生产 Worker/外发、POC-03 质量、Server 2025/Debian、UAT 与可用发行包未验。
- Next：`AI-01-A05-P05-A03-P04` Windows 显式写模式 Provider 激活组合及隔离验证。
