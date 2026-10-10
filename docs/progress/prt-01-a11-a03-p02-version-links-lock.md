# PRT-01-A11-A03-P02：当前批准 PrototypeVersion 与 ACTIVE Link 锁定输入

日期：2026-10-08。状态：内部输入验证通过；A11-A03 真实聚合资格 Owner 与 Workflow 接线未完成。

编码前检查：承接 A11-A03-P01 的项目共享锁围栏与 `CR-PRT-005`。本项只处理 Prototype 模块当前 Approved Version、批准终态投影、Approval Trace 清单及 ACTIVE Link，不改数据库、冻结 API 或他模块写路径。验收是 ACTIVE 根须有精确当前 Approved Version；评审批准结果、版本固定内容摘要及 Trace 清单相符；全部 ACTIVE Link 只能指向这些当前版本，Coverage 投影必须规范。空原型/无关旧关联、陈旧指针、缺失清单或不规范覆盖失败关闭。

实现：在同一调用者事务读取并共享锁定 Version、批准终态结果、Trace 清单和全部 ACTIVE Link；复用既有不可变 Version 重建及 Trace 活动计数证明。NOT_REQUIRED 根不得有当前批准版本或活动 Link。返回锁定输入，不向 Workflow 输出 PASS。后续 Owner 仍须重证当前 Requirement、实际 Review、来源 Evidence、固定 Document、Trace 端点、Audit，以及纯范围/覆盖策略；不能把本项投影当充分条件。

验证：定向 4 项（批准投影、陈旧版本/Review/清单、旧版 Link、全 NOT_REQUIRED 的多余 Link）通过；后端全量 3222 项通过、3 项条件跳过、4791 个子例通过。当前无 PostgreSQL 实例级验证，A11-A05 才能形成正式 PG/HTTP 结论。兼容性/升级/回滚：无 Schema、API、生产依赖或迁移；停止装配新只读适配器即可回滚，历史不变。

TraceLink：`CR-PRT-005` → `DEC-20261008-1073` → `PRT-01-A11-A03-P01/P02` → A11-A03 聚合 Owner → A11-A04 接线 → A11-A05 实例验证。
