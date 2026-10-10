# JOB-01-A06-P04：前端 Job 详情安全客户端

2026-10-02 / Phase 2 / INTERNAL_PASS（客户端合同）。输入：Gate 2 冻结 `JOB_PROJECT_GET`/`JOB_ADMIN_GET` 及 `JOB-01-A04-P04` Windows 显式后端详情；`JOB-01-A06-P01` 安全 Job 投影解析器。编码前检查：前置后端实际 Owner/权限/强 ETag 已验，当前只实现前端传输；涉及 Jobs API 客户端、Job 元数据，不改 Schema、后端 API、权限、License 或依赖。

项目与 Admin 详情入口明确分开，路径仅接受规范非零 UUID。GET 使用同源 Cookie、no-store、超时中止且不自动重试；响应必须具有安全 JSON Envelope，JobId/ProjectId 与请求一致，Admin 不接受 PROJECT Job，HTTP 强 ETag 必须等于安全投影中的 lock_version ETag。复用列表投影白名单，服务器私有字段/异常不进入客户端对象或错误文案。ETag 只表示版本，不作为授权凭据；服务端仍逐次重核会话、License、项目和 Owner。

Files：`apps/frontend/src/modules/jobs/api/jobDetailClient.ts` 及测试、`jobListClient.ts` 导出原有投影解析函数供复用。Migration/API/依赖：无。兼容性：尚未由页面引用，现有构建资产未改变。升级/回滚：无数据迁移，撤新客户端与解析器导出即可，后端历史和冻结合同不变。

验证：定向15/15、前端全量1116/1116、typecheck/build PASS；跨项目/错Job/错ETag/带未验证结果/错误映射/超时边界覆盖。未运行页面、真实浏览器/正式账户、三平台网络或性能测试；不判 Gate 3 PASS。

Next：`JOB-01-A06-P05` 项目 Job 详情只读页面与导航，并单独核管理员详情页面；取消/重试写入口仍关闭。正式 License 信任、法律、质量/UAT、发行保持开放。
