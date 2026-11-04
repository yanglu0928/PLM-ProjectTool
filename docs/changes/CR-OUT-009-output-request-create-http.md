# CR-OUT-009：OutputRequest Create 可选HTTP边界

- 日期：2026-11-04
- 状态：已按持续授权登记；OUT-01-A01-P12编码前检查通过，待开始实现
- 来源：CR-EXEC-002 Windows内部Pilot纵向链；OUT-01-A01-P11完成后复核冻结API-03的Output Create缺口
- 基线：API-03 / API Contract V1 的 OUTPUT_REQUEST_CREATE；不修改API、数据模型或Schema

## 原因与决定

内部 OutputRequest Owner、固定版本 Resolver、Policy/Template/Requirement Source 与 Plugin capability 均已建立，但模块当前无 HTTP API。实现单一可注入、默认不挂载的 POST /api/v1/projects/{project_id}/output-requests adapter，复用内部 Owner。只完成 request enqueue，不执行插件、不渲染/发布文件，不实现其它 Output endpoints。

## 边界与安全

HTTP层严格解析冻结请求字段，复用 Owner 对 Session/CSRF/Project role/License/Idempotency/Audit 的检查，并投影最小 202 RequestRef + JobRef。稳定业务错误映射为安全响应，不回传异常。正式publisher registry为空时必须继续拒绝 Output capability。仅合成 HTTP/数据库，不发客户数据，不访问外部AI。

## 风险、回滚与验证

无数据库/API迁移。风险是字段越权或业务验证绕过；通过 schema allowlist、route contract、Owner复用和失败关闭验证。回滚为移除 router 和HTTP测试。Hosted验证计划：定向HTTP、后端全量/wheel、PG18、父包/A17/A34/A35/A50；运行环境不在用户本机/C盘。
