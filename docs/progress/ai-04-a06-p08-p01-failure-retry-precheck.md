# AI-04-A06-P08-P01 失败、取消、对账与重试前置核查

日期：2026-10-03；状态：`PRECHECK_PASS_WITH_REQUIRED_SPLIT`；依据冻结 DM-04/API-03、CR-AI-018、DEC-753～757。

核查确认现有 Job `retry_or_fail` 可把当前 generation 自动推进 `RETRY_WAIT`，但 AI Provider 发送栅栏后绝不能自动重发；现有 AITask 又禁止终态复活，而冻结 API 同时要求显式 Retry 产生新 Job/Invocation。直接复用通用自动重试或把 FAILED Task 改回 RUNNING 都会破坏冻结不变量。

决定把 P08 拆为：P02 当前 Lease 下原子失败发布；P03 过期 RUNNING 栅栏对账；P04 用户取消检查点；P05 显式 Retry generation。P02 对 Jobs 始终传 `retryable=false`，避免 `RETRY_WAIT`；Task/Invocation 的 retryable 仅表示用户是否可创建新 generation。P05 保留旧终态，并以新派生 AITask/Job/Invocation 承载重试，登记不可变来源关系；不复活旧 Task。取消时 PENDING 可安全 CANCELLED，已越过 RUNNING 栅栏则不得声称远端未执行，须按 UNKNOWN 收敛。

Changed/Files：本记录、CR-AI-018、DEC-758、状态/版本说明。Migration/API/Dependencies：无。Tests：静态核对冻结DM/API、Task/Invocation触发器、Jobs Lease/Retry和现有通用用户重试实现；无代码行为或外发。Compatibility/Rollback：后续均为内部Owner/追加generation设计，不改冻结状态枚举或URL；停止消费并保留历史即可。Known Issues：P03～P05仍待；Server 2025/Gate 3/UAT/可用包未完成。Next：P08-P02原子失败发布。
