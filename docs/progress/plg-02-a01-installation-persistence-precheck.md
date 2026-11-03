# PLG-02-A01：PluginInstallation冻结根持久化编码前检查

- 日期：2026-11-04
- 状态：CODE_SUBMITTED_AWAITING_HOSTED（编码前检查已通过；云端验收待完成）
- WBS：PLG-02-A01
- 变更记录：CR-PLG-007
- 当前分支父提交：38ade3a290ba2b69113ad6c207357d045c65500f

## 编码前检查

- 冻结模型定义PLG-02 PluginInstallation的精确package_ref、状态、validated runtime snapshot、enabled operations子集、installed/enabled actor与UTC时间；SC-01已映射根plg_installations和owned plg_enabled_operations、plg_runtime_validations；SC-02给出M-DEP字段profile。此任务补齐缺失物理实现，不改冻结文档或新增Aggregate Root。
- 当前PLG ORM/migrations仅覆盖PLG-01到revision 20261103_0224，没有PLG-02 ORM/Table。A08 Worker只登记Package VERIFIED元数据，不创建安装、启用、兼容性或信任事实。
- 无安装/启用API Owner，故本WBS只建立ORM、migration、database-schema verifier及hosted验收，不挂路由/命令，不创建演示/客户事实。
- Installation用复合FK固定引用Package及其plugin normalized id；enabled operation用复合FK确保操作声明来自安装的精确Package；partial unique index落实同plugin operation至多一个启用行。Runtime validations独立记录并只追加。
- 初始migration的三表写入口保持关闭、拒绝TRUNCATE；后续PLG-02 Owner WBS单独按审计/幂等/expected lock_version打开允许的写入。down仅对全空三表开放，存有记录则失败关闭。
- 不需改API Contract、Schema冻结文件、默认组合或外部依赖；无Project正文或Secret进入字段/测试工件。
- 验收位置为GitHub Actions hosted Windows runner D盘工作区；本机不运行代码/测试。

## 实施与验收计划

新增revision 20261104_0225 Migration及对应ORM，验证Alembic head与metadata一致；增加定向schema契约测试，并扩展PG18 smoke覆盖空库升级/降级/重升、0224既有PLG-01数据升级保留、父子FK/unique/state/time/snapshot拒绝、Owner写关闭、TRUNCATE拒绝和有数据down保护。提交后等待完整hosted workflow：backend全量/wheel、frontend、PG18/pgvector、Windows父包、A17/A34。失败先记录CR偏差再修复。

## 明确不在本项

不安装或启用插件，不更改publisher trust manifest，不把VERIFIED写成ENABLED，不运行插件子进程，不实现安装/升级/启停Owner/API，也不宣称Output Create可用。A01通过最多为PASS_SCOPE_LIMITED；Pilot/Gate/Release结论不变。


## 实现提交

- 实现提交374fb1f619467e99590a622b5118c9c58c13b8da包含三表ORM、Migration 20261104_0225、Schema metadata约束和Alembic head契约检查。
- GitHub hosted workflow尚未完成；结果补录前保持A01进行中。


## 首轮GitHub hosted偏差（2026-11-04）

- Workflow [41699265146](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41699265146) 在Backend全量测试中3925项有1项失败；失败测试为 `test_platform_audit_auth_and_license_tables_are_registered`。
- 失败原因：该历史元数据清单的排除集合仍只覆盖既有PLG表；ORM本次正确新增的 `plg_installations`、`plg_enabled_operations`、`plg_runtime_validations` 被误计为平台/Audit/Auth/License元数据。没有证据表明Migration或业务逻辑失败；Backend步骤在完整测试后以该一项断言退出，wheel/A17后续Job因此跳过。
- 修复计划：仅将三张PLG-02表纳入该清单的排除集合，保留本次表结构和冻结约束不变；重新运行同分支完整hosted workflow，取得PostgreSQL 18及A17证据后再关闭A01。
- 偏差记录先于修复提交；未在本机运行测试。
