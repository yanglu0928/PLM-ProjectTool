# SUR-06-A06：Workflow 前端严格双阶段支持

日期：2026-10-07。结论：`SUR_06_A06_WORKFLOW_FRONTEND_PASS`。下一项：`SUR-06-A07`
Windows 11 真实 Edge 完成 `HANDOVER → SURVEY → REQUIREMENT` 全链验收。

## 实施结果

- Checklist 客户端以显式 item→stage 映射支持 Handover 与 Survey 四个 item；记录请求只允许当前阶段
  item，响应必须逐项匹配 stage/item。原 Handover 请求、回执和错误恢复合同保持不变。
- qualification 客户端改为严格判别联合：Handover 只接受 `handover_analysis_version_id`，Survey
  只接受 `survey_conclusion_id`；多字段、错字段、跨阶段 item、ETag/身份漂移全部失败关闭。
- Transition 客户端仅开放 `HANDOVER→SURVEY`、`SURVEY→REQUIREMENT` 两条显式相邻映射，target
  由当前可信快照派生而非用户输入；回执中的 from/to 不匹配即作为不确定结果处理。
- 页面只在当前 Handover 或 Survey 阶段显示两项记录动作；资格预览、PASS/FAIL、原 Key 恢复和
  二次确认均复用既有安全流程，推进文案及保存 target 随当前阶段严格变化。

## 兼容、偏差与回滚

- 无 Schema/Migration、API path、请求字段、依赖、Secret、License 或外发变化；这是
  CR-SUR-012 已记录兼容扩展，不修改 Gate 2 冻结基线。
- Handover 既有测试全部保留；Survey 使用独立响应变体，未把业务 subject identity 放入记录请求。
- 回滚可撤销前端 Survey allowlist、判别分支和第二条 transition 映射，恢复 Handover-only；服务端
  历史不修改。主 JS `722.81 kB` 的既有大分块警告仍保留，未以本项顺手改构建架构。

## 验证证据

- 定向 5 文件 225 项通过，覆盖两阶段资格、记录、Transition、页面和 Session 写边界。
- 前端全量 88 文件 1482 项通过；`vue-tsc + tsc` 类型检查通过。
- Vite 生产构建 184 modules 通过；产物主 JS `722.81 kB`、gzip `178.96 kB`，仅有已知
  500 kB chunk 警告。
