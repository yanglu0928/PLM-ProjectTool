# AI-04-A06-P04-P04-A01 服务端 Preview Plan Builder

日期：2026-10-03；状态：`INTERNAL_PASS`；依据 CR-AI-016、DEC-731～734。该切片只建立内部规划合同，尚未修改Preview HTTP或生产组合。

新增 `AITaskPreviewPlanRequest`、服务端Route/Plan Request与 `AIExecutionPreviewPlanBuilder`。Builder先解析冻结的Task Policy，再取得当前Prompt规划投影，逐个调用显式注册的Source Owner取得精确最小投影，构建Content Plan和确定性Envelope；客户端不能提供record count、payload hash、Prompt版本、Source revision、模型revision或estimator。当前Context仅显式`no-retrieval.v1/NONE`可由既有Registry通过，RAG继续失败关闭。

新增不含Task/Job伪身份的 `AIExecutionPromptPlanningContent`，复用严格Prompt校验与Renderer；正文、参数和Envelope bytes均排除repr。未复用未来TaskId/JobId，也未持久化或外发。

验证：新增2项Builder单元并回归Prompt/Envelope合计14项；覆盖服务端Plan/Envelope、精确Source映射、Policy/Prompt/未知Source失败关闭和敏感repr。后端全量 **2199项运行、3项既有环境跳过、无失败**；开发wheel SHA-256 `da9d8cc92d8442955ceec44c01deecd9fc0c00494f5e50932b73bdb81bae81ce`。无Schema/API/依赖/网络变化。

下一切片 `P04-P04-A02`：实现当前Prompt规划期PostgreSQL Owner，锁定Active Prompt Version并从服务端规范化参数；随后A03接Document规划投影、A04接Preview事务、A05 HTTP合同、A06 Windows组合验证。
