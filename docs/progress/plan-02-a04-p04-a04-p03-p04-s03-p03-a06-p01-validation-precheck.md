# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P01：PlanVersion Validate 编码前核查

日期：2026-10-26。状态：`PRECHECK_COMPLETE`；本项仅静态核查和内部实施边界，不是Validate功能或Gate结论。

## 编码前检查

- 当前Phase：Phase 2 Platform Core。
- 当前WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P01`。
- 输入基线：Gate 2冻结API-04 `PLAN_VERSION_VALIDATE`、API-01 Session/License/CSRF/Idempotency/Audit约束、PlanVersion完整快照输入及A02/A03/A04/A05的持久化/创建/读取实现。
- 前置任务：PlanVersion原子创建、固定版本完整快照读取和WBS keyset读取已在Windows 11/隔离PG18合成环境内部验收；此事实不代表正式信任或Gate通过。
- 涉及模块：Plan Application/Infrastructure/API、Project Authorization、Approved Solution Input Proof、Audit/Idempotency、Windows显式组合。
- 涉及实体：不可变PlanVersion/WBS/依赖/里程碑/排除快照、当前Approved Solution/Requirement覆盖证据、通用Audit与幂等收据。
- 涉及API：冻结`POST /api/v1/projects/{project_id}/plans/{plan_id}/versions/{plan_version_id}:validate`；空请求体；`200 ValidationReport(valid, blocking_issues, warnings, coverage_summary, checked_at)`；不改变版本状态。
- 涉及权限：Session + CSRF + 有效License + 当前ProjectManager或ImplementationMember授权；版本必须在给定Project/Plan下存在；按项目资源隐藏不存在/越权对象。
- 验收标准：固定版本读取不可变快照；重新校验层级、DAG、日期及当前Approved Solution/Requirement/Solution覆盖；缺失或陈旧来源作为blocking issue返回而非伪装VALID；无状态写入；同Key/同请求审计回执可重放，异请求冲突；真实PG18/HTTP权限、来源变化和Audit/收据原子性验证；默认应用不挂载。
- 风险：冻结合同只给出报告最小字段，未枚举issue code、warning目录、coverage_summary内部指标，也未给出幂等历史专用表。不能以新列/新状态改写冻结Schema，也不能把Plan创建时的纯结构校验误称为当前来源有效性。

## 核查结果与实施决策

- `parse_plan_version_draft`在创建时已拒绝层级/父节点不一致、重复WBS、非法依赖与DAG环、缺失固定引用和基本日期矛盾；因此Validate必须对持久化快照重新检查，以防数据库完整性/历史版本/来源资格变化，不能只复用“构造成功”事实。
- `ApprovedSolutionInputProofService`可复核当前Approved Outline指针、已批准版本和Review、验证事实、当前Coverage及固定Section/Spec资格；Plan创建Owner已使用它。Validate应在本事务持锁/重查PlanVersion后调用该证明，并以固定Plan WBS/排除快照计算Requirement、Solution覆盖，不把AI或客户端摘要当事实。
- Capability Validate已提供相邻实现范式：空体、CSRF、幂等键、当前授权/License、目标不可变快照、同事务Audit和通用IdempotencyReceipt；用Audit事件身份作为首次报告证明，并验证重放仍绑定当前actor和目标版本，无需新增Schema。Plan侧必须做自己的Scope和Source Proof，不能复用Capability授权身份。
- 本系列顺序采用“只读验证 + Audit/幂等回执”，不写PlanVersion状态、不持久化派生报告副本；稳定问题码与Coverage计数由Plan模块拥有。`warnings`当前无已证实可安全降级的项时返回空数组；阻断型来源/覆盖缺陷只能出现在`blocking_issues`，验证请求本身的认证/格式/资源错误仍走错误Envelope。
- 本项未发现必须修改冻结API/Schema/Scope的差异，故不新增CR；字段语义细化仅限冻结报告DTO的兼容投影，issue code将通过版本化常量/测试稳定。若实现中发现必须增加持久层来支撑可靠审计/重放，先暂停该编码片并登记CR，而不是直接改迁移。

## 兼容、回滚与后续

- 本项无代码、Schema、API、License、正式业务数据或外发变化；无迁移/升级动作。回滚即撤本前置记录，不影响运行行为。
- 下一项：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P02`，实现PlanVersion验证报告纯合同与快照评价器（层级/DAG/日期/覆盖问题码），不接数据库、HTTP、Audit或外部网络；先补完整输入/边界测试。
- Server 2025、Debian 13、正式公钥/目标服务账户信任、Pilot、Gate 3及正式Release仍未验。
