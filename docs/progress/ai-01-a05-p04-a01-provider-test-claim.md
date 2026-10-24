# AI-01-A05-P04-A01：Provider Test 专属领取与 fencing

日期：2026-10-02；状态：Windows 11 / 隔离 PostgreSQL 18.6 合成验证 PASS；P04 整体、A05、Gate 3 仍开放。

## 编码前检查与边界

- Phase 2，输入冻结 DM-04 Job/Outbox 至少一次语义、P03 原子提交、CR-AI-002 与 DEC-20261002-644；前置满足。
- 涉及 Jobs 内部 Job/Outbox/Attempt/Lease，AI Worker 只通过类型化 `AIProviderTestClaim` 领取；无公开 API、数据库迁移、Secret 访问、网络调用或厂商请求。仅允许内部 Worker 使用，领取绝不是外发/激活许可。
- 验收：只领取 `ai/AI_PROVIDER_TEST/DEPLOYMENT` 成对且引用载荷正确的 Job；两个 Worker 不重复领取；过期租约关闭旧 Attempt、递增 fencing；旧 token 拒绝；畸形队列/事务失败不提交。
- 风险：目前未接执行前 License/配置/Secret/策略重验、DNS/出站目标控制、结果发布或终态失败处理，因此 Worker 循环继续关闭。

## 实施和验证

- 新增专属 Claim Service/Repository。`FOR UPDATE SKIP LOCKED` 隔离并发，校验 Job/Outbox 归属和引用一致；只处理未耗尽 PENDING/RETRY_WAIT 或已过期 RUNNING。过期旧 Lease/Attempt 在同一事务标记，再生成新 Lease/Attempt，返回配置/Secret/策略摘要与 fencing/attempt 的类型化引用。`check_current` 复用 Jobs 当前租约证明并重新校验专属归属。
- 单元新增 3 项；隔离 PG 脚本 `validation/ai-01-a05-p04-a01-probe-claim/verify.py` 完整迁移临时库，验证双 Worker、排除高优先级 Audit Job、租约过期/旧 fencing 拒绝、领取事务回滚、孤立畸形 Job 失败关闭。临时库删除，PG 服务恢复停止。
- 后端全量 1952 项运行、3 项跳过、0 失败。开发 wheel `plm_project_tool_backend-0.1.0.dev0-py3-none-any.whl` SHA-256 `2a9013ba7fb58a30105b2149be0c864df65d4cd4ff97c13c1b4373cbb47619e7`；非可用发行包。

## 后续

下一项 P04-A02 执行前对 License、当前配置/策略、SecretVersion 和 fencing 做同一安全边界重验；随后 A03 本机合成受限传输、A04 不可变结果/Job 终态。真实厂商连通、正式信任源、质量/三平台/Gate/UAT/发行尚无完成证据。
