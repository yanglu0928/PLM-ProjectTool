# REQ-01-A12-A04-A01：Workflow 聚合资格写链

日期：2026-10-08。结论：`REQ_01_A12_A04_A01_AGGREGATE_WRITE_CHAIN_PASS`。下一项：
`REQ-01-A12-A04-A02` Windows 生产组合注册。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A12-A04-A01
输入基线：CR-REQ-004、DEC-1014～1017、Requirement聚合资格Owner/Repository
前置任务：REQ-01-A12-A03-A02 PASS
涉及模块：workflow qualification preview、checklist record、stage transition
涉及实体：只读取聚合资格并写既有Workflow历史；不改Schema
涉及API/权限：扩展既有内部item白名单及响应variant；鉴权、License和项目权限不变
验收标准：复数Version/Review/Evidence不丢失，两个Checklist item同Scope，REQUIREMENT→PROTOTYPE失败关闭
风险：聚合证据重复不一致；两个item范围漂移；旧单Subject响应被破坏
```

## 实现结果

- 资格预览新增Requirement严格variant，返回规范化的`requirement_version_refs`、`review_round_refs`和
  去重`evidence_refs`；Handover、Survey原有单Subject字段和响应保持不变。
- Checklist写入接受聚合资格，将每个真实ReviewRound及所有当前Evidence写入既有不可变Basis；相同
  Evidence ID若观察值不一致立即拒绝，不选择或合成一个“主Review”。
- 阶段推进新增`REQUIREMENT -> PROTOTYPE`，固定复核`REQUIREMENT_FORMAL_VERSIONS`与
  `REQUIREMENT_ACCEPTANCE`；两次资格必须同类型、同Project、同Stage并共享聚合coherence key。
- 只扩展通用写链能力，未在Windows生产组合中注册Requirement Owner，因此本项不改变生产可达行为。

## 验证、兼容与回滚

- 预览、Checklist记录、阶段推进及HTTP合同定向28项通过；后端全量3083项通过、3项按既定条件跳过，
  source/tests `compileall`通过。
- 开发wheel共1167项，SHA-256
  `a32865d93e60eaef38000d53b803b9ccab9175024792df620a8ab63adc4b1347`。
- 无Schema/Migration、依赖、Secret、客户数据或外发变化；撤销四个通用Workflow文件中的Requirement
  variant和对应测试即可回滚，既有Handover/Survey历史与响应不变。
- Windows 11生产注册、真实PostgreSQL/HTTP组合、前端和Edge分别留A04-A02、A05～A07验证；本项不
  声称Gate 3、UAT、三平台兼容或发行通过。
