# PRJ-04-A14-P03：Windows 显式平台 Department 创建组合

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A14-P03。来源：冻结 API-01/02、PRJ-04-A14-P01/P02；决策 DEC-20260925-081。
- Changed：仅在 `--platform` 和 `--platform-write` 已有 Schema/License/游标信任源门禁通过后，装配部门创建服务及 POST；复用当前 Session、ProjectManager、Audit、同事务幂等。普通默认登录模式继续 404。
- Compatibility/Upgrade：冻结 `/api/v1` 不变；无新 Migration/依赖。目标库须升级至含 `20260925_0018` 的 head，升级前备份数据库。
- Tests：Windows 11/Python 3.13 后端 434/434 PASS；PostgreSQL 18 临时库两种显式组合真实 Session 首次/重放同为 201、仅一部门/Audit、非负责人/License 拒绝、缺部门游标密钥启动失败关闭 PASS；开发 wheel PASS。临时库已删除，测试服务已停止。
- Result：Windows 合成平台组合 PASS；正式发行信任源、Server 2025/HTTPS、Gate 3 和可用程序包未完成。
- Known Issues：目标账户正式密钥、公钥/可信时间与 Secret 主密钥仍需发行仪式；Debian 13 按用户要求暂不验证。第一次集成运行因验证脚本使用已关闭的数据库连接失败，已修复测试夹具并完整重跑通过。
- Next：PRJ-04-A15 Department PATCH HTTP 前置核查，按冻结强 If-Match 与现有内部命令推进。
