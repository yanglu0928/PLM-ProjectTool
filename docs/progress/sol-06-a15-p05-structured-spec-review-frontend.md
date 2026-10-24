# SOL-06-A15-P05：结构化专项 Reviewer 前端

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`STRUCTURED_SPEC_REVIEW_FRONTEND_PASS`；证明基于已知 Review ID 的前端传输与交互合同，不表示浏览器真实链或 REVIEW_LIST 已完成。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A15-P05`|
|输入基线|A15-P03/P04 REVIEW_GET、冻结 REVIEW_DECIDE、A14-P08 送审回执与现有 SessionClient 安全写模式|
|前置状态|Windows 后端已能读取/决定；无 Review Client、路由或 Reviewer 页面；REVIEW_LIST/任务发现尚无后端|
|涉及模块|前端 Session 写桥、Review Client/View/route、结构化专项详情回执入口与测试|
|涉及 API / Schema / 权限|严格复用两个冻结端点；无后端、Migration、角色、License 或依赖变化|
|验收标准|已知 ID 先读；严格 DTO/ETag/Trace；仅当前 PENDING assignee 可决定；退回意见；未知结果原 Key/决定/意见重试；成功后回读一致|
|风险|盲写 UUID；非 assigned member 决定；断连换 Key；回执与当前状态不一致；把精确 GET 冒充收件箱或客户确认|

## 实施结果

- 新增 `ProjectReviewClient`：严格解析 SOL-06 Review/活动轮/Assignment/Decision，校验 `Cache-Control`、Trace 与 Review/Round ETag；写请求通过 Auth-owned `SessionClient` 注入 CSRF 和 Idempotency-Key，页面代码接触不到 CSRF。
- 新增 `/projects/:projectId/reviews/:reviewId` 懒加载页面。只从结构化专项已存在的 `review_ref` 或送审成功回执进入，页面明确说明不是评审收件箱；没有 REVIEW_LIST 时不生成手工待办或猜测 Review ID。
- 页面先读取服务端活动轮，只有当前 Session 用户对应的 PENDING Assignment 才显示操作；其他当前 Project member 只能查看。批准要求显式核对，退回要求实质意见。
- 每次决定先按 Actor/Project/Review/Round/Decision/Comment 保存原操作号；断连或 503 保持原值并要求人工勾选后精准重试。确定拒绝清理待重试状态；幂等碰撞锁死并提示核对。
- 成功回执后立即重新 GET，并要求 Review ID、状态与 ETag 完全一致；不一致时停止后续提交。终态页保持 `active_round=null`，不把历史轮伪装为待办；所有提示明确评审决定不等于实施完成、客户确认或 UAT。

## 验证证据

- Review Client/View 与结构化专项入口定向：3 文件、13 项全部通过，覆盖严格读写、assigned reviewer、批准、退回意见、未知结果原请求重试、非分配成员只读及 known-ID 路由。
- 前端全量：`149 test files / 1823 tests` 全部通过。
- `vue-tsc` 与 Node TypeScript typecheck 通过；Vite production build 通过，322 modules transformed，新 Reviewer 页面独立懒加载 chunk 14.62 kB（gzip 5.77 kB）。
- 既有主 bundle 804.17 kB 的大于 500 kB 警告仍存在；本页已独立分块，警告不是本项新增功能失败，也不能忽略后续性能验收。

## 兼容、回滚与未完成项

- 无后端/Migration、冻结请求响应、角色/License、依赖或旧数据变化；前后端同版升级。可撤前端 route/client/view 停止 UI，后端 Review/Decision/Audit/收据历史必须保留。
- 浏览器刷新后只有从仍显示 `review_ref` 的结构化专项详情可重新进入；完整 Reviewer 收件箱需要正式 REVIEW_LIST，不能以 localStorage/sessionStorage 长期保存客户待办替代。
- Windows Edge 真实决定链、正式信任、Gate 3、Pilot 与 Release 仍未通过。

Next：`SOL-06-A15-P06` 使用 Windows 11 实际 Edge、生产 Vue、FastAPI/Uvicorn 与可弃 PostgreSQL 18.6 验证送审回执进入 Reviewer 页面、assigned reviewer 决定、未知结果精准重试、终态回读与跨项目清屏。
