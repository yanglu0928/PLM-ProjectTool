# CR-OUT-008：Plugin OperationCapability 只读Owner适配

- 日期：2026-11-04
- 状态：已按持续授权登记；OUT-01-A01-P11编码中
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
