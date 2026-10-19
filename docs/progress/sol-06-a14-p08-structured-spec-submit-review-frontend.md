# SOL-06-A14-P08：结构化专项安全送审客户端与详情动作

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_SUBMIT_FRONTEND_PASS`；已完成前端冻结送审传输和固定版本详情动作，不表示 Windows 浏览器真实链、正式信任或 Gate 3 已通过。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A14-P08`|
|输入基线|冻结 `SOL_SPEC_SUBMIT_REVIEW`、CR-SOL-021、DEC-1210、A14-P06 HTTP 合同与 A14-P07 Windows 显式写组合|
|前置任务|固定版本详情、当前事实验证报告、项目成员只读客户端和真实后端送审闭环均已通过|
|涉及模块/实体|Auth Session 写桥、Solution 送审客户端、固定版本详情页；无后端或数据库实体变化|
|涉及 API / Schema / 权限|严格复用冻结路径/四字段请求/201 响应；仅 ProjectManager 可在 UI 发起，服务端仍为最终授权与当前事实裁决者|
|验收标准|精确请求/响应/Header；非负责人不发送；只在匹配当前 DRAFT 的现时报告 `ready_for_review=true` 时创建新操作；当前 ACTIVE 成员选择；不确定结果保留原 Key/评审人并显式确认重试；成功不宣称批准|
|风险|旧验证报告误用；重复送审；不确定结果换 Key；评审人状态变化；响应身份错绑；201 被误解为批准|

## 实施结果

- Session 写桥新增冻结 `:submit-review` 路径，CSRF 仍只在 Auth Client 内持有；请求体和幂等键按单次写发送，不自动重试。
- 新增 `StructuredSpecSubmitReviewClient`：本地只接受当前 ProjectManager、canonical UUID、1～32 个唯一评审人和有效原操作号；评审人排序后发送精确 `reviewer_ids/policy_ref/due_at/submission_note` 四字段。
- 客户端严格核对 201 的项目、系列、固定版本、提交人、Reviewer、Review/Round、首轮、`IN_REVIEW`、`"v1"` ETag、UTC 时间、Trace、JSON 和 no-store；错绑、缺字段、未知错误或断连全部视为结果不明。
- 固定版本详情只在验证报告与当前不可变详情身份/指纹/数量一致且 `ready_for_review=true`、版本仍是无 Review 的 DRAFT 时允许创建新送审。ImplementationMember 仍可验证但看不到送审操作。
- 评审人从当前 ACTIVE 项目成员读取并排序。列表读取最多 20 页（1000 条）且游标/成员重复或未完整结束时失败关闭；这不改变服务端 1～32 人资格规则。
- 发送前把 actor/project/spec/series/排序后评审人/Key 写入会话级存储。断连或 503 后禁止换 Key/评审人，必须明确勾选才可精准重试；确定性拒绝清理待发记录并要求重新验证，幂等碰撞则锁定并提示核对审计。
- 成功页显示 Review/Round 与“评审中”，同时明确该回执不是批准、实施完成或客户确认。

## 验证证据

- 客户端与详情动作定向：`11 passed`；覆盖冻结请求、排序、严格 201、非负责人/非法输入本地拒绝、全部公共错误、断连/503/错绑/错误 Header、不确定结果原 Key/原评审人重试、成功回执和角色隐藏。
- 前端全量：`147` 个文件、`1817 passed`；TypeScript/Vue 类型检查通过。
- Vite 生产构建通过，318 个模块完成转换；既有主包大于 500 kB 的提示仍存在，本项未引入新依赖或路由。

## 兼容、升级与回滚

- 无 Migration、后端冻结合同、角色、License、依赖、路由或旧数据变化；前后端应同版部署，旧前端不会显示送审动作。
- 只使用 `sessionStorage` 保存当前浏览器标签页内的不确定操作，不保存 CSRF、Session、密码或客户正文；记录在成功/确定性拒绝后清理。
- 可移除详情动作与新客户端回滚 UI；已由后端产生的 Review、状态、Audit 和收据必须保留。若浏览器存有结果不明操作，回滚前须先核对评审记录，不得直接换 Key 重发。
- 正式服务账户/公钥信任、Windows Server 2025、Debian 13、性能、Gate 3、Pilot 和正式发行状态不变。

Next：`SOL-06-A14-P09` 使用 Windows 11 Edge、生产构建、生产 FastAPI/Uvicorn 与可弃 PostgreSQL 18.6 完成真实浏览器送审闭环，验证负责人可见、实施成员隐藏、现时验证、评审人选择、201 页面状态、数据库唯一事实、跨项目清屏和原 Key 重放保护。
