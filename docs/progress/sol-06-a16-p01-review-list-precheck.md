# SOL-06-A16-P01：Review List / Reviewer Inbox 前置核查

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`REVIEW_LIST_PRECHECK_PASS`；本项只证明实现路径和前置已明确，不表示 REVIEW_LIST、Inbox、Gate 3 或 Pilot 已通过。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A16-P01`|
|输入基线|Gate 2 冻结 API-01/02、Q-RVW-01、DM-02 Review、A15 known-ID Reviewer 真实 Edge 闭环|
|前置任务|A15-P01～P06 已通过；当前 Review 可精确读取/决定，但没有任务发现|
|涉及模块|review、project authorization、platform secret/cursor、Windows composition、frontend；P01 仅核查与记录|
|涉及实体|Review、ReviewRound、ReviewAssignment、Subject Owner authorization；不新增业务 Aggregate|
|涉及 API|已冻结 `REVIEW_LIST GET /api/v1/projects/{project_id}/reviews`；非新路径|
|涉及权限|当前 Project member + 每候选 Subject Owner；`my_pending` Assignment 不是授权替代|
|验收标准|明确分页/筛选/投影、索引/密钥前置、迁移/回滚、失败关闭与后续独立验收任务|
|风险|浏览器存储冒充 Inbox；历史 Assignment 越权；游标跨 Session/Project；无索引扫描；列表泄露主题或其他 reviewer 意见|

## 核查结果

1. 冻结 API 已包含 `REVIEW_LIST`，标准 Page 固定为 `items/next_cursor/has_more`，默认 `page_size=50`、上限 200，游标必须完整性保护。因此实现既有路径不需要 API Breaking Change。
2. 当前 Project 权限目录只有 `REVIEW_GET/CREATE/START/DECIDE/WITHDRAW`，缺 `REVIEW_LIST`；Review application/repository/router 也只有精确读取。
3. A15 前端只能从送审回执或专项已有 `review_ref` 进入。把该入口保存到浏览器只能覆盖本机已见任务，不能替代跨设备、撤权后现时授权的收件箱。
4. Subject Owner 必须逐候选重证当前访问；assigned reviewer 只用于 `my_pending` 候选筛选，不能绕过当前 Project member、系列或固定版本权限。
5. Review/Assignment 现有索引不足以稳定支持 Project 倒序页和 reviewer pending 候选。新增索引属于冻结 Schema 后增量，已先登记 `CR-RVW-004`，不修改旧迁移或业务事实。
6. Windows 生产组合需要独立 `review-list-cursor-v1` Vault 引用；不得复用 Member/Document/Job 游标密钥或启动时生成临时 fallback。

## 选择与分片

采用 `CR-RVW-004`：冻结路径上细化 `view=all|my_pending`，固定 `created_at DESC, review_id DESC`，列表仅返回活动轮最小摘要及当前 actor 的 Assignment。按合同/游标、Schema 索引、Repository/授权、HTTP、Windows、前端、Edge 八步独立验收，避免在一个 WBS 中同时改 Schema、权限和 UI。

P01 未修改代码、Schema、API 运行行为、权限或依赖，未运行功能测试；依据为冻结文档、manifest、Review/Project/Windows/前端代码静态交叉核查。

Next：`SOL-06-A16-P02` 固化 Review List 增量 API 文档、列表 DTO 与专用 Session/Project/view/page_size 绑定的 HMAC 游标纯合同，并先以单元测试验证篡改和跨范围拒绝。
