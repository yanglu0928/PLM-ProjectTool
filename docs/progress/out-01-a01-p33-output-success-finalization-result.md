# OUT-01-A01-P33：输出成功终结Owner验收结果

- 日期：2026-11-05
- Change Request：[CR-OUT-029](../changes/CR-OUT-029-output-success-finalization-owner.md)
- 结论：PASS_SCOPE_LIMITED
- Hosted run：[42013184586](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42013184586)（PR #61）
- 执行环境：GitHub Actions Windows Server 2025 hosted runner，D盘临时目录与隔离 PostgreSQL 18；使用纯合成记录。

## 验收结果

父包 PostgreSQL smoke 及 P33 verifier 通过：

- 有效 Output Generate Claim 下，Artifact 转为 AVAILABLE，OutputRequest 与 Job 转为 SUCCEEDED，Lease RELEASED、Attempt完成，并在同一事务写入SYSTEM Audit。
- Audit端口故障使Artifact、四项validation、OutputRequest、Job、Lease、Attempt及Audit全部回滚。
- 错误 Document 引用被拒绝；修改后的成功重放被拒绝且持久状态不变。
- 四项validation各一条且均为PASSED。
- 使用完全相同的已成功Claim与发布元数据重放时，Owner返回原成功Facts（changed=false）；Artifact、validation、Audit、Job状态及引用计数不变。
- Hosted后端全量测试与wheel、前端测试/build、PG18 sidecar重建、父包组装、A17、A34、P24、A50通过。

## 变更范围与兼容性

增加内部成功终结Owner的严格幂等重放检查及Job完成Claim只读验证。重放要求同一项目、OutputRequest、PluginExecution、Artifact、DocumentVersion、FileObject、内容Hash、四项validation及已成功Job/已释放原Lease。变更不涉及Schema/Migration、冻结API或默认应用装配，无安装或数据迁移要求。

## 限制与遗留事项

- 同run的独立 P25 initdb.exe 仍以 Windows 0xC0000135 失败，真实 P25 HTTP/Edge未启动；因此整体workflow为failure，不能把P25标为通过。
- 此证据不代表真实本地文件生成/原子提升、插件进程、生产Publisher信任、默认API/Worker接线或生产环境数据。
- Windows 11 Pilot、Gate 3及正式多平台Release仍未通过。
- 下一项：OUT-01-A01-P34编码前检查，依据ADR-008评估本地Storage到GENERATED_ARTIFACT的原子提升、Hash复验、补偿与恢复一致性。

没有在用户本机运行程序；所有运行均使用GitHub托管runner。
