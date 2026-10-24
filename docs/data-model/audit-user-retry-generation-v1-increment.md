# Audit用户重试generation设计增量

2026-09-27 / CR-JOB-006 / JOB-03-A02-P01编码前评审。

Phase2；前置重试核查/0044、当前Audit immutable Export/Acceptance和通用收据已验。仅Audit owned generation表及内部DTO，尚不开放权限或命令。实体新aud_export_retry_generations；无新API/依赖/角色。风险为错源/历史丢失，验收Schema/DTO、空与有数据迁移、约束/不可变/失败回滚。

一个新export对应一条不可变关系：source_export_id/source_job_id/source_failure_event_id/new_export_id/new_job_id/new_event_id/retry_audit_event_id/expected_source_version/first_job_version/created_at。新old Export均引用已存在Acceptance；trigger核对相应Job/Event坐标及原失败SYSTEM Audit、新USER retry Audit的Scope/actor/trace/时序/状态。旧失败只AUDIT_UNAVAILABLE且RUNNING→FAILED；实际Jobs状态/Attempt/版本/权限必须后续owned Jobs Port核对，数据库Audit表约束不能替代该授权。

两Export query/policy/format/projection逐字段相同、时间窗口固定；new requested_at不早于old失败，newActor来自新Root而非复用旧Actor。first_job_version固定0，只首次PENDING快照，不因未来Job前进改写。新old IDs必须不同，FK/非零/finite/正序/唯一retryAudit/newJob/newEvent。不复制captured members或文件，不保证新文件字节相同。

通用幂等收据结果引用新export关系；后续Service必须用当前Actor/Scope/源Job/operation/key+包含expected_version的指纹原子创建/重放，本文不宣称收据编排完成。多个不同Key可创建多个新generation，不加错误的source唯一限制。

Migration0045只新增，历史普通Export不回填；downgrade独占锁并在有关系时拒绝，不能丢失追溯。UPDATE/DELETE/TRUNCATE阻断。P01验证fixture可合成失败Audit/新USER事件以测约束，不能当实际重试Worker/权限证明；P02/P03必须实际来源和事务验收。
