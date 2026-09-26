# DOC-01-A04-P05 Windows DocumentVersion 读组合

- 日期：2026-09-26；状态：Windows 11 显式平台合成组合 PASS；正式目标账户密钥/发行公钥未供给。
- `--platform` 与 `--platform-write` 复用当前 Session、License、DocumentReadService、Project/Auth Owner Port 装配版本列表/详情 Router；普通登录模式和默认应用仍 404。两种显式模式均要求 Windows 当前账户独立 `document-version-cursor-v1` 密钥，缺失/无效则整模式启动失败并释放数据库资源，不复用 Document 列表或其他密钥。
- 验证：Windows 11/Python 3.13 后端 528 项无失败（2 项既有符号链接环境跳过）；平台合同 18 项含缺版本密钥失败关闭、普通/显式模式路由差异；开发 wheel PASS。前序隔离 PostgreSQL 18.6 的版本 HTTP 同链路已通过，但本项未使用真实发行 License 或正式目标账户密钥，不能称生产可用。
- 无 Migration、冻结 API Breaking Change 或新依赖。后续为受权内容下载的文件完整性/范围与流式失败关闭；正式发行信任源、Server 2025 仍待。
