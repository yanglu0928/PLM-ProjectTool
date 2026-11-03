# CR-PLG-005：可信插件包元数据登记Owner与路线纠正

- 日期：2026-11-03
- 状态：APPROVED_BY_CONTINUOUS_USER_AUTHORIZATION / IMPLEMENTATION_IN_PROGRESS
- 适用WBS：PLG-01-A07
- 分支：feature/p51-a33-launcher-checksum-recovery
- 依据：Gate 2冻结的API-03/DM-04/SC-01～03、ADR-005、CR-PLG-001～004、CR-EXEC-002、用户持续自主执行授权

## 触发与路线证据

- A06全链路run 41582564698已13/13 jobs成功。A06 CR明确不写PluginPackage ORM，持久登记留给后续独立WBS。
- 仓库已有PLG-01-A01四张元数据表及闭写守卫、A02 Ed25519 verifier、A03 Manifest parser、A05只读包内signer resolver、A06有界ZIP/签名联合Inspector。
- OUT-01-A01-P03并非待做项：其结果文档记录源码e0b69bdcdc06765e5192d57fe84f924d30606958及run 41417503109全13 jobs成功。PLG-01-A01～A06也均已有PASS_SCOPE_LIMITED结果。上一轮从旧STATUS行误判P03为下一项，现保留历史并更正为A07。
- API-03定义PLUGIN_PACKAGE_IMPORT为DeploymentAdmin的异步验证作业，并定义PackageView的签名、Manifest及验证摘要。本WBS只提供该异步流程将来可调用的内部持久Owner，不实现公开路由、Job orchestration或安装流程。

## 选定方案与实现边界

A07实现单一问题：将成功完成A06安全检查及受注入兼容策略判定的签名包，原子登记到现有0222元数据Schema。

- application service接收有界完整ZIP bytes、detached signature、signer key ref、compatibility policy ref、执行身份和trace。
- service内部调用现有ArchiveInspector（其内部完成Manifest解析及完整ZIP验签），并通过显式注入的CompatibilityPolicyPort核对声明OS/架构/Plugin API与固定策略。
- 仅经验证且兼容的包写入Package、Manifest Operation/Dependency及PASSED Verification行；兼容不通过可在后续WBS定义持久拒绝记录，本WBS拒绝写入。
- 同一plugin id/version + 同一archive digest视为幂等返回原记录；同一身份不同digest视为不可变版本冲突。
- 所有持久写入、子表及Audit必须在同一调用方UOW提交；SQL repository只接受活动事务、不自行commit。
- Migration 0223为现有闭写Owner安装窄写路径：允许INSERT；Package/Operations/Dependencies/Verifications行的UPDATE/DELETE改为显式拒绝，TRUNCATE继续拒绝。down恢复闭写并保留已存在数据；0222自身仍会阻止有历史数据的破坏性降级。
- 数据库只保存DM-04既有元数据/签名/摘要，不保存ZIP正文、私钥、API Key、临时路径或客户资料。后续安装前必须重新获得相同包字节并验证其SHA-256或新增独立内容存储WBS。
- 默认生产信任清单仍为空，故真实签名导入在生产组合失败关闭；合成测试使用仅进程内key，不改包内信任manifest，不产生发布信任。

## 当前实施状态

- A07 application service、PostgreSQL metadata repository、migration `20261103_0223` 与 synthetic unit tests 已提交到本分支。
- PLG 与共享 Output migration validators 已适配 0223；hosted run 41585611247 等待执行，尚无 A07 验收结论。
- 偏差记录（run 41585754961，修复前）：后端全量3,909项有1项既有 `test_migration_contract` 仍将Alembic head固定断言为0222，实际脚本head已随本项迁移推进至0223。A07新增单测及产品代码无失败报告；父包链因后端失败按工作流规则跳过。根因为维护契约测试未随增量Schema head更新；修复仅更新该测试期望值为0223，随后以新的云端全量验收确认。
- SQLAlchemy/PostgreSQL实际事务集成、审计同事务、迁移上/下行及全链路仍以云端run结果为准。

## 影响、迁移、回滚和验证

- 不修改Gate 2冻结API/数据字段，不新增公开API、业务Scope或HTTP；新增内部application Port、ORM repository及Alembic revision 0223。
- 空库验证0222→0223、0223→0222闭写恢复、再升级；含数据数据库验证downgrade拒绝丢弃记录且表行保持，任何外部migration downgrade仍按既有保护拒绝破坏历史。
- PostgreSQL 18 hosted验证空库和有记录升级、原子父/子/Audit写入、重复同digest、同版本异digest拒绝、rollback及行不可变/不可truncate；后端全量、wheel与现有PR集成链全跑。
- 所有包/签名为合成数据；不读客户包，不外发，不在用户本机/C盘执行。只在GitHub hosted runner的D盘临时目录执行测试。
- 回滚保留0223 migration作为历史；空表时可恢复0222闭写触发器。出现数据记录时只可回到“保留记录、闭写”，不得删包历史或回滚用户数据。

## 未覆盖

本WBS不提供HTTP上传/异步Job、二进制包归档、Verification失败审计、管理员授权/License Router、公开Package查询、revoke/install/enable/disable、Plugin subprocess、Output registry生产装配、正式签发key、Windows 11设备验收或Gate/Pilot/Release证据。生产service组合在可信兼容策略与正式signer source齐备之前不注册。
