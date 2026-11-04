# OUT-01-A01-P15：OutputRequest 取消编码前检查

- 日期：2026-11-04
- 状态：PASS_WITH_LIMITATION；已登记 CR-OUT-012，可进入 P16 实施前终态/锁序核查
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P15
- 执行环境：仅 GitHub API 只读源码检查；未在本机执行项目代码、测试或构建
- 依据：Gate 2冻结 API Contract V1/API-03、API-01、OutputRequest P12/P13/P14 Owner、Jobs cancellation Contract、CR-JOB-003/004

## 单一目标与输入

为冻结 `OUTPUT_REQUEST_CANCEL` 确认可实施的事务边界、依赖和安全验收面；本 WBS 仅做编码前检查/变更登记，不改程序、测试、Schema、API Contract，也不运行测试。

## 源码核查

1. API-03 冻结 `POST /api/v1/projects/{project_id}/output-requests/{output_request_id}:cancel`，角色为创建者或 ProjectManager，控制 S/L/C/I/M/A，结果为 `CANCEL_REQUESTED` 或终态。API-01 要求可重试 POST 的 Idempotency-Key，以及可变资源命令的强 If-Match。
2. P12 的 Create Owner 在一个调用方 UOW 内完成 OutputRequest、Job/Outbox、Audit、幂等写入；OutputRequest 有 requester/project/job_ref/request_state/lock_version。Output 目前只有 Create/Read/List opt-in Router；未发现 Output-specific Cancel Owner/API。
3. Jobs 的 `ProjectJobCancellation` 使用显式 (owner_module, job_type) registry；先在只读 UOW取得 Job hint，关闭 UOW，再调用 Owner 自己写事务。其公共 HTTP DTO以 JobId 为路径资源，不能直接用于 OutputRequest path；如果直接串接，会把 OutputRequest 状态与 Job/Audit 拆到不同事务。
4. Output enqueue 将 Job 固定为 `owner_module=output`、`job_type=OUTPUT_GENERATE`、`scope=PROJECT`，payload refs绑定 output_request_id/context_snapshot_id；新 Owner 必须从已锁定 OutputRequest 的 job_ref复验此绑定，不信任 HTTP/body或Job hint。
5. Job 取消既有规则区分无活动租约的 PENDING/RETRY_WAIT 立即 CANCELLED、RUNNING 设置 CANCEL_REQUESTED、终态 SUCCEEDED/FAILED 不再变化。P16 必须核查 Output worker最终成功/失败 Owner 和锁顺序后才写跨实体事务，避免 Job 与 Output 状态反向锁序。
6. 强 If-Match 的资源版本来自 OutputRequest 行 lock_version，不得把 Job.lock_version或缓存值冒充公开 ETag。幂等范围固定为当前 actor/project/OUTPUT_REQUEST_CANCEL/key，并绑定标准化 reason 与预期版本；当前权限复验后，合法重放要按已记录幂等结果处理，不能用后续版本变化误报新命令冲突。
7. 输出取消与 Job 状态/审计需同一事务：Output拥有输出请求状态与 Audit业务事件；Jobs-owned transaction Port 才能修改 Job/Lease/Attempt。Output 不可直接访问 Jobs ORM 或单独启动 Jobs UOW。任一校验、Audit、Job Port失败均回滚全事务。
8. 当前 Jobs ProjectAuthorization operation policy没有 OUTPUT_REQUEST_CANCEL；应由 Output Owner验证创建者/ProjectManager的冻结规则，不得把通用 ALL_MEMBERS 只读策略误当写授权。项目锁、当前Session/CSRF/License、资源所属 Project均须在实际写UOW内重验。
9. API-03未给取消响应字段的专门 DTO；保持冻结路径/权限/行为和公共 envelope，仅返回 OutputRequest 标识及取消后状态所需最小字段，不暴露内部 Job/租约/路径/Context。路由显式注入、默认仍不挂载。

## 编码前检查结论

- 当前Phase：Phase 2 Platform Core。
- 前置：P11能力端口、P12 Create、P13详情与P14列表已按CR完成并记录范围限制；当前分支 STATUS 已将P15列为下一WBS。
- 模块范围：Output application/infrastructure/api，以及由 Jobs 提供的 transaction-scoped Output cancellation Owner Port；本任务不改普通 Job cancel Router、默认应用组合、Output生成执行器或Artifact。
- Schema/API：现有状态列和 lock_version可表达冻结取消状态；目前证据未证明需要 Migration/API Contract Change。P16若实际响应快照/审计要求迫使新增Schema，先扩展CR与兼容/降级方案后实施，不暗改冻结基线。
- 验收计划：P16前补足终态Worker owner/锁序只读检查；定向覆盖请求解析、强ETag/幂等重放、创建者/PM与拒绝角色、Project/Job绑定、终态与运行中/待运行转换、并发和Audit故障回滚；使用Hosted Actions隔离 PostgreSQL 18真实行/事务验证，再跑后端全量/wheel及仓库完整workflow。
- 秘密与环境：只读仓库源代码；不使用客户资料、Secret、外部AI或用户本机C盘资源。
- 偏差：取消HTTP必须以OutputRequest为资源；现有Job取消分派使用JobId和独立Owner事务，不能安全复用。已先记入 CR-OUT-012；需新增输出专属事务协调边界，但不变更冻结合同或默认开启。
- 回滚：无代码/数据变更；P16若失败关闭，仅移除新的opt-in组件，保留已有P12/P13/P14实现及所有历史。

## 结论

P15 的源码边界核查完成，准许按 CR-OUT-012 进入 P16。P16 编码前必须核实 Output 终态Worker实际写入者和锁序；如果它与“Output行→Job行”不一致，应先调整Owner协调方案并补记偏差。P15 未运行测试，未通过 Gate、Pilot 或 Release。
