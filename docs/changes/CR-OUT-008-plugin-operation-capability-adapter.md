# CR-OUT-008：Plugin OperationCapability 只读Owner适配

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED；OUT-01-A01-P11 已由 hosted run 41777943851 验收关闭
- 来源：CR-EXEC-002 Windows Pilot纵向链优先；OUT-01-A01-P10遗留阻断复核
- 相关冻结合同：API-03/DM-04/DB Schema V1；不修改冻结基线

## 变更原因

OUT-01-A01-P03建立了Fail-Closed Resolver，P09建立固定Policy，但Plugin Operation capability仍无生产Owner适配。P10当时因缺少Installation/EnabledOperation/RuntimeValidation事实Owner而转入PLG-02施工。PLG-02-A01～A08已提供这些持久化Owner与停用/状态管理；可继续接通一个严格只读Port。

## 决定与边界

实施单一WBS OUT-01-A01-P11：Plugin公开只读Owner查询 → Output composition adapter → `PluginOperationRegistryPort`。能力判断必须验证精确Manifest operation、唯一当前ENABLED Installation、EnabledOperation记录、最新兼容RuntimeValidation、输出类型以及正式publisher签名信任。不得读取对方私有ORM，不执行插件，不修改Output API/Schema/公开组合，不生成客户文件。可信publisher registry缺失时保持`trusted=false`，Output Resolver拒绝，不得用合成Key改写生产状态。

## 风险、兼容与回滚

没有数据迁移、API Contract变化或ORM新增。主要风险是将历史验证/manifest自述误当当前可信能力；通过Owner显式复验最新状态并对缺失/冲突/异常失败关闭。回滚撤去只读查询/适配器和定向测试，Output缺依赖时继续拒绝。

## 验收计划

单测、PG18合成正负例、Resolver拒绝路径、后端全量/wheel、A17同run packaged Output marker、clean parent PG18、A34/A35/A50全部由GitHub hosted runner执行。不得使用客户数据或外部AI；不得在用户本机/C盘执行。最终至多`PASS_SCOPE_LIMITED`，不代表真实publisher信任、Pilot/Gate/Release或插件执行通过。

## Hosted验收偏差记录（2026-11-04）

- 证据：首次P11托管运行 41775475116 后端全量测试 3,975 项中 1 项失败。新适配器返回 trusted=false 的明确拒绝能力事实；失败单测错误地期待该值直接变成“能力缺失”。
- 原因：测试将“失败关闭”误读为隐藏有效的负向Owner事实。正确契约是保留 enabled/trusted 两个布尔事实，让既有 Output Resolver 拒绝不可信能力。
- 决定：仅将单测调整为验证负向事实被保留，并由 Resolver 做最终拒绝；不修改生产适配器行为、Schema/API或数据。
- 风险/回滚：无持久化变化；若修正后验收失败，仍保持 resolver 默认拒绝并按后续证据记录。
- 验证计划：托管后端全量、PG18 owner projection、Resolver拒绝路径及完整父包链复验；本机不运行。

## 最终验收（2026-11-04）

- 最终 hosted run：41777943851，14/14 jobs成功。后端3,975 tests/wheel，前端构建、PG18.6能力查询合成正反例、父包、A17/A34/A35/A50均通过。
- P11 capability query 通过合成完整Owner正例、正式publisher registry空时trusted=false、最新RuntimeValidation不兼容和重复Manifest operation歧义失败关闭。
- 初次单测断言失败在 41775475116：测试错误要求adapter隐藏 trusted=false。按“先记录后修复”先追加本CR偏差记录，再只修正测试期望；最终代码按计划保持 Fail-Closed。
- 结论 PASS_SCOPE_LIMITED。无正式publisher key、产品API启动或插件执行，因此不表示生产信任、Pilot/Gate 3/Release已通过。
