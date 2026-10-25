# PLAN-02-A04-P04-A04-P03-P04-S03-P01：PlanVersion 输入模型与纯校验

日期：2026-10-26。结果：`PASS_SCOPE_LIMITED`。仅内部输入解析/纯校验；无数据库写入、HTTP挂载或业务事实创建。

## 编码前检查

|项目|结论|
|---|---|
|Phase / WBS|Phase 2 / `PLAN-02-A04-P04-A04-P03-P04-S03-P01`|
|输入基线|Gate 2冻结DM-05/API-04、CR-PLAN-002、CR-PLAN-003、0186 Schema、S03前置核查|
|前置任务|0186首片Schema已PASS_SCOPE_LIMITED；S03已拆成输入/纯校验与原子写Owner|
|涉及模块/实体|Plan application输入DTO；WBS、固定 Requirement/Solution/Prototype/Evidence refs、FS依赖、Milestone、排除项|
|涉及API|无HTTP变化；仅解析与未来冻结 `PLAN_VERSION_CREATE` 对齐的输入语义；拒绝未知键|
|涉及权限|不做权限判定、不访问数据库；后续Owner必须同事务重验授权和来源|
|验收标准|严格键集和类型；稳定规范化/指纹；日期、层级、同版本FS DAG、lag、重复引用、显式排除、output失败关闭负例|
|风险|冻结合同未给所有字段的字段级限制；本片采用与0186列约束一致的规范化/上限，但不替代业务白名单/Approved来源证明|

## Changed / Tests

- 新增 `plan_version_input.py`：严格字典键集、UUID/date/文本规范化、不可变类型化 DTO、顺序敏感 canonical JSON 和绑定 Project/Plan 的 SHA-256 请求指纹。
- 校验WBS父节点存在且层级连续、最多6级；依赖仅FS、同版本端点、禁止自环/重复/成环，非零lag必须提供单位与理由；校验日期成对/顺序、里程碑WBS引用、排除目标、固定引用唯一性。
- 非空 `output_refs` 返回 `OUTPUT_REFERENCE_UNAVAILABLE`，不接收伪引用。Prototype refs 在输入模型中以独立固定 PrototypeVersion typed ref 保留；因当前Schema缺少其持久目标，已登记CR-PLAN-003，Owner实现前先补0187。
- PlanVersion输入专属测试：7 passed；初次全量回归4117 passed、3 skipped、6153 subtests passed。追加Prototype关系Schema测试后，合并定向18项通过；最终全量回归结果以STATUS为准。
- API、ORM、Migration、依赖、权限、业务数据均未改变。无外发资料或客户数据。

## Known issues / Next

- P01纯校验不复核项目内成员ACTIVE状态、来源Approved指针、Review、Coverage、Trace、License或授权；这些只允许由后续同事务Owner完成。
- 当前现有类别、协作角色、Calendar code仅作格式规范化，实际允许集合须由后续受控Registry决定。Prototype refs 在0187实施前不允许被持久化。
- Next：`PLAN-02-A04-P04-A04-P03-P04-S03-P02` 已按CR-PLAN-003独立实施，见对应进度记录；之后进入同事务 PlanVersion 聚合写Owner。Pilot/Gate/Release状态不变。
