# SOL-03-A06-P03-A05-P03-A04：Windows Outline VALIDATE 装配

日期：2026-10-24。状态：`WINDOWS_COMPOSITION_PASS`（真实三维PG待A05）。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前 Phase/WBS | Phase 2 / SOL-03-A06-P03-A05-P03-A04 |
| 输入基线 | 冻结 API-04；A01三维事实、P02完整覆盖Owner、A02命令/Audit、A03可选HTTP；既有Windows Section/Requirement/Reference组合 |
| 前置 | Windows显式写入模式拥有Session、正式License Guard、Audit、Document/Evidence来源和PG UoW；无生产正式公钥与服务账户时仅能进行受控合成环境验证 |
| 涉及模块 | entrypoints Windows组合；不修改业务Owner、Schema、权限、License权益或冻结API |
| 验收标准 | 写入模式显式装配Outline验证；读/默认模式保持404；端口使用同事务有界500根需求库存、当前正式Section/Review/Trace/Spec，任何缺源失败关闭；组合定向与后端回归；一次性PG真实三维完整/缺口/竞态另设验收片 |
| 风险/回滚 | 多源组合可能因既有可信来源缺失而UNAVAILABLE，不能降级为PASS。可撤显式装配回到404，历史Audit/Receipt保持 |

单一WBS限于生产依赖装配与静态/单元验证；真实三维一次性PG业务链另作为`SOL-03-A06-P03-A05-P03-A05`。此拆分只细化验收顺序，不减少原目标。

## 验证

- Windows显式写入模式传入Outline VALIDATE Router；默认/只读模式不装配。构造时复用现有Requirement现时资格Owner，并强制库存仓储`max_roots=500`；Section当前六维、Review、Trace、Spec与Reference使用现有端口。
- 首轮组合测试因测试本身读取了不存在的`_repository`属性失败；修为实际`_repo`后2通过/10子例。关联定向15通过/26子例；后端全量4014通过/3跳过/6107子例。
- 本片未执行新路由真实Session/PG三维业务状态或浏览器验收。正式信任源仍未就绪，Gate/Pilot保持未通过。
