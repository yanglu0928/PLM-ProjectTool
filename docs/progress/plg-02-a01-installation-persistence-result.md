# PLG-02-A01：PluginInstallation冻结根持久化 — 云端验收结果

- 日期：2026-11-04
- 结论：`PASS_SCOPE_LIMITED`
- 变更基线：冻结Data Model/SC-01/SC-02；Migration `20261104_0225`，下迁移 `20261103_0224`。
- 实现提交：`374fb1f619467e99590a622b5118c9c58c13b8da`；PG verifier最终修正：`75319ae2fd7584688c4317c9bbef1f5f46e4be7d`。
- CR：[`CR-PLG-007`](../changes/CR-PLG-007-plugin-installation-persistence.md)

## 实现范围

新增 `plg_installations`、`plg_enabled_operations`、`plg_runtime_validations` ORM和PostgreSQL迁移。安装身份复合指向精确的不可变PluginPackage；EnabledOperation复合指向Installation/Package Manifest operation，并约束同一plugin operation不可重复启用；RuntimeValidation保存兼容性快照。首版三表INSERT/UPDATE/DELETE均由Owner关闭，三表TRUNCATE被拒，RuntimeValidation不可变。没有新增API或业务Owner，不会安装、启用、信任或执行插件。

## 云端验证

- GitHub hosted workflow [41711045048](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41711045048)：13/13 jobs成功；全量后端回归/wheel、前端构建、PG18/pgvector、Python运行时、Windows父包、A17、A34与A35均通过。
- PostgreSQL 18.6隔离临时数据库：全新迁移升级成功；四个复合FK及操作唯一索引在系统目录中存在；三表Owner INSERT拒绝；两个子表单独TRUNCATE和三表同句TRUNCATE均返回触发器拒绝；0225空表降级到0224并重升成功。
- 在仅供本轮使用的数据库中，使用受控触发器旁路写入合成Installation/EnabledOperation/RuntimeValidation数据，模拟已有历史；降级至0224按设计拒绝，Alembic revision保持0225且表内计数为2/1/1。之后测试库由runner清理。该旁路仅是测试夹具，不开放生产写权限。
- 与已有PLG-01 package/manifest合成历史一起从0224升级至0225，既有记录及平台维护状态保持；外部调用0、客户数据0、生产数据库false。
- 同run内部父包候选20,161文件，SHA-256 `5227ebdf41bca790a5af75ae68964b599059807ad5117ed6e9a88e8abcd01858`；候选为非发行，未启动产品API或服务。A17/A34仅说明已有合成业务链和包替换演练通过。

## 偏差与修复追溯

1. 后端首次回归的历史ORM清单漏排除三张PLG-02表，已先记CR后修复清单。
2. 旧PLG-01 PG verifier固定期待0224，造成首轮父包migration smoke失败；已登记后将版本头与三表存在性同步到0225。
3. 首次对照原验收清单发现没有实库TRUNCATE及有数据降级反例；已先登记后加入PG18负例。
4. 首次TRUNCATE根表单表探测被PostgreSQL外键预检查提前拒绝；已先记录后改为子表单独探测与三表同句探测。最终实库日志均为PASS。

## 限制与下一步

此WBS只验证冻结持久化结构及迁移保护。安装事实Owner命令、状态转换服务、API、授权/License/正式信任、插件执行及Output生产Create仍未完成。未进行本机运行或Windows 11本次实机安装。Pilot、Gate 3～7及正式Release保持NOT_READY。下一项为PLG-02-A02 Installation事实Owner编码前核查。
