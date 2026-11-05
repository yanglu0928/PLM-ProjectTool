# CR-OUT-028：OutputArtifact 持久化基础

- 日期：2026-11-05
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P32
- 状态：编码中；PLG-03-A01 依赖已以 PASS_SCOPE_LIMITED 完成，P32 PG18 验收待完成
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


## P32 恢复核查与实现决定（2026-11-05，编码前）

PLG-03-A01 的 `plg_executions`、result-file 与 state-event 表已由 hosted PG18 verifier 验收，依赖阻断解除。编码前重新核对 ORM、迁移链与冻结 SC-01/SC-02/DM V1：OutputRequest、PluginExecution、DocumentVersion、FileObject 均有可引用的持久 Root；仍无 OutputArtifact ORM/Migration/Owner。P32恢复为单项数据库持久化任务。

按冻结 OUT-02、M-PRJ 与可用性一致性实现，不改变模型/API合同：
- 新增 `out_artifacts` M-PRJ root 与 `out_artifact_validation_results` append-only child。Artifact固定绑定 Project、OutputRequest、PluginExecution、DocumentVersion、FileObject、媒体类型、SHA-256与字节数；状态限定 `VALIDATING / AVAILABLE / RESTRICTED / REVOKED`，AVAILABLE必须存在受控验证证据引用形状；不存文档正文、绝对路径或客户自由文本。
- 使用复合外键将 Artifact 的 Project、OutputRequest 与对应 PluginExecution 绑定；增加支持该关系的 PLG Execution 唯一键。用复合外键将 DocumentVersion 与 scope/project/file/hash/size/MIME 绑定，并新增对应候选键；Artifact的文件和文档版本两条关系必须一致。直接验证 FileObject 的 PROJECT scope/project一致性。
- Validation结果仅存受控代码、枚举结果、32字节指纹与时间，不存正文或任意诊断文本。Artifact root写入通过独立GUC trigger保持关闭；验证历史仅允许该Owner GUC插入且拒绝更新/删除；两表均拒绝TRUNCATE。
- 新增 Alembic revision `20261105_0232`。空库/含既有合成行升级、空库降级重升、有历史拒绝降级并保留，以及正反复合FK/状态/hash/大小、写关闭/追加/TRUNCATE行为均由隔离 PG18 hosted verifier执行。
- 降级仅在两张新表为空时移除本迁移新增表与候选键；任何 Artifact/validation history存在则先拒绝并保持 head与数据不变。

风险是任何过宽的复合键或缺少绑定可允许跨项目引用或让不一致内容进入AVAILABLE；已以复合FK、唯一键和状态约束压低该风险。回滚依据为受数据保护的 0232 downgrade；不更新冻结基线、不删除非空业务历史。P32不实现生成/存储文件、Publisher、Output成功Owner、插件执行、API或默认挂载；生产可用发布链继续失败关闭。具体验收边界见 [P32编码前检查](../progress/out-01-a01-p32-output-artifact-precheck.md)。
