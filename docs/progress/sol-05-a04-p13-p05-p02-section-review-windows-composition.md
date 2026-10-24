# SOL-05-A04-P13-P05-P02：Windows Section 送审显式组合

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`WINDOWS_COMPOSITION_CONTRACT_PASS / REAL_SUBMISSION_PG_PENDING`。

编码前检查：Phase 2；输入 Gate 2 API-04、CR-SOL-024、P13-P04 Subject/内部服务及 P13-P05-P01 可选 HTTP，前置满足。涉及 Windows Solution 组合与生产入口的可选路由装配，实体为已有 SectionVersion/Review/Result/Receipt；无 Schema 或冻结 API 修改，ProjectManager/客户角色限制不变。验收为显式 write/source 模式才开放提交入口，复用当前六维来源树、完整依赖注入、缺信任源失败关闭、只读/默认模式不挂载。风险是验证与送审使用不同现时来源、缺少 Review 组件或意外扩大只读模式。

将 Section VALIDATE 的当前来源装配提成单一内部工厂，同时供 Review START 使用，包含 Document、Requirement、Evidence、Trace 与 Spec 资格，不复用历史 VALIDATE 结果。Windows 显式写入模式注入真实 Section Subject Repository、Reviewer 资格、Review 创建/轮次/快照、同事务收据和提交服务；普通默认应用/只读平台模式不注册写路由。终态回调仍失败关闭，不代表客户决定。

兼容/回滚：无 Migration、冻结路径/DTO、角色或 License 权益变化；撤显式装配可恢复原关闭状态，历史不改。合同测试验证 Windows 显式写路由存在、只读不存在及关联原有路由；真实 Session/PG 当前六维/重放/权限/并发与正式信任待下一片独立验收。Gate 3、Pilot、Release 未通过。

验证结果：Windows 组合定向 48/48（27 子例）PASS；关联可选HTTP/VALIDATE 定向 63/63 PASS；后端全量 3964 通过/3 跳过/6079 子例，exit 0。未执行本片真实PG端到端，下一片须补。
