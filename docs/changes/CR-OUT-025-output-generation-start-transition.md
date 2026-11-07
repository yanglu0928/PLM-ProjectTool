# CR-OUT-025：Output 生成启动的原子状态推进与审计

- 日期：2026-11-05
- 来源：P28活动lease proof完成后，补齐Output Worker真正开始副作用前的队列状态推进
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P29
- 类型：Output内部Owner + Jobs当前lease proof同事务组合；不改Schema/Migration/API/default composition
- 状态：PASS_SCOPE_LIMITED（GitHub hosted Windows Server 2025/D盘runner；真实Worker/Plugin执行不在本项范围）

## 现状/决策

- OutputRequest已有QUEUED、GENERATING状态、job_ref、context_snapshot_id、current_execution_ref和lock_version；没有启动生成的Owner。
- P28 JobLeaseRepository.check_output_claim在同一transaction里可直接核验活动Output lease；JobLeaseService包装会开自己的UOW，不能用于本次跨Owner原子动作。
- 取消Owner先锁定OutputRequest，再调用Jobs取消命令。初始实现草稿按“先锁Jobs、再锁Output”会与并发取消形成反向锁顺序，存在数据库死锁风险。实施时采用一致的OutputRequest→Jobs lease顺序：Output Owner先在同一UOW锁定并验证精确绑定的QUEUED请求，再由Jobs proof Port检查job/worker/fencing/attempt/DB到期，最后更新OutputRequest并追加AuditEvent。此为原验收边界内的并发安全实现调整；任何失败整笔回滚，不改状态机或冻结Schema。
- AuditEvent对SYSTEM要求actor_id和original_actor_id。Owner将要求服务组合显式注入server-controlled system_actor_id，original_actor_id取已存requester；不接受HTTP/作业payload指定Actor，不以requester冒充worker。当前没有真实Output Worker/受控服务账户，故Owner只作为内部能力，不自动挂载或执行副作用。
- 命令携带排队request与snapshot refs，须精确匹配Job payload、request绑定与当前claim；相同execution idempotent replay返回当前GENERATING结果，错token/错request拒绝。完成文件输出与最终SUCCEEDED状态不在本WBS。
- 不得生成文件、启动插件、运行外部调用；不改正式服务账户/Vault、Publisher信任或安装包。

## 最终验收结果

- 完整hosted run [41953529123](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41953529123)：P29隔离PostgreSQL 18.6 verifier为PASS_SCOPE_LIMITED；父包PG smoke/A17/A34/A35/A50均成功，独立P25 HTTP/Edge仍因initdb 0xC0000135失败，不影响本Owner数据库验证。后端4036 tests/wheel、前端/build、PG18/pgvector通过。
- PG18证据：当前Output lease及精确Request/Project/Snapshot绑定成功；错worker、前序正fencing token、错request拒绝；GENERATING/current_execution_ref/lock_version及SYSTEM Audit原子写入；同执行重放不重复Audit；Audit故障全回滚；Job维持RUNNING，lease proof本身无Job状态副作用。
- 运行位置：GitHub hosted Windows Server 2025，D盘RUNNER_TEMP；隔离合成PG。无客户数据、外部API、插件执行或输出文件。无Schema/Migration/API/default组合变化。Windows 11真实设备、真实Output Worker、受控服务身份、正式信任及Pilot/Gate/Release不因此通过。

## 云端验收偏差记录

- 首轮hosted run 41948211782：后端4036项/wheel、前端/build、PG18/pgvector等相关前置成功；父包PG smoke在解析阶段失败，定位为工具脚本结果字典含字面量\\n，Python语法错误，尚未执行新P29 verifier。
- 影响仅为验收未完成，不是产品路径失败。先修复smoke脚本拼接并再次执行完整hosted工作流；保留首轮失败记录。P25独立0xC0000135失败仍不归因P29。

- 第二轮hosted run 41949611412：全量后端4036 tests/wheel、前端/build、sidecar及父包组装通过；父包PG smoke已进入P29 verifier，但因验收fixture将2个输出组误按5个变量解包而失败，业务Owner尚未执行。偏差范围仅是Verifier夹具；修复为明确选取两个fixture索引并保留全部负向校验，再完整重跑hosted链。

- 第三轮hosted run 41951315834：PG18 verifier进入P29实际断言；正向和错误worker路径先行通过，随后“stale token”负例被接受。诊断发现测试循环计算了旧token但仍传原始ClaimedJob，变量未用于构造输入；这使该负例没有真正改变token，不能作为产品缺陷证据。已先登记本项偏差，下一步用 dataclasses.replace 构造 fencing_token=当前值-1 的真实旧claim，确保测试的是已签发活动token的前序代次；再执行完整hosted复验。P29暂不PASS。

## 风险/恢复/验证

- 风险：UOW提交后实际Worker副作用仍可能因租约过期/撤销而不能开始；副作用边界必须再次proof/fencing，不能把GENERATING状态视为授权。
- 回滚：撤回新Owner/Repository/测试即可；事务回滚保证无部分Job/Output状态。
- 验证：定向unittest；Hosted PG18验证正确绑定原子转GENERATING、系统审计原子写入，错worker/token/已变更状态无写入，audit注入失败Job/Output两边回滚；D盘全量云端验收。
- 用户本机/C盘不运行代码；无客户数据或正式密钥外发。
