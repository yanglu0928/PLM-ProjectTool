# PRJ-04-A12-P03：Windows 显式平台成员状态组合

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A12-P03。来源：冻结 API-01/02、PRJ-04-A12-P01/P02；决策 DEC-20260925-074。
- Changed：仅在 `--platform` 与 `--platform-write` 已有 Schema/License/密钥门禁通过后，装配成员状态服务与三个 HTTP 路由。复用当前 Session、ProjectManager、Audit、同事务幂等；普通默认登录模式继续 404。
- Compatibility/Upgrade：冻结 `/api/v1` 不变；无新 Migration/依赖。目标库必须升级到含 `20260925_0017` 的 head，升级前备份数据库。
- Tests：Windows 11/Python 3.13 后端 421/421 PASS；PostgreSQL 18 临时库两种显式组合三状态真实 Session 首次/重放、仅三次审计、合成 License 拒绝及缺成员游标密钥启动失败关闭 PASS；开发 wheel PASS。临时库已删除，测试服务已停止。
- Result：Windows 合成平台组合 PASS；正式发行信任源、Server 2025/HTTPS、Gate 3 和可用程序包未完成。
- Known Issues：目标账户正式密钥、公钥/可信时间与 Secret 主密钥仍需发行仪式；Debian 13 按用户要求暂不验证。
- Next：核对冻结 WBS 中 PRJ-04 后续任务，继续不依赖正式信任源的独立工作。
