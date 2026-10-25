# AI-04-A06-P09-P03 业务 AI one-shot Worker

日期：2026-10-03；状态：`BUSINESS_ONE_SHOT_PASS`；依据 CR-AI-019、DEC-764～765，无公开 API、Schema 或第三方依赖变化。

新增单周期业务 Worker，固定执行 `Owner专用claim → Prepare → Begin → 双重pre-send/Secret/持久发送栅栏 → Adapter → Parse → Success/Failure Publish`。prepare 失败在零 Invocation 边界调用 P02 收敛；Begin 将是否已提交作为显式错误事实，提交前失败可安全收敛，提交后 License 复核失败则保留给过期对账，绝不重建或重发。发送后未能发布结果也仅返回 `RECONCILIATION_PENDING`；响应在所有退出路径关闭，未知异常不携带私有正文。

验证：新增 Worker 13 项单元与 Begin 持久事实 1 项，相关定向 36 项通过。Windows 11/PostgreSQL 18.6 从真实 ASGI 合成 Task 开始，用真实 Repository/Owner 完成整条 one-shot 链，只调用一次本地合成 Adapter，最终 Task/Invocation/Job/Lease/Suggestion/Audit 一致终态，第二周期 IDLE，Secret 明文缓冲清零。后端全量 2294 项通过、3 项既有条件跳过；最终 wheel 804 项，SHA-256 `aa3f580203457a2e5856b72f4f29914426847e8fe78385ba71339f4bab916452`。零真实 Provider 网络、真实 Secret 或客户数据外发。

兼容/回滚：仅追加内部 Worker 编排并对 Begin 内部错误增加 `committed` 事实，既有默认为 `false`；可停止业务消费并移除 Worker 组合，已越过发送栅栏或已提交 Invocation 的历史必须保留并对账。

Next：`AI-04-A06-P09-P04` 公平有界组合循环、过期对账与协作排空。
