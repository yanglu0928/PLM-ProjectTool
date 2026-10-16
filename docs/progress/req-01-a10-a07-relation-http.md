# REQ-01-A10-A07：RequirementRelation 四个冻结 HTTP

日期：2026-10-08。结论：`REQ_01_A10_A07_RELATION_HTTP_PASS`。下一项：
`REQ-01-A10-A08` Windows 显式组合与真实 PostgreSQL 总链。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A10-A07
输入基线：冻结API-01/API-04、REQ-04、CR-REQ-001、Migration0121
前置任务：A09 Relation Schema/Owner生命周期、A02读取授权均PASS
涉及模块：RequirementRelation application/api/cursor、Project授权、Audit
涉及实体：RequirementRelation、RequirementVersion固定端点、IdempotencyReceipt、AuditEvent
涉及API：REQ_RELATION_LIST/CREATE/REVOKE/SUPERSEDE
涉及权限：Project member读取；ProjectManager/ImplementationMember写
验收标准：专用签cursor、DAG/规范端点、终态强If-Match、持久幂等、安全错误、默认关闭
风险：跨资源cursor重放；终态只依赖数据库碰巧为v0；非法环；replacement语义投影错误
```

## 结果

- 新增独立 `RequirementRelationCursorCodec`，以独立32字节key和`requirement-relations`
  family绑定Project、Session摘要、page size和UUIDv7 relation位置，拒绝跨上下文重放。
- 新增opt-in Router实现LIST/CREATE/REVOKE/SUPERSEDE；CREATE与SUPERSEDE严格接收固定Version
  端点和relation_type，输出不复制Version正文，四个Operation保持冻结路径与角色。
- Revoke/Supersede内部命令新增`expected_version`并固定只接受0，HTTP强制`If-Match: "v0"`；
  expected version纳入请求指纹，不能以数据库当前状态碰巧等价替代冻结并发控制。
- 保留Project行锁串行图写、DEPENDS_ON/PARENT_OF分类型DAG、DUPLICATES/CONFLICTS_WITH
  规范端点、ACTIVE到终态单向转换和持久回放；Supersede 201返回replacement ACTIVE关系。
- 定向Owner/cursor/API 13项通过；完整后端3066项通过、3项跳过。
- Windows 11/PostgreSQL 18.6真实四HTTP、双页cursor、创建/替代/撤销回放、DAG拒绝、对称
  规范、If-Match、角色/License、Audit、receipt及Alembic drift通过。
- 开发wheel共1164项，SHA-256
  `3ec77a59bb36cef9a91e3f31fcd6664f3d781d4d10b67b56a693eb033f3166c9`。
- 无Schema/Migration、依赖、Secret、客户数据或外发变化；正式cursor密钥与显式组合留A08。
