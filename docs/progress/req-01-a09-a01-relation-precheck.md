# REQ-01-A09-A01：RequirementRelation 编码前核查

日期：2026-10-07。结论：`REQ_01_A09_A01_RELATION_PRECHECK_PASS`。下一项：
`REQ-01-A09-A02` RequirementRelation Schema/Migration0121。

## 基线结论

- REQ-04是独立PROJECT append-only/supersede Aggregate，不能用通用TraceLink替代；TraceLink用于跨模块
  可追溯边，RequirementRelation用于需求图业务约束，两者生命周期与关系类型不同。
- 每端保存`requirement_id + requirement_version_id + project_id`并使用复合外键，不能只验证两个裸Version
  UUID存在。端点可引用同一项目任意固定Version；冻结基线未要求只能引用APPROVED，首版不擅自收紧。
- 关系类型固定为`DEPENDS_ON / PARENT_OF / RELATED_TO / DUPLICATES / CONFLICTS_WITH`；状态固定为
  `ACTIVE / SUPERSEDED / REVOKED`，终态不可恢复，SUPERSEDED必须精确指向同项目replacement。

## 图与并发边界

- DUPLICATES、CONFLICTS_WITH按`(requirement_id.bytes, version_id.bytes)`升序保存；反向重复会命中同一
  ACTIVE唯一边。冻结基线只点名这两类，对RELATED_TO不擅自改成无向边。
- DEPENDS_ON、PARENT_OF禁止自环，并分别在同一Project、同一relation_type、ACTIVE子图内执行有界递归
  反向可达检查；两类不混合推断。RELATED_TO及两类对称边只执行一般非自关系约束。
- 所有写操作由ProjectAuthorization的write policy先锁Project行，因此同项目图写串行；跨项目可并行。
  仅靠READ COMMITTED递归或触发器无法阻止两笔并发互补边，不把这种实现描述为已验证DAG。
- Version内`dependencies`是固定文本声明，不自动创建、更新或撤销REQ-04边；需要业务关系时必须显式命令。

## 实施拆分

1. A02：Migration0121与ORM，组合FK、规范端点、ACTIVE唯一索引、不可变字段及单向终态守卫；业务入口关闭。
2. A03：create/list Owner，补齐四个冻结授权策略中的CREATE/LIST、同事务端点证明、DAG检查、幂等/Audit。
3. A04：revoke/supersede Owner，旧边锁、replacement排除旧边的DAG检查、终态原子转换、幂等/Audit。
4. A10：统一接入冻结`/api/v1/projects/{project_id}/requirement-relations` HTTP和Windows显式组合。

回滚：A02空历史可降0120；存在关系历史后只向前修复。无API、Schema、程序、依赖、Secret、客户数据或
外发变化；Gate3/UAT/发行不因本核查关闭。
