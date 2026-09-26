# Subject Owner 固定送审合同 V1

2026-09-26；RVW-02-A04；来源 AF-02/DM-02/API-02/CR-RVW-001、0034 和送审前置 V1。语言级内部 Port，不改冻结外部请求或 Schema。

## 固定输入与结果

`ReviewSubjectStartRequest` 绑定当前受控 PROJECT Review 根、Actor、预分配的新 Round ID、固定业务 Version ID 和完整唯一 reviewer IDs。根 policy/逻辑主题由已授权当前 Repository 读取，不能使用客户端快照。IN_REVIEW 根拒绝再次准备；其他状态仅结构可表示，真实 Owner 与应用服务必须核验版本状态/退回新版本/If-Match，不由 DTO 自动准许。

`PreparedReviewSubject` 完整绑定原 Request、32 字节内容摘要、proof_schema_version=1、UTC verified_at、完整逐人主题资格结果与固定来源观测。`require_binding` 不接受不同 Actor/Project/Review/逻辑主题/policy/Version/Round/确认人集合，禁止复用旧或其他主题的准备结果。引用仅同项目 Evidence/Trace 或明确 GLOBAL Evidence，身份唯一；所有引用验证时间不得晚于完整 Subject 观测时间。Trace 的来源版本 0 明示无锁字段，不是签名/真实批准。

空依据只能在结构上表达，不意味着满足业务来源要求；实际 Owner 按具体业务 Version 核验来源/完整性，不能把空集合或非空 hash 当完整 Evidence。旧观测不自动变成当前资格，Sources 在实际 start 事务还需各 Owner/数据库重验。

## 真实 Owner 职责

`prepare_start_in_transaction` 必须在调用方事务：当前 Actor 管理权、逐人对具体主题/版本确认资格、实际固定内容/来源、可送审状态、真实逻辑身份与版本锁绑定 review/round/version。锁必须阻止版本内容/child 修改和创建替代 Draft，不仅是 Review 表的 ACTIVE UUID。

`assert_active_lock_in_transaction` 在准备与持久化/提交之间独立复核实际 Owner 锁及版本绑定；缺失/变化直接失败，不能使用常量 True、客户端所谓 proof、process-only lock 或仅 DTO 构造成功替代。准备/检查使用相同 tx，Owner 写在完整 Review/Audit/receipt 故障时回滚。终态消费/释放锁另立合同，不让 Review 直接修改 Owner 表。

本项没有默认生产实现或恒真适配，没有实际业务 Owner Schema/状态锁/来源解析。内部 DTO 是受控 Port 的数据形状，不是安全签名、客户批准或 Gate 证明。没有公开 HTTP/动态 Owner 注册；缺真实 Owner 不开放接口。

## 下一任务与验收

RVW-02-A05 受控内部完整 start-round：真实 Session/CSRF/Project/账户资格、当前 Review 行锁/If-Match、上述 Port、0034 完整八表/STARTED、Audit/receipt 同事务。新 Scope/角色/依赖/Migration 不在此合同。真实 Owner 缺失时仅隔离合成协议验收，不能标业务审批通过；完整与既有成员写/撤权的并发锁顺序需单独实测。
