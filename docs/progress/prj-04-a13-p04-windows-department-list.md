# PRJ-04-A13-P04：Windows 显式平台 Department 列表组合

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A13-P04。来源：冻结 API-01/02、PRJ-04-A13-P01～P03；决策 DEC-20260925-078。
- Changed：仅在 `--platform` 与 `--platform-write` 已有 Schema/License/游标密钥门禁通过后，要求独立 Department cursor Vault 来源并挂载 Department GET；默认登录模式继续 404。既有平台回归脚本显式提供合成部门密钥，不削弱启动门禁。
- Compatibility/Upgrade：无新 Schema/Migration/依赖或 Breaking API；目标库需维持当前 head，升级无需数据转换。
- Tests：Windows 11/Python 3.13 后端 430/430 PASS；PostgreSQL 18 临时库两种显式模式真实 Session 双页/跨项目/合成 License 拒绝及缺部门密钥启动失败关闭 PASS；8 个受影响 Project/Member/Department 验证脚本回归 PASS；开发 wheel PASS。临时库已删除，测试服务已停止。
- Result：Windows 合成平台组合 PASS；正式目标账户密钥、Server 2025/HTTPS、Gate 3 与可用程序包未完成。
- Known Issues：Windows Server 2025 异账户密钥恢复、Debian 13 按用户要求暂不验证；合成 License/密钥不等于正式发行材料。
- Next：PRJ-04-A14-P01 核查 Department 创建冻结幂等要求与现有内部命令，必要时补同事务持久收据。
