# SOL-05-A02-P03：SectionVersion 固定 RequirementVersion 当前批准证明复用

日期：2026-10-09。结果：`REUSE_VERIFIED_REQUIREMENT_CURRENT_PROOF`；不新增同义服务，不代表 SectionVersion 已可写入。

Phase 2 Platform Core；输入 Gate2 DM-05/API-04、CR-SOL-003/0138、SectionVersion DRAFT 输入、已验 `OutlineRequirementUseProofService` 与其 Requirement-owned PostgreSQL 证明。单一问题：SectionVersion 固定 Requirement 根/版本时是否已有同事务、同项目、当前已批准且有 Review 的最小证明。涉及 Requirement Application Port 和 Solution 后续 Owner；本项不改实体、API、权限、Schema/Migration 或现有运行代码。验收是静态合同核对加复跑正负 PG 证明，风险是把“当前已批准需求”误写成章节覆盖/Trace 通过。

核查 `SqlAlchemyPrototypeApprovedRequirementVersionProof`：仅在调用者事务内对同 Project ACTIVE 根、当前批准指针、APPROVED 固定版本和非空 Review/Round 共享锁读取；`OutlineRequirementUseProofService` 严格核对身份、版本号和 32 字节摘要并只返回固定 ID、摘要、Review，不返回需求正文。虽然服务以 Outline 命名，其签名与返回事实不依赖 Outline，未来 Section Owner 可以按每条 `SectionRequirementRef` 直接复用；须在项目写授权完成后、与版本写入同一事务调用，不能跨事务缓存。它不证明 Section 内容实际实现需求、Evidence/Trace 或 Review 已通过。

复跑既有 `validation/sol-03-a04-p03-p02-a02-requirement-use-proof/verify.py`：Windows11一次性PG18.6/合成来源脚本退出0，输出当前批准证明 PASS，并包含跨项目、旧指针、归档和根锁负例；上游真实来源/PROJECT Reference 夹具同轮也退出0。本项未运行新的后端全量或 SectionVersion PG 写入；前一 P02 全量结果不能算本项新测试。

兼容性/升级/回滚：只读核查及复用决定，无代码、API、Schema、配置、依赖或数据变更；撤复用决定即可改走独立服务，但不得绕过 Requirement-owned 现时证明。下一项 `SOL-05-A02-P04` 核查并补足 PROJECT Evidence 的现时资格与物理来源证明，再建设 Section 当前基底、受控 Owner/Guard。正式信任、Server2025、性能、质量、Gate3/发行仍未通过；Debian13实机依用户指令跳过。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-003/0138 → SOL-05-A02-P01/P02 → Outline Requirement Proof 原证据 → 本复用决定 → SectionVersion Owner/VALIDATE/Trace → Gate3。
