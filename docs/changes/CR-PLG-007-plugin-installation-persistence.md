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
