# SOL-05-A04-P12-P05-P03：Section Spec 现时证明 Windows 组合编码前检查

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`WINDOWS_INTERNAL_PASS`。

|检查项|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `SOL-05-A04-P12-P05-P03`，只安装现时Spec资格只读适配器到Windows显式VALIDATE组合|
|输入基线|Gate 2六维合同、CR-SOL-022/023、P05-P02只读合同、现有CREATE资格证明与Windows Section验证组合|
|前置任务|0182逐引用依据Owner与Win11/PG真实HTTP通过；P05-P02后端全量通过；当前VALIDATE仍未装真实Spec端口|
|模块/实体|Solution资格服务复用现时Spec/Review/章节祖先/共同需求端口，SectionVersion现时只读适配器、Windows显式VALIDATE工厂；无Schema|
|API/权限|原VALIDATE路径/Session/CSRF/角色/License/幂等/Audit不变；不挂默认应用|
|验收标准|真实批准Spec与逐引用依据在新Key下Spec PASS；无依据/已替代/撤销Review/错源/缺共同需求/跨项目/失效正文不得ready；旧Key回放首次事实，收据/Audit一次；PG/HTTP和全量回归|
|风险|CREATE资格的`next_version_no`不得直接用于VALIDATE；必须以固定目标版本号和前驱为参照重查当前事实。作者文字仅表示送审准备，不当客户Review|

缺正式公钥与服务账户时仅认定Windows一次性合成信任内部验收，不宣称Gate/Pilot/发行通过。

## 实施与独立验收

- 现有CREATE资格服务抽出共同的单条现时事实核查，另提供固定历史版本重证入口：使用被验证SectionVersion自身版本号及其前驱，不伪造下一版Base；当前批准Spec唯一性、精确Review已批准快照、同项目章节祖先和共同固定需求在调用事务内重新读取。CREATE接口和原资格条件未改。
- Windows显式Section VALIDATE组合注入只读Spec资格服务；默认应用仍未挂载。未声明或旧固定引用缺适配依据继续UNAVAILABLE，正文/Trace维独立决定最终ready_for_review。
- 一次性Win11/PG18.6真实SOL-06批准、旧固定引用与新带依据SectionVersion：HTTP验证新版本Spec PASS、旧版NULL依据UNAVAILABLE；一次性库模拟批准状态失效后新Key重证UNAVAILABLE、旧Key仍回放首次PASS。该模拟只发生在可弃验证库，不代表正式业务变更操作。
- 资格定向37通过/30子例，完整后端3920通过、3跳过、6074子例；原CREATE批准链亦在本次一次性库脚本中回归。没有Schema/API形状/角色变化。尚未验证Trace与Spec同时PASS的实际送审就绪链，也未完成Section统一Review与客户批准；下一片继续。
