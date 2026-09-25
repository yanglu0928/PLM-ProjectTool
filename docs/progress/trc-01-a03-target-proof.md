# TRC-01-A03：目标 Owner Port 与 DocumentVersion 证明

- Changed：Trace 应用新增显式注册的目标 Owner Port 和双端固定引用证明；未注册类型、错误 Scope/Project、错误版本或无权目标均失败关闭。组合层仅将 `document/DOC-02` 接至既有 DocumentReadService 的真实 Session、License、GLOBAL 管理员/PROJECT 成员授权。返回值仅为匹配引用，不带正文、路径、Hash 或可枚举元数据。
- Files：Trace 应用合同、组合层 Document 适配、单元测试、既有 DocumentVersion 隔离 PostgreSQL 验证脚本扩展；Migration/公开 API/新依赖：无；版本 `0.1.0.dev0`。
- Tests：Windows 11/Python 3.13 后端 592 项无失败（2 项既有符号链接环境跳过）；隔离 PostgreSQL 18.6 固定版本成功、外部用户/无权管理员/项目成员读取 GLOBAL 拒绝 PASS；开发 wheel PASS，SHA-256 `14348c16af9af895f4ef434849a83c5f3311a339ffca1384ae696725b2e6c597`。
- Result：DocumentVersion 端点证明 PASS；其他 Owner 未注册并拒绝。正式状态、无环、持久幂等、Audit 与逐节点图读取未完成；无 Trace 公共写路由，TRC-01 整体及 Gate 3 未通过。
- Next：TRC-01-A04 受控关系无环写入期校验。Windows Server 2025 本项未运行，Debian 13 按用户指令暂不验证。
