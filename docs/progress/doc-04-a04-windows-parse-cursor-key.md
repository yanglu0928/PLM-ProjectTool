# DOC-04-A04：Windows Parse 游标专用密钥来源

- Changed：新增 Windows 当前账户 Credential Manager 的 `document-parse-cursor-v1` 只读入口，独立于其他游标密钥；缺失/无效时生产装配失败关闭，不内置或自动生成正式密钥。
- Files：Windows Parse 游标装配适配、单元及当前账户临时备份恢复测试；Migration/API/新依赖：无；版本 `0.1.0.dev0`。
- Tests：Windows 11/Python 3.13 后端 581 项无失败（2 项既有符号链接环境跳过）；临时密钥失密、加密备份恢复、旧游标再验证和测试凭据清理 PASS；开发 wheel PASS，SHA-256 `35f6ff7ca46e6477be2edaede2d7c928403cfb535f7bcdd3f55f50536c062c65`。
- Result：当前账户合成恢复 PASS；正式部署账户密钥未供给，不能声称生产密钥来源就绪。Parse HTTP 仍未挂平台组合。
- Next：DOC-04-A05 显式 Windows 平台组合与 PostgreSQL HTTP 端到端。Windows Server 2025 未运行，Debian 13 按用户指令暂不验证。
