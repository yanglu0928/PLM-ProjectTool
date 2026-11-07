# CR-EXEC-052：PLG-03-A05 Admission Owner Hosted PG18 针对性验收

- 日期：2026-11-07
- Phase/WBS：Phase 2 Platform Core / PLG-03-A05
- 状态：编码前检查完成，待新增托管验收器与独立复验
- 基线：CR-EXEC-050、CR-EXEC-051；冻结 PluginExecution schema、Jobs/Output/Audit contracts 不变
- 类型：验证范围补齐；仅新增 Hosted synthetic PG18 验收器及调用点，不改产品API、DB Schema、Migration、默认组合或Worker

## 发现与证据

CR-EXEC-051 实现已提交并通过静态复核。锁顺序修正先登记于 CR-EXEC-051：精确拒绝非整数 attempt，且避免在已锁定 Installation 后逆序锁定不可变 Package/Manifest。

Hosted run [42326604885](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42326604885) 证据：
- Backend 全量 4,105 tests、wheel；Frontend tests/build；同一提交的 embedded runtime、parent package、A17 candidate assembly 均成功。
- P25 real HTTP/Edge failure-closed 通过；A17 packaged PlanVersion/HTTPS/PostgreSQL 流程通过。
- A05新增单元用例纳入Backend全量，但该套件使用应用测试端口/mock，未在PG18实际调用Admission Owner/Repository/Audit；因此A05数据库验收标准尚未满足，不得标PASS。
- 同次run的SUR-07-A08仍因 child initdb.exe exit 3221225781失败；TEMP环境探测同码，且未应用，按CR-EXEC-039维持停止。父包P40在history-ready阶段失败，安全诊断仅显示登录200、output-request history GET 200、无网络失败、无运行时异常、无summary；两者均非本WBS，不在此处顺手修复。
- 公开/生产Publisher trust仍为空；真实Worker未接线；不能执行插件。

## 编码前检查与计划

- 输入：PLG-03-A05 Owner/Repository/Application tests、PLG-03-A01 migration verifier、父包PG18 lifecycle smoke。
- 缺口：当前PG18 smoke验证迁移和其他Owners，但没有对新Admission Owner作数据库调用；A05只获得4,105项应用回归，不能替代该证据。
- 唯一任务：增加独立Windows Hosted D盘 PG18 验收器，并从既有临时PG18 smoke在migration及PLG-03 schema完成后调用。
- 验收：在独立合成数据库上迁移至当前Head，使用真实SQLAlchemy UoW、Plugin Execution Repository及AuditService；Jobs fencing/Output admission仅注入显式synthetic ports，不伪装为正式信任或客户事实。验证 PENDING root、state event、Audit 同事务持久化；相同绑定重放不增加记录；审计失败整体回滚；invalid attempt/stale claim在零持久化时拒绝；数据库guard关闭时写入仍失败。数据库及临时文件严格归GitHub Hosted runner D盘当前run，清理仅限自有随机数据库和目录。
- 本验收不得安装/启动/运行插件，不开启Worker，不发客户数据，不加入生产装配。回滚为移除验收器/调用点；无需数据迁移。

## 实施进展

2026-11-07：针对性 Hosted PG18 verifier 与独立 Workflow job 已提交，等待该提交对应的 Windows runner 结果；在结果到达前 PLG-03-A05 不关闭。验证器使用真实 Jobs fencing Repository、Plugin Execution Repository、SQLAlchemy UoW 与 AuditService，Output admission 为明确 synthetic port。
- 前置数据：只合成Project/User/OutputRequest/ContextSnapshot/Plugin package/install/manifest/Job；Publisher trust及用户客户数据均不参与。
- Secret scan：提交前扫描全部新增/修改文件内容；Hosted Windows runner执行语法、PG18 smoke与后端全量/wheel。

## 偏差边界

本次补验是关闭原已批准验收标准的证据缺口，不更改冻结Schema、授权语义、模块边界或正式范围。A08/P40失败保持单独记录并在有独立可行路径时处理；不将整体非全绿run表述成全通过。


## 实现前静态复核记录（2026-11-07）

针对性验收器首次提交后、Hosted执行前复核发现测试夹具自身三项问题：tools/下脚本的仓库根目录层级计算多了一层；两个合成请求重复创建同一插件版本/启用安装，违反唯一约束且会令target查询歧义；计数辅助函数在无参数查询时缺少默认参数。均为验证器缺陷，尚未声称PG验收失败或通过。修复前先记录：将根路径改为仓库根、两请求共享一个合成安装目标、计数查询默认空参数，并在修正后由新Hosted提交复验；产品Owner代码不因本记录改动。


## Hosted fixture与记录格式复核（2026-11-07，修正前记录）

进一步检查冻结Plugin Installation迁移发现ENABLED installation/operation fixture受 plm.plugin_installation_owner_write 事务GUC保护。验收器必须仅在新建的合成PG数据库fixture写入事务内通过事务本地GUC准备安装事实；随后实际Admission Owner使用独立UoW并自行设置plm.plugin_execution_owner_write。此fixture办法只为建立合成输入，不验证/冒充安装Owner或正式trust。另发现上次文件写入把两个换行标记成字面反斜线n，导致CR和STATUS局部Markdown不整洁；本次修复前先记录，将恢复为真实换行且不改记录内容。

## 首轮 Hosted 验收偏差（修正前记录）

Hosted run [42329871400](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42329871400) 的新增A05 job在PG初始化前失败：复用的parent staging helper要求提取目标为RUNNER_TEMP的直接子目录，而首轮脚本将其放在本run根目录下的子目录。失败发生于路径边界检查，没有启动PG、没有调用Owner、没有产品代码副作用或外发数据。修正为同一个run拥有的D盘RUNNER_TEMP两个直接子目录（受校验包暂存目录、PG运行目录），并对二者分别验证边界后清理；随后重新Hosted复验。


## 第二轮 Hosted 验收偏差（修正前记录）

Hosted run [42330769351](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42330769351) 已通过路径暂存边界并校验父包，随后 packaged initdb.exe 返回非零，stdout/stderr均为空；PG尚未启动、数据库尚未创建，因此Owner未被调用。现有验证辅助函数只回显空输出，遗漏numeric process exit code，无法区分原生加载失败与其他初始化拒绝。此失败属于新建验收器/运行输入诊断，未证明产品Owner失败。实施前记录诊断调整：固定输出子进程basename与数值exit code，将该步骤Stage写入仅合成摘要；不回显任意环境或用户内容，不改产品代码。之后Hosted D盘重跑。


## 第三轮 Hosted A05 启动失败（修正前记录）

Hosted run [42331887380](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42331887380) 的A05 job已完成父包SHA/清单校验和PG verifier依赖安装，但随包 `initdb.exe` 以Windows进程退出码 `3221225781` 退出，折合 `0xC0000135`，没有标准输出/错误；PG实例未初始化，Admission Owner未调用。该状态码指向DLL装载失败，尚未证明具体缺失模块或产品问题。A05仍未通过。

修正前记录的唯一调整：为验收器启动的每个随包PostgreSQL进程设置显式子进程环境，将已经校验的 `payload/pgsql/bin` 置于PATH首位并设为工作目录；继承其它Hosted环境，禁止打印环境变量，不更改父包内容、业务实现、DB Schema/Migration或产品装配。随后在同run父包上重跑A05；若原生加载错误仍存在，再以受限且不回显环境的Windows依赖诊断定位模块，不将假设记为根因。