# CR-OUT-028：OutputArtifact 持久化基础

- 日期：2026-11-05
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P32
- 状态：BLOCKED_DEPENDENCY（未开始编码）
- 基线：Gate 2 冻结 Data Model V1、DB Schema V1 的 OUT-02；SC-01 映射 `out_artifacts` 与 `out_artifact_validation_results`，SC-02 将 OUT-02 定为 M-PRJ。
- 来源：P31已完成Job/Output重试与失败状态收敛；实现安全成功发布还需要OutputArtifact持久化。

## 编码前检查与阻断

原始P32检查记录误将冻结候选模型中的 PluginExecution 聚合描述为已有实现。随后检查当前分支ORM/迁移树确认：PLG-03虽在冻结模型定义，但当前没有 PluginExecution ORM、`plg_executions` 表或其Migration；并且 FileObject/DocumentVersion 是现有Owner基础，PluginExecution不是。已在任何Artifact代码开始前更正。

冻结规则要求 OutputArtifact AVAILABLE 时关联一致的 FileObject、DocumentVersion、PluginExecution、Hash与OutputRequest。SC-01要求固定目标关系以FK约束。因此，在 PluginExecution 物理Root缺失时实现 `out_artifacts.plugin_execution_ref` 不能满足冻结引用约束，绕开FK或伪造Execution均不可接受。P32保持阻断，未写Artifact ORM/Migration。

## 决策及后续依赖

- 先实现冻结PLG-03 PluginExecution及owned result/state history persistence，登记于CR-PLG-014 / PLG-03-A01。
- PLG-03只实现数据持久化基础，不执行插件或开放生产写入口；后续再按真实子进程/JSON-RPC和安全Publisher验收逐个开放Owner。
- PluginExecution Root验证、状态和项目一致性完成后，重新执行P32编码前检查，再添加OUT-02 Artifact Root及validation result child。
- P32未来实现不得把 Job `finish` 或插件临时结果单独标记为Output成功/Artifact可用。

## 风险、回滚与验收

- 失败风险：无真实Execution FK会使Artifact记录无法反向追溯或跨项目漂移。
- 回滚：P32尚未改动代码/Schema；只有P32 blocker/precheck和本纠正记录。
- P32恢复条件：PLG-03 ORM/Migration已在迁移链存在、完成hosted PG18验收后重核跨Root约束。
- 本轮只做源码/冻结基线核查，无客户数据、外发、插件执行、文件操作或本机代码运行。
