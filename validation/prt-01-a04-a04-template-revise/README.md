# PRT-01-A04-A04 Template Revise 验证

在Windows 11一次性PostgreSQL 18数据库中从空库升级到head，形成PROJECT/GLOBAL首版后验证：

- PROJECT PM/ImplementationMember与GLOBAL DeploymentAdmin授权；
- License、Scope、DocumentVersion证明及OutputArtifact失败关闭；
- 强版本前置、不可变追加链、Root当前指针/lock原子推进；
- 幂等重放/冲突、Audit故障回滚、撤权后重放拒绝；
- 数据库提交闭包、Alembic drift与有修订历史拒降。

脚本只写隔离合成数据，结束时销毁数据库；不形成客户或正式项目事实。
