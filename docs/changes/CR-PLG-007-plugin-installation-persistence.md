# CR-PLG-007：实现冻结PLG-02安装事实的持久化基础

- 日期：2026-11-04
- 状态：已登记；按用户持续自主执行授权进入实施，客观验收未完成前不得关闭
- 原因：OUT-01-A01-P10确认当前缺少PluginInstallation、enabled operation及runtime validation持久化Owner；冻结模型/SC-01已定义PLG-02根及owned tables。
- 范围：只实现冻结PLG-02的PostgreSQL ORM/Migration和Schema验证；不改Gate 2基线内容、不新增Root、API、依赖、插件执行器或正式信任来源。

## 决定

依冻结Data Model、SC-01映射和SC-02 M-DEP profile，新增Migration 20261104_0225：

- plg_installations：安装身份、精确Package复合引用、plugin normalized id、安装状态、当前validated runtime snapshot、安装/启用责任主体及UTC时间、M-DEP创建/更新与lock_version字段。
- plg_enabled_operations：安装所选启用操作，复合引用精确Installation和该Package的Manifest operation；操作行唯一，并以(plugin_id_normalized, operation_id)唯一索引阻止同一插件操作同时由多个Installation启用。
- plg_runtime_validations：保留安装运行环境检查快照、兼容结果、检查主体及UTC时间；只追加，不允许UPDATE/DELETE。
- 新表初始保持Owner写入口关闭；分别拒绝TRUNCATE。后续PLG-02业务Owner WBS再按明确生命周期命令开放最小写入，不由PLG-01包验证Worker写入。
- Installation精确指向Package及normalized plugin id；状态用冻结值INSTALLED/ENABLED/DISABLED/INCOMPATIBLE/RETIRED。本次迁移不创建安装、启用、信任或客户事实。

## 偏差、风险、兼容与回滚

这是既有冻结Root/table mapping的物理Migration实现，不新增或重定义Schema/API/Data Model基线。列按M-DEP通用字段语义展开。不涉及外部API或用户数据迁移，无新增运行依赖。

父子复合FK、部分唯一索引和保护触发器的风险由GitHub hosted PostgreSQL 18验收覆盖：空库升级、既有PLG-01行保留、约束反例、空表降级重升、有记录降级拒绝。降级仅当三个PLG-02表全空时允许；存在记录即拒绝以保留事实及版本链。失败时不开放Owner写入；先记录CR偏差，再修复代码/夹具，不删除历史。

## 验收

实现后在GitHub hosted runner的D盘临时空间执行ORM契约、后端全量/wheel、PG18迁移与父子约束/Owner写关闭/TRUNCATE/有数据降级反例、Windows父包及A17/A34全流程。禁止本机/C盘运行项目代码或测试。

## 授权边界

按用户已持续授权自主实施。此CR不授权真实发布者Key/信任、客户数据访问或外发、插件正式安装/启用、插件代码执行、付款、强推或不可恢复生产变更；验收结论仅按实际hosted run记录。


## PLG-02-A01编码提交（hosted验收待完成，2026-11-04）

- 实现提交：374fb1f619467e99590a622b5118c9c58c13b8da。新增Installation、enabled operation和runtime validation ORM以及Migration 20261104_0225；三表Owner写入口关闭，enabled operation复合引用安装和Package Manifest，unique index限制同插件操作的重复启用行。
- 增加插件Schema metadata与Migration head契约测试。已推送至PR #61分支；等待GitHub hosted全链验收，通过前不关闭A01。
- 目前没有安装/启用Owner/API或写入数据；信任清单未变，未运行插件。


## 首轮GitHub hosted偏差（2026-11-04）

- Workflow [41699265146](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41699265146) 在Backend全量测试中3925项有1项失败；失败测试为 `test_platform_audit_auth_and_license_tables_are_registered`。
- 失败原因：该历史元数据清单的排除集合仍只覆盖既有PLG表；ORM本次正确新增的 `plg_installations`、`plg_enabled_operations`、`plg_runtime_validations` 被误计为平台/Audit/Auth/License元数据。没有证据表明Migration或业务逻辑失败；Backend步骤在完整测试后以该一项断言退出，wheel/A17后续Job因此跳过。
- 修复计划：仅将三张PLG-02表纳入该清单的排除集合，保留本次表结构和冻结约束不变；重新运行同分支完整hosted workflow，取得PostgreSQL 18及A17证据后再关闭A01。
- 偏差记录先于修复提交；未在本机运行测试。


