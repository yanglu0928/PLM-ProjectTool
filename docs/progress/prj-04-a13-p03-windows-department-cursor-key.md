# PRJ-04-A13-P03：Windows 独立 Department cursor 密钥来源

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A13-P03。来源：PRJ-04-A13-P01/P02、既有 Windows Vault 安全来源；决策 DEC-20260925-077。
- Changed：新增只读 Windows 当前账户 Vault 入口，固定独立引用 `project-department-list-cursor-v1`，缺钥/错长拒绝启动；临时测试引用完成 Vault 丢失与加密备份恢复后旧 cursor 验证。不创建、覆盖或导出正式密钥。
- Compatibility/Upgrade：无新 Schema/Migration/依赖或公开 API；升级无需数据操作。
- Tests：Windows 11/Python 3.13 后端 429/429 PASS；专用引用、缺钥/错长失败关闭、临时 UUID Vault 备份恢复后旧游标有效 PASS；开发 wheel PASS。PostgreSQL 不适用于本密钥适配器，本项未运行数据库测试。
- Result：Windows 合成密钥来源 PASS；正式目标账户供给、平台组合、Gate 3 和可用程序包未完成。
- Known Issues：Windows Server 2025 异账户恢复、Debian 13 按用户要求暂不验证；临时测试引用不等于正式发行材料。
- Next：PRJ-04-A13-P04 Windows 显式平台 Department 列表组合。
