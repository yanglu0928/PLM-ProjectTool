# CR-OUT-012：冻结 OutputRequest 取消的原子 Owner 与可选 HTTP 接入

- 日期：2026-11-04
- 状态：P15/P16编码前核查通过；P16实现可开始
- 来源：冻结 API Contract V1 / API-03 的 `OUTPUT_REQUEST_CANCEL`
- 基线：不修改 API 路径、角色、数据模型、DB Schema 或现有 Migration；沿用持续授权，实施与验收证据按提交追溯

## 问题与证据

冻结合同要求创建者或 ProjectManager 可取消 OutputRequest；现有 OUTPUT_REQUEST_CREATE、GET、LIST 已有可选适配器，但没有 OUTPUT_REQUEST_CANCEL Owner/HTTP 路由。Job 通用取消有显式 Owner registry 与 Job 自身 If-Match；其 dispatcher 在关闭 hint 读取 UOW 后调用 Owner 自有写 UOW，因此不能直接套用来完成 OutputRequest 与 Job 的同事务状态更新。

现有创建流水线把 Job 写为 `owner_module=output`、`job_type=OUTPUT_GENERATE`、`scope=PROJECT`，payload绑定 OutputRequest/ContextSnapshot；OutputRequest 自身持有 Project、创建者、job_ref、request_state 与 lock_version。API-03 只列出取消操作的控制项和 `CANCEL_REQUESTED/terminal` 结果，没有另行冻结响应字段，因此本实现维持公共 JSON envelope 与最小状态结果，不新增合同字段或公开 Job 内部引用。

## 方案与范围

P16 在 Output application/infrastructure/api 内实现可注入的取消 Owner 与 opt-in POST。Output 保有 OutputRequest 状态和项目/创建者授权；Job 状态只能经 Jobs 提供的显式 transaction-scoped Owner Port 操作，禁止 Output 直接写 Jobs 表或打开第二个 UOW。一个外层事务内重新验证当前 Session、License、CSRF、Project/创建者或 ProjectManager 权限，按固定顺序锁定并核验 OutputRequest、已绑定的 `OUTPUT_GENERATE` Job，再同步两个状态、追加 Audit 与幂等结果。新命令使用 OutputRequest 实际 lock_version 校验强 If-Match；同键重放先按当前权限/项目归属核验，再读取幂等结果所绑定的请求并返回当前 `CANCEL_REQUESTED` 或终态，不以更新后的版本误拒首次命令重放。拒绝跨项目、错 Job 类型/owner、无来源、未知 Job owner 和版本/载荷冲突；未知异常失败关闭。

严格 JSON body 仅接受 `reason`，不接受 JobId、ProjectId、actor、路径或状态。日志/Audit不保存正文、Secret或内部路径。GET/Cancel 路由仍由显式组合者注入，默认与正式产品组合不挂载。本 CR 不做插件执行、实际文件生成、Route 默认启用、生产信任或用户数据处理。

## 风险、回滚与验证

- 竞争风险：Worker 与 Cancel 同时推进时，必须遵循已存在的 Job 行/租约锁与版本事实；P16 实施前核查 Output 相关完成/失败 Owner 的锁序和审计事务，无法证明同序时拆分并先修正范围，不引入猜测性版本。
- 状态风险：只允许 `PENDING/RETRY_WAIT` 直接终止与 `RUNNING` 请求取消的既有 Jobs 语义；Job 与 OutputRequest 不一致、缺少绑定或终态不一致时拒绝写入并记录安全冲突。
- 回滚：撤销 opt-in Router 与新 Owner 代码即可；不删除请求、Job、Audit、幂等历史。不改 Schema/Migration。
- 验收：Hosted Actions 定向应用/HTTP/Repository 测试；真实 PostgreSQL 18 隔离正负状态行、错误 If-Match、并发/同键重放及 Audit 失败回滚；随后后端全量/wheel与既有全仓 hosted 回归。所有本地不运行要求继续遵守。

## 编码前结论

P15 证实必须以 OutputRequest lock_version 为公开并发版本，由 Output 在其事务内协调 Jobs-owned cancellation Port；通用 Job dispatcher 的两个 UOW不满足原子状态更新。P16 开始前需核查终态 Worker/审计锁序并保持显式 Owner。未发现需要改写冻结路径或角色；如直接 PG18验收无法在单任务完成，必须降级为 `PASS_SCOPE_LIMITED` 并明示限制，不得虚报 Gate/Pilot/Release。


## P16 编码前终态/锁序复核（2026-11-04）

- 检查 `modules/output` application、infrastructure、API 目录与其关联测试，未发现生成执行、成功/失败终态写入Owner或Output专属取消Owner。当前可证事实仅到P12创建入队、P13/P14读取；因此没有现存Output/Job双行锁序可复用。
- 决定：新取消Owner按单向 `OutputRequest → Job` 锁序，在同一显式UOW完成强版本比较、Job取消状态命令、OutputRequest同步、Audit和幂等写入；如任一Job绑定/状态与Output不符则全事务失败。RUNNING只设置双方的CANCEL_REQUESTED请求，不宣称Worker已确认；PENDING/RETRY_WAIT遵循JobOwner的立即取消规则。未来生成Worker必须遵循同一资源锁序并以既有fencing lease处理取消。
- 这是对原计划“核查现有终态Owner锁序”的证据性偏差：被核查Owner当前不存在，故锁序改为本CR显式规定的前向兼容约束。实施前先记本节，不涉及冻结架构/契约/Schema或生产事实改变。
- 诚实限制：当前无Output执行/终态Owner意味着本轮可以验收取消请求存储与状态同步，不能验证实际生成进程终止或RUNNING取消确认。Hosted PG18并发和事务测试只证明数据库边界，不代表真实Worker执行。

