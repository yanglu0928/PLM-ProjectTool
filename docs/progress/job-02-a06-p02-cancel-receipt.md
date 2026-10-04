# JOB-02-A06-P02：项目 Job 取消安全回执客户端

2026-10-02 / Phase 2。编码前核查：JOB-02-A06-P01、冻结项目 Job 取消 API 增量及 Windows 写组合满足。仅新增前端响应校验与安全错误映射；涉及 JobId、ProjectId、版本与操作 Key，不改 DB/后端 API/权限/依赖。验收为原回执绑定、重放不冒充当前状态、拒绝错误状态/ETag/URL/不可信正文与全量回归。

实现：只接收同项目 PROJECT Job 的原始强 ETag、Key 和有效原因；POST 仍由 SessionClient 私有 CSRF 发出。200 回执严格核 job_id、四种首结果状态、changed 布尔、强 ETag 对应 HTTP Header、固定当前详情 URL 与有效 trace_id；返回冻结的最小白名单投影、`is_current_state_proof=false`。原 Key 重放继续用原请求版本；错误仅按状态+已知 code 映射安全文案，未知/非 JSON/网络故障统一 `JOB_CANCEL_UNCERTAIN`，不声称失败也不自动重试。

验证：定向 25 项、全量前端 1156/1156、typecheck/build PASS；后续 Unicode 控制字符边界复跑全量同结果。Migration/API/架构无变动。已知：页面尚未接入；未知结果需在页面持久保留原 Key/ETag 且显式 GET 当前状态，真实浏览器/正式信任/三平台/Gate 3 未验。下一项 JOB-02-A06-P03 项目 Job 详情人工取消页面。
