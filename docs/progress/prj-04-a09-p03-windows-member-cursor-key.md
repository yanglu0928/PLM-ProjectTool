# PRJ-04-A09-P03：Windows 成员 cursor 独立密钥来源

- Phase/WBS：Phase 2 Platform Core / PRJ-04-A09-P03。输入：P01 HMAC cursor、现有 Windows 当前账户 Vault 与加密备份恢复；决策 `DEC-20260925-065`。
- Changed：新增只读 Windows 装配入口，固定引用 `project-member-list-cursor-v1`，缺钥/错长拒绝；UUID 范围测试引用完成 Vault 丢失与加密备份恢复后旧 cursor 验证。不创建、覆盖或导出正式密钥。
- Files：Windows 装配入口、单元/Vault 恢复测试、决策/状态/版本记录。
- Migration：无。API：无新增公开路由；P02 成员列表仍未挂入平台组合。
- Tests：Windows 11/Python 3.13 后端 407/407 PASS，测试 Vault 密钥供给→删除→恢复→旧 cursor 验签 PASS；开发 wheel 构建 PASS。本项无 SQL，未运行 PostgreSQL。
- Result：合成来源与恢复 PASS；正式目标账户密钥/离线备份、显式平台组合、PRJ-04 整体、Gate 3 与可用程序包未完成。
- Known Issues：正式备份口令必须由操作员独立保管；Windows Server 2025/异账户及 Debian 13 未验证。
- Next：PRJ-04-A09-P04 将成员列表与独立密钥来源接入 Windows 显式平台，并在隔离 PostgreSQL 验证。
