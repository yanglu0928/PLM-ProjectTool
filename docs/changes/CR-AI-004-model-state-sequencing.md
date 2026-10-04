# CR-AI-004：AIModel 状态与质量证明验收顺序调整

日期：2026-10-02；状态：按 V1.1 持续授权登记并执行顺序调整；原冻结 Gate 2/API/DM 不追写。WBS：AI-02-A07 前置核查。

原计划/差异：冻结 API-03 包含 Model PATCH 与 `:set-state`，DM-04 允许质量引用可空且明确 AVAILABLE 仅代表可路由、不等于 POC-03 质量通过。当前 Schema 0057 只有 `ai_quality_profile_refs` 引用表；仓库 AI 模块没有独立质量结论 Owner、核验适配器或受权关联命令。AI-01 真实 Provider Worker/目标账户/出站资格仍未通过，Test/Activate 生产路由关闭。若直接开放 AVAILABLE/质量关联，会把没有证明的引用或 Provider 可用性误当成可路由/质量通过。

方案比较：A 直接开放完整状态/引用，进度快但会虚报前置证明，否决。B 暂停全部状态工作，安全但延迟可独立实现的暂停/退役，否决。C 先实现 SUSPENDED/RETIRED 的受权安全转移与历史留痕，质量关联和 AVAILABLE 分别以独立质量 Owner 与当前 Provider 证明为前置，选择 C。

影响/风险：调整 WBS 顺序，不变更冻结 API 路径、状态集合、Schema、技术栈或对外数据范围；首版仍不可把模型置 AVAILABLE。风险是部分管理 UI 只能读取/登记/暂停/退役，不能启用调用；需明确提示，不伪造 Gate PASS。

迁移/回滚：本次只登记方案，不迁移或写生产数据。后续安全状态命令应同事务 ETag/管理员/License/幂等/Audit；未投产可撤路由，已有历史保留并向前修复。后续质量 Owner/AVAILABLE 若涉及新增事实/约束，另行增量 Migration 与验证，不改写0057。

验证计划：A07 静态核对冻结 DM/API、Schema/AI 模块与 AI-01 前置；A08 对安全状态命令做隔离 PG18 并发/版本/审计回滚、HTTP/平台模式和全量回归。真实质量 Owner/Provider Worker/出站与模型调用必须以后续单独证据验收，不能用 A08 代替。
