# AI-04-A06-P05-P04 真实 Claim / Envelope / Begin 发送前组合

日期：2026-10-03；状态：`WINDOWS_PG_PASS`；依据 CR-AI-015/016、DEC-740～744、Schema0073。

新增内部 `AITaskInvocationPrepareService`：先由实时 Job Claim 签发不含正文的 Grant，然后在 Task 仍为 `QUEUED` 的短读事务中精确取回已持久化 Content Plan、当前 Prompt/参数及 Plan 指定的 Document ParseResult，构建确定性 Envelope 和无正文 payload proof。读事务结束后再检 License。Begin 写事务重签当前 Grant，强制 proof 与 Task/Job/attempt/fencing/授权/payload/上限完全一致后，才原子写入 `PENDING` Invocation 并推进 Task。整条链路不持有数据库事务跨网络，也未装配 Provider Adapter。

兼容偏差：原 P05-P03 Begin 仅重签 Grant，但未能证明待写 Invocation 对应的是刚构建的实际 Envelope。本项将 Begin 内部合同收紧为必须提供 `AITaskPayloadPlanProof`；旧服务尚未进入生产组合，无已发行调用方破坏。历史 PENDING 记录不改写，应用回滚只能停止新 AI Task 消费并保留历史。

验证：Windows 11 / PostgreSQL 18.6 使用真实 ASGI Session、Project、Document/ParseResult、Prompt、Preview/Authorization/Task、Job Lease/Attempt、Grant、Content Plan Owner 和 Invocation Repository。错误 fencing token 无法准备载荷；篡改 payload proof 无 Invocation/Task 写入；正确 proof 只创建一条 `PENDING` Invocation，Task为 `RUNNING@v1`，数据库中请求摘要与内存 Envelope 逐字节一致，Provider I/O 为0。开发期首轮验证因通用 claim 先取到 Document Parse Job，改为验证夹具将目标 AI Job 提高优先级后全新资源重跑通过，生产选择逻辑未放宽。定向14项、后端全量 **2216项通过、3项既有条件跳过、无失败**；开发 wheel SHA-256 `e9679924e35e775446d2907523926a75073a5a4443e827abf77ec07de0df93b1`。

Changed：发送前准备编排、Begin proof 强制复核、单元与 Windows/PG 验证。Files：AI application、单元测试、P04/P03验证兼容入口和新P05-P04验证。Migration/API/Dependencies：无。Known Issues：尚无 ModelRouter/ProviderAdapter、Secret最小读取、发送前最后一次租约/授权复核、Invocation终态/对账、RAG Context；Windows Server 2025本切片未复验，Debian 13按用户指令跳过，Gate 3/UAT/可用包未完成。Next：`AI-04-A06-P06-P01` Provider Adapter/ModelRouter/Secret/网络边界编码前核查。
