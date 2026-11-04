# CR-PLG-011：Installation操作受控停用Owner

- 日期：2026-11-04
- 状态：已登记；A06编码与托管验收待完成
- WBS：PLG-02-A06
- 基线：Gate 2冻结的Data Model V1、DB Schema V1、API Contract V1；CR-PLG-008/009/010

## 原因

冻结API-03定义DeploymentAdmin的`PLUGIN_DISABLE`，要求对Installation执行受控停用。当前Activation Owner只有启用/操作集合替换命令；Runtime Revalidation会在运行时不兼容时撤销操作，Retirement Owner会把Installation终态退役，但两者都不能表达管理员主动停用且保留Installation为DISABLED的事实。真实文件安装适配器和正式包签名信任源尚未提供，因此不能把物理安装或其安全性当成当前可验收前置。

## 决定与范围

- 本CR将PLG-02-A06拆分为可独立云端验收的内部停用Owner；不实现HTTP/API、默认组合、物理安装/卸载或PluginExecution。
- 命令绑定Installation ID、actor、trace及expected lock_version。使用现有plugin级事务锁、Installation/操作锁、Activation Context、数据库Owner授权标记和UoW。
- 对合格的ENABLED Installation原子清除全部启用操作，为每项写不可变DISABLED History和关联Audit，再写Installation停用Audit、置为DISABLED并递增版本。仅当已DISABLED且没有活动操作时允许精确版本的无变更重放。
- RETIRED、INCOMPATIBLE、陈旧版本、活动操作/状态不一致及非兼容Package/Runtime均失败关闭。
- 先核对0227～0229约束是否已覆盖此转换。若数据库守卫无法表达该冻结状态，先暂停该写路径并另建CR/最小迁移；不得绕开触发器或扩大运行时权限。
- 不新增业务Root/表/字段/公开API、外部依赖或冻结协议变更；不创建真实安装事实，不启动子进程。

## 风险与回滚

风险包括并发启用与停用、漏撤操作、History/Audit部分提交、错误版本状态以及把DISABLED误当成UNINSTALLED。采用共同plugin锁、锁版本比较和单事务，定向覆盖竞态、失败回滚和重复命令。代码回滚不恢复已提交的业务状态；当前工作只使用合成托管数据，不操作生产数据库，数据清理由测试事务/隔离数据库负责。

## 验证计划

GitHub hosted Windows runner D:临时目录中运行定向测试、后端全量测试/wheel、PG18真实Migration guard以及既有包构建验收链。检查提交中不存在Secret、客户数据、日志和本地配置。无本机或C盘程序执行。结论不超过`PASS_SCOPE_LIMITED`；不代表真实签名信任、实机安装、Pilot、Gate或Release通过。


## 编码阶段偏差记录（2026-11-04）

- 初始实现的关闭校验误把“当前已DISABLED且无活动操作”拒绝，和本CR声明的精确版本无变化重放行为相反。
- 发现于代码提交后的静态复核，尚无hosted验收结论；不是测试通过或客户/生产事实。
- 处理计划：先修正校验只拒绝ENABLED但无操作、或非ENABLED仍有操作的矛盾状态；保留DISABLED/空操作且expected lock_version精确匹配的无变化返回。用定向单测覆盖后在GitHub hosted runner复验。无数据迁移或业务数据写入。
