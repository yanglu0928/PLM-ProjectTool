# CR-PLG-011：Installation操作受控停用Owner

- 日期：2026-11-04
- 状态：已完成；PLG-02-A06 `PASS_SCOPE_LIMITED`，GitHub hosted run 41755590662 全部13个jobs成功
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


## PostgreSQL 验收夹具偏差记录（2026-11-04）

- 新增PG18集成验证脚本后静态复核发现合成签名消息中的Python字节转义多了一层反斜杠，会让签名夹具与包验签规范不匹配。
- 尚未执行该集成脚本；现有A06 Owner单元测试及其所在的全量云端测试已通过，该签名夹具问题不影响产品代码。
- 处理计划：将字节分隔符修复为与已有PLG-01合成验证一致的NUL字节，并由同一PG18 hosted smoke执行实际登记、安装事实、两操作启用/停用、并发版本拒绝、审计回滚和精确重放。


## 首轮PG18 hosted smoke超时记录（2026-11-04）

- Hosted run [41754111643](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41754111643) 的后端3,959项测试、前端、PG sidecar、embedded runtime和父包组装成功；A35交接也成功。
- 父包PG smoke在运行新A06验证前，于既有Pilot readiness PowerShell探针等待30秒后触发`subprocess.TimeoutExpired`。因此本轮没有执行到A06 PG owner集成脚本；不得把本轮解释为A06 PG用例失败或通过。
- 修正计划：把该隔离诊断探针的执行上限从30秒提高到90秒，保持输入/断言/产品行为不变，然后完整重跑 hosted 链，确认A06验证确实执行。


## 验收结果（2026-11-04）

- Owner代码提交：`50d25328e04e45dca90a58b5faea53d4a4a3140b`；PG验证脚本接线/签名夹具和等待上限修正提交：`f50005053b644a94a00ee3df3066169a58519ac2`、`75c13c2224e86fa91307079d43d220a60cffe705`、`1c542ea52ff7bef4f87fd558ee4e01e5c0b1ab6b`。
- GitHub hosted workflow [41755590662](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41755590662) 与最终分支头一致，13/13 jobs成功。后端3,959项全量测试、wheel、前端、PG18/pgvector、嵌入式后端、父包、A35/A17/A34/A50均成功。
- 新增真实PG18临时数据库集成：合成签名包两操作启用后，停用成功落库为`DISABLED`、lock_version=2、active_operations=0、4条不可变history和2条逐操作disable Audit。陈旧版本拒绝；Audit失败回滚全部操作/Installation变化；精确版本重放无变化。结果在PG smoke artifact 13287594475。
- 父包候选SHA-256 `cfe8f74d3a1b8da7a76aa35e86baa8026e9148414c76c499e04de24baa3d1072`，20,173文件。A17 artifact 13288092884为合成hosted Windows Server 2025流程：29 API调用、PlanVersion IN_REVIEW、客户决定0。A34 artifact 13288657373通过4个marker保留和人工恢复；产品API仍未启动，正式信任前置仍阻塞。
- A06仅新增内部Owner/托管验收，不挂公开HTTP/默认组合，不进行物理安装、卸载或插件执行，不构成Win11实机、正式信任、Pilot/Gate/Release通过。本机/C盘没有运行代码。
- 先前PG smoke的Pilot readiness PowerShell子进程30秒超时已记录；等待上限增至90秒后完整workflow通过。初次代码静态复核中发现的disabled replay条件及签名夹具转义问题均先记CR再修正；最终定向、全量与PG18验证通过。
- 下一项：PLG-02-A07 `PLUGIN_INSTALLATION_GET`只读详情API编码前检查。
