# CR-JOB-002：补齐协作取消追溯信息

日期2026-09-26；实施前登记；来源AUD-03-A06-A02-P02核查。依据用户持续授权自主实施，保留冻结64cdf09及0001～0038，不追写旧模型/迁移。正式总控V1.1/实施方案V2.1已核对。

## 证据、比较与选择

冻结DM-04 Job Aggregate明确cancel_requested_by/reason可为空，API-03协作取消并保留终态/副作用。当前Job ORM/0025～0038没有取消信息字段，仅有CANCEL_REQUESTED/CANCELLED枚举，不能证明已保留实际申请人与原因。

A：增量0039增加nullable取消申请人、原因和申请时点，不猜旧行；有信息时固定首次值并保护取消历史、down锁表后拒绝任何信息删除。随后单独实现真正的取消/确认/到期恢复事务Port及受权Audit编排。

B：只改state并丢弃申请信息，或把原因塞Job payload/自由日志；不能满足追溯且污染最小引用，不选。新增独立取消子系统会增加Owner/实体，不选。

选择A，补齐冻结模型实现遗漏；不新增Scope/API/角色/依赖/License机制。申请人FK仅元数据存在性，不是权限，当前授权仍需公共Port。原Job payload不含原因/凭据，不暴露取消原因至公开JobView；公开投影和Audit只使用受控code，不复制自由原因。应用理由输入安全约束随后验收，Schema不能证明文本没有Secret。

## Schema、迁移、回滚与验收

0039 Job增加cancel_requested_by(UUID FK Auth User)、cancel_reason(Text)、cancel_requested_at(UTC)。三字段全空保留旧历史，或全非空：nonzero真实User、trim后1～1024字符、有限时点不早于Job创建，state仅CANCEL_REQUESTED/CANCELLED。首次登记只能从PENDING/RETRY_WAIT/RUNNING进入取消态；旧取消态不回填猜申请人。首组三字段登记后不得修改/清空，不能复活/删有取消信息Job，TRUNCATE含任何取消信息时拒绝。保留既有Lease/Attempt与Audit历史。

增量DDL有锁；生产需备份/维护窗口，本轮只独立UUID库。down先ACCESS EXCLUSIVE锁Job，再检查任一取消字段，有信息拒绝且版本/数据保持；无信息可删新增列/约束/函数。离线down关闭，不能自动删除信息绕过。实际空库/旧数据up/down/re-up、ORM parity、NULL旧行不变/无回填、错误成组/原因/时点/申请人/状态拒绝、首值不可改/不可删/不可truncate/不可复活、合法REQUESTED→CANCELLED、并发down写锁和含历史拒绝必须验证。

本CR分项：P02-A01 Schema与迁移；P02-A02真正Jobs事务取消/协作确认/到期恢复；后续Audit当前许可/Session/CSRF/PM/资源绑定、receipt/Audit原子与Worker竞争。不能把Schema PASS或合成state当完整取消通过。正式包/性能/Gate/三平台目标不缩减；Win11先验，Server2025未验、Debian13暂缓。

状态IMPLEMENTATION_IN_PROGRESS。无生产操作或公开导出/取消API。

P02-A01执行结果：0039/ORM、真实空/旧数据up/down/re-up/parity、旧NULL无回填、成组/申请人/原因/时点/状态约束、首次信息与Job技术身份/终态保护、delete/truncate拒绝、down实际竞争写锁及含历史拒绝通过。860项无失败（2环境跳过）、四项相关真实回归与开发wheel通过。详见docs/progress/aud-03-a06-a02-p02-a01-cancel-schema.md。合成元数据转换不是实际取消；P02-A02命令/确认/恢复及受权编排仍待，CR整体IN_PROGRESS，无生产操作。

P02-A02执行结果：Jobs owned实际取消请求/当前Worker确认/数据库租约到期恢复、精确首次pair绑定、重复首信息保留、真实并发单次变化、故障回滚、两种顺序取消与finish竞争等待及终态副作用保留通过。866项无失败（2环境跳过）、Schema/原子提交回归与开发wheel通过；详见docs/progress/aud-03-a06-a02-p02-a02-cancel.md。原Export/当前用户授权/receipt/Audit及真实Artifact编排未接入，合成发布marker不冒充文件；CR整体IN_PROGRESS，无生产操作/公开取消API。
