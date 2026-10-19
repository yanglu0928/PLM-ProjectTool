# CR-RVW-004：Review List 与 Reviewer Inbox 兼容细化

日期：2026-10-19。状态：依据 `CR-EXEC-001` 持续授权批准实施。Gate 2 原冻结提交 `64cdf09` 保留；本 CR 实现已冻结的 `REVIEW_LIST`，不新增审批捷径、不改变 REVIEW_GET/DECIDE，也不把任务发现结果当作客户确认。

## 来源与差异

Gate 2 已冻结 `GET /api/v1/projects/{project_id}/reviews`、Project member 权限和标准 Page 响应，但只写明 `Review page`，尚未细化列表项、筛选、排序和游标。当前代码只有精确 `REVIEW_GET`；Project 授权策略没有 `REVIEW_LIST`，Review Repository 没有列表 Port，Windows 没有列表游标密钥来源，前端只能从已知送审回执进入。

现有 `rvw_reviews` 可按 Project 前缀检索但缺稳定列表排序索引；`rvw_review_assignments` 的唯一索引以 Round 开头，不能有效支持“我的待处理”按 reviewer 查询。直接扫描全量、把 Review ID 存在浏览器或把 GET 冒充 LIST 都不能形成安全 Inbox。

## 方案比较与选择

- 不选浏览器 local/session storage 作为长期待办源：换浏览器、撤权和并发状态会漂移，也无法发现其他设备产生的评审。
- 不选逐个枚举或让用户输入 Review UUID：既不友好，也泄露资源探测面。
- 不选只返回 assigned reviewer 即授权：历史 Assignment 不能替代当前 Project 与 Subject Owner 权限。
- 选择实现冻结 REVIEW_LIST，并兼容细化 `view=all|my_pending`、标准 `page_size/cursor`。服务每页重新验证 License、Session、当前 Project member 和每个候选 Subject Owner；`my_pending` 只把当前 actor 的活动 PENDING Assignment 作为候选条件，不绕过主题权限。

## V1 列表合同边界

- 路径保持 `GET /api/v1/projects/{project_id}/reviews`；query 只允许 `page_size`、`cursor`、`view`，默认 `view=all`，`my_pending` 为 Reviewer Inbox。
- 排序固定 `created_at DESC, review_id DESC`；专用 AES-256-GCM 不透明游标绑定 family/version、Session 摘要、Project、view、page_size 与最后位置。位置密文不返回 SQL、物理索引或未授权 ID。
- `data={items,next_cursor,has_more}`；列表项只含 Review/Subject 身份、policy/state/created_at/etag，活动轮最小摘要和当前 actor 的 `my_assignment`。不返回主题正文、来源、指纹、内部锁或其他人的意见。
- 候选逐项经过 Subject Owner 当前授权；被隐藏候选仍消耗游标位置，因此允许短页或空页但 `has_more=true`，客户端继续取下一页。GET 不写 Audit。
- `all` 是受权 Review 历史页；`my_pending` 才是精确待办，不在客户端对单页结果二次猜测完整收件箱。

## Schema、迁移与回滚

- 计划追加普通 Migration `20261019_0166`，只增加 Project Review 稳定排序索引和当前 reviewer Assignment 候选索引；不新增业务列、不回填或改写历史。
- ORM 必须声明同名索引并通过 Alembic drift。索引可在应用入口关闭后回滚；降级只删除索引，不删除 Review/Assignment/Decision 事实。
- 应用回滚可关闭 REVIEW_LIST Router；精确 GET/DECIDE 和历史数据保持。专用 cursor key 缺失或错误时生产组合失败关闭，不临时生成替代。

## 实施分解

1. `SOL-06-A16-P01`：冻结合同/代码/索引/前端差距核查并登记本 CR。
2. `SOL-06-A16-P02`：固化增量 API 合同、列表 DTO 与专用签名游标纯合同。
3. `SOL-06-A16-P03`：增加 0166 索引与 ORM，完成空/有数据升降、约束和 drift 验证。
4. `SOL-06-A16-P04`：实现候选 Repository、逐项 Subject Owner 授权与 `all/my_pending` Application Service。
5. `SOL-06-A16-P05`：实现默认关闭的 REVIEW_LIST HTTP，并完成合同、权限、分页与异常测试。
6. `SOL-06-A16-P06`：接入 Windows 专用 Vault cursor key/显式读取组合，完成真实 PG/HTTP。
7. `SOL-06-A16-P07`：实现 Reviewer Inbox 前端、项目入口和自动分页。
8. `SOL-06-A16-P08`：Windows 11 实际 Edge 验证发现待办、决定后消失、历史仍可查与跨项目清屏。

## 验证计划

- Unit/API：严格 query、默认值、canonical UUID、游标签名/篡改/跨 Session/Project/view/page_size、DTO 白名单与安全错误映射。
- Permission：四类当前 Project member 候选、撤权/部门停用/Project 归档、Subject Owner 隐藏、assigned reviewer 不越权、License 失效。
- PostgreSQL 18.6：空库/有历史升级、空降级重升、ORM drift、两类 keyset 分页、并发状态变化、短页/空页继续、查询只读和新增索引使用证据。
- Frontend/Edge：只从服务端 Inbox 发现，决定后 `my_pending` 消失但 `all` 保留；断网精准重试、跨项目清屏、无手工 UUID。
- 里程碑前仍需全量后端/前端、性能、正式信任与安装验证；本 CR 不自动关闭 Gate 3、Pilot 或 Release。

## 风险与边界

分页不承诺固定快照；并发新建/终态可能改变后续页，客户端以刷新为准。Subject Owner 异常是 503，不伪装为空列表；正常无权候选可隐藏。Reviewer Inbox 只解决任务发现，不增加提醒、邮件、SSE 推送或第三方消息组件。不得由 Review state 推断客户已确认、实施完成或 UAT 通过。

## 实施进度

- 2026-10-19 / `SOL-06-A16-P03`：已增加 Migration 0166 与 ORM 两个最小索引；Win11/PostgreSQL 18.6 空库和 24 条有效 Review 历史的升降重升、行数保持、索引定义/计划及 drift 通过，后端全量与 wheel 入包通过。尚未增加授权策略、Repository/Application 或挂载 Router；下一项 P04。
- 2026-10-19 / `SOL-06-A16-P02`：已固化 `all/my_pending`、最小 actor-only Assignment 投影和短页继续语义；专用游标使用 AES-256-GCM 隐藏候选位置并绑定 Session/Project/view/page_size。定向、后端全量与 wheel 入包通过；尚未修改 Schema、授权策略或挂载 Router。下一项 P03 索引迁移。
