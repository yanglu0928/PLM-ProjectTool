# SOL-04-A01：SolutionSection 身份 CREATE 前置核查

日期：2026-10-09。结果：`SOL_04_A01_SECTION_CREATE_PRECHECK_PASS`；本项仅对账与登记 CR，不表示 CREATE 已实现或可用。

编码前检查：Phase 2 / SOL-04-A01；输入 Gate 2 API-04/DM-05/SC-01、0136/0137/0138/0146、CR-SOL-001/002/011 与 SOL-03-A01；前置为 Outline 身份 CREATE/GET/LIST 合成验证。模块 Solution/Project/Auth/Audit/License；实体 SolutionSection 与同项目 Outline；API 为冻结 `SOL_SECTION_CREATE`，角色 PM/ImplementationMember，最终由服务端复验。验收是记录现有 Guard、字段/角色、快照/原子幂等缺口、迁移及回滚计划；风险是仅开放 INSERT 会留下无快照或将来重放漂移的历史。

事实：0136 `sol_sections` 有 `(section_id,project_id)` 唯一、同 Outline `section_key` 唯一、同项目 Outline FK、ACTIVE/ARCHIVED、批准指针与锁版本；0137 加 `(section_id,outline_id,project_id)` 唯一供版本固定引用；0138 加批准 SectionVersion FK，但 Version 全写保护。0146 Guard 仍拒绝 Section DML。Project 策略没有 `SOL_SECTION_CREATE`；Solution 应用/仓储/API 无 Section 创建 Owner。通用 Receipt 可复用，但缺不可变首次 201 快照与闭合约束。创建 Section 只建逻辑身份，不固定正文/需求/证据，也不满足 SOL-03 版本或 Gate 3。

登记 [CR-SOL-012](../changes/CR-SOL-012-section-identity-create-owner.md) 后，按 A02 Schema/快照关闭迁移 → A03 Owner/最小 Guard 解锁 → HTTP/Windows/UI/Edge 分项施工。每步记录迁移、历史拒降、权限/并发/回滚/直接 SQL 负例；不追写冻结版本。兼容性：本项仅文档，无程序、Schema、公开 API、依赖或数据迁移；停止此施工排序可回退计划，不能豁免客观验收。验证为静态对账，未运行新测试。TraceLink：Gate 2 → SOL-03-A01 → SOL-04-A01/CR-SOL-012 → SOL-04-A02。
