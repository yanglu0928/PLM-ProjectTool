# AI-01-A05-P02 Provider Test 结果证明 Schema

日期：2026-10-02；状态：Windows 11 隔离 Schema 验证 PASS；来源：冻结 DM-04/API-03、CR-AI-002；决策：DEC-20261002-640。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase|Phase 2 Platform Core，Gate 2 已批准，Gate 3 未通过|
|当前WBS|AI-01-A05-P02|
|输入基线|0054 AIProvider 配置历史、PLT-02 Secret 版本、Job/Outbox；CR-AI-002 增量方案|
|前置任务|P01 固定探针离线合同 PASS 且已同步；Provider/Secret/Job 稳定键存在|
|涉及模块|AI Provider 持久结果、Alembic；本项不改 Job Worker 或公开 API|
|涉及实体|新增不可变 ProviderProbeResult，绑定 Provider/Config、SecretRecord/Version、Job|
|涉及API|无公开 API 变化；冻结 Test 仍须后续返回 202 JobRef|
|涉及权限|本项不提供写入口；后续 Worker/读服务要分别做授权、License/fencing/Secret 重验|
|验收标准|ORM/Alembic 一致；空库 up/down/re-up、有数据升级；复合 FK/唯一/形状/不可变、非空降级拒绝；全量测试和 wheel|
|风险|Schema 只能证明键归属和历史不被改写，不单独证明真实网络、安全外发或激活资格|

## 执行结果

- Changed/Files：AI Provider 结果 ORM、Alembic `20261002_0055`、隔离 PG 验证脚本、迁移头及 ORM 库存合同；物理字段详见 `docs/database-schema/ai-provider-probe-result-v1-increment.md`。
- Migration/API：0054→0055 增量；无公开 API 或生产组合变化，未执行生产迁移。
- Tests：首轮全量 2 项失败，均为迁移头/ORM 历史库存测试尚指向 0054；更新后定向 7 项与全量 1938 运行/3 跳过通过。隔离 PostgreSQL 18.6 两库空/有数据 up/down、ORM drift=0、复合 FK/唯一/成功失败形状/时间/历史保护/非空降级拒绝通过。开发 wheel SHA-256 `c9bc8c9d3163666fdb24d3f2c4127f6e6f8579758cafef73146b31a24672bf37`，测试集群恢复停止。
- 兼容/升级/回滚：原冻结提交保留；需备份后应用 0055，空结果表可降 0054；有历史结果不可物理降级，采用向前修复或受控恢复。
- Known Issues：Schema 不证明 Job/Worker 实际授权或外发；正式端点策略、真实 DeepSeek 连接、P03～P05、质量、三平台/Gate/UAT/可用包仍待。下一项 P03 内部异步提交与收据/Outbox。
