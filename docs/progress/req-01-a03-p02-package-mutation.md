# REQ-01-A03-P02：Package 元数据与 Requirement membership Owner

日期：2026-10-07。结论：`REQ_01_A03_P02_PACKAGE_MUTATION_PASS`。下一项：`REQ-01-A03-P03`
Requirement 元数据及 DEFER/REJECT 决定 Owner。

## 实现与边界

- 新增 Package PATCH、ADD、REMOVE 三类内部命令；PM、ImplementationMember 可写，统一执行
  Session/CSRF、License、当前 Project 角色、持久幂等、Audit、行锁和 ETag 版本栅栏。
- membership 命令一次限 1～200 个唯一 UUID，规范排序后参与请求指纹；ADD 要求 Requirement 全部属于
  同项目且尚未加入，REMOVE 只删除 membership，绝不删除 Requirement。
- Migration0113 开放 Package 受约束元数据/状态修改和 membership 增删，Requirement Root 更新仍关闭；
  新增不可变命令结果快照。每次成功写只递增一个 Package 版本，重放返回首次成员集合而非当前集合。
- Package 状态转换固定为 ACTIVE/RESTRICTED 双向、任一非归档状态可归档、ARCHIVED 终态；只有 ACTIVE
  可增删成员。无命令历史可降0112，有历史拒降并要求向前修复或备份恢复。

## 验证

- Windows 11 / PostgreSQL 18.6：0112→head→0112→head、两次 drift、真实Session/三角色、License、
  PATCH/ADD/REMOVE、异载荷、跨项目、重复成员、同版本双线程竞争、Audit故障回滚恢复、首结果跨后续变更
  重放、伪造快照拒绝、撤权后历史拒读、移除后Requirement计数不变及有历史拒降全部通过。
- 定向26项通过；后端全量2973项通过、3项既有环境跳过；compileall通过。
- 开发wheel共1120项，包含P02应用/仓储与Migration0113，SHA-256
  `db92bf02a3a7b3b37c272b3d6efd3f2bfb2e3af05a899c06e571cae726f8bdd3`，不是正式发行包。

无公开API、前端、依赖、Secret、客户数据或外发变化；P03、A04 Version、HTTP/UI/Workflow、
Gate3/UAT/发行仍待。
