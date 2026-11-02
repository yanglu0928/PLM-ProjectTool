# CR-OUT-002：OutputRequest 原子创建 Owner 与受控写路径

- 日期：2026-11-02
- 状态：已记录 / 按持续授权实施 / 待托管验收
- 分支：feature/p51-a33-launcher-checksum-recovery
- 关联 WBS：OUT-01-A01-P02
- 前置：CR-OUT-001 / 20261102_0220
- 基线：Gate 2冻结 DB Schema V1（原提交64cdf09）、API-03、DM-04；遵循用户持续自主执行授权

## 原因与目标

P01 为确保新 Output 表在业务 Owner 未就绪时不能写入，建立了全表拒绝 INSERT/UPDATE/DELETE 的触发器。P02 根据冻结 API/数据模型实现受控 Owner；若保留该触发器，Owner无法持久化ContextSnapshot和OutputRequest。因此需要追加一条可逆迁移：开放表的受控应用写入，但保留数据库截断防护、所有Project/字段/指纹/幂等约束和既有历史保护。

冻结模型要求 OutputRequest、固定Context、Job、Outbox、Audit在一个事务内提交。为强制其JobRef有效，本次Owner还需建立到Job的外键，并提供由Jobs模块所有的同事务enqueue Port。API-03语义不改，不新增HTTP或公开端点。

## 变更差异

计划新增：

- 内部 OutputRequestService 与 SQL repository：项目身份/License/授权检查后，规范化固定引用、生成最小Context snapshot，采用幂等receipt与同generation收敛；Request/Job/Outbox/Audit/receipt共用一次UOW。
- Jobs模块的OutputJobQueue Port/adapter：只写输出Job和最小Outbox引用，不含正文、插件运行或外部调用。
- Alembic revision 20261102_0221：移除out_context_snapshots和out_output_requests的Owner拒绝写入trigger；保留NO-TRUNCATE trigger；为out_output_requests.job_ref增加指向plm.job_jobs.job_id的NO ACTION外键；downgrade重新封闭写入且不删除请求/快照/Job历史。
- 内部单元与临时 PostgreSQL 合成并发/失败回滚验证。不新增公开API、插件调用、Artifact、文件输出或客户数据。

## 兼容性与风险

- API-03的固定Project归属、输出类型/模板/策略/插件操作/固定版本引用/幂等/202 RequestRef+JobRef语义不变。
- job_ref原为空，迁移新增外键不会回填或改变既有数据。
- 0221只作用于本功能新增的两张表和Job FK；已部署到存在无Job引用请求的实例时，downgrade会重新封闭写入但保留这些记录。
- 风险：跨表请求/Job/outbox/audit部分提交会形成不可恢复孤儿。缓解：同一个调用方UOW、Jobs Port禁止独立提交、Audit/receipt失败即整体回滚；PG18测试验证并发与失败注入。
- 输出来源解析/真实模板策略注册在当前树中未形成完整生产组合。本Owner只接受trusted resolver结果并用合成 resolver 做临时PG验证，不将其接到公开路由；真实HTTP和来源组合另设后续WBS。

## 迁移、回滚与验证计划

- 升级：0220 → 0221，表保持数据，Job FK建立；开放应用Owner写路径，同时仍无公开HTTP。
- 降级：删除job_ref外键，重建Owner写拒绝trigger；不删除既有行、不降级0220。
- 验证：空库升级；当前head既有合成数据升级；0221降/升且历史行不变；PG18并发同Key单请求/单Job/单Outbox、异载荷冲突、同generation合流、Unauthorized/License拒绝无副作用、Audit或enqueue故障整体回滚；后端全量、前端构建、Secret检查与hosted Windows parent/A17/A34链。
- 仅在GitHub hosted Windows Server 2025的D盘临时目录、loopback PG数据库运行；所有数据为合成数据，job结束清理。用户本机不执行代码。

## 当前结论

此CR目前仅为先行记录，不能作为实现或验收通过证据。原Gate 2 DB Schema冻结内容64cdf09保留，不静默改写；迁移/Owner仍需按证据验证。失败先追加本CR，再修正。


## 实施前代码审查补充（2026-11-02，先于修正提交）

首次实现已进入分支，托管验收尚未完成。代码审查发现三项需在结论前修正/补证：

1. Migration revision 使用了次日日期；修订为当日唯一序号 `20261102_0221`，同步模块名及迁移合同测试，避免迁移时间线倒置。
2. OutputRequest 当前写入随机请求UUID作为 `idempotency_key`，没有保存调用幂等身份的稳定不可逆指纹；调整为只存 `IdempotencyScope.key_digest` 的十六进制摘要，禁止存原始调用Key，并增加回归断言。
3. 已有单测使用内存假件，尚未覆盖声明的真实PG同事务、并发、异载荷冲突和失败回滚验收；在 GitHub hosted Windows 工作流的临时 PG18 数据库增加合成 Owner 集成验证与可逆迁移生命周期检查。若仓库已有临时数据库脚本调用约束，先按其模式接线；无可复用调用点时，补充独立 hosted validation step。

此补充先于上述修正提交，以保留计划与实现的时间顺序。无客户正文或外部API调用；不扩大公开API或Production Scope。


## 追加安全审查（2026-11-02，先于迁移修正）

迁移审查发现：若移除 ContextSnapshot 的拒绝写trigger后不另加不可变约束，任意后续 SQL 写路径可以覆盖/删除已锁定上下文，与 DM-04 不可变快照要求冲突。0221 将新增仅阻止 `UPDATE/DELETE` 的 ContextSnapshot 不可变 trigger，允许 Owner `INSERT`；保留既有 NO-TRUNCATE trigger。迁移验收将同时检查该 trigger 在升级、降级、重升后的状态。
