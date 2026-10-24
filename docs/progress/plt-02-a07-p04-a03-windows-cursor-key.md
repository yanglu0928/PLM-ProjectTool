# PLT-02-A07-P04-A03：Windows 游标签名密钥来源

- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P04-A03。输入：冻结 API-01 游标完整性要求、P04-A02 HMAC 游标、P02 Windows 当前账户 Vault 与独立备份恢复。上述前置满足本项 Windows 来源实现。
- Changed：新增固定独立引用 `secret-list-cursor-v1` 的 Windows 组合入口；仅从当前运行账户受保护 Vault 解析 32 字节密钥，缺失/错误/异常拒绝装配。沿用本机交互式供给、离线加密备份和空目标恢复，不打印、不自动生成生产密钥。
- Files：Windows 组合入口、单元/本机 Vault 丢失恢复测试、决策/版本/状态文档。
- Migration/API：无 Schema、Migration 或 API 合同变更；默认应用仍不挂载 Secret 管理接口。
- Tests：Windows 11/Python 3.13 后端 357/357 PASS；独立引用与缺钥拒绝、UUID 隔离的真实 Windows Vault 凭据丢失和加密备份恢复后旧游标验证 PASS；开发 wheel PASS。测试凭据在 finally 中删除。
- Result：Windows 来源和合成恢复测试 PASS；正式目标服务账户未供给/备份，不能标生产装配 PASS。
- Known Issues：Windows Server 2025 异账户恢复、目标账户真实供给、正式 License 公钥/可信时间密钥及 Debian 13 仍未验收；生产只读路由装配仍缺前置。
- Next：PLT-02-A07-P04-A04 Windows Secret 只读生产组合根前置收口，按真实 License/Session/游标密钥和数据库证据决定是否装配；不得注入测试信任锚。
