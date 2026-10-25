# SOL-05-A04-P12-P05-P04：Section Trace+Spec 送审准备 Windows 验收前检查

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`WINDOWS_INTERNAL_PASS`。

|检查项|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `SOL-05-A04-P12-P05-P04`，只验真实Windows/PG同一SectionVersion的六维ready_for_review|
|输入基线|Gate 2六维VALIDATE、CR-SOL-023、P05-P03真实Spec现时证明、P10-P02真实Trace现时证明|
|前置任务|带作者依据的SectionVersion CREATE/反读通过，Spec现时维能PASS；Trace另已在Win11真实PG验证|
|模块/实体|只新增一次性验证脚本和进度记录，不改业务代码/Schema/API|
|API/权限|复用当前显式Windows路由的原Session/CSRF/项目授权/License/幂等/Audit；无新权限|
|验收标准|无Trace时Spec PASS而ready=false；精确ACTIVE IMPLEMENTS后六维PASS、valid=true、ready=true；撤边后新Key Trace FAIL、ready=false，旧Key回放首次ready；记录真实收据/Audit且不创建客户Review|
|风险|不能把报告ready当客户批准或SectionVersion APPROVED；合成信任一次性库不能支持Pilot/发行结论|

## 独立验收结果

- 一次性Win11/PostgreSQL 18.6构造真实SOL-06当前批准、SectionVersion逐引用作者依据、既有Session/License合成信任及项目授权，使用显式Windows VALIDATE HTTP。
- 无边首次报告：Spec PASS、Trace FAIL、ready=false；通过正式Trace创建服务建精确RequirementVersion→目标SectionVersion ACTIVE IMPLEMENTS后，新Key六维PASS、valid=true、ready=true。
- 正式Trace撤销服务撤边后，新Key Trace FAIL、Spec仍PASS、ready=false；旧Key回放之前的完整PASS报告，收据与Audit首次观察一致。验证后数据库中SectionVersion仍DRAFT，未生成客户Review或APPROVED状态。
- 本片仅新增可重复脚本和记录，无业务代码/Schema/API修改；运行该脚本exit 0。上一片后端全量3920通过/3跳过仍为代码回归证据，本片未重复全量。真实客户签署、Section统一Review、正式信任/Gate/Pilot/发行尚未完成。
