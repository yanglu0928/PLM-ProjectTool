# AI-01 Provider Test 结果物理增量

版本：`20261002_0055`；日期：2026-10-02；来源：冻结 DM-04/API-03 与 CR-AI-002。Gate 2 原冻结提交 `64cdf09` 不变。

`plm.ai_provider_probe_results` 只保存最终测试证明：ProviderId、不可变配置版本Id、SecretRecord/VersionId、唯一 JobId、Job AttemptNo/Lease fencing token、固定 `CHAT_CONNECTIVITY_V1`、受控端点策略 SHA-256、`SUCCEEDED/FAILED` 与安全失败码、观察/创建时间。无 URL、密钥、客户正文、请求/响应正文或原始异常。配置版本新增三字段唯一键以让结果的 `(配置版本, Provider, SecretRecord)` 通过复合 FK 绑定；另以复合 FK 绑定 SecretVersion/Record、JobAttempt/Job、JobLease/Job，防止跨归属结果。

历史结果禁止 UPDATE/DELETE/TRUNCATE；JobId 唯一防止同一任务多份相互矛盾的最终证明。表约束不替代 Worker 对当次 License、当前配置、策略摘要、Secret 状态、Job Owner、fencing 和真实外发授权的重新检查。成功结果只是后续激活的候选证据，不改变 Provider 状态，也不代表 AI 质量通过。

升级：从 0054 增量加唯一键与空结果表，不回填旧配置或 Job。回滚：表空可降至 0054；有结果历史则安全拒绝，必须备份并向前修复/受控恢复。正式生产库尚未迁移。

验证：Windows 11 隔离 PostgreSQL 18.6 双库完成空库 up/down/re-up、有 Provider/Secret/Job 数据升级、Alembic ORM 无漂移、成功/失败结果、复合归属/唯一/时间/形状约束、历史不可变与非空降级拒绝；后端全量 1938 运行/3 跳过，开发 wheel SHA-256 `c9bc8c9d3163666fdb24d3f2c4127f6e6f8579758cafef73146b31a24672bf37`。无真实网络或 Secret 解密。
