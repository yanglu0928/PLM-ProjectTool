# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P02：PlanVersion验证报告合同与纯评价器

日期：2026-10-26。结果：`PLAN_VERSION_VALIDATION_PURE_CONTRACT_PASS`；仅纯逻辑内部通过，不含数据库/授权/HTTP或Gate结论。

## 编码前检查

- 当前Phase：Phase 2 Platform Core。
- 当前WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P02`。
- 输入基线：冻结API-04 `ValidationReport(valid, blocking_issues, warnings, coverage_summary, checked_at)`、A06-P01及PlanVersion typed input。
- 前置任务：A06-P01完成静态前置核查并确定只读审计/幂等方向；PlanVersion原子创建及固定版本完整读取已内部通过。
- 涉及模块：仅Plan Application纯验证合同/评价器与单元测试。
- 涉及实体：PlanVersion不可变快照、WBS/FS依赖/排除、调用方传入的当前Approved Solution/Requirement固定来源集合。
- 涉及API：无HTTP变更；仅实现冻结Validate返回值的内部纯合同。
- 涉及权限：本项无授权职责；来源引用参数必须由后续已授权 Owner 在事务内证明，不接受客户端提供。
- 验收标准：确定性结构层级/DAG/日期校验；基于可信当前固定来源计算需求/方案映射、排除与缺口；旧/多余引用作为阻断问题；报告字段、计数与时间严格校验；无I/O/时钟读取/状态修改。
- 风险：冻结合同未定义警告目录或逐问题对象结构；因此先用稳定问题码数组，未有安全降级依据时warnings为空；不擅自附加来源正文/内部数据库字段。

## 实施结果

- 新增`PlanVersionValidationSnapshot`、`PlanVersionCoverageSummary`、`PlanVersionValidationReport`及纯函数`evaluate_plan_version`。
- 稳定问题码涵盖空/重复/断层WBS、非法日期、非法依赖/DAG环、Milestone WBS引用、需求/方案旧来源、映射与排除冲突以及未覆盖来源；排序后输出，`valid`与blocking集合一致。
- Coverage分别统计当前来源总数、WBS映射数、显式排除数和未覆盖数；以外部传入的当前批准来源集为权威，不以旧PlanVersion中的固定refs冒充当前资格。纯函数接收显式`checked_at`，不读系统时钟；报告保持版本状态不变。
- `warnings`当前返回空元组：冻结基线未给出可安全降级的Plan警告条件。后续若提出新警告类别，需有冻结语义/决策依据。
- 更改仅限Plan Application纯合同及单元测试；无Migration、API、License、Vault、数据库或外部网络变化。

## 验证

- 定向Plan输入/验证/创建Owner回归：`16 passed, 3 subtests passed`。
- 全量后端：`4139 passed, 3 skipped, 6190 subtests passed`。
- `compileall`与`git diff --check`通过。未发现项目venv提供可执行Ruff，因此不报告Ruff结果。

## 兼容与后续

- 无数据迁移；回滚可撤掉新模块及测试，无历史影响。
- 下一项：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P03`，实现内部受权验证Owner：锁定持久PlanVersion快照、当前Session/License/Project PM或IM授权、批准来源/覆盖复证、Audit与同事务通用幂等回执；暂不挂HTTP。
- 尚未验证PostgreSQL组合、事务授权/审计/幂等、HTTP、Windows组合、正式信任、Server 2025/Debian、Pilot/Gate/Release。
