# DOC-04-A03：ParseRecord 列表可选 HTTP

- Changed：按冻结 `DOCUMENT_PARSE_LIST` 暴露 PROJECT/GLOBAL 两条显式 GET，仅通过注入 Router 可用。游标使用独立 32 字节 HMAC 密钥，绑定当前 Session、Scope/Project、Document、DocumentVersion、页大小及稳定 keyset 位置；拒绝篡改/跨资源/跨会话/重复参数。只输出 ParseRecord 安全元数据与 trace_id，禁止路径、正文、结果 Hash 和 traceback。
- Files：Document Router/游标、可选应用挂载、HTTP 合同测试；Migration/新依赖：无；版本 `0.1.0.dev0`。
- Tests：Windows 11/Python 3.13 后端 578 项无失败（2 项既有符号链接环境跳过）；合成 HTTP 双 Scope、分页、游标绑定、许可/不存在/不可用错误及默认 404 PASS；开发 wheel PASS，SHA-256 `ce7de0ce723d69f497bcf50ad85e9330fe5edcb4db2cbee9eb2a3a56ab15c2bd`。
- Result：可选合同 PASS。未挂 Windows 平台组合，未用真实 PostgreSQL 做 HTTP 联调，未供给正式游标密钥。解析成功结果文件完整性与实际 Parser/OCR 不在本项，不能视为可用解析功能。
- Next：DOC-04-A04 独立 Windows 当前账户密钥来源及恢复；A05 平台组合和真实 PostgreSQL HTTP 验证。Windows Server 2025 未运行，Debian 13 按用户指令暂不验证。
