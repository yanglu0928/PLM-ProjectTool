# AI-01-A05-P04-A05：Provider Test 单次 Worker 组合

- 日期/版本：2026-10-02 / `0.1.0.dev0`；依据 CR-AI-002、DEC-20261002-650，P04-A01～A04 已验证内部组件。
- 实施：新增纯 Application `run_once`，一次只领取一个专属 Job，复用逐次预检、固定无客户数据探针、成功或失败同事务发布；校验返回观察值与 claim 的 JobId/fencing 完全一致。无任务返回 IDLE，不解密、不联网；错误或结果发布失败不得报成功。没有进程循环、Windows 生产组合注入、厂商端点/真实 Key 外发。
- 验证：Windows 11 隔离 PostgreSQL 18 与本机临时 CA TLS，使用真实 Job/Outbox/Secret 只读 Store 和合成解密器，分别验证 IDLE 零外发、固定 POST 成功后的 Job/唯一结果/Audit、重定向失败后的 Job/唯一失败结果/Audit、SecretVersion 绑定与缓冲清零。测试覆盖真实事务及网络；定向单元 8 项、后端全量 1982 项运行/3 跳过，开发 wheel SHA-256 见版本说明。
- 兼容/升级/回滚：无 Schema、依赖或公开 API 变化；复用 `0055`。未装配时无运行变化，撤内部单次入口可回退，已提交的 Job/结果/Audit 历史保留。
- 剩余：P05 受权 Job 读取、当前成功证明激活及 Windows 显式组合；生产 Worker 守护/调度、正式信任、真实厂商 Key/外发、质量、Server 2025/Debian、Gate 3/UAT/可用包仍待。合成端到端不构成真实外发授权或发行验收。
