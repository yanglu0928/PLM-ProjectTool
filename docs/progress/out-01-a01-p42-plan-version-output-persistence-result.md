# OUT-01-A01-P42：PlanVersion 到 OutputRequest 事务持久化结果

日期：2026-11-07  
状态：PASS_SCOPE_LIMITED  
变更记录：CR-EXEC-041  
Hosted run：[42298833604](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42298833604)

## 验收结论

在GitHub Hosted Windows Server 2025 runner的D盘owned临时目录和隔离PostgreSQL 18数据库中，通过真实 `TrustedOutputContextResolver` 与 `OutputRequestService`，完成APPROVED PlanVersion固定来源至以下持久化链的检查：

- OutputRequest 与不可变 ContextSnapshot；
- Job 与单条 Outbox；
- Audit 与幂等收据；
- 相同幂等键重放保持原Request/Job结果及唯一事务记录；
- 精确 source ref、source kind、review state与五项允许字段；
- DRAFT版本拒绝、跨Project版本拒绝，均保持零业务写入；
- Plugin execution count为0，未运行PluginService、子进程或文档生成。

PG18 smoke的独立摘要为 `plan_version_output_persistence.status=PASS_SCOPE_LIMITED`。后端全量测试/wheel、前端/build、PG18/pgvector、父包组装、A17、P25、A34、A35、P24/P39/P40/A50均成功。

## 范围限制与未通过事项

Plan Owner projection与Plugin Operation capability为隔离合成夹具；P41真实Owner授权/精确project-scoped查询保留独立证据，P41 snapshot reconstruction仍使用fixture。本项不证明生产Publisher信任、真实Operation启用授权、实际DOCX生成、正式License/账户/服务权限、Windows 11实机、Pilot、Gate或Release。

同run唯一失败为SUR-07-A08 packaged SurveyVersion flow：initdb退出码3221225781，stage `SUR_07_A08_STAGE_TARGET_PG_TEMP_ENV_PROBE_DONE`，无业务markers。CR-EXEC-039的TEMP/TMP差分假设未获支持且已停止；不把该失败归因于P42。

无API/Schema/Migration变化、无客户数据和外部API、未执行插件；本机/C盘未运行项目代码。

## 下一项

OUT-01-A01-P43编码前检查：复核打包Windows组合中PlanVersion Source resolver、Output请求授权和Plugin capability的实际接线，确定正式Publisher trust缺失时仍可安全验收的最小范围。实施前按规则登记CR-EXEC-042，保持fail-closed。
