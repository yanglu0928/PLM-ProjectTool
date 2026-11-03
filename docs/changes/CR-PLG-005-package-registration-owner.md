# CR-PLG-005：可信插件包元数据登记Owner与路线纠正

- 日期：2026-11-03
- 状态：PASS_SCOPE_LIMITED
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
- 验收范围补强（实施前记录）：run 41586377357全13 jobs成功，3,909后端项及0223 schema lifecycle通过；复核后确认现有集成链只验证Plugin migration guards，PackageRegistration SQLAlchemy repository 与真实 Audit 在PostgreSQL同事务的端到端断言尚缺。为满足本CR原定原子性验收，在临时PG18 smoke中增加合成包真实SQLAlchemy UOW + Audit验证（首次写入、幂等、版本冲突、审计异常回滚及不可变守卫），不改产品行为或冻结基线。A07在补强验收完成前保持未关闭。
- 代码审查偏差（验证前记录）：新增PG集成夹具的Python bytes字面量在生成时将Ed25519域分隔符的 `\\x00` 留成双反斜杠，静态对照现有Verifier后发现会导致签名消息不一致；测试输入修正为单个Python转义表示，产品代码不变。
- 云端依赖偏差（run 41588604941）：A07 PG集成脚本由Smoke runner Python调用，但Smoke的独立migration验证依赖安装未包含已批准且在 backend pyproject 固定为 `cryptography==50.0.1` 的验证器依赖，故脚本在签名夹具初始化前以ModuleNotFoundError退出。仅给托管验证器依赖安装补上相同锁定版本；不更改产品依赖或运行逻辑，再跑完整链。
- 集成验收偏差（run 41589975872）：cryptography补齐后，真实登记调用失败并按应用安全边界返回 `PLUGIN_PACKAGE_STORE_UNAVAILABLE`；当前验收日志无法区分仓储flush与Audit append阶段。先在 synthetic verifier 中加入仅输出执行阶段、异常类型及数据库SQLSTATE的临时安全诊断，以定位缺陷；不记录异常消息、SQL参数或业务内容。定位后先在本CR记录修复，再修产品/验证并重新完整复验。
- 第二轮诊断结果（run 41591445571）：失败定位到 `repository.create_verified`，底层为SQLAlchemy `IntegrityError`；包裹错误的SQLSTATE在 `orig.sqlstate`，约束名在 `orig.diag.constraint_name`，上一版诊断读取了外层字段因而未提供细因。仅扩展临时诊断读取上述两个结构化字段，仍不打印SQL/参数/异常消息，再定位具体约束。
- 第三轮根因及修复计划（run 41592723031）：A07真实PG登记在 `plg_manifest_operations` 触发 `fk_plg_manifest_operations__package` / SQLSTATE `23503`。SQLAlchemy UOW关闭autoflush，且当前子表ORM无关系映射提供排序，仓储一次加入父子后批量flush使子行先写。修复仅在同一UOW中先 `flush([package])` 明确父行，再添加并flush operations/dependencies/verification；不得提前commit。子表失败或Audit失败仍整体rollback。验证覆盖真实PG首次写入、审计提交/失败回滚、幂等、冲突及迁移守卫。

## 影响、迁移、回滚和验证

- 不修改Gate 2冻结API/数据字段，不新增公开API、业务Scope或HTTP；新增内部application Port、ORM repository及Alembic revision 0223。
- 空库验证0222→0223、0223→0222闭写恢复、再升级；含数据数据库验证downgrade拒绝丢弃记录且表行保持，任何外部migration downgrade仍按既有保护拒绝破坏历史。
- PostgreSQL 18 hosted验证空库和有记录升级、原子父/子/Audit写入、重复同digest、同版本异digest拒绝、rollback及行不可变/不可truncate；后端全量、wheel与现有PR集成链全跑。
- 所有包/签名为合成数据；不读客户包，不外发，不在用户本机/C盘执行。只在GitHub hosted runner的D盘临时目录执行测试。
- 回滚保留0223 migration作为历史；空表时可恢复0222闭写触发器。出现数据记录时只可回到“保留记录、闭写”，不得删包历史或回滚用户数据。

## 未覆盖

本WBS不提供HTTP上传/异步Job、二进制包归档、Verification失败审计、管理员授权/License Router、公开Package查询、revoke/install/enable/disable、Plugin subprocess、Output registry生产装配、正式签发key、Windows 11设备验收或Gate/Pilot/Release证据。生产service组合在可信兼容策略与正式signer source齐备之前不注册。


## 最终验收与关闭（2026-11-03）

- GitHub hosted run [41593955795](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41593955795) 全13/13 jobs成功；后端3,909项、wheel、前端、PG18/pgvector、父包、A35/A17/A34链均成功。
- PostgreSQL 18真实临时库通过同UOW Package父行/Manifest子表/PASSED Verification/Audit提交，Audit异常回滚，重复同摘要幂等、版本摘要冲突及0223不可变守卫。
- A07实现与父行flush修复提交分别为 `715c1646b2ba530e15998bb0cf63eddd7bf4a55f` 与 `894dd2d3f4c5fc6fc5acba5c29ec0f5a528b34c2`。
- 结论：`PASS_SCOPE_LIMITED`。仅合成包/密钥/兼容策略与托管PG证据；未连接公开HTTP/Job、未持久化ZIP、未安装/运行插件。生产信任、Win11实机、Gate、Pilot、Release状态不变。
- 所有测试均在GitHub hosted Windows Server 2025 runner D盘临时工作区执行，未在用户本机/C盘运行。
