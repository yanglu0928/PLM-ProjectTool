# REQ-01-A12-A03-A01：Requirement Workflow 当前事实 Owner

日期：2026-10-08。结论：`REQ_01_A12_A03_A01_OWNER_INTERNAL_PASS`。下一项：
`REQ-01-A12-A03-A02` PostgreSQL完整范围锁定Repository。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A12-A03-A01
输入基线：CR-REQ-004、DEC-1014/1015、A12-A02聚合合同、REQ-01现有Version/Review/Evidence事实
前置任务：REQ-01-A12-A02 PASS
涉及模块：requirement.application.workflow_qualification及纯单元测试
涉及实体：只读资格投影；不新增业务实体、Schema或Migration
涉及API/权限：无公开API、生产组合、路由或授权变化
验收标准：完整Scope、当前Version事实、逐Version批准、范围决定、Evidence漂移、五要素验收失败关闭
风险：漏掉未入Package需求；用历史校验代替当前事实；直接归档被误认为已有范围决定；集合顺序不稳定
```

## 实现结果

- 新增Requirement聚合资格Owner和内部锁定合同。完整项目Scope必须至少包含一个ACTIVE且当前、最新、
  APPROVED的RequirementVersion；全部Root数量必须等于正式版本与有决定的非活动Root之和，Package成员
  不参与缩小Scope。
- 每个正式Version在调用方事务内重跑`RequirementVersionCurrentValidator`，重新证明PROJECT Evidence，
  并精确匹配`REQ-03 + REQUIREMENT_ALL_V1`的APPROVED Review/Round/Version/内容指纹。
- DEFERRED/REJECTED必须匹配相同类型的不可变决定；ARCHIVED也必须能回溯到先前DEFER或REJECT决定。
  决定Evidence逐项重新证明；缺决定、Evidence漂移或跨项目内容一律统一失败关闭。
- `REQUIREMENT_ACCEPTANCE`额外复核每项至少一个完整的五要素验收标准；两个Checklist item共享同一
  Scope指纹、正式Version和ReviewRound集合，但保留各自资格指纹。
- Scope和成员按UUID规范排序并纳入稳定指纹，不使用当前时间或查询顺序作为业务指纹输入。

## 验证、兼容与回滚

- 新增6项Owner测试，覆盖双正式Version、独立Review、延期/归档决定、当前事实问题、Evidence/Review
  漂移、缺决定、错误决定类型、五要素缺失、空/乱序Scope和Checklist错路由。
- 后端全量3079项通过、3项环境跳过；source/tests `compileall`通过。
- 开发wheel 1166项，SHA-256：
  `1460b429de8c22d1f914ac3e0c1c192827d18788be8a8f479f23af32bd3651c8`。
- 无Schema/Migration、公开API、依赖、权限、Secret、客户数据或外发变化；A03-A02前没有生产Repository，
  A04前没有注册到Workflow。删除新增Owner和测试即可回滚，既有业务与Workflow历史不变。
- 当前不声称PostgreSQL锁定、生产接线、Checklist写入、阶段推进、真实Edge、Gate 3或发行通过。
