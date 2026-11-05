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


## 0232 字段与候选键精化（编码前补记）

为确保“受控类型”与来源请求不可漂移，`artifact_kind`取同一 `OutputRequest.output_type`，新增候选键 `(output_request_id, project_id, output_type)` 并使用复合FK；媒体类型只接受 DOCX/PPTX/PNG/JPEG 对应MIME。Artifact同时保存并绑定GENERATED_ARTIFACT Document身份、DocumentVersion及其FileObject/hash/size/MIME；Document、DocumentVersion、FileObject和PluginExecution所需复合候选键仅为支持这些冻结引用而添加。JSONB `validation_summary`限定为四个受控代码键（format/structure/hash/content），值只接受安全枚举代码语法，不承载自由文本。该精化没有增加新的业务Root、状态、API或Owner。


AVAILABLE额外守卫：物理CHECK要求Artifact进入AVAILABLE前，受控摘要中的format/structure/hash/content四项均为`PASSED`，且published_at已设置。Root内容引用在触发器中不可变；Owner仅可推进状态/验证摘要/发布时间/lock_version，Validation结果只能追加。这避免仅有任意校验字符串时将未通过文件标成可用。


## 首轮 P32 hosted 偏差（2026-11-05，修复前登记）

- Hosted run [41979765906](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41979765906) 的后端全量/wheel、前端/build、父包组装均成功；父包PG smoke已进入P32 verifier。0232升级及新关系安装执行到既有合成Job保留查询；验证器以`uuid.UUID`绑定`job_jobs.trace_id`（数据库类型为TEXT），PG拒绝`text = uuid`比较。该夹具错误导致verifier在约束目录/负例与升降重验前停止，P32结论未定，不能视为通过或DDL失败。P25同run为独立失败。
- 修复计划：仅将 verifier 的合成`trace_id`参数固定为字符串，使INSERT/保留查询与TEXT schema一致；不改变产品ORM、Migration或验收范围，随后重跑Hosted全链。


## 第二轮 P32 hosted 偏差（2026-11-05，修复前登记）

- run [41981257687](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41981257687) 后端全量/wheel、前端/build、父包组装成功；P32 verifier已通过0232升级、既有哨兵保留查询、关系约束/支持候选键/保护触发器存在性、Owner关闭、无效状态和缺失FK负例。单独执行`TRUNCATE out_artifacts`时，PostgreSQL先因子表`out_artifact_validation_results`的FK返回`FeatureNotSupported`，未调用根表TRUNCATE guard，导致verifier将预期保护误认成失败。不能据此判定P32失败或通过；其余升降重/历史验收未执行到。
- 修复计划：将根、子表放入同一条不使用CASCADE的TRUNCATE负例，使数据库进入两个表的保护触发器后验证拒绝；保持独立子表TRUNCATE测试和产品DDL不变，随后重跑Hosted全链。P25仍为独立问题。
