# RVW-01-A02 Review 八表持久层

2026-09-26；0.1.0.dev0；CR-RVW-001；结果 WINDOWS_ISOLATED_SCHEMA_PASS。

## 编码前检查与实施

Phase 2；WBS RVW-01-A02；输入冻结 DM-01/DM-02、SC-01/02/03、API-02、CR-RVW-001、八表设计与已验证多人纯领域。前置设计/变更/迁移回滚/验证已记录；仅 Review owned 八表/ORM/独立增量 0034，不改 API/角色/技术栈/依赖/业务 Scope。正式客户资格/Subject Owner 未具备，不通过此任务开放审批入口。

reviews、review_rounds、assignments、decisions、subject_snapshots、snapshot_refs、subject_locks、round_events 保存固定身份/版本/观测与追加历史、状态投影；GLOBAL 与 PROJECT 都有真实 Scope check/非空 generated scope_project_key 复合父键，GLOBAL 不能借 NULL 绕过 FK。active_round 循环 FK deferred，新 Review 只能 DRAFT、完整新 Round 原子 IN_REVIEW，轮次连续、最多一个活动 Round/逻辑 Subject 锁。

Decision 每人一次，版本/创建事务由数据库强制，Assignment/决定/Review 与 Round 锁计数/状态/事件/Subject 锁提交一致；全人处理后才汇总，提前批准或首个 RETURN 提前终结拒绝。退回原版本不能直接开新轮，终态封口，撤回保留已有决定及 PENDING Assignment。起始 Assignment/Snapshot/引用/身份锁仅创建事务追加，提交后不能补人/引用；事件只能记录当前更改事务，不能事后补成功历史。

Source Evidence 与 TraceLink 实际共享锁/初次观测/提交重核；Evidence 实际版本/摘要，Trace 无来源锁版本，固定 0 明示 SOURCE_NO_LOCK_V1、固定关系 tuple 的 JSONB 数组 UTF-8 SHA-256，不把它当签名或隐含版本。未来合法来源状态变化不改历史，实际最终批准仍需 Subject Owner 受权重验；Schema 的合成 Subject UUID/操作者 User 身份不证明客户资格。

## 实际验收

Windows 11/Python 3.13/PostgreSQL 18.6；`validation/rvw-01-a02-review-schema/verify.py` 随机隔离库 PASS，清理只针对脚本自建库。

- 空库 up/0033 down/re-up；已有 Project/Workflow 数据升级原样保留，不造 Review；ORM parity 无 pending 操作。非空历史拒绝 down，拒绝后 head 0034/八表及 Sources 完整快照不变。
- 完整 PROJECT/GLOBAL 初态/启动/固定 Snapshot/真实 Evidence/Trace 引用；半套 Assignment/Snapshot/锁/Review 指针/Event、跨 Scope/Project/未知父/错误 round_no/初态/来源版本/摘要/重复人拒绝。GLOBAL→其他 GLOBAL Round 的 active 指针经真实复合 FK immediate 校验拒绝，非单靠 BEFORE 检查；实际八个 scope_project_key 为 ALWAYS generated，GLOBAL 生成零键，ref identity 生成值正确。
- 三人第一条 RETURN 后仍 IN_REVIEW/ACTIVE Subject 锁，全部决定后 RETURNED；缺 Assignment/投影/事件/锁释放、提前 APPROVED、陌生 reviewer、重复/空白/全角空白 RETURN 拒绝。退回后复用旧版本拒绝，新版本/新 Assignment 启动成功。
- 部分决定后撤回保留旧 Decision 和两位 PENDING，Subject 锁 RELEASED；GLOBAL 单人批准；同逻辑主题两 Review 不得同时持锁，释放后另一 Review 可获取。
- 真实 Trace 观测零来源版本/固定内容摘要，假版本/摘要拒绝；Trace 后续 REVOKED 保留历史 ACTIVE。该历史观测不是现在仍有效，测试不作为真实 Gate/批准；真实 Owner 会在应用阶段独立验证。
- 合成 Audit 故障在完整决定写后全回滚；实际 Audit 服务尚未调用。最后一条决定 vs 撤回并发只有一终态成功，另一个仅允许已验证 P0001/终态拒绝；两位不同 Reviewer 并发决定都保留、Round IN_REVIEW/锁版本 2，最后一位处理后 APPROVED/版本 3；不是把任意 SQL 错误当正确冲突。
- 来源 Evidence 在 start 提交前变化拒绝并全回滚；所有八表 DELETE/TRUNCATE CASCADE 拒绝，Decision/Snapshot/refs/Event UPDATE 拒绝；提交后补 Reviewer/terminal event 拒绝。数据库事件时间不得早于相关决定；真实时钟/License 来源仍待发行验收。

首轮发现 CHECK 名冲突与 PL/pgSQL IF 内 CASE 需要括号、验证脚本约束 schema 定位/元数据缩进问题，均修复后重跑；不把初次失败当 PASS。Alembic 对 generated default 的警告保留，额外实际验证 ALWAYS/生成结果与 Global FK，不能仅靠 metadata check 声称表达式验证。

完整后端 684 项无失败（新增 3 项 owned 表/复合父键/冻结 migration factory parity/保护契约测试，2 项既有符号链接环境跳过）。既有 Gate 固定记录、Checklist 当前查询/0032、0031 legacy 历史升级与受权初始化/Workflow GET/Windows 两模式 HTTP 脚本回归 PASS；旧降级失败后的 head 断言更新为实际 0034，原迁移保留。

开发 wheel 构建/包含 Review ORM/0034 PASS；SHA-256 `f2fcddbb90592c2922100ac69e9c54b562036048a40afa7bd0668f2f16d96c9d`。未测覆盖率/性能，不是正式安装程序包。

## 兼容、升级与后续

升级先备份，Alembic 至 0034；不修改旧业务/Gate/合成 refs，不将 UUID 自动回填成真实批准。新八表非空拒绝破坏性 down，空表可退 0033；应用回滚不装配审批入口，保留历史。不改变冻结 API 或真实角色授权边界。

无正式受权 Review 命令/Subject Owner/客户资格/审批 HTTP/状态证明供 Gate 接线；业务 Owner 版本锁也未验证，SQL 结构只保护记录，不宣称阻断真实 Owner 的替代 Draft。Server 2025 未验、Debian 13 暂不验证；Gate 3/正式发行仍未通过。

Next：RVW-01-A03 受控事务 Review/固定 Round 与 Subject Snapshot 查询 Port，区分历史观测与实际批准证明；随后完成真实资格/Owner/状态命令/审计幂等，不凭 APPROVED 字符串放行 Gate。