## PostgreSQL hosted smoke验收脚本偏差（2026-11-04）

- Hosted run [41700273515](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41700273515) 的Backend 3,925项全量测试通过，随后父包PostgreSQL smoke因旧 `validation/out-01-a01-p01-migration/verify.py` 固定期待Migration head 20261103_0224而失败；报告为“empty upgrade did not reach schema head”。
- 初步归因是验收脚本尚未跟进本次合法head 20261104_0225；不是数据库建表失败证据。A17在该run中的结果尚未结束，A01仍未通过。
- 修复前计划：更新该PG verifier的目标head和下迁移边界，确保新增表存在、空库降级/重升安全且原有Output Migration保护仍验证；之后完整重跑hosted workflow。失败与修复先后保留。


## Windows父包PG smoke的PLG-01验证器版本边界偏差（2026-11-04）

- Hosted run [41702575629](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41702575629) 的后端全量回归、前端构建、PG18 sidecar、Windows父包组装、A17 PlanVersion流程、A35交接均通过；父包PG smoke在调用既有 `validation/plg-01-a01-package-schema/verify.py` 时失败，原因是该脚本仍把当前Migration head固定为 `20261103_0224`。
- 该偏差来自PLG-02新增head `20261104_0225` 后，PLG-01端到端迁移验证器未同步版本边界；不是PLG-02迁移建表失败证据。A17虽通过，但A34因父包PG smoke依赖失败而跳过；本轮整体不可判全通过。
- 修复计划：将PLG-01 verifier的预期head更新为 `20261104_0225`，保留其 `0223` downgrade边界及原PLG-01存量保护断言；另在PG18脚本里核对PLG-02三张表、Owner关闭和TRUNCATE守卫，并覆盖空库升级/降级/重升。随后重跑GitHub hosted完整工作流。此变更只同步schema验证目标，不修改产品Schema/API/Owner。
- 偏差在修复提交之前登记；所有运行只在GitHub hosted Windows runner的D盘临时区进行。


## PLG-02完整数据库反例验收缺口（2026-11-04）

- Hosted run [41705767222](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41705767222) 在版本头/表检查修正后13/13 jobs成功，含后端全量、父包PG18 migration smoke、A17与A34。A17/A34通过只证明各自既有业务流程。
- 对照本CR原始验收清单复核 `validation/out-01-a01-p01-migration/verify.py` 后发现：PLG-02 smoke 已检查三表建表、三个Owner关闭触发器及空库降级/重升，但没有实际对三表逐项执行TRUNCATE拒绝，也没有对已含PluginInstallation合成记录的库执行0225降级拒绝；复合FK/唯一索引目前仅有ORM单元契约检查，尚缺PG18实库catalog断言。故run全绿仍不足以关闭PLG-02-A01。
- 下一步先增加本缺口记录，再扩展PG18隔离验证：核对四个复合FK和操作唯一索引、对三表执行TRUNCATE拒绝、使用仅测试库的受控触发器旁路插入合成安装事实并验证降0225被拒且revision/记录保留；不连真实客户库，不创建生产安装/信任事实。完成后重新跑完整GitHub hosted工作流，再据证据判定A01。
- 所有反例仅运行在GitHub hosted Windows runner D盘临时区；用户本机不运行代码或测试。


## PG18 TRUNCATE反例被外键检查提前拒绝（2026-11-04）

- Hosted run [41708851678](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41708851678) 后端、前端、wheel、运行时组装均成功；新增的PG18迁移反例在检查 `plg_installations` 单表TRUNCATE时收到PostgreSQL `FeatureNotSupported`（被 `plg_enabled_operations` 外键引用），未到达目标Owner触发器。此次失败是验证方法不正确，不是业务表可被清空的证据；A01尚未通过。
- 修复计划：保持三表触发器及FK不变。对无子表引用的enabled/runtime history分别执行TRUNCATE负例；对安装根及其子表使用同一TRUNCATE语句，避免数据库FK预检查截断验证路径，并要求触发器RaiseException。之后重跑同一完整hosted workflow。
- 偏差已先记录；运行仍仅使用GitHub hosted runner的D盘临时数据库。


