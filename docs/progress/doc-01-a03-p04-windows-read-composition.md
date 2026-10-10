# DOC-01-A03-P04 Windows Document 只读平台组合

- 日期：2026-09-26；状态：Windows 11 显式平台合成组合 PASS；目标账户正式密钥未供给。
- `--platform`、`--platform-write` 复用当前真实 PostgreSQL Session、License Guard、Project/Auth Owner Port 装配 DocumentService/Router；普通登录模式和默认应用仍 404。两个显式模式均先要求 Windows 当前账户 `document-list-cursor-v1` 专用密钥，缺失/无效/不可读直接拒绝启动并释放数据库资源，不回退其他密钥。
- 验证：Windows 11/Python 3.13 后端 518 项无失败（2 项既有符号链接环境跳过）；平台合同 17 项 PASS，新增缺 Document 密钥失败关闭与普通/显式模式路由差异；开发 wheel PASS。上一项隔离 PostgreSQL 18.6 的 HTTP 同链路验证已通过，但本项没有用真实发行 License/目标账户密钥启动正式平台，因此只称合成组合。
- 无 Migration、冻结 API Breaking Change 或新依赖。正式目标账户密钥/公钥、Server 2025 平台启动、文档版本读取及受权内容下载仍待。
