# JOB-02-A06-P01：项目 Job 取消的前端会话写桥接

2026-10-02 / Phase 2。编码前核查：Gate 2、JOB-02-A05 Windows 显式写组合、冻结 API-03 与 Job 取消增量已满足。本任务仅在 SessionClient 增加项目取消 POST 的私有 CSRF 传输；涉及 Job 项目 ID/版本与原幂等 Key，不改后端实体、权限、API 路径、Schema 或依赖。验收为安全请求边界、401 清会话、超时不重试、全量前端测试和构建。

实现：规范项目/Job UUID、强 ETag、安全整数版本、16～128 ASCII Key 和 trim 后 1～1024 字无控制字符原因；JSON 请求小于 8192 字节。仅同源 Cookie、私有 CSRF、原 If-Match/Key 发送一次。HTTP 回执原样交下一层验证；不把原取消收据当当前 Job 状态。网络未知结果不自动换 Key/重试。当前传输不开放页面按钮。

验证：SessionClient 定向 153/153、前端全量 1130/1130、typecheck/build PASS。无 Migration；无新 API/权限/架构变动。风险：真实浏览器、正式信任、三平台、性能、Gate 3 尚未验证。下一项 JOB-02-A06-P02 验证取消响应与错误的安全客户端，后续页面需对未知结果保留原 Key/ETag 并显式 GET 当前状态。
