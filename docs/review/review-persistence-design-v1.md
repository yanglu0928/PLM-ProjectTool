# Review owned 持久层设计 V1

2026-09-26；RVW-01-A01；CR-RVW-001；设计由 RVW-01-A02/0034 实施，隔离 Schema 验收见 A02 报告；受权应用/真实 Subject Owner 尚未实施。

## Aggregate 与表

保留 RVW-01 Review、RVW-02 ReviewRound 两个冻结 Aggregate。所有 ID 为 UUIDv7，UTC timestamptz(6)，指纹 bytea/32 bytes，锁 bigint，状态 text/白名单。PROJECT project_id 非零且真实 Project FK；GLOBAL project_id NULL。复合父子关系用生成 scope_project_key=coalesce(project_id,zero UUID) 配合 scope，零值只作物理 GLOBAL 键，不作为实际 Project 身份；每层另有精确 Scope check。

|表|职责及关键规则|
|---|---|
|rvw_reviews|review_id、scope/project、主题逻辑 type/id、server policy、DRAFT/IN_REVIEW/APPROVED/RETURNED/WITHDRAWN、active_round_id、lock/创建更新操作者；主题身份不变、不持正文|
|rvw_review_rounds|round_id/review_id/Scope、round_no、固定 version_id、PENDING/IN_REVIEW/APPROVED/RETURNED/WITHDRAWN、started_by/at、lock；同 Review 单调编号，最多一个 IN_REVIEW；终态封口|
|rvw_review_assignments|round+reviewer 唯一、PENDING/DECIDED 投影；reviewer/归属固定，至少一个；不把撤回的未处理人改成 DECIDED|
|rvw_review_decisions|Assignment/Reviewer/round/Scope 复合关系，一人一最终 Decision，APPROVE/RETURN、UTC/comment/trace；RETURN 实质意见，追加不可改写|
|rvw_subject_snapshots|每轮唯一固定 Subject Identity/Version/Scope/指纹/Owner 证明版本/观测时间；Round 开始事务创建并封口，不保存正文|
|rvw_subject_snapshot_refs|Snapshot 所用 Evidence/Trace typed refs/Scope/观测版本/状态/指纹/时间；真实可用类型用身份 FK，缺 Owner 不假造存在；和 Snapshot 同事务追加后封口|
|rvw_subject_locks|同 Scope/逻辑主题最多一 ACTIVE 锁，关联 Round，ACTIVE/RELEASED、获取/释放时点；身份/历史保留；阻断修改版本与替代 Draft，不只是版本键锁|
|rvw_round_events|STARTED/DECISION_RECORDED/COMPLETED/WITHDRAWN 追加事件及 Actor/trace/前后锁、结果引用；不复制 comment/正文；与投影/Audit 同事务|

Review.active_round_id 指向本父的 IN_REVIEW Round；非 IN_REVIEW 时为空，历史由独立 Round 查。循环引用需 deferred FK/提交核对，不以关闭 FK 解决。PENDING 为冻结内部状态，公开 start-round 原子产生完整 IN_REVIEW/Assignment/Snapshot/Lock，不暴露半套 pending。

0034 实施前细化：现有 TraceLink 没有 lock_version/content_fingerprint 列，不能伪称读到了来源锁。TRACE_LINK refs 的 observed_lock_version 固定为 0（明确 SOURCE_NO_LOCK_V1），数据库对固定身份/Scope/源目标 Version/关系 tuple 的 JSONB 数组 UTF-8 文本计算 SHA-256，并锁真实 TraceLink/比对 ACTIVE 及内容；这不是 Trace 版本或签名。Evidence 则锁真实行、保存其实际锁版本/指纹。PROJECT Snapshot 只允许同项目 Trace 和同项目/显式 GLOBAL Evidence；GLOBAL Snapshot 只能 GLOBAL refs。后续服务仍需 Owner 受权解析，不凭 Hash 认定实际业务批准。

## 决定、撤回和再评审

只允许当前 IN_REVIEW Round 的本轮 assigned reviewer 提交最终决定；实际 Actor 从 Session，不由请求决定。唯一 Assignment/Decision 防重复；重放走持久幂等，不能把新的 Key 当覆盖旧意见。已退回但有待处理人时保持 IN_REVIEW 与主题锁，全部完成才按所有决定汇总。终态不能再决定或撤回。

PM 受权撤回只在 IN_REVIEW：保留所有已提交决定，剩余 Assignment 仍 PENDING，Round/Review WITHDRAWN、清 active 指针/释放身份锁并写事件/Audit。退回后修改必须新业务 Version、新 Round/Assignments，历史意见不重用；撤回后开启下一轮的版本/Owner 条件在 start-round 应用前置独立检查，不默认为需要新字段或可复用批准。

批准结果只供主题 Owner 消费；不让 Review 直接修改 current approved version，不让 Workflow 用孤立 APPROVED 字符串绕过 Snapshot/Scope/Owner。GLOBAL 策略独立，不把管理员当任意项目审批人的替身。

## 原子、并发、验收与迁移

应用锁顺序应先当前身份/Project 授权事实，后 Subject Owner 身份/固定版本与 Review/Round；所有命令使用一致顺序，具体交叉 Owner 锁由应用 Port 前置验证，不能以描述代替死锁验收。锁获取/释放、决定/状态、事件/Audit/收据一事务；任一故障全回滚。最终 decide 与 withdraw 并发只有一个状态转换成功，不能丢失已决定历史或提前释放锁。

拟从 0033 增量，不写旧 Gate/合成 UUID 的历史假 Review。先备份；空库 up/down/re-up、有其他模块数据升级/原值保留、GLOBAL FK/完整性/非法状态/并发/不可变/非空 down 必验。非空 owned 历史拒绝 down，应用可关闭新入口回滚并保留事实。

RVW-02-A01 纯领域和 RVW-01-A02/0034 隔离数据库验收已完成。PENDING 枚举保留，当前 Schema 的可提交新 Round 必须原子完整 IN_REVIEW，不提供半套 PENDING 提交。尚未运行实际 API/权限/Subject Owner/覆盖率/性能验证，无公开 Review 接口，不判实际客户 Review/Gate PASS；后续接受控 Query/Owner/受权服务。
