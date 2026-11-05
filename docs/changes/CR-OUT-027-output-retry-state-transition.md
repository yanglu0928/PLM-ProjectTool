# CR-OUT-027：Output 可重试生成失败的原子回队

- 日期：2026-11-05
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P31
- 来源：P30已完成不可重试失败原子收敛；retryable Job失败仍未与Output generation state统一
- 状态：编码前检查 PASS_WITH_LIMITATION，可实施
- 基线：冻结 Jobs retry/failure Owner 与 OutputRequest状态；无Schema/Migration/API/default挂载变化

## 决策

对活动Output lease下的固定白名单瞬时错误，Output Owner在共享UnitOfWork按Output→Jobs顺序锁定和验证绑定，调用Jobs.retry_or_fail(retryable=true, delay_seconds=30)，然后根据Jobs Owner的实际结果同步Output：若Job为RETRY_WAIT，Output回到QUEUED并清除当前execution ref、保留未完成状态；若最大attempt耗尽导致Job为FAILED，Output同步置FAILED并写completed_at。两种结果均递增Output lock_version并写SYSTEM Audit。

worker只能提交白名单代码；不可自选retry flag或delay，不持久化自由文本。Audit失败使Job attempt/lease/Output/Audit整体回滚。该项只覆盖状态调度，不在事务内执行插件、渲染或文件操作。

## 方案比较/差异

- 仅将Job转RETRY_WAIT：会使Output仍标GENERATING，重领后无法启动，排除。
- Output自行写Job ORM：越过Jobs Owner边界，排除。
- 复用Jobs retry_or_fail并在同UOW更新已锁Output：保持Owner边界，选择。
- 固定退避30秒和错误码集合，不开放worker传入重试周期；attempt耗尽映射FAILED。无需迁移。

## 风险、回滚与验收

- 风险：调度仅证明持久状态一致，非实际Worker重启/插件能力。
- 回滚：移除新Owner/repository/tests/verifier/smoke hook；无数据迁移。
- 验收：PG18真实lease验证第一次失败转RETRY_WAIT+QUEUED、固定30秒、ref清除、attempt/Audit原子；attempt耗尽转Job/Output FAILED；错worker/stale token/非白名单拒绝；Audit异常回滚。后端全量/wheel、父包PG smoke和hosted全链。
- 所有执行只用GitHub hosted Windows D盘runner，不用用户本机/C盘；无客户资料、外部API、插件执行或文件生成。P25仍独立BLOCKED_DIAGNOSTIC，不与P31结果混淆。


## 首轮 hosted 验收偏差（2026-11-05，修正前登记）

- Run [41961855190](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41961855190) 后端4047 tests/wheel与前端/build通过；父包PG smoke启动PostgreSQL成功并已完成P26-P30 verifier，P31 verifier在导入阶段失败：脚本误引用不存在的旧P30 Repository 模块路径。未执行P31业务断言、未留下验证数据库变更；独立P25仍initdb失败。
- 修复计划：删除P31 verifier未使用的P30失败Owner/Repository导入，仅保留P31真实重试Owner与仓储；经hosted PG smoke完整验证回队/耗尽/rollback后才关闭P31。
