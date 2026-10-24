# AI-01-A05-P05-A03-P02：Provider 内部受权激活命令

日期/版本：2026-10-02 / `0.1.0.dev0`；依据：冻结 API-03、CR-AI-002、DEC-20261002-654。

编码前检查：Phase 2；P05-A02 当前激活资格证明及 P05-A03-P01 不可变首次响应 Schema 0056 已在隔离 PG18 验证。仅涉及 AI Application/Repository 内部激活命令、通用幂等收据与 Audit；不新增 Schema、公开 API、依赖或真实厂商调用。验收：当前部署管理员 Session/CSRF、License、最新成功探针、CONFIGURED/SUSPENDED 和强版本才允许 ACTIVE；同 Key 原响应重放不再次写状态；并发与审计失败整笔回滚。风险是重放在后续暂停后伪装当前 ACTIVE；返回值明确为首次历史结果，未来 HTTP 需保留原始 ETag，不代表当前状态或数据外发许可。

实现：请求校验后两次管理员鉴权，写事务内按 actor/操作/Key 原子预留收据。首次执行锁定当前 Provider/config/Secret/策略/最新探针，条件更新状态和版本，同事务写 USER Audit、0056 快照及收据，提交前再次检查 License。历史重放必须核对原 actor/Provider/期望版本及 Audit 绑定，直接返回不可变首次快照；不同 Key 在已 ACTIVE 状态不再隐式写入。

验证：Windows 11 隔离 PostgreSQL 18.6 真实 Session 管理员/普通用户、License 失效、同 Key 双并发一次结果、暂停后历史重放、不同 Key 版本冲突、Secret 停用、Audit 故障回滚及失败后成功重试；原 P05-A01 受权 Job 读链回归 PASS。定向单测 10/10；后端全量 1997 运行/3 跳过；开发 wheel SHA-256 `42c8c814b980d8ca622c81431950c504fb0f76559abda19dc8ef3e38717272a9`。隔离数据库已删除，临时 PG 服务已停止。无新 Migration；撤内部命令入口可回退，已提交历史不删除。

边界：此项没有公开 `AI_PROVIDER_ACTIVATE` HTTP 或 Windows 正式组合、未运行生产 Worker/真实外发；Server 2025/Debian、Gate 3/UAT/可用包仍待。下一 WBS：`AI-01-A05-P05-A03-P03` 可选激活 HTTP 边界。
