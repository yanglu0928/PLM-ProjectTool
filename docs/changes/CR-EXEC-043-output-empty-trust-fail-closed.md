# CR-EXEC-043：OUT-01-A01-P44 空 Publisher Trust 下的 Output fail-closed PG18 验证

日期：2026-11-07  
状态：PASS_SCOPE_LIMITED（2026-11-07；GitHub Hosted run 42304500028）。

## 当前阶段与 WBS

Phase 2 Platform Core / Windows 11 Pilot 纵向业务链。WBS：OUT-01-A01-P44。

## 输入与编码前检查

- 前置：OUT-01-A01-P41/P42 PASS_SCOPE_LIMITED；OUT-01-A01-P43按CR-EXEC-042完成源码检查，确认Production Output组合和空Publisher trust边界。
- 问题：现有PG18隔离Output verifier使用测试Operation Capability验证成功事务路径；尚未在同一真实PG18 Output Owner事务中用实际Plugin Operation读取器、包内空signer manifest验证缺失Capability的拒绝及零副作用。
- 目标：在现有新建/清理的synthetic PG18数据库中，加载产品包内PackagedPluginSignerResolver（keys=[]）和SqlAlchemyPluginOperationCapabilityRepository/Reader/Output adapter；无Operation安装事实时返回无Capability，真实TrustedOutputContextResolver和OutputRequestService拒绝请求且六类Output持久化计数为零。
- 修改范围：只扩展`validation/out-01-a01-p02-owner/verify.py`与现有Hosted PG18验收链；不改产品代码、ORM、Migration、API、schema、signer manifest、Production组合或Publisher配置。
- 数据与信任：新合成Project、UUID、PlanVersion投影；不生成/持有Publisher密钥、不写入fake trusted=true、不注册或启用插件、不提供签名包。
- 验收：实际包内空keyring断言；实际SQLAlchemy Plugin capability reader在PG18事务中无记录返回None；Resolver/Output Owner请求失败关闭；OutputRequest、Snapshot、Job、Outbox、Audit、Idempotency均零新增；source projection调用次数为0；plugin execution=0；P42正路径、P02原验收和后端全量回归继续通过。
- 风险：该负例证明当前空registry/空trust配置失败关闭，不证明“有installation facts但不受信任”的全部组合；不将其描述为完整插件信任测试或正式生成能力。
- 回滚：只移除P44 verifier函数和Hosted父包PG18摘要字段，不触及产品代码与既有冻结基线。
- 执行位置：GitHub Hosted Windows Server 2025 owned RUNNER_TEMP D盘临时数据库；不在本机/C盘运行。

## 关闭标准

只有最新Hosted PG18摘要字段为PASS_SCOPE_LIMITED、六表计数为零、无插件执行且全量后端通过，才关闭P44。整体run若被独立A08阻断，仍仅按P44专项证据给出局部结论；不虚报Pilot/Gate/Release。

## 实施及验收结果

- 将P44检查加入现有一次性PG18 Output Owner verifier；实际加载产品包内 `PackagedPluginSignerResolver`、SQLAlchemy Plugin capability repository/reader及Output adapter。无已安装Operation事实时实际PG18查询返回无Capability。
- Run [42304500028](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42304500028) 的独立摘要 `empty_trust_output_failure` 为PASS_SCOPE_LIMITED：包内signer key数为0；Output Create拒绝；六类Output持久化计数前后不变；Plan source projection调用0次；plugin execution count=0。没有签署包、注入trusted=true或启动子进程。
- 同run后端全量测试/wheel、前端/build、PG18/pgvector、父包、A17、P25、A34/A35、P24/P39/P40/A50均通过。全run仍仅SUR-07-A08 packaged SurveyVersion job失败：TEMP/TMP探针未应用，initdb退出3221225781，无业务markers。按CR-EXEC-039保持停止该组环境假设，不据此改产品或判A08通过。
- P44为PASS_SCOPE_LIMITED，只证明当前空operation registry + 空signer keyring组合 fail closed；不覆盖“安装事实齐全但signer不受信任”的所有组合，也不代表真实Output生成、Win11实机、Pilot、Gate或Release。
- 无API/Schema/Migration/产品代码变更；无客户数据/外部API；本机/C盘未运行项目代码。
- 下一项OUT-01-A01-P45编码前检查：评估消除P41真实Plan Owner PG18 probe中snapshot reconstruction fixture的最小安全方式，以迁移后的真实Plan/WBS行验证固定版本快照投影；实施前登记CR-EXEC-044。