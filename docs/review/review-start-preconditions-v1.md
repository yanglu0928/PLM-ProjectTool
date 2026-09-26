# 送审前置与确认人资格 V1

2026-09-26；RVW-02-A02；来源 AF-02/DM-02/API-02 REVIEW_START_ROUND、CR-RVW-001/0034。此文件细化内部实现，不改冻结 API/Schema/角色。

## 完整送审事实

送审由真实 Session/CSRF 的 ACTIVE Project PM 发起，必须核对当前 Review Scope/逻辑 Subject/server policy、If-Match 与同事务幂等。确认人集合为 1～N 个唯一非零 User ID；集合顺序不改变资格。先锁真实 ENABLED User，再锁同项目 ACTIVE/effective/not-ended 成员和 ACTIVE 部门；角色需符合服务器 Owner 政策。部署管理员或 ID 存在不产生项目资格，SUSPENDED/REMOVED/未生效/已停用/跨项目必须拒绝。

成员资格只是必要条件。Owner 必须逐人核验对该具体逻辑主题/固定 Version 的实际确认资格（包括适用部门/范围），不能由 Project 角色或任意 policy_code 冒充。首版客户确认流程可选择 CM/CustomerMember，但冻结 API 也允许 PM/其他角色的 assigned 决定；因此基础资格组件接受仅服务器传入的明确角色子集，不擅自将全部评审改成仅客户或所有成员。实际 Owner 政策尚待实现；当前合成 CUSTOMER_ALL_V1 字符串不是生产政策注册。

Owner 同事务锁定主题逻辑身份和实际不可变版本、核验可送审状态/来源和内容摘要，并保证 IN_REVIEW 禁止修改版本内容/child 或创建替代 Draft。Review owned ACTIVE subject lock 不足以证明真实 Owner 已锁。Owner 产出 actor/project/subject/version、固定内容 SHA-256/proof version/UTC、受权 Evidence/Trace refs 和资格结果；缺字段/未知 Owner 默认拒绝。来源 observed state/version/hash 必须由各 Owner 实际读取，不能从请求或历史快照直接复用。Trace 0 来源版本显式无锁列，不当实际批准证明。

新 Round/Assignments/Subject Snapshot/refs/身份锁、Review 指针/计数、STARTED Event、Audit/receipt 完整同事务；任何故障全回滚，不提交 PENDING 半套。首条 RETURN 后维持 IN_REVIEW，全部处理才汇总。退回必须新业务 Version/新 Round；撤回历史决定/pending 保留；送审重试重新校验当前权限，不重复加人/锁或 Audit。

## 锁序与实施拆分

已有通用 Auth 写适配先锁 actor User，若随后持 Project 再等待其他 reviewer User，可能与成员创建/停用产生反向等待。新增送审前置需窄 Auth enabled-users 共享锁：先锁全部候选账户（UUID 排序），再访问 Project 当前事实。送审 Session/CSRF 读取应使用共享 User 锁；不得沿用会提前持 actor User 排他锁的通用写适配并声称全链无死锁。

推荐相对顺序：Auth 当前 Session/User 与全部 reviewer User 共享锁 → Project 当前成员/部门/PM → Review/receipt → Subject Owner 身份/版本/资格 → Round → Sources（依据 Owner 固定次序）。完整 start 服务实施时必须实际验证与现有成员写/撤权路径的竞争；独立资格组件测试不能替代此验收。现有 Review read/create 功能不在本任务顺手改造。

RVW-02-A03 先完成真实账户 + Project 成员基础资格内部组件，返回固定 ID/角色，不返回用户名/账户敏感值；角色子集只来自受控服务调用，未知/空策略拒绝，无 GLOBAL 或管理员回退。本组件不承担交互 Actor/License/主题权限，不挂载 HTTP；Owner/完整 start 仍是独立待办。

之后 RVW-02-A04 明确 Subject 固定快照/真实身份锁 Port，RVW-02-A05 内部完整 start-round/幂等/审计及隔离数据库验收；真实业务 Owner 必须实现后才开放 API。无真实 Owner 时转向独立 Phase 2 工作，不跨 Phase 编造业务成果。无新迁移/依赖；停用内部组件即可回滚，保留历史。
