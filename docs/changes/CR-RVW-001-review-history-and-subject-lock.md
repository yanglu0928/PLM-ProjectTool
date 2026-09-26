# CR-RVW-001：统一 Review 历史与主题锁物理化

2026-09-26；RVW-01-A01/RVW-02-A01；状态 DESIGN_REGISTERED；依据冻结 DM-01/DM-02、SC-01/02/03、API-02 与 AF-02 Review Engine，原 `64cdf09` 不覆盖。按用户持续授权先记录差异/风险/验证再实施。

实施检查点：RVW-02-A01 多人决定/撤回纯领域进度值已实现并完成单测/后端回归；状态 DOMAIN_IMPLEMENTED / SCHEMA_APPLICATION_PENDING。进度值不是完整 ReviewRound Aggregate，不能凭构造结果发布客户批准，详见本项报告。

后续检查点：RVW-01-A02 已实施八表 ORM/独立 0034，状态 SCHEMA_IMPLEMENTED / APPLICATION_PENDING；隔离完整集合/历史/身份锁/Scope/并发/回滚验证见 A02 报告。TraceLink 来源无锁/摘要列的实施前细化已写入设计：观测版本 0 明确 SOURCE_NO_LOCK_V1，固定关系内容另算摘要，不伪称来源锁版本。上条设计/领域检查点作为历史保留；实际角色资格/主题 Owner/客户批准服务仍未验。

## 证据与时序澄清

代码中尚无 Review 实现；Gate 的 REVIEW_ROUND UUID/APPROVED 为结构，不能当实际批准。SC-01 已要求 reviews/rounds/assignments/decisions/subject_snapshots，但缺运行中主题锁和状态变更追加事件的具体物理化。

DM-01 RVW-02 和 DM-02 明确所有 Assignment 都完成才汇总，AF-02 同样要求所有人处理完。API-02 的“任一 RETURN 则本轮 RETURNED”按完整集合的结果规则解释，不作为提前终结/解锁：一条 RETURN 但其他待处理时仍 IN_REVIEW；全部完成则任一 RETURN→RETURNED、全 APPROVE→APPROVED。这是澄清接口摘要，不改冻结请求字段/路径/结果枚举；不隐式免除剩余确认人。

## 比较与采用

拒绝只保存一个 approved 布尔值/覆盖旧决定；拒绝把主题 JSON 正文复制进评审，或直接让 Review 写业务 Owner 表；拒绝遇到首条 RETURN 提前解除锁。采用两既定 Aggregate、固定不可变主题版本/指纹/受权引用、Assignment/Decision 追加历史、Round 可受控状态投影、同事务主题锁与追加事件。

具体八表设计见 `docs/review/review-persistence-design-v1.md`。SC-01 五张既定表细化，再增三个 owned 辅助表 `rvw_subject_snapshot_refs`、`rvw_subject_locks`、`rvw_round_events`，不增加业务 Aggregate/Scope。只保存引用与观测，不保存客户正文或 Secret。需独立后续 migration，当前未有 0034，不声称 Schema 可用。

## 边界、迁移与回滚

真实 Session/License/Project/CSRF/角色/当前成员事实由受权应用检查。PROJECT 发起人为 PM，确认人为策略限定客户确认人；GLOBAL 只能走明确全局策略，不能借用项目 PM 权限。未注册 Subject Owner 拒绝，不能凭 UUID/指纹长度认定存在或批准。

主题 Owner 必须事务内锁固定版本和逻辑身份，禁止 IN_REVIEW 修改该 Version 或创建替代 Draft；Review 不跨模块直连/修改业务表。正式批准版本由 Owner 消费结果更新，Round APPROVED 本身不直接发布业务事实。撤回保留已产生的 Decision，不把未处理人伪造成已决定。

未来 migration 从实际 head 0033 新建 owned 表，不修改旧 Gate 或虚构 Review，历史合成 refs 不自动回填。GLOBAL nullable Project 使用 generated scope_project_key/Scope check 与复合父键，避免 NULL 导致跨 Scope FK 跳过；ProjectId 真实 FK 保留。非空历史 down 拒绝，空表才降级；应用回滚不装配服务并保留历史。

## 验证与风险

纯领域先验证唯一 1～N ReviewerSet、每人一次最终决定、RETURN 实质意见、全部完成才汇总、终态/撤回封口、旧决定保留、UUID/UTC/不可变/跨轮拒绝。此形状不证明 reviewer 资格或客户批准。

Schema 必须空/有数据 up/down/re-up、ORM parity、Scope/GLOBAL 父键、唯一活动轮次/身份锁、Assignment/Decision 归属、完整快照/提交后封口、状态/锁/Audit/事件/幂等原子、并发决定/撤回与伪造批准拒绝。应用再验证真实权限/撤权/跨项目/失效 License/Owner 版本及主题锁/持久幂等、HTTP/性能/覆盖率、Gate 所用批准查询。

当前 Owner 业务表未完成，真实 Review 服务/客户评审不能运行；先补 Platform Core，不跨 Phase 编造主题或审批。Server 2025 未验、Debian 13 暂不验证，Gate 3/发行仍未通过。
