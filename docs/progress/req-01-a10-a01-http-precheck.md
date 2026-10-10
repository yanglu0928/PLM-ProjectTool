# REQ-01-A10-A01：Requirement HTTP 与 Windows 组合前置核查

日期：2026-10-07。结论：`REQ_01_A10_A01_HTTP_PRECHECK_PASS`。下一项：
`REQ-01-A10-A02` Package/Requirement identity 读取 Owner。

## 编码前检查

```text
当前Phase：Phase 2 Platform Core；Gate 3保持BLOCKED
当前WBS：REQ-01-A10-A01
输入基线：冻结API-01/API-02/API-04、REQ-01～REQ-04、CR-REQ-001、Migration0111～0121
前置任务：A02～A09 Schema、identity/version/relation Owner与Requirement Review Subject已通过
涉及模块：requirement application/infrastructure/api；review；platform Windows显式组合
涉及实体：RequirementPackage、Requirement、RequirementVersion、RequirementRelation、Review/Round
涉及API：22个冻结Requirement Operation；不增加、删除或改名Operation
涉及权限：当前Project member读取；冻结写角色；ProjectManager送审；Cookie/CSRF/License/项目隔离
验收标准：逐Operation映射Owner差距、HTTP/游标/ETag/幂等边界、组合顺序、回滚与真实PG验证
风险：缺读取Owner即挂Router、以通用Review两次HTTP代替原子送审、Relation状态命令漏If-Match、游标密钥复用
```

## 现状与差距

- 冻结22个Operation均无Requirement Router，`create_app`和Windows生产组合也没有Requirement注入点。
- 已有17个可复用内部行为：Package create/patch/add/remove，Requirement create/patch/defer/reject/archive，
  Version create/list/get/validate，以及Relation list/create/revoke/supersede。
- 缺少`REQ_PACKAGE_LIST/GET`和`REQ_LIST/GET`四个当前成员读取Owner；不能用写命令的首次结果或直接ORM
  查询代替当前授权投影。
- 已有`REQ-03 + REQUIREMENT_ALL_V1` Review Subject与终态消费，但缺少冻结
  `REQ_VERSION_SUBMIT_REVIEW`的Session/CSRF/License/持久幂等原子业务编排。前端不得串行调用通用Review
  create/start暴露中间DRAFT Review。
- Package、Requirement、Version和Relation四类列表各需独立HMAC cursor用途/密钥，绑定Session、Project、
  父资源、page size与稳定位置；不得复用Project、Survey、Handover或彼此的密钥。
- Package/Requirement变更和Version create已有expected lock version。Relation revoke/supersede虽只允许
  ACTIVE v0，但命令DTO尚未承接API-01强`If-Match`；A07必须显式传入并验证`expected_version=0`，不能只
  依赖数据库状态碰巧等价。
- Requirement通用Review决定Router的Windows Subject Registry尚未注册Requirement Owner；仅接业务送审
  Router不足以让Review后续批准、退回或撤回完成业务终态消费。

## 实施分解

|WBS|唯一问题|验收边界|
|---|---|---|
|`REQ-01-A10-A02`|Package/Requirement读取Owner|四个LIST/GET、当前成员、项目隔离、稳定keyset、最小安全投影、零业务写|
|`REQ-01-A10-A03`|Package六个冻结HTTP|独立Package cursor、严格DTO、强ETag/If-Match、持久幂等、默认关闭|
|`REQ-01-A10-A04`|Requirement identity七个冻结HTTP|独立Requirement cursor、决定Evidence引用、强ETag/If-Match、默认关闭|
|`REQ-01-A10-A05`|Version四个普通HTTP|独立Version cursor、完整固定快照、create/validate最小投影、默认关闭|
|`REQ-01-A10-A06`|`REQ_VERSION_SUBMIT_REVIEW`原子编排|固定`REQUIREMENT_ALL_V1`，当前事实重验与Review create/start/receipt同UOW|
|`REQ-01-A10-A07`|Relation四个冻结HTTP|独立Relation cursor、规范端点、终态强If-Match、201 replacement语义、默认关闭|
|`REQ-01-A10-A08`|Windows显式组合与真实PG|只读模式七个GET；写模式全22 Operation并注册Requirement Review Subject|

送审V1沿用现有Review能力可保存的字段：请求精确包含`reviewer_ids/policy_ref/due_at/submission_note`，
`policy_ref`固定`REQUIREMENT_ALL_V1`，当前Schema未保存调度/备注，因此后二者必须显式为`null`；非空
失败关闭，不能静默丢弃。各HTTP任务需建立冻结合同增量与合同测试，不修改原冻结路径或角色。

## 验证、兼容与边界

本项静态交叉核对冻结API-01/API-04、Requirement源码、授权策略、Review Registry、`create_app`及Windows
组合。无程序、Schema/Migration、公开API、依赖、配置、Secret、网络或客户数据外发变化；未运行新增
程序测试，不把后续22 Operation或Windows组合标为通过。Router均应显式注入且默认404；停止注入即可
回滚新流量，既有Requirement/Review/Audit/receipt历史不得删除。正式cursor密钥、发行信任锚、
Windows Server 2025、性能、Gate 3、UAT和发行仍按总状态跟踪；Debian 13实机按用户指令跳过。
