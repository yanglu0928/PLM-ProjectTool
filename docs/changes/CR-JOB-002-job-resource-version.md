# CR-JOB-002：Job用户并发版本

2026-09-27 / IN_PROGRESS，Phase2/JOB-01-A02-P01，原冻结64cdf09保留。用户持续授权兼容偏差先记录后实施。API-01明确可变资源强ETag为v<lock_version>，现Job只有Lease fencing而无用户版本，不能用hash/弱ETag/固定v0替代。

选择：新增Job.lock_version bigint非负默认0，Migration0043。数据库BEFORE UPDATE触发器统一在任意业务字段实际变化时递增，覆盖既有所有Jobs写路径和可信SQL更新；只排除lock_version本身与lease_expires_at（纯heartbeat续租），fencing变更仍计版本。直接UPDATE指定不同版本拒绝；达到bigint上限的业务更新失败关闭；无变化UPDATE不递增。受控数据恢复INSERT可以保留历史版本，应用新Job不指定版本使用默认0。

影响：新增ORM/迁移/内部Job事实version，原Frozen API强ETag格式不改，后续GET使用实际version，取消命令尚未接线。version是用户并发计数，不授许可/Lease/正文权限，也不是实际业务成果VersionId。DB触发器依赖须加入部署迁移门禁。所有现有Job进入升级时0，切勿生产热降级或把离线降级后重建0当历史版本保留。

前置/编码前：输入API-01/API-03、0042与实际Job写Repo、前A01安全读取；涉及Jobs/ORM/Migration/读取DTO，权限不扩大，依赖不变。验收：空库全量up/down至0042/re-up；有真实已发布数据升级列不丢业务/历史，默认版本、业务状态变化+1、heartbeat不增加、无变化不增加、手动版本拒绝、溢出拒绝；现后台claim/heartbeat/publish/提交确认/原读取回归。风险：并发更新都持原行锁，非原子客户端加一不能绕过；触发器放大写入但每次一行、性能仍待，不以验证代生产吞吐。

迁移/回滚：维护模式停止API与Worker，按原人工备份流程再0043升级；downgrade删除trigger/function/constraint/column，必须同时回旧代码，丢用户版本，因此仅离线回滚并通知客户端旧ETag无效重新读取，历史Job/Lease/业务结果不删除。本轮仅隔离库，不生产迁移，不关闭Gate/发行。

P01更新：0043/ORM/内部读取版本已实现，空库与真实已有数据升降级旧业务保留、v0/claimv1/真实heartbeat稳定/publishv2、manual/overflow拒绝通过；1145无失败/2跳过、实际读取/提交确认/混排/耗尽安全收尾/原发布与开发wheel通过。数据快照测试初始排序及参数重载错误保留进度。状态P01_SCHEMA_INTERNAL_PASS/IN_PROGRESS，公开GET/If-Match/生产部署未关闭。
