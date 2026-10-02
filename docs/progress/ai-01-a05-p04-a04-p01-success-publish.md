# AI-01-A05-P04-A04-P01 Provider 探针成功结果原子发布

- 日期/版本：2026-10-02 / `0.1.0.dev0`；依据：CR-AI-002、DEC-20261002-648、Schema `20261002_0055`。
- 实施：将既有 Provider Test 预检抽取为调用方事务内的 `check_locked`；成功发布在同一短事务中锁定当前 Job/fencing、Provider 当前配置和 ACTIVE SecretVersion，重算策略摘要；只写配置/Secret/Job/租约等不可变引用及安全 `SUCCEEDED`，随后完成 Job/Lease/Attempt 终态并提交。未验证或过期的观察值不能发布；没有网络调用或生产 Worker 装配。
- 验证：Windows 11 临时 PostgreSQL 18 空库迁移后，真实 Job/Secret/Provider 测试了成功结果与三张 Job 状态一致、重复发布/旧 fencing 拒绝、Secret 停用和配置升版拒绝、结果插入后终态失败的整笔回滚。定向单元 7 项；后端全量 1967 项运行、3 项跳过；开发 wheel SHA-256 见版本说明。
- 兼容/升级/回滚：无新 Schema、依赖或公开 API；仅内部新增，复用 `0055`，既有部署不需新迁移。可撤内部发布调用；已提交的不可变成功证明和 Job 历史不物理删除。
- 剩余：P02 失败/重试/终态与审计尚待；真实厂商外发、生产 Worker、正式信任材料/目标账户、Server 2025/Debian、AI 质量、Gate 3、UAT、可用包均未验。成功观察值只能由受信内部 Worker 提供，不是公开调用授权。
