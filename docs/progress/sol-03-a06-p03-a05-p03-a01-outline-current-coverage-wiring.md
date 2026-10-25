# SOL-03-A06-P03-A05-P03-A01：Outline 现时事实接入覆盖证明

日期：2026-10-24。状态：`INTERNAL_UNIT_PASS`。本片仅在现有现时事实计算器内接入已验内部 Coverage Owner，不开放公开 VALIDATE。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前 Phase/WBS | Phase 2 / SOL-03-A06-P03-A05-P03-A01 |
| 输入基线 | Gate 2 DM-05/API-04；A03 固定顺序/来源现时事实；A05-P02 内部覆盖 Owner（仅单元） |
| 前置 | A05-P02 已内部单元通过；现有 Outline 事实类缺可选 Coverage Port，公开 VALIDATE Service/Router 尚未实现 |
| 涉及模块/实体 | solution OutlineVersion 与内部 Coverage Proof；无持久实体写入 |
| 涉及 API/权限 | 无公开 API；计算器不独立授权，Coverage Owner 在同事务由库存服务验证 License/Session/Project；不把测试端口默认挂载 |
| 验收标准 | 仅 order/source 已 PASS 且精确 Coverage Proof 成功才给 coverage PASS；已知全集缺口 FAIL；无端口、来源失败、证明形状/权限/未知失败均 UNAVAILABLE；既有默认行为不变 |
| 风险 | 把单元模拟端口视作 PG 合格会错误放行；本片只做可选接线，Windows 真实组合/公开审计验证后续独立完成 |

本片无 Migration、公开 API 或旧数据变化。回退可选 Coverage 参数即可恢复原恒 UNAVAILABLE；不得把本片单元 PASS 写成 Win11 PG、Outline Review、Pilot 或 Gate 通过。

验证：现时事实与Coverage关联定向19/19；后端全量`4000 passed, 3 skipped, 6079 subtests passed`。单元覆盖精确证明PASS、返回错配UNAVAILABLE、已知完整范围缺口FAIL、来源失效不调用Coverage、默认未装配UNAVAILABLE。真实Windows/PG、Audit/HTTP和用户可见验证尚未接线，因此仅内部单元通过。
