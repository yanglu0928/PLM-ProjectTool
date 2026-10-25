# AI-01-A05-P04-A04-P02：失败、重试、最终证明与审计

- 日期/版本：2026-10-02 / `0.1.0.dev0`；依据 CR-AI-002、DEC-20261002-649、结果 Schema `20261002_0055`。
- 变更：只接收固定安全错误码；网络/DNS 暂不可用等错误在第 1/2 次按 5/15 秒退避，第三次或配置/策略/Secret/License/协议类错误终止。当前 AI Job/worker/fencing 的同事务中关闭 Attempt/Lease、更新 Job、写 SYSTEM Audit；仅终态 FAILED 写唯一不可变 ProviderProbeResult。成功发布亦补入同事务 SYSTEM Audit。原始异常、Key 与响应不落库；不启用 Worker 或真实外发。
- 验证：Windows 11 临时 PostgreSQL 18 空库迁移后实际三轮领取，前两轮结果表为空且各有尝试/审计记录，第三轮绑定原配置/SecretVersion/Attempt/Lease 的唯一 FAILED 结果；旧 fencing 拒绝，非重试错误立即失败，审计写入故障使 Job/结果整笔回滚。成功路径回归和审计同时通过；定向单元 11 项、后端全量 1974 项运行/3 跳过；开发 wheel SHA-256 见版本说明。
- 兼容/升级/回滚：无新 Schema、依赖或公开 API；复用 `0055`，旧部署无需新迁移。撤内部调用可回退；已提交历史不物理删除。
- 剩余：P04-A05 需将专属领取、Runner、成功/失败发布组成受控单次 Worker 并进行合成端到端；P05 受权 Job 读取/激活证明和 Windows 显式组合仍待。正式信任、真实厂商 Key/外发、质量、Server 2025/Debian、Gate 3/UAT/可用包均未验。当前非 200 HTTP 一律终止，不区分可重试 429/5xx；后续若需分类，先记录协议决策与验证。
