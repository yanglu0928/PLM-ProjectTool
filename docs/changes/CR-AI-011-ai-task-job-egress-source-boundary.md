# CR-AI-011：AITask 唯一 Job 绑定与外发授权来源边界

日期：2026-10-02；状态：依 V1.1 持续授权登记，0066 Job绑定已实施并完成Win11隔离验证，内部创建/Egress Owner待后续；关联冻结 API-03 `AI_TASK_CREATE` / `EGRESS_*`、DM-04、Schema0063～0066、DEC-698～703；原 Gate 2 冻结提交 `64cdf09` 不改。WBS `AI-04-A03-P04～P05`。

冲突与证据：冻结 `AI_TASK_CREATE` 必须以 202 同时返回 AITaskRef 与 JobRef，并由持久幂等保证重放。现有通用幂等收据只能保存一个 UUID，因此只有在 AITask 上能稳定反查同一 JobRef 时才能精确恢复首次 202。Schema0063 的 `job_ref` 允许 NULL，且不在不可变字段中，也未限制一个 Job 只属于一个 Task。另一方面，0064 只定义了 Task 内不可变外发授权快照，当前代码库没有冻结 `EGRESS_PREVIEW_CREATE/EGRESS_AUTHORIZE/REVOKE` 的生产聚合、Owner Port 或持久实现；不能把客户端 DTO、AI 输出或测试夹具当成真实授权。

方案比较：A 扩展通用收据同时存 Task/Job 两个 UUID，会波及全平台收据合同和既有数据，本阶段否决。B 保留收据指向 AITask，为新 Task 强制非空、唯一且不可变的 JobRef，首次创建在同一事务中写 Job/Outbox/Task/Input/Snapshot/Receipt，重放由 Task 反查 Job；选择 B。授权方面，C 信任请求中的 AuthorizationRef 并现场组装快照，会伪造批准事实，否决。D 定义显式 EgressAuthorization Owner Port，只接受同项目、同用途、未撤销且未过期的完整快照；Owner 未实现时任务创建失败关闭，选择 D。

差异与风险：0066 将对迁移后新 Task 强制完整 Job 绑定，0063～0065 既有 NULL 行只保留历史、不允许执行或猜测补值。应用层将先实现可注入授权 Owner 契约与原子创建，但在 Egress 正式聚合完成前不挂载公开 `AI_TASK_CREATE`。主要风险是旧 Task 被误执行、Job 被多 Task 复用、授权撤销/过期竞态和跨项目引用；通过数据库插入/更新守卫、唯一约束、Owner 同事务行锁/快照、双重 Scope 校验和未装配 404 控制。

迁移/回滚：0066 增加部分唯一索引和新写/不可变守卫，不猜测更新旧行。仅有历史 NULL 且无新完整绑定时可回退0065；存在新绑定时拒绝物理降级，采用向前修复或受控备份恢复。应用层可通过停止组合根挂载回滚，已有 Task/Job/Outbox/审计历史不删除。

验证计划：P04 登记边界；P05 在 Win11/PostgreSQL18 验证0066空库与旧 NULL 历史升降重升、新 Task 缺 Job/重用 Job/更换 Job 拒绝、正确绑定、drift 和有新数据拒降；P06 实现授权 Owner Port 与同事务 Task/Job/Outbox/Input/Snapshot/Receipt 内部创建，验证重放、并发、授权缺失/过期/撤销/跨项目、Owner/Audit 失败全回滚。正式 Egress 聚合、真实外发、公开 HTTP 和三平台另行客观验收。

P05结果：ORM/Migration0066已实施；Win11隔离PostgreSQL18.6空库与旧NULL历史升降重升、drift=0、缺Job/错Owner/复用/换绑拒绝、正确绑定与非空历史拒降全部PASS。首轮夹具JSONB未显式适配而在业务断言前停止，修正后完整重跑。后端2106运行/3跳过PASS；开发wheel SHA-256 `56e45841582d8e764b53a78426e9a43171f2924aa86cd509a0a61419e5cd658f`。无真实外发/API/生产迁移。
