# AI-01-A05-P05-A02：Provider 当前激活资格证明

日期/版本：2026-10-02 / `0.1.0.dev0`；依据：冻结 DM-04/API-03、CR-AI-002、DEC-20261002-652。

编码前检查：Phase 2；P05-A01 受权历史 Job 读取、P04 原子成功/失败结果和当前事实预检均已验证。仅新增 AI Application 内部证明服务及只读 Repository，不改 Provider 状态、Schema、公开 API、权限或依赖。验收为调用方 PostgreSQL 事务内锁定当前 Provider，重验 License、配置版本、ACTIVE SecretVersion、受控策略摘要及最新终态探针 Job/Outbox/结果；任一过期或较新失败均拒绝。风险是历史成功被误用，故服务不自行授权、激活或提交事务；后续命令须同事务完成管理员权限、If-Match/幂等、状态更新、Audit 与最终 License 重验。

实现：按 `observed_at,probe_result_id` 降序只选该 Provider 最新终态结果，不回退选择旧成功；通过 P05-A01 的严格原 Job/Outbox 与结果归属检查后才形成内部 `ProviderActivationProof`。Proof 不包含 Key、URL 或响应正文。配置升版、SecretVersion 轮换/停用、策略摘要变动及较新的 FAILED 结果均失败关闭。

验证：Windows 11 隔离 PostgreSQL 18.6 在真实表/事务中验证当前成功、策略变更、Secret 停用/轮换、配置升版与后续 FAILED 结果；原 P05-A01 受权读取回归同时 PASS。定向单测 5/5；后端全量 1992 运行/3 跳过；开发 wheel SHA-256 `f4aaa7d735211f39bd5db66c33b8bd756ac12e4ae1010afb593df701a7254951`。隔离数据库已删除，临时 PG 服务已停止。无 Migration；撤内部服务调用可回退，历史证明保留。

边界：本项未执行激活状态变更或开放 `AI_PROVIDER_ACTIVATE` API，不证明真实厂商外发、生产 Worker、Windows 正式组合、Server 2025/Debian、Gate 3/UAT/可用包。下一 WBS：`AI-01-A05-P05-A03` 内部受权激活命令。
