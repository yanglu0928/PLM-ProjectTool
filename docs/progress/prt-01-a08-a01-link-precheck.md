# PRT-01-A08-A01：RequirementPrototypeLink 编码前核查

日期：2026-10-08。结论：`PRT_01_A08_A01_LINK_PRECHECK_PASS`。下一项：
`PRT-01-A08-A02` RequirementPrototypeLink Schema/Migration0134。

## 基线结论

- PRT-05 是 prototype 模块拥有的 PROJECT append-only/supersede Aggregate，不能用通用 TraceLink 或
  PrototypeVersion 自带的 RequirementRef 代替。RequirementRef 固定版本输入，TraceLink提供跨模块追溯，
  RequirementPrototypeLink表达正式覆盖关系，三者必须一致但生命周期不同。
- 每端保存逻辑身份、固定Version及Project，并使用复合外键证明同项目归属。CREATE只接受当前 Approved
  RequirementVersion及当前 Approved PrototypeVersion；后续上游升版不改写历史Link。
- PrototypeVersion必须已拥有完全相同的RequirementVersionRef；Link不能向已批准Version补录一个原本不在
  其不可变输入集合中的需求。当前Artifact可访问性/完整性、Prototype Review批准事实也必须由Owner重证。
- purpose固定为`ILLUSTRATES / VALIDATES / ACCEPTANCE_REFERENCE`；状态固定为
  `ACTIVE / SUPERSEDED / REVOKED`，终态不可恢复，SUPERSEDED精确指向同项目ACTIVE replacement。

## Coverage V1 与一致性

冻结基线只规定“覆盖范围和未覆盖项”，没有冻结JSON字段。为避免自由文本被误判为完整覆盖，首版固定
`coverage_schema_version=1`和有界JSON对象：

```json
{
  "covered_acceptance_criterion_refs": ["uuid", "..."],
  "uncovered_acceptance_criteria": [
    {"acceptance_criterion_ref": "uuid", "reason": "non-empty bounded text"}
  ]
}
```

- 两个集合均按UUID字节序规范化、内部唯一且互斥；每个未覆盖项必须有规范化后的非空理由。
- 两个集合的并集必须恰好等于固定RequirementVersion的AcceptanceCriterion全集，不允许漏项、外来项或仅报
  汇总数字。至少一个验收条件被覆盖；若全部未覆盖，应走显式NOT_REQUIRED/范围决定而不是建立虚假ACTIVE
  Link。
- 覆盖判断不是单表投影：读取/创建/替换时重证ACTIVE Link、PrototypeVersion owned RequirementRef、固定
  RequirementVersion验收条件、Prototype当前Approved指针、批准Review及全部Artifact当前可访问性/完整性。
  历史Link仍保留，但当前事实失效时Coverage报告必须失败关闭，不能改写历史状态冒充有效。

## 生命周期、唯一性与并发

- 同一Project、Requirement逻辑身份、Prototype逻辑身份和purpose最多一条ACTIVE Link；同一对身份可用不同
  purpose表达不同语义。CREATE自然重复返回既有ACTIVE Link，异载荷由幂等指纹/收据拒绝。
- REVOKE仅允许ACTIVE→REVOKED。SUPERSEDE只允许同一Requirement身份、Prototype身份及purpose，允许端点升到
  新固定Version或修订coverage；完全相同规范载荷禁止自替代。改变purpose必须撤销旧Link并显式创建新Link。
- 所有写操作先取得Project写锁，再锁定两端身份/Version与旧Link；同项目写串行，跨项目可并行。替代在单一
  事务中先终结旧ACTIVE唯一键、再插入预生成ID的replacement，并由延迟FK/闭包在提交时证明旧指针和新
  ACTIVE行同时成立，不暴露中间状态。
- LIST按UUIDv7 Link ID倒序keyset，只返回本项目固定引用、purpose、coverage、状态和替换指针；项目成员每次
  重证权限。写操作固定ProjectManager、ImplementationMember，并复用License、Session/CSRF、Audit和持久
  幂等收据。

## 实施拆分

1. A02：Migration0134与ORM；复合端点FK、Coverage JSON基础约束、ACTIVE逻辑对/purpose唯一索引、不可变
   字段、终态守卫、replacement延迟闭包；业务入口保持关闭。
2. A03：CREATE/LIST Owner；补齐四项冻结授权策略，事务内两端、Review、Artifact、owned RequirementRef与
   AcceptanceCriterion全集证明，Coverage V1规范化、幂等/Audit及分页。
3. A04：REVOKE/SUPERSEDE Owner；旧Link锁、同身份/同purpose replacement、原子终态转换、持久重放及故障
   回滚证明。
4. A09：统一接入冻结四个`/api/v1/projects/{project_id}/prototype-requirement-links` HTTP Operation，并做
   Windows 11/PostgreSQL 18真实组合；不在A08偷开公开Router。

回滚：A02空Link历史可降0133；产生Link历史后只允许前向修复。应用Owner可停止装配关闭新写，既有Link、
receipt和Audit必须保留。本核查为纯文档，无Schema、API、代码、依赖、Secret、客户数据或外发变化；
Gate 3、UAT、Server 2025、发行及可使用程序包不因本项关闭，Debian 13按用户指令跳过。
