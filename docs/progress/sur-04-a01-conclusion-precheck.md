# SUR-04-A01：SurveyConclusion 运行时前置核查

日期：2026-10-07。结论：`SUR_04_A01_CONCLUSION_PRECHECK_PASS`。下一项：`SUR-04-A02` 五表 ORM 与
Migration `20261007_0109`。

## 编码前检查

- Phase 2 / Gate 3 开放；Gate 2 冻结提交 `64cdf09` 保留。任务只核清 SRV-05 实现边界并登记 CR，
  不修改运行代码、数据库、公开 API、依赖或客户数据。
- 冻结证据一致：DM-05 定义不可变 series/version、实际来源、冲突/待办和 Review；SC-01 定义五表；
  SC-02 指定 V-PRJ；SC-03 指定 Version 与 PROJECT keyset 索引；API-04 固定五个 Operation、角色、DTO
  及 `SURVEY_CONCLUSION_SOURCE_INVALID` / `SURVEY_CONFLICT_UNRESOLVED`。
- 当前代码只在 Audit/Trace allowlist、Workflow checklist 和 Root manifest 中声明 SRV-05；`survey`
  模块、测试与 Migration 中没有 Conclusion ORM、Owner、Router 或页面。当前 head 为 0108。
- 已有 SurveyVersion Review 使用 `SRV-02 + SURVEY_ALL_V1`，不能让 Conclusion 复用同一 subject type；
  通用 Review registry 可扩展，但必须注册独立 `SRV-05` Owner 和 policy。
- 当前没有 ApprovedException/风险接受 Owner。故首版不得自行生成此类事实，也不得用文本备注解除关键
  冲突；这项客观边界不阻塞 Schema 和严格失败关闭的业务 Owner。

## 决策与追溯

已登记 `docs/changes/CR-SUR-009-survey-conclusion-runtime.md`，固定版本序列、五表字段方向、typed refs、
来源重证、Review subject、任务拆分、迁移/回滚与验证计划。它只补充冻结实现细节，不改变五表、五个
Operation、角色、URL 或正式化规则。

## 静态验收

- `rg` 确认唯一物理清单为冻结五表，运行实现为零；Root manifest 已保留 `SRV-05`。
- `srv_conclusions` 列表采用 `(project_id, created_at DESC, survey_conclusion_id DESC)`；series 历史采用
  `(project_id, conclusion_series_id, version_no DESC)`，owned rows 采用 version + ordinal/key，符合 SC-03。
- A02 只能新增 Schema/ORM 和验证，不接 Owner、HTTP 或 Review；避免一个 WBS 跨状态机。

本项没有执行生产迁移、外部 AI、客户数据发送、Gate 关闭或平台兼容声明。

