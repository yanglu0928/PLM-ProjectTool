# WFL-01-A07-P06：Workflow 固定 Evidence 最小观测适配

日期：2026-10-02；Phase 2；状态：**内部适配 PASS，Checklist/Gate 写链未开放**。输入为 Gate 2 冻结 Workflow 清单模型、CR-WFL-005、P04-A02/A03 已验证的 PROJECT/GLOBAL 标准 Evidence Owner；决策 `DEC-20261002-607`。

Workflow Application 新增显式 Scope 的固定 Evidence 证明入口，保持调用方事务不提交；PROJECT 只调用同项目 Owner，GLOBAL 只调用窄 `STANDARD_CAPABILITY` Owner。校验精确 EvidenceId、目标 ProjectId、来源 Scope、ELIGIBLE、版本与 32 字节指纹后，转换为 `ChecklistBasisObservation`，只含引用/范围/资格/版本/Hash/验证时间，不含正文或本地路径。未知范围、Owner 报错、跨项目/错身份/错状态/指纹异常失败关闭。此观测本身不是正式 Review 或例外批准，也不证明客户已完成十二项清单。

验证：新增定向单元 5/5；后端全量 1857 运行、3 跳过、无失败；开发 wheel SHA-256 `86f51f47f207df6b82770f6f44f7a72403762468168d756216d0ee2414f80e89`。P04 Owner 已分别在隔离 PostgreSQL 18/本地合成文件验证，**本项未新跑端到端 Workflow 写事务或目标平台**。无新公开 API、Schema/Migration、依赖或历史数据变更；回滚为不装配本内部 Port，现有读取和持久数据不受影响。正式 Review/ApprovedException Owner、实际 Session/License/CSRF/Audit/收据组合、Server 2025/Debian、正式信任/法律/UAT/Gate 仍开放；`release_eligible=false`。
