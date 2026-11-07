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

## 第四轮 Hosted A05 启动失败（修正前记录）

Hosted run [42333300077](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42333300077) 的 backend 全量、frontend、PG18侧车构建、父包组装、P40和A35均成功；A05仍在调用Owner之前失败，随包 `initdb.exe` 同样返回 `3221225781 / 0xC0000135` 且无输出。前次仅把随包 `bin` 放入PATH并设置cwd未解决，故“仅缺bin搜索路径”假设不成立；仍不能据此认定产品或PG包根因。

修正前记录：下一轮将随包已校验的 `bin` 与 `lib` 两个目录按固定顺序置于子进程PATH首位，继续继承Hosted环境，并执行A05 PG18针对验收。此更改仅在A05验证器内，不调整父包、产品代码、Schema/Migration或生产装配。若仍为同一NTSTATUS，下一步改为记录受限PE导入依赖清单/文件存在性，避免继续猜测路径。

## 第五轮 Hosted A05 启动失败与 extraction 路径对齐（修正前记录）

Hosted run [42334361407](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42334361407) 再次在Owner调用前收到 initdb.exe exit 3221225781 / 0xC0000135；即使加入随包 bin+lib 到PATH仍未改变。该run同提交、同父包的 Clean extraction, PG18 lifecycle, and P40 live Edge download job 成功，报告 PARENT_PG18_TEMP_LIFECYCLE_PASS_LIMITED，PG18.6/pgvector 0.8.6真实临时库通过。对照已通过的 tools/smoke_windows_parent_package_pg_cloud.py，A05明显差异是PG二进制由通用候选stager解压后直接启动，而父包烟测先用stager校验/清理，再按包解压语义直接解压并逐文件复核哈希后启动。

实施前记录：A05改为先运行同一候选stager并验证收据，随后立即清理该验收副本；再将原同一ZIP直接解压到本run独占的RUNNER_TEMP根目录，检查清单、目录清单、路径/链接边界和全部payload SHA-256。取消自行定制的PATH/cwd，采用父包PG smoke相同的继承进程环境与目录布局。验收范围仍仅A05 Owner/Repository/Audit；不改产品或父包，不运行插件，不使用客户数据。若仍失败再采集受限原生依赖诊断，不再尝试路径猜测。

## 第六轮 Hosted A05 超时与 PG child pipe 修复（修正前记录）

Hosted run [42335600556](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42335600556) 的A05已通过父包校验、直接逐文件解压与 initdb，随后在 pg_ctl start 超时。日志显示 pg_ctl 使用 stdout/stderr capture pipes；Python 3.13 触发 TimeoutExpired 后，Windows communicate 仍等待 stdout reader thread join，直到整个45分钟Hosted job被取消。PG18 server child 可继承该管道，令EOF迟迟不来。这与父包烟测已成功的实现对照一致：其 pg_ctl stdout/stderr重定向至D盘文件，因此不是Owner阻塞或产品失败。另确认当前A05清理分支仍引用已删 staging 路径，需一并修正，防止未来数据库启动后残留。

实施前记录：将pg_ctl start/stop输出重定向到本run D盘日志文件，不由Python捕获继承型子进程管道；启动超时后在关闭日志句柄后读取受限尾部诊断。对已经尝试启动的PG进程使用同包 pg_ctl status检查，并只在该run自有data目录存在运行实例时fast-stop；status不能证明已停则失败关闭、不删除运行目录。清理使用直接解压目录下 pg_ctl 路径。仅验收器/CR/STATUS变更，产品Owner、包、Schema、Migration不变；继续同run父包synthetic PG18复验。


## 第七轮 Hosted A05 SQLAlchemy fixture 失败（修正前记录）

Hosted run [42339772925](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42339772925) 已成功验证同run父包、直接解压与临时 PostgreSQL 18 启动，并进入合成 fixture 数据准备；随后 SQLAlchemy 在 _seed 插入 out_context_snapshots.source_version_refs 时，将 SQL 字符串 JSON 字面量中的 :true 误解析为命名绑定参数，抛出 InvalidRequestError: A value is required for bind parameter 'true'。失败发生在 Admission Owner 首次调用之前；无Owner验收marker，未证明产品Owner错误，也未生成通过证据。该run其它并行任务状态独立记录，不混入A05结论。

实施前记录：只调整 Hosted 验收器合成fixture，将含冒号的内嵌 JSON SQL 字面量替换为 PostgreSQL jsonb_build_array(jsonb_build_object(...)) 构造（或等效的显式绑定值），不改产品Owner、冻结Schema/Migration、父包或验收范围。修复后在GitHub Hosted D盘对同run打包的合成PG18重跑A05全部原验收断言；若越过fixture后失败，依据新的固定断言/脱敏诊断再处置。回滚为还原单个fixture SQL。仅合成数据，无插件执行、客户数据或外发。
