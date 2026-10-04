# CR-HND-003：Handover Action 生命周期与解决 Trace 完整性

日期：2026-10-05。状态：依据 `CR-EXEC-001` 持续授权批准分步实施。Gate 2 原冻结提交 `64cdf09`、DM-05/API-04 和Schema0098保留；本CR不新增公开Operation、角色或Root。

## 缺口与风险

Schema0098只开放`OPEN/v0`创建，response/evidence和后续状态全部失败关闭。冻结合同要求`OPEN -> IN_PROGRESS -> SUBMITTED -> VERIFIED -> CLOSED`及`CANCELLED`，且SUBMITTED不等于CLOSED；但尚未固定每次Root投影、append-only事件、owned refs、强ETag和Audit必须如何原子对应。

`ActionItem.resolution_trace_ref`引用现有TraceLink，而冻结TraceLink节点只包含版本化业务对象，不包含无版本的HND-03 Action。若关闭Owner只检查“同项目存在一条ACTIVE Trace”，任意无关关系都可能被冒充解决证据；HUMAN来源又没有固定AnalysisVersion可直接匹配。

## 选择

1. Schema0099只开放Owner可表达的精确状态与owned refs完整性，不开放HTTP：
   - `OPEN -> IN_PROGRESS -> SUBMITTED -> VERIFIED -> CLOSED`；
   - ProjectManager可从任一非终态取消到`CANCELLED`；`CLOSED/CANCELLED`不可复活，重新处理必须新建替代Action；
   - 每次转换Root `lock_version + 1`、`updated_by/updated_at`与唯一下一序号事件同事务，事件Actor/reason/time必须对应Root更新；
   - `submitted_at`、`verified_by/verified_at`、`closed_at/resolution_trace_ref`只在相应前向状态首次出现且不得清空/改写；CANCELLED时间由终态事件保存，不冒充`closed_at`。
2. SUBMIT至少固定一个当前PROJECT DocumentVersion响应和一条当前合格SUBMISSION Evidence；VERIFY必须在当前固定响应完整的基础上再固定至少一条VERIFICATION Evidence。任何后续状态不得删除或替换这些历史引用。
3. CLOSE只接受ACTIVE、同项目且由Trace Owner当前事实验证的解决关系：ANALYSIS_ITEM来源必须以该固定HandoverAnalysisVersion为source；HUMAN来源必须由受权项目成员显式选择一条目标为后续Survey/Requirement等正式版本的PROJECT Trace，并由Owner验证目标存在/状态及与本Action的人工关闭reason。Action通过自身`resolution_trace_ref`和关闭事件绑定该关系，不修改TraceLink历史。
4. 状态操作拆为Schema、PATCH、START、SUBMIT、VERIFY、CLOSE/CANCEL六个独立Owner任务；每项保持Session/CSRF、License、当前项目事实、强ETag、持久幂等、Audit和首次响应重放。HTTP/Windows组合在内部Owner全部通过后另行实施。

## 不选择

- 不以通用UPDATE一次开放所有状态，避免绕过固定响应、Evidence、Trace和权限。
- 不新增`HND-03` Trace节点或伪造Action版本；冻结Trace模型保持不变。
- 不把Review APPROVED、Item CONFIRMED、Action SUBMITTED或VERIFIED自动投影为CLOSED。
- 不在HUMAN来源缺真实下游Trace时伪造关系；此类Action可停在VERIFIED，待后续正式版本存在后关闭。

## 兼容、迁移与回滚

后续Schema0099替换0098守卫，不新增表/列和依赖，不改变冻结URL/DTO资源族。无后续状态历史可降回0098；存在非OPEN状态、额外事件、response/evidence或Root版本推进时拒绝降级并向前修复。应用回滚停止装配Owner，合法历史不删除。

## 验证计划

每个增量验证合法状态链、非法跳转/复活、事件序号与Root版本、固定Document/Evidence当前事实、Trace来源/目标/项目、权限矩阵、并发ETag/幂等、Audit/License失败整笔回滚、空库和有历史升降以及wheel解包。Gate只消费满足规则的VERIFIED/CLOSED，不因本CR或Schema存在而通过。
