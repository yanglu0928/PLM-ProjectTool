# PLT-02-A07-P05-A08：Windows Secret 写组合

- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P05-A08。输入：冻结 API-02、生产登录/只读平台组合、Windows 当前账户 Vault 主密钥适配、Secret 内部写服务与可选创建/轮换/停用 HTTP。决策 `DEC-20260925-052`。
- Changed：新增显式 `--platform-write` 启动模式，保持默认登录与 `--platform` 只读语义不变。写模式先验证 PostgreSQL Schema、包内 License 信任链、游标签名密钥及当前运行账户固定 `secret-master-v1` 32 字节 Vault 主密钥，再以共用 SecretWriteService 挂载三个 write-only Router。任何前置失败均拒绝启动、释放数据库连接，不从普通配置读取主密钥。
- Files：Windows 写组合、生产应用/启动入口、组合/密钥单测、PostgreSQL 端到端验证、决策/状态/版本记录。
- Migration：无；目标库需升级至包含通用幂等收据的 `0015`。API：只装配冻结 API-02 路径，无 Breaking Change。
- Tests：Windows 11/Python 3.13 后端 381/381 PASS；默认/只读模式无写路由、缺主密钥拒绝启动、信任源满足后显式挂载；PostgreSQL 18 临时库由生产组合经过现行 Session/真实写服务完成创建→轮换→停用及各一次 Audit PASS；开发 wheel 构建 PASS。临时库已删除，数据库服务停止。
- Result：Windows 显式写组合代码与隔离合成端到端 PASS；正式目标账户/发行公钥和主密钥并未供给，`PLT-02-A07` 整体、Gate 3、生产安全验收和最终可用程序包未通过。
- Known Issues：Windows Server 2025 目标账户/Vault 恢复与 HTTPS 代理、Debian 13 未验证；正式发行信任锚缺失时显式写模式按设计拒绝启动。真实 Secret 不得进入合成验证。
- Next：继续发行可信来源与目标账户安全验收；并行推进其他不受该前置阻塞的 Phase 2 WBS。
