# OUT-01-A01-P25 编码前检查：真实Harness复用完整父包PG运行根

- 日期：2026-11-06
- Change Request：CR-OUT-021
- WBS：OUT-01-A01-P25
- 结论：PASS_WITH_LIMITATION，允许实施一个可回滚的Hosted测试夹具布局修正；P25维持BLOCKED_DIAGNOSTIC。

## 单一问题与证据

run [42166973706](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42166973706) 在同一Hosted Windows Server 2025 job中，以相同P25 initdb profile和原始runner环境，在经完整性校验的父包提取根成功（exit 0，PG_VERSION=true）；现有compare的PG-only提取根及真实P25 Harness侧车提取均返回0xC0000135、零输出。父包/sidecar的1,627项PG payload路径与Hash完全一致。布局/加载上下文影响是证据支持的判断；尚未定位具体DLL。

## 编码前检查与实施

- 现有流程已同job下载、验签名/Hash并完整解包非发行父包，之后删除提取根；P25 Harness再次从同run PG sidecar独立解包，导致运行上下文不同。
- 仅让P25 workflow使用parent-smoke helper的可选“保留提取根”flag；成功后保留完整包根，清除helper产生的合成PG临时数据。非P25调用保持原清理路径。
- P25 Harness从保留根的 payload/pgsql 运行，并要求同run smoke摘要中的Run ID、Commit、PASS状态和完整根P25 initdb成功字段匹配；把sidecar逐文件hash与父包嵌入式PG树核验，避免错用或未经校验二进制。
- Hosted workflow的P25步骤结束后执行always清理，仅允许本Run的D盘RUNNER_TEMP直系精确命名目录；Harness自身在finally也执行受路径约束清理。
- 保留compare中的PG-only失败摘要作为原故障基线；不改变生产API、Schema、迁移、License/Publisher信任或默认挂载。

## 验收与边界

只在GitHub Hosted Windows Server 2025/D盘运行。合成数据库/Project、空Publisher manifest、无客户数据/外部API/插件/文件生成。若数据库不能安全停止或清理路径不匹配则失败并保留受限诊断。运行成功最多为PASS_SCOPE_LIMITED；不得推断Pilot/Gate/Release通过。

回滚删除保留flag、完整根传递、复用验证和always清理代码，恢复sidecar PG-only解包方式。只记录退出/字节数/状态布尔，不输出环境值、原始错误文本、DB内容。Secret检查不提交客户数据/令牌/密码。
