# DOC-01-A05-P05 Windows 显式平台下载组合

- 日期：2026-09-26；结论：Windows 11 合成组合 PASS；未达到正式发行/生产验收。
- 基线：冻结 API-02 `DOCUMENT_VERSION_DOWNLOAD`、DOC-01-A05-P03/P04 已验证内部来源/快照/可选 HTTP。
- 实现：仅 `--platform` 与 `--platform-write` 注入 Document 读取、受权下载准备服务、同一数据根的本地存储及 Audit；普通应用与仅登录模式保持 404。原有 License、Session、Project/GLOBAL 授权照常适用。存储根目录检查或其他信任源失败时销毁数据库 Runtime 并拒绝发布平台。
- 验证：Windows 11/Python 3.13 全部后端 540 项无失败（2 项已有符号链接权限环境跳过）；组合合同覆盖默认 404、显式模式未认证 401、存储构建失败拒绝启动并释放 Runtime；开发 wheel PASS。P04 已单独在隔离 PostgreSQL 18.6/临时文件验证真实 Session 成功下载、损坏 Audit 与复核后撤权；本项没有重跑正式平台真实账户端到端。
- 数据库 Migration：无。冻结 API 路径/权限：不变。版本：`0.1.0.dev0`。
- 已知限制：正式发行公钥/目标运行账户可信时间及密钥材料未供给；真实客户端主动断线、多进程共用数据卷的快照磁盘预算、Windows Server 2025 尚未验证。Gate 3 与可使用发行包不可据此判 PASS。
- 回滚：移除平台入口的下载 Router 注入即可恢复 404；不删除文件、Version 或 Audit 历史。
