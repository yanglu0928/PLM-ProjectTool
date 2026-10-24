# AI-04-A06-P08-P02 AI Task 原子失败发布

日期：2026-10-03；状态：`TASK_FAILURE_PASS`；依据 CR-AI-018、DEC-758/759、P07发送栅栏与成功发布。

新增失败发布合同、PostgreSQL Repository与Provider失败编排。发送服务显式携带是否已提交持久栅栏：栅栏后任何Adapter/清理异常统一转为 `AI_PROVIDER_OUTCOME_UNKNOWN`，不可自动重试；栅栏前失败可保留显式用户重试提示。结构化响应解析失败保存响应指纹、Invocation `schema_validation_state=INVALID`，不产生Suggestion。Job/Attempt/Lease、Invocation、Task与Project Audit在同一短事务失败关闭；Jobs调用固定`retryable=false/delay=0`，不进入`RETRY_WAIT`。Audit或Lease失败整笔回滚，旧Worker不得发布。

Changed/Files：`send_provider_request.py`、`complete_provider_success.py`、新增`complete_provider_failure.py`、`publish_task_failure.py`、`task_failure_repository.py`、单元与Win11/PG验证、CR/DEC/状态/版本说明。Migration/API/Dependencies：无。Compatibility/Upgrade：内部错误语义收紧，不改冻结状态枚举、URL、依赖或Schema；生产Worker尚未装配。Rollback：停止AI消费并撤内部编排，已终态历史保留；禁止把FAILED/RUNNING改回PENDING。Known Issues：过期Lease崩溃对账、用户取消、显式Retry generation、Server 2025/Gate 3/UAT/可用包仍待。

验证：Windows 11/PostgreSQL 18.6 真实 Claim/Invocation/Secret/Audit与合成Adapter，证明RUNNING栅栏后的传输失败固定UNKNOWN/non-retryable；注入Audit失败时 Job/Invocation/Task/Lease全部回滚，随后不再次调用Adapter即可原子提交FAILED与Audit。新增定向15项通过；首次全量误用精简PoC虚拟环境，14项在收集期因缺`pydantic-settings`失败且不计结论；切换项目完整Python 3.13环境后全量2256运行/3跳过通过。开发wheel SHA-256 `b0928fe407cc91e9e0dfe99aae4b6e3755c17941bf12b081ebd6e9dec48192f2`。未访问真实Provider、真实Secret或客户数据。
