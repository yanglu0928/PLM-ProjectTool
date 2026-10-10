# DOC-01-A04-P03 DocumentVersion 可选 HTTP GET

- 日期：2026-09-26；状态：HTTP 合同 PASS；默认/当前平台组合仍不装配。
- 基线：冻结 API-02 `DOCUMENT_VERSION_LIST/GET`，内部版本读取 DOC-01-A04-P01，专用签名游标 DOC-01-A04-P02；决策 `DEC-20260926-126`。
- 实现：PROJECT/GLOBAL 四条固定 GET 路径；可信 Host、Session、License 与父 Document 授权；页大小 1～200，专用游标绑定父 Document/Scope/Session/page_size；版本详情只投影 ID/序号/摘要/大小/MIME/可用状态/前驱/时间，不含 FileObject ID、Locator、来源元数据或正文。默认应用不装配时仍 404。
- 验证：Windows 11/Python 3.13 后端 527 项无失败（2 项既有符号链接环境跳过）；3 项 HTTP 合同测试覆盖双页、详情、GLOBAL、投影、跨上下文游标/查询拒绝及错误映射；开发 wheel PASS。前序内部 PostgreSQL 18.6 版本读 PASS，但本项尚未把 HTTP 与真实数据库放在同一合成链路，不能标生产端到端。
- 无 Migration、新依赖或冻结 API Breaking Change；下一项须做 HTTP+PostgreSQL 同链路验证，再将版本专用游标密钥接入 Windows 显式模式。受权文件下载另列任务。
