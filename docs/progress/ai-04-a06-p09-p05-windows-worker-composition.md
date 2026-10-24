# AI-04-A06-P09-P05 Windows AI Provider Worker 生产组合

日期：2026-10-03；状态：`WINDOWS_WORKER_COMPOSITION_PASS`；依据 CR-AI-019、DEC-764～768，无公开 API、Schema 或第三方依赖变化。

新增严格非 Secret `ai_execution_policies` Bootstrap 来源，固定 Provider 类型、HTTPS Endpoint、区域、外发等级、模型白名单、最大响应字节及连接/读取/总时限；最多 16 项，任何缺项、重复、额外 Secret 字段、不安全 URL、模型/时限/大小越界均固定失败且不回显内容。业务 Task 策略与 Execution 策略必须成对存在；不完整配置在打开数据库前拒绝，SCM 服务计划也不生成 AI Worker 命令。

既有 `AI_PROVIDER_WORKER` 现按配置选择：仅 Probe 时保持原 Probe-only 组合；存在完整业务策略时使用 P04 组合循环，并装配 Owner 专用 claim、Grant、精确 Prompt/Document/Envelope、Begin、双 pre-send、加密 Secret、持久发送栅栏、固定 HTTPS OpenAI-compatible Adapter、响应 Schema、Suggestion/Failure 原子发布及过期对账。Probe 和业务链只共享进程、数据库、License/系统 Actor 与维护准入，使用独立 Worker、Transport/Adapter、Secret Audit 和策略来源；业务-only 时 Probe 为无副作用 IDLE 链。

验证：新增 Execution Policy 3 项、统一生产组合 5 项及服务计划业务配对 1 项；13 个相关测试文件共 83 项通过。Windows 11/PostgreSQL 18.6 一次性数据库以真实 Worker runtime/maintenance admission 完成生产对象图构建，启动前后均为零 Invocation/Secret Access Audit，Adapter 未调用。首次验证脚本误用模型表连接字段，按真实 Schema 改为 `ai_provider_id` 后以全新临时库重跑通过；生产代码未放宽。后端全量 2310 项通过、3 项既有条件跳过；最终 wheel 807 项并包含策略/Worker入口，SHA-256 `fad0c47681f29496d5968e9a2396a437553726b63bfabe2fbfc2132326f06dbf`。零真实 Provider 网络、真实 Provider Key 或客户数据外发。

兼容/升级/回滚：Probe-only Bootstrap 和行为保持；业务 Task 部署须新增完整非 Secret Execution Policy 并受控重启。回滚可恢复旧服务入口并移除业务策略，既有 Task/Invocation/Job/Audit 历史保留，RUNNING 记录必须先对账。示例 Bootstrap 已补业务策略并修正首版实际支持的 `gap-output.v1/no-retrieval.v1` 示例。

Next：`AI-04-A06-P09-P06` Windows 11 合成 License/Secret/本地 HTTPS Provider 的真实服务循环、停止排空与进程级验证。
