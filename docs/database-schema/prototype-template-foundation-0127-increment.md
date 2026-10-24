# PrototypeTemplate foundation 0127 increment

日期：2026-10-08；WBS：`PRT-01-A04-A02`；父版本：`20261008_0126`。

Migration0127物理化 `prt_templates`、`prt_template_versions`、
`prt_template_artifact_refs` 和 `prt_template_command_results`。Root固定 GLOBAL/PROJECT Scope，
保存当前不可变版本指针；Version固定正整数序号、PUBLISHED状态、32字节内容指纹、前版、JSONB布局/
组件合同、1～16个适用终端及创建事实；ArtifactRef只允许 DOCUMENT_VERSION/OUTPUT_ARTIFACT并在版本内
按ordinal去重；结果表为后续CREATE/REVISE持久重放预留不可变身份。

A03 Owner前四表的INSERT/UPDATE/DELETE全部失败关闭，TRUNCATE永久拒绝。无Template历史可降0126；
任何Root/Version/Artifact/Result历史均拒绝破坏性降级。多态Artifact目标完整性不使用跨模块共享写FK，
后续Owner必须经document/output Application Port证明；OutputArtifact Owner未实现时失败关闭。

Windows 11/PostgreSQL 18.6验证包括0126既有Project升级保留、空历史降级/重升、Alembic drift、Owner关闭、
Scope与JSON对象约束、不可TRUNCATE和有历史拒降。该增量不开放HTTP、不形成可用Template、不执行合同内容，
Windows Server 2025未跑本链，Debian 13按用户指令跳过。
