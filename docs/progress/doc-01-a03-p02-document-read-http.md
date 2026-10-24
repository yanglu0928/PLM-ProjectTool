# DOC-01-A03-P02 Document 元数据只读 HTTP

- 日期：2026-09-26；状态：可选 Router / 合同 PASS，正式 Windows 组合未挂载。
- 基线：API-02 `DOCUMENT_LIST`/`DOCUMENT_GET`；决策 `DEC-20260926-122`；前置 DOC-01-A02 内部读与 DOC-01-A03-P01 独立签名游标。
- 范围：PROJECT 和 GLOBAL 四条固定 GET 路径；可信 Host、Session、License、当前项目成员或 GLOBAL 管理员；页大小 1～200，游标绑定 Session/Scope/Project/page_size；详情强 ETag。默认应用仍 404。
- 安全边界：请求不接受任意 Scope；列表与详情均验证当前项目或管理员资格；响应只含元数据、版本引用与时间，不含文件物理路径、storage_locator 或正文；受限/跨项目文档统一隐藏。GLOBAL 非管理员/正式项目引用规则暂不扩展。
- 验证：Windows 11/Python 3.13 后端 517 项 PASS（2 项既有符号链接环境跳过）；4 项 HTTP 合同测试包含双页、详情、GLOBAL 路径、跨会话/Scope/项目游标拒绝、异常映射与默认关闭；既有隔离 PostgreSQL 18 A02 验证再次 PASS，覆盖真实 Session/项目成员/License/分页/隐藏；开发 wheel 构建 PASS。HTTP 与 PostgreSQL 尚未在同一合成链路验证，不能称为生产端到端。
- 无 Migration、依赖或冻结 API Breaking Change；正式目标账户专用游标密钥、Windows 显式平台装配、版本读取/受权内容下载及最终程序包仍待。
