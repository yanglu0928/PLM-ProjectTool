# EVD-01-A04-P03-A08-P09：资格操作收据内部回查

日期：2026-10-01；Phase 2 Platform Core；结果：`WINDOWS_INTERNAL_PG_PASS / HTTP_OPEN`。

编码前检查：输入 CR-EVD-004、P07 收据只读 Port、P08 当前身份规则及 Evidence scoped 表；前置均已验证。涉及 Evidence Application Service/Repository 与现有 Platform 收据读取 Port；不改 ORM/Schema、公开 API、角色或依赖。验收为 License→当前 Session/CSRF/角色→scoped Evidence 存在→原 actor/project/operation/key 收据，完整匹配才 `COMPLETED`，缺收据 `UNCONFIRMED`，无 commit/预留或当前状态推断。风险是已提交首次收据不代表 Evidence 当前资格，也未证明浏览器回查路径。

新增最小 scoped Evidence 身份 `SELECT`（只读、no autoflush、无正文/锁）和内部 `EvidenceEligibilityOperationLookupService`。命令 DTO 不在 repr 输出原 Key/Session/CSRF；原 Key 仅计算现有 SHA-256 scope digest。当前角色先于 Evidence 和收据查询，异 Evidence 引用/结果类型/首次 HTTP 状态不匹配统一 `CONFLICT_IDEMPOTENCY`。事务退出回滚只读快照，无业务写入。GLOBAL 和归档历史授权由 P08 提供，普通项目跨 Scope 无旁路。

单元定向10项 PASS（含新增 Repository 1、Service 6）；Windows11/Python3.13 后端全量1,810项 PASS、3项既有环境跳过；开发 wheel SHA-256 `e1211558eaef2341c33ee6d41bb7d42a6af7c15bf7f8e16d767e2ceaf27e35bd`。扩展现有全新临时 PostgreSQL18/pgvector 脚本实际验收已提交/缺收据、错 Evidence/跨项目、许可失效、归档历史可回查但资格写拒绝、成员暂停拒绝；原资格 POST/并发/Audit 回滚矩阵回归退出0。脚本最终停止并清理其自建临时实例。仅使用合成资料和信任源，不代表正式目标账户或客户 UAT。

无 Migration；复用 `0015`。可撤内部服务和最小查询而保留已提交收据/审计回滚。公开可选 HTTP、Windows 显式组合、前端按操作号回查、真实浏览器/正式账户仍待，Gate3/可用程序包未通过。
