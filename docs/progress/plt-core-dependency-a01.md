# PLT-CORE-DEPENDENCY-A01：Phase 2 真实 Owner 依赖核查

日期：2026-10-02；结论：`DEPENDENCY_AUDIT_PASS / PHASE_2_IN_PROGRESS`。本 WBS 只做静态依赖核查与下一路径选择，没有程序、Schema、API 或外发变化。

## 核查

冻结 V2.1 先 Phase 2 Platform Core，再 Phase 3 AI/RAG，后 Phase 4 起实现业务主体；Phase 2 验收要求权限和阶段可走通。Review 当前只有 Subject Port/合成测试 Owner，没有交接等生产业务 Subject Owner；Workflow 的 `ApprovedException` 目标无实体/审批 Owner，Checklist/Gate 不可仅凭保存的状态引用放行；Trace 只有 DOC-02 Owner，通用 HTTP 依 CR-TRC-002 关闭。详情见 RVW-02-A10、WFL-01-A07-P05、六阶段定义与最近 Trace 记录。数据库里的观测 UUID、旧 APPROVED 或合成项目都不能替代当前受权固定业务事实。

## 判定与后继

依 CR-SEQ-001 调整**执行顺序而非验收标准**：保留 Phase 2 开放及所有未完成 Owner/Review/Workflow/Trace 项，下一独立 WBS 为 `AI-01-A01`，先核对冻结 Provider/Model/AIService 合同、已有 Secret/Job/License 边界，再决定最小正式实现。尚不调用厂商、不读取或发送客户资料；外发需逐次授权。AI/RAG 基础任务可前置编码，不据此宣布 Phase 3 或 Gate 3 通过。业务 Owner 完成后回接并实测 Phase 2 六阶段权限链。

验证：V2.1 §Phase 2～4/正式开发顺序、冻结 ADR-004/DM-04/API-03 与现有代码静态核查；本 WBS 无新增运行测试。POC-03 来源配额/质量、正式 License 信任、Server 2025/Debian 及发行/UAT 仍按 STATUS 未验证。
