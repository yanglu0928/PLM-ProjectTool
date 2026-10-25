# SOL-06-A16-P04：Review List Repository 与授权服务

日期/版本：2026-10-19 / `0.1.0-dev.0`。状态：`REVIEW_LIST_SERVICE_PASS`；本项只完成内部只读服务，不表示 HTTP、Windows Inbox、正式 Subject 信任或 Gate/Pilot 已通过。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `SOL-06-A16-P04`|
|输入基线|冻结 REVIEW_LIST、CR-RVW-004、P02 DTO/加密游标、P03 Migration 0166|
|前置任务|稳定排序与 PENDING reviewer 候选索引已实库通过；读取 Subject Registry 与 Project 授权事务边界已存在|
|涉及模块|Review list Application/Repository、Project policy、单元与 Win11/PG 验收|
|涉及实体|只读 Review/活动 Round/当前 actor Assignment/Decision 最小投影；不创建或修改业务事实|
|涉及 API|不挂 Router；冻结 URL/请求/响应仍无运行变化|
|涉及权限|新增 Project `REVIEW_LIST`，四类当前成员只读；每个候选仍经 Subject Owner identity 和活动固定版本授权|
|验收标准|all/my_pending、稳定分页、隐藏短/空页续取、actor-only Assignment、撤权与异常失败关闭、零写入、全量与 wheel|
|风险|assigned reviewer 被误作授权；隐藏候选游标停滞；Owner 故障伪装空结果；候选连接泄露他人意见|

## 实施结果

- 新增 `SqlAlchemyReviewListRepository`：在调用方活动事务内以 0166 顺序读取 `page_size+1` 个候选，只关联当前活动 Round、当前 actor Assignment 及该 Assignment 的决定；`my_pending` 从 actor 的当前 PENDING Assignment 生成候选。Review 根以共享锁保持本次 Owner 检查期间不被终态切换。
- 新增 `ReviewListService`：每页重验 License、Session 与 `REVIEW_LIST` Project current member；验证 Repository 的项目、严格降序、无重复、页上限和 `my_pending` 形状，然后对本页实际消费的每个原始候选调用 Subject Owner。identity 或活动固定版本明确无权即隐藏；Owner 抛错、畸形 proof 或 Repository 破坏合同均失败关闭。
- 每次最多消费 `page_size` 个原始候选，第 `page_size+1` 个只证明仍有下一页；续页位置取最后一个已消费原始候选而不是最后一个可见项。因此全部被隐藏时可返回空 `items`、非空 `next_position` 和 `has_more=true`，不会反复扫描同一候选。
- 列表不返回其他 reviewer、意见、主题正文、来源或内部锁；终态只投影 Review identity，不伪造活动 Round。服务返回前再次验证 License，不写 Audit。

## 验证证据

- 定向：`24 passed, 845 subtests passed`，覆盖四角色、隐藏/空页、原始位置、终态 identity-only、my_pending、候选畸形、Project/Session/License/Owner 错误、二次 License 与 Repository 边界。
- 首轮定向只因策略矩阵总数仍为 171 而失败；新增唯一 `REVIEW_LIST` 后将精确总数更新为 172，角色仍为四类成员只读，重跑全绿。
- Windows 11 / PostgreSQL 18.6：真实 Session、Project member、SQL Repository 与 Migration 0166 下完成三页 `all`、两角色 `my_pending`、两条 Subject 隐藏形成空首页继续、终态保留、决定后待办消失但 all 仍保留、跨项目/失效 Session/License/成员停用/Owner 故障和前后数据库快照零写入；`alembic check` 无新操作。Subject Owner 与 License 为明确的合成测试夹具，不作为正式信任。
- 后端全量：`3773 passed, 3 skipped, 5899 subtests passed`；新增模块 `compileall` 通过。
- Python 3.13 开发 wheel：1421 项，List Service/Repository 均入包，SHA-256 `12ed65acae76390aa158e1cb86f600252e32d584dbf57758a2d2ec55466e94fa`；不是 Pilot/Release 包。

## 兼容、升级、回滚与未完成项

- 无新 Migration、列、依赖、License 或历史数据变化；需先部署已通过的 0166。关闭/不装配后续 Router 并撤内部模块/策略可回滚，既有 Review 历史不受影响。
- 列表是当前授权下的任务发现，不是固定快照；并发新建/决定可能改变后页，刷新即可。assigned reviewer 只参与候选筛选，不能绕过 Project 或 Subject Owner。
- 默认关闭的 HTTP、严格 query/响应映射、Windows 专用 cursor key 与组合、前端 Inbox、Edge 和正式规模性能仍未完成；Gate 3、Pilot 和正式发行状态不变。

Next：`SOL-06-A16-P05` 实现默认关闭的冻结 REVIEW_LIST HTTP，严格解析 `view/page_size/cursor`，编码加密续页并验证响应白名单与安全错误映射；不提前接入 Windows 生产组合。
