# PRT-01-A03-A01：Prototype identity 与范围决定 Owner 前置核查

日期：2026-10-08。结论：`PRT_01_A03_A01_OWNER_PRECHECK_PASS`。下一项：`PRT-01-A03-A02`
Package/Prototype创建Owner与不可变首结果。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：PRT-01-A03-A01
输入基线：CR-PRT-001、Schema0122、冻结七个identity/scope写Operation、API-01控制位
前置任务：PRT-01-A02 PASS；五表Owner全部关闭
涉及模块：prototype application/infrastructure、project authorization、license/session/csrf、audit/idempotency
涉及实体：PRT-01 Package、PRT-02 Prototype、NOT_REQUIRED决定与固定RequirementVersion范围
涉及API：本项无Router；内部命令形状必须能无损承接后续冻结HTTP
涉及权限：PM/ImplementationMember普通写；CustomerManager仅MARK_NOT_REQUIRED；PM可全部范围决定
验收标准：真实权限、Project锁、强ETag、持久重放、同事务Audit/结果、决定范围当前事实重验
风险：PATCH幂等错配；SET_MEMBERS删除业务对象；PM决定被伪称客户确认；半套决定或历史漂移
```

## 命令差距与决定

|冻结Operation|现状|实现边界|
|---|---|---|
|PRT_PACKAGE_CREATE / PRT_CREATE|仅Schema初态直写窄门|A02增加持久幂等首结果、授权和Audit|
|PRT_PACKAGE_PATCH|冻结无`I`|A03仅强If-Match，不生成幂等receipt；不可变command result闭合提交|
|PRT_PACKAGE_SET_MEMBERS|冻结含`I/M`|A03原子替换同项目成员集合，不删除Prototype|
|PRT_PATCH|冻结无`I`|A04仅强If-Match；修改name，不通过通用PATCH静默改变范围决定|
|PRT_ARCHIVE|冻结含`I/M`|A04单向终态，历史Version/Decision/Link保留|
|PRT_MARK_NOT_REQUIRED|冻结含`I/M`|A05原子写Root、决定、固定范围、Audit、结果和receipt|

- `ACTIVE / RESTRICTED` 不在冻结公开命令中获得独立切换语义；首版普通 PATCH 不新增未冻结的安全状态机。
  RESTRICTED保留给后续有权威来源的系统安全动作，不能用备注或前端选择直接设置。
- NOT_REQUIRED命令的受权PM/CustomerManager和当前Session构成真实人工决定，保存confirmed_by，不把PM决定
  描述为客户确认。可选Review/Round必须为同项目Approved且快照匹配决定内容，只作附加证明；没有Review时
  Workflow仍可按实际决定角色/范围规则判定，不制造合成Review。
- A05必须锁Project、Prototype及全部受影响Requirement/Version，要求Version当前Approved且集合非空、
  去重、规范排序；写Root状态、唯一决定、有序引用、持久首结果、Audit和receipt在同一事务完成。无Link/
  无PrototypeVersion不是NOT_REQUIRED决定。

## 子项拆分与边界

1. `A02`：Package/Prototype create DTO、Service、Repository、Migration0123不可变首结果。
2. `A03`：Package PATCH/SET_MEMBERS、Migration0124不可变命令结果与集合闭包。
3. `A04`：Prototype PATCH/ARCHIVE、Migration0125不可变命令结果与终态闭包。
4. `A05`：MARK_NOT_REQUIRED当前事实证明、Migration0126原子决定结果与可选Review重验。

本项纯设计/静态对账，不修改Schema、程序、API、依赖、Secret或外发；不声称Owner、正式范围决定、
Prototype API/Review/Workflow、Gate 3、UAT或发行通过。
