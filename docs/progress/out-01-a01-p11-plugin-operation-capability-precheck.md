# OUT-01-A01-P11：Plugin OperationCapability Owner-backed 只读适配（编码前检查）

- 日期：2026-11-04
- 状态：编码前检查通过；CR-OUT-008已登记；实现已提交至托管CI验收
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P11
- 依据：冻结API-03/DM-04/DB Schema V1；CR-OUT-004/007；OUT-01-A01-P03/P09/P10；CR-PLG-013及PLG-02-A01～A08验收
- 执行环境：GitHub hosted runner；临时数据库/文件均在runner临时目录；用户本机/C盘不运行代码

## 单一目标

为Output模块的 `PluginOperationRegistryPort.get_operation()` 提供只读Owner-backed capability adapter，使Resolver可核验操作是否由受信任Package声明、当前Installation启用且最新RuntimeValidation兼容。仅投影固定字段，不开放任何安装、启用、停用或执行动作。

## 编码前核查

- P10历史判断已被PLG-02-A01～A08进展改变：仓库现在有Package验证事实、PluginInstallation、EnabledOperation、RuntimeValidation及原子Owner；P10的旧结论保留在原文件并由后续复核说明更新。
- 数据读取必须经Plugin模块公开只读Service/Port，再由composition root适配为Output `PluginOperationCapability`；禁止Output直接import Plugin私有ORM，禁止跨Project source读取或当前版本猜测。
- operation能力为true的必要条件：对应不可变Manifest operation精确存在；唯一当前Installation为ENABLED；对应EnabledOperation行存在；最新RuntimeValidation为COMPATIBLE；输出类型与Manifest完全匹配。任一缺失、重复/冲突或查询异常均返回缺失/不可用并由Output Resolver失败关闭。
- `trusted` 必须来自Plugin Package签名验证对正式publisher trust registry的可验证结果；不得从manifest自述、operation名称、安装状态、合成Key或单一布尔字段推定。当前正式publisher key registry为空，故没有正式信任证明时必须返回`trusted=false`；合成PG测试可覆盖受控信任正例，但不得进入包或生产组合。
- P11不新增ORM、Migration、API Contract或公开HTTP，不放宽Scope，不启动外部进程/插件，不生成Output Artifact，不把Policy允许标签解释成信任/启用证明。

## 验收计划

- 单元覆盖operation/输出类型白名单、安装状态、EnabledOperation、最新RuntimeValidation、缺失/重复/过期行、正式Key缺失、未知Package与Plugin Owner异常。
- GitHub hosted PG18真实查询覆盖ENABLED+COMPATIBLE与负例，使用合成Package/Key和数据，证明跨模块Service只读，查询不泄露包正文/签名/路径。
- Output Resolver集成验证：能力缺失、disabled、incompatible或untrusted时均拒绝；只有合成的完整正向事实通过Resolver。正例仅证明端口契约，不构成正式publisher信任、客户插件安装或插件执行。
- 后端定向与全量/wheel、A17 Output marker、前端build、clean parent PG18、A34/A35/A50全链均在hosted runner执行；Secret pattern检查确认仅有合成哨兵。

## 风险、迁移与回滚

跨模块适配器若查询旧/冲突事实会误报可执行能力；因此要求Owner在同一只读事务返回单一当前状态并复验最新RuntimeValidation。若Owner无法安全证明正式trust，trusted保持false、Output Create继续失败关闭。无Schema/API变更及迁移；回滚为移除Plugin capability read port、Output adapter与新增测试，原Resolver缺依赖时继续拒绝。

## 编码前结论

前置满足：PLG-02-A01～A08提供最小持久事实与Owner；OUT-01-A01-P03/P09提供Resolver/Policy契约。剩余正式publisher key材料不可由自动化伪造，作为独立Pilot/Release blocker。按CR-OUT-008开始单一只读适配实现，不请求普通任务确认。
