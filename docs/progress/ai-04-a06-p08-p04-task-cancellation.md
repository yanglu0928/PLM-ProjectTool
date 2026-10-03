# AI-04-A06-P08-P04 AI Task 用户取消与发送栅栏语义

日期：2026-10-03；状态：`TASK_CANCELLATION_PASS`；依据 CR-AI-018、DEC-753/758～761、冻结 Project Job Cancel API。

AI Task 取消复用既有 `POST /api/v1/projects/{project_id}/jobs/{job_id}:cancel`，未新增或破坏冻结 URL/请求合同。Owner 在写事务内重新验证当前 Session/CSRF、License、项目成员关系及“原任务创建者或当前项目经理”权限，并用 Job 强 ETag 和 actor/project/operation scoped Idempotency Key 绑定请求。发送栅栏前，Job/Attempt/Lease/PENDING Invocation/Task 与 USER Audit 原子收敛为 `CANCELLED`，后续 pre-send 被拒；Invocation 已为 RUNNING 时不声称远端副作用已撤回，原子收敛为 `FAILED + AI_PROVIDER_OUTCOME_UNKNOWN + retryable=false`。冻结 Job Cancel 回执禁止 `FAILED + changed=true`，因此发送后公开回执为 `FAILED/changed=false`（取消未确认成功），内部 Audit 仍记录 `RUNNING→FAILED`。

Changed/Files：新增取消核心、当前授权/幂等 Job Owner、PostgreSQL仓储、生产写组合、单元与Win11/PG验证；旧组合验证上下文仅追加合成Session资料。Migration/API/Dependencies：无；复用冻结API、现有Schema和依赖。Compatibility/Upgrade：现有Audit/Document Job Owner不变；AI Job现在可由同一取消端点分派。Rollback：停止AI消费并移除AI Owner注册；已终态Job/Task/Invocation/Audit和幂等回执必须保留，不得复活或删除。Known Issues：显式Retry generation、生产AI Worker/对账循环、Server 2025、Gate 3/UAT及可用发行包仍待。

验证：Windows 11/PostgreSQL 18.6 真实ASGI/Session/CSRF/Project/Job链证明普通非创建成员404、升任项目经理后可取消、创建者可取消、错误ETag 409、License 403、同Key精确重放、同Key不同原因409；发送前取消阻止后续Provider授权，发送后只发生一次合成Adapter调用并按UNKNOWN终结；Audit注入失败全回滚，零真实Provider网络/客户数据外发。定向7项、后端全量2266项通过/3项既有条件跳过；开发wheel内796项完整，SHA-256 `1a464698c47a85c65423666dd29f13fc1471d0a5fcb30fd1ef82941cafb718cc`。实施中首次重复递增数据库自管Job版本被触发器拒绝，已删除应用递增并复验；`python -m build`因当前环境模块入口不可用，改用仓库既有`pip wheel --no-deps`构建，产品依赖与代码未改变。
