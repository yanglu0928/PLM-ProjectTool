# Review List HTTP 增量合同 V1

日期：2026-10-19；WBS：`SOL-06-A16-P02`；来源：Gate 2 冻结 API-01/02 `REVIEW_LIST`、Q-RVW-01、DM-02、`CR-RVW-004` 与 A15 known-ID Reviewer 闭环。本文细化已冻结路径，不新增审批权限或客户事实。

## 请求与分页

- `GET /api/v1/projects/{project_id}/reviews`；当前 Project member，当前 License/Session/Project/Subject Owner 每页重证；GET 不要求 CSRF、Idempotency-Key，也不写 Audit。
- query 只允许互不重复的 `page_size/cursor/view`。`page_size` 默认 50、范围 1～200；`view` 默认 `all`，只允许 `all` 或 `my_pending`。
- `all` 返回当前用户仍有 Subject Owner 读取权的 Review 历史候选；`my_pending` 只候选当前 actor 在活动轮的 PENDING Assignment，但 Assignment 不能替代 Project/Subject 授权。
- 排序固定 `created_at DESC, review_id DESC`。游标使用专用 AES-256-GCM 认证加密，AAD 绑定 `review-list` family/version、Session 摘要、Project、view、page_size，密文保存 created_at/review_id；不含原始 Session、Secret 或客户正文，也不明文暴露被隐藏候选的位置。
- 并发列表不是固定快照。隐藏候选消耗 keyset 位置，可返回短页或空页且 `has_more=true`；客户端必须沿 `next_cursor` 继续，不能自行构造位置或把单页过滤当完整 Inbox。

## 成功投影

状态 200、`Cache-Control: no-store`；Envelope 为 `data={items,next_cursor,has_more},trace_id`。每个 item 精确包含：

- `review_id/project_id`；
- `subject_ref.resource_type/resource_id`；
- `policy_code/state/created_by/created_at/etag`；
- `active_round`：非 IN_REVIEW 为 null；活动时只含 `review_round_id/round_no/subject_version_ref/started_at/my_assignment`；
- `my_assignment`：当前 actor 未被分配时为 null；否则含 `assignment_id/state/decision/decided_at`。不返回其他 reviewer 的身份、意见或决定。

列表不返回主题名称/正文、Evidence/Trace refs、快照指纹、内部锁、SQL/索引、物理路径或 Owner 名称。前端使用 `subject_version_ref` 打开相应受权主题，再用 `review_id` 进入精确 Review；获得 ID 不授予后续读取。

## 错误与兼容

- 无/失效 Session 401；不受信 Host、License 403；无权/未知 Project 404；非法 project UUID、page_size/view 422；重复/未知 query、畸形或错范围游标 400；受信依赖异常 503。
- 未注册/正常无权 Subject 候选可隐藏；Owner/Repository 返回畸形或异常必须 503，不能伪装为空列表。
- 本合同不改变冻结 Method/Path/Project member/Page，也不修改 REVIEW_GET/DECIDE。新增列表索引、应用服务、默认关闭 Router、Windows 专用 key 和前端按 `CR-RVW-004` 后续独立验收。
