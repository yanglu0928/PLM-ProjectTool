# PLG-02-A04 运行时兼容性重验证结果

- 日期：2026-11-04
- CR：`CR-PLG-009`
- 代码提交：`c780dd991cdf1e515f68d2858c685c02157b7335`
- 最终验证提交：`0f299221c5af6b3b605f39f60a05292052285884`
- GitHub Actions：[Cloud sandbox validation run 41738951137](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41738951137)
- 结论：`PASS_SCOPE_LIMITED`（仅合成数据和托管环境）

## 实施

新增内部 Plugin runtime revalidation Owner、PostgreSQL repository 和 Migration `20261104_0228`。受控证据需精确匹配已安装包、包摘要、最新验证和 lock version；每次有效复验追加 RuntimeValidation/Audit。兼容时保留合法启用；不兼容时同事务撤销全部启用操作并记录逐项 DISABLED 历史/Audit；从不兼容恢复只进入 DISABLED，需后续显式重新启用。历史保持只追加，迁移降级在存在PLG-02事实时失败关闭。

未新增API、公开组合、依赖或物理安装/卸载行为；未启动或执行插件，未清理既有输出产物。

## 托管验证证据

GitHub hosted run 共13/13 jobs成功：后端3,945项全量测试与wheel、synthetic key ceremony、前端测试/typecheck/build、Python embedded runtime、PG18/pgvector sidecar、Windows父包组装、清洁解包后的PG生命周期 smoke、A17 packaged PlanVersion flow、A34恢复演练、A35候选交接及A50 Edge source navigation。

Migration验收覆盖空库升级到0228、降级/重升、完整空库降级/重升；已有合成PLG-01包事实升级保留；具有PLG-02安装、兼容与不兼容RuntimeValidation、操作历史的数据库拒绝降级且schema revision、关键行计数、安装ID均保持不变。证据仅来自GitHub托管Windows Server 2025 runner的D盘临时工作区。

首轮 smoke 因验证器期待了过时的降级错误文案失败；第二轮因计数仍期待A03旧fixture而失败。两轮偏差先写入CR-PLG-009，随后仅更新验证器断言/历史计数快照逻辑，最终全链运行成功。失败运行保留作追溯，不作为通过证据。

## 限制与下一项

本项不是Windows 11实机验收、公开生产装配、正式插件信任或PluginExecution，不代表Pilot/Gate/Release通过。后续为`PLG-02-A05` Installation生命周期终态操作Owner编码前检查；须先核对冻结的状态、引用保护、Audit和不可变历史边界。