## PLG-02-A01最终云端验收（2026-11-04）

- PLG-02-A01实现提交 `374fb1f619467e99590a622b5118c9c58c13b8da` 增加三张冻结安装持久化ORM表与Migration `20261104_0225`；PG18验证器最终修订提交 `75319ae2fd7584688c4317c9bbef1f5f46e4be7d`。
- GitHub hosted workflow [41711045048](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41711045048) 完成13/13 jobs成功，含后端全量/wheel、前端构建、PG18/pgvector重建、Windows候选父包、PG18迁移、A17和A34。
- PG18.6隔离临时库结果：全新升级/空库降级重升、既有PLG-01合成行升级保留均PASS；验证4个复合FK与操作唯一索引；三个Owner INSERT关闭；子表单独TRUNCATE及含父子三表的组TRUNCATE均由触发器拒绝；用受控的仅测试库Owner触发器旁路写入合成Installation/EnabledOperation/RuntimeValidation记录后，降级至0224被拒，revision及3表记录计数保持不变。数据库均为临时合成库，外部调用0，客户数据0。
- 同run父包候选20161个文件，归档SHA-256 `5227ebdf41bca790a5af75ae68964b599059807ad5117ed6e9a88e8abcd01858`；不是发行包。A17与A34均成功，但它们不表示用户Windows 11新设备、正式插件信任、实际插件安装/执行通过。
- 先前偏差与修复已按顺序留痕：ORM历史metadata清单漏排除三表；旧PG验证器期待0224；实库验收最初只检查元数据；首次TRUNCATE根表探测被FK预检查提前拒绝。对应偏差均先在本CR/进度文件记录再修正验证器或测试。
- 结论：PLG-02-A01 `PASS_SCOPE_LIMITED`，范围仅为冻结持久化结构及迁移保护；安装事实Owner API、启用流程、正式信任、插件执行均未开放。Pilot、Gate、正式Release状态不变。下一项PLG-02-A02安装事实Owner编码前核查。


## PLG-02-A02编码前决定（2026-11-04）

- 检查确认冻结模型定义Installation事实，但当前只有PLG-01 Package元数据登记和A01关闭写入表；没有物理安装器、Installation Owner、公开API或默认组合。为避免把VERIFIED误记成已安装，本WBS限定为：内部Owner只接收受控安装适配器核实的精确Package/包Hash及宿主兼容性快照，原子创建`INSTALLED`行、RuntimeValidation和Audit；重复installation ID同内容回放幂等、内容冲突拒绝。
- 本项不执行包文件部署，不启用/停用、不变更enabled_operations、不建API/默认组合、不运行插件。无真实受控适配器的部署无法调用该Owner；合成适配器仅用于hosted验收。
- A01的所有写入关闭守卫需改为仅两张Owner目标表允许事务局部授权INSERT，继续拒绝UPDATE/DELETE/TRUNCATE；enabled_operations维持关闭。局部DB标记只约束应用写路径，不替代未来真实数据库身份隔离。该实现偏差先记于本决定，待验证失败时先补记再修复。
- 无冻结模型/API变化、外部依赖、客户数据或外部调用；风险、迁移/回滚及PG18验收细项见`docs/progress/plg-02-a02-installation-owner-precheck.md`。`20261104_0226`降级只允许两张目标表均为空；含事实时拒绝且保留历史。


## PLG-02-A02首轮托管回归偏差（2026-11-04，修复前记录）

- Hosted run [41717001638](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41717001638) 后端运行3,932项，唯一失败为 `test_configuration_revision_follows_platform_baseline`：新增migration head实际为`20261104_0226`，历史契约测试仍期待`20261104_0225`。前端、PG18 sidecar、Python base、A50均通过；依赖后端成功的wheel、父包、A17/A34链被跳过。
- 当前证据指向迁移head测试夹具未随合法PLG-02增量更新，不表示Owner业务断言失败。修复计划仅把该单一测试的head预期更新为0226，保留其单head检查和其他migration contract；随后重跑完整hosted工作流及PG18 Owner smoke。该偏差已先记录，后修改测试。
