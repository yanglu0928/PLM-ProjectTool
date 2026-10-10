# DOC-01-A05-P04 可选受权流式下载 HTTP

- 日期：2026-09-26；状态：Windows 11 可选 Router 合成端到端 PASS；默认/当前 Windows 平台未装配。
- 基线：冻结 API-02 `DOCUMENT_VERSION_DOWNLOAD`、已验证下载快照与授权编排；决策 `DEC-20260926-131`。
- 实现：PROJECT/GLOBAL 两条固定内容 GET 路径，可信 Host、Session、License/父 Document/Version/FileObject 当前授权由内部 Service 核验；拒绝查询/Range。首字节前完成整个文件的 100 MB 有界 Hash/身份验证和发送前复核；每 Router 默认四个并行快照/响应，按 1 MiB 分块，从私有快照而非原文件读取。返回受控 MIME、长度、nosniff、no-store 与不含用户输入的附件名；正常、异常读流及响应后台使用幂等关闭释放文件和名额。
- 验证：Windows 11/Python 3.13 后端 539 项无失败（2 项既有符号链接环境跳过）；5 项 HTTP 合同涵盖默认 404、PROJECT/GLOBAL 内容和响应头、坏文件错误、查询/Range 拒绝、恶意 MIME 拒绝、并行限流和异常读流后名额释放；隔离 PostgreSQL 18.6 + 临时物理文件经 HTTP 真实 Session/Document 读取成功，既有脚本同时验证损坏 Audit 与复制后撤权；开发 wheel PASS。临时库/文件已删除，测试服务停止。
- 无 Migration、新依赖或冻结 API Breaking Change。真实客户端主动断线、多进程总磁盘预算、正式发行信任源与 Windows Server 2025 仍待验证；未挂载 Windows 显式模式，不能声称生产可用。
