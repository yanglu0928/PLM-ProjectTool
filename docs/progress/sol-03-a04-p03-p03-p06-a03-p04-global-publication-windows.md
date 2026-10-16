# SOL-03-A04-P03-P03-P06-A03-P04：GLOBAL 候选发布 Windows 写组合

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P06_A03_P04_GLOBAL_PUBLICATION_WINDOWS_PG_PASS`（Windows 11 隔离环境）；Gate 3 仍阻塞。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本项单一问题为 CR-SOL-018 管理发布命令的 Windows 显式写模式组装。前置为 Gate 2 冻结 API-04、DEC-1150、0158、已验内部 Owner 与可选 HTTP。
- 范围：仅 Solution Windows 工厂、生产应用写模式注入与验证资产；不增加 Schema、Migration、依赖、角色或旧 `/api/v1` 变更。
- 依赖：真实 Session/可信 Origin/License/Audit、Document/Download/Parse 与数据库 Unit of Work 均不可缺；缺失时必须拒绝启动。默认登录和只读模式不能安装此写路由。
- 验收：工厂缺依赖、只读模式关闭、写模式路由及 Win11 隔离 PG18.6 管理员发布/撤回/重放/权限负例与后端全量回归。

## 实施与证据

`create_windows_global_reference_publication_router` 复用当前受控 Document/Evidence/脱敏确认来源证明，装配独立发布 Owner。`production_login` 仅在 `include_secret_write` 分支构造并注入 Router；未显式写模式保留 404。缺关键端口或构造异常统一失败关闭，不改旧入口。

定向 Windows 工厂与启动失败关闭测试 10 通过、73 子例通过；Win11 隔离 PostgreSQL 18.6 工厂/ASGI/真实合成文件来源脚本退出 0，打印 `SOL_03_A04_P03_P03_P06_A03_P04_GLOBAL_PUBLICATION_WINDOWS_PG_PASS`，复验默认 404、普通用户拒绝、管理员发布/撤回及原键重放、过期事件号、最小投影、事件/Audit 与来源证明。后端全量 3483 通过、3 跳过、5359 子例通过。

边界：此证据验证 Windows 工厂及独立真实 ASGI/PG 组合，不代表正式生产应用在目标服务账户、真实 Vault/CA/发行配置下完成端到端启动；Windows Server 2025 当前链、20 并发、项目成员 GLOBAL 候选读面/浏览器和 Gate 3 尚未通过。Debian 13 实机按用户指令跳过。

兼容/升级/回滚：无需数据库升级、额外依赖或配置变更；显式写模式启用时要求原有受控来源端口完整。移除本 Router 的写模式注入即可关闭新入口，已写发布事件、收据和 Audit 历史保留，不作破坏性回滚。下一项建设项目上下文的最小 GLOBAL 候选读取，不复用管理员响应。

TraceLink：Gate 2 API-04 → CR-SOL-018 → DEC-1150/1151 → 0158/内部 Owner → 管理员 HTTP → Windows 写模式 → 项目候选只读。
