# CR-JOB-001：恢复 Job/Outbox DEPLOYMENT Scope

日期2026-09-26；来源AUD-03-A01实际隔离库证据；执行依据用户2026-09-24/26持续授权及V1.1，实施前记录。范围Phase2审计导出必要平台前置，不跨Phase扩建AI任务。原冻结64cdf09及既有0035历史不重写。

## 冲突与方案

正式V2.1/总控V1.1及当前Skill已核对。冻结DM-04 Job scope允许GLOBAL/PROJECT/DEPLOYMENT，API-03管理面对应部署任务；现有0025和Job/Outbox ORM只允许GLOBAL/PROJECT。A01在0035真实复现两类部署插入被scope CHECK拒绝。

A：增量0036使无项目的GLOBAL或DEPLOYMENT均合法，PROJECT仍必须project_id；保持唯一键含scope、原FK/索引/状态/租约/幂等。

B：将部署导出映射GLOBAL或单独新队列；会混淆既有Scope或复制任务机制，不选。

选择A，属于补齐冻结模型的生产实现遗漏，不新增业务Scope/角色/依赖/公开API，也不赋予Admin项目访问。ParseJobRequest及Document enqueue继续仅GLOBAL/PROJECT；尚不存在部署任务公共创建接口。本项不新增Export snapshot或下载能力。

## 风险、升级、回滚与验证计划

- 0036仅替换两个scope CHECK，现有数据全部保留；table DDL有锁，生产升级仍人工备份/维护模式，AI不操作真实生产库。
- down先ACCESS EXCLUSIVE锁两表，再检查任一DEPLOYMENT行。有数据明确拒绝，不删任务/事件、不重标GLOBAL、不降版本号；防止检查后并发插入。离线down禁止，因为无法核验数据。无DEPLOYMENT数据可恢复旧CHECK。
- ORM与migration一致；真实空库up/down/re-up、有GLOBAL/PROJECT旧数据升级/降级保留、DEPLOYMENT ORM插入/错误Scope-project拒绝、GLOBAL与DEPLOYMENT相同key独立但各自重复拒绝、旧外键与唯一性、部署claim/finish/outbox，Parse仍拒DEPLOYMENT。
- down拒绝分别覆盖Job/Outbox及并发锁探针；恢复需完整备份而非自动数据删除。实际结果在进度文件填写，不以授权替代验收。
- 三平台目标不变，本轮Win11，Server2025未验、Debian暂不验证。Gate/正式导出与可用包仍未通过。

## 执行结果

0036/ORM按A实施，Win11真实隔离PostgreSQL空/有数据升降级与旧行保留、两Scope唯一键/错误Scope拒绝、两类部署历史拒绝down、并发双表写锁、部署Job领取完成/Outbox确认、Document Parse仍拒部署通过。Job Schema/lease/outbox ORM parity与历史回归、Windows平台审计回归通过；后端797项无失败（2项环境跳过）。详见docs/progress/aud-03-a02-job-deployment-scope.md。未运行生产migration，不声明导出/正式Gate/可用包完成。
