# AI-04-A06-P08-P05-P02 显式 Retry Owner 与冻结 API 接线

日期：2026-10-03；状态：`AI_TASK_RETRY_OWNER_PASS`；依据 CR-AI-018、DEC-758/759/762/763、Schema0075及冻结API-03。

AI Task Job现已通过既有`POST /api/v1/projects/{project_id}/jobs/{job_id}:retry`分派给AI Owner。Owner不信任Job读取的`retryable`提示，在同一写事务重新锁定Task/Job/Egress快照并重验当前Session/CSRF、License、Project角色、Job ETag和当前Egress Authorization；仅原创建者或当前项目经理可执行。当前Authorization必须仍处于AUTHORIZED、未过期/撤销、Provider/Config/Model可用，且与原快照完全一致。

成功时原FAILED/CANCELLED Task与Job不变，原子生成新QUEUED Task、PENDING Job、有序Input引用、Egress快照、Outbox、USER Audit、幂等收据及0075 Lineage；同actor/key返回同一新Job，不同key不能从同一源分叉。远端结果未知或`retryable=false`的FAILED仍拒绝。新Invocation不在HTTP请求中伪造，继续由正常Worker领取新Job并执行Begin后创建。

Tests：新增AI Owner/安全Job投影单元6项，相关定向23项通过；Windows11/PostgreSQL18.6一次性数据库验证原子链、源不变、错误ETag零残留、幂等回放、分叉拒绝和新Invocation为0；后端全量2275项通过/3项既有条件跳过。最终开发wheel包含801项，SHA-256 `d5d693afce4e879b090846613f6edd4d54f71c0d60bb5f832bc9869e88c7a07b`。

Compatibility/Migration/Dependencies：复用Schema0075和冻结API，无新Migration、依赖或Breaking Change；生产写组合只有配置Task Policy时开放AI Retry Owner，其他Job Owner不变。回滚为停止AI消费并移除Owner注册，既有代际、Audit和收据必须保留。未访问真实Provider、Secret或客户数据。

Known Issues/Next：P08执行安全闭环已完成，但现有业务AI执行组件尚未组成可持续运行的生产Worker服务。下一项`AI-04-A06-P09-P01`核查并规划Windows AI Worker组合、停止/恢复/过期对账循环和正式启动边界；Server2025、Gate3、UAT及可使用程序包仍未完成。
