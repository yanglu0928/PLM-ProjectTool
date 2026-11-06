# OUT-01-A01-P44：空 Publisher Trust 下 Output fail-closed 结果

日期：2026-11-07  
状态：PASS_SCOPE_LIMITED  
变更记录：CR-EXEC-043  
Hosted run：[42304500028](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42304500028)

## 验收结果

在GitHub Hosted Windows Server 2025 D盘owned临时目录的PostgreSQL 18.6数据库中，使用产品包内实际 `PackagedPluginSignerResolver`、`SqlAlchemyPluginOperationCapabilityRepository`、Reader及Output adapter：

- signer key数量为0，Plugin operation capability在真实PG18查询中为missing；
- 真实 `TrustedOutputContextResolver` / `OutputRequestService` 对该请求失败关闭；
- OutputRequest、ContextSnapshot、Job、Outbox、Audit与Idempotency六类数据均零新增；
- Source Owner projection未被调用，Plugin execution count为0；
- 无插件签名、插件子进程、文件生成、客户数据或外部API调用。

P42成功事务路径和P44空信任拒绝路径均由同一 Hosted PG18验收器输出独立摘要；两者使用边界明确的隔离fixture。

## 限制

只证明当前空Plugin operation registry与空packaged signer keyring的组合失败关闭；不代表有installation facts但signer无效的全部状态、不代表真实Publisher信任、生产授权、文档生成、Windows 11实机、Pilot、Gate或Release。全run唯一失败仍是SUR-07-A08：initdb返回3221225781，阶段TARGET_PG_TEMP_ENV_PROBE_DONE，无业务markers；CR-EXEC-039假设维持停止。

## 下一项

OUT-01-A01-P45编码前检查：只读核查PlanVersion Owner真实快照重建所需Plan/WBS数据与约束，明确如何在合成迁移后PG18库中构造固定版本事实并替换P41的快照fixture；不触碰客户数据或正式信任。实施前登记CR-EXEC-044。
