# CR-OUT-021：真实 Output Create HTTP 与 hosted Edge 失败关闭集成

- 日期：2026-11-05
- 状态：编码前检查PASS_WITH_LIMITATION；hosted桥接代码已实现，P25真实HTTP/Edge验收仍被PG初始化阻断
- 来源：CR-OUT-015/P19真实PG18 API失败关闭证据、CR-OUT-020/P24 Edge模拟API证据
- 基线：冻结 API Contract V1 OUTPUT_REQUEST_CREATE、已批准Windows显式write组合；不改冻结合同/Schema/Migration/默认挂载

## 观察到的证据缺口

P19验证了真实Windows Create HTTP组合在Publisher manifest空时失败关闭且没有持久副作用；P24验证了真实production build的Edge请求交互，但POST由浏览器harness模拟。这两者尚未证明浏览器请求能到达真实组合、真实拒绝能以安全方式呈现在页面并保持数据库无写入。

## 选择的最小补足

在CR-OUT-021下新增仅Hosted使用的P25桥接：GitHub hosted Windows Server 2025/D盘临时目录启动隔离PG18与合成账户/Project，真实建造显式Windows Create HTTP组合并绑定loopback；Edge加载同run前端production build。登录和需求读取保持合成fixture；同源Create POST由harness通过loopback转发到真实后端，沿用浏览器Origin、Session Cookie、CSRF、Idempotency与请求体。对OutputRequest/Job/Outbox/Audit/Idempotency相关表做请求前后计数对比。

服务器Publisher manifest保持空。预期真实HTTP安全拒绝、页面提示可见、无受理回执/自动重试、持久计数不变。若HTTP意外接受或有任何写入，P25应失败关闭并调查，不伪造验收结果。

## 方案比较与差异

- 重复P19的ASGI直调：实现简单，但无法验证浏览器到HTTP、Cookie/Origin/CSRF及UI错误映射的组合，不足以补P24边界。
- 使用真实Publisher或配置测试签名钥匙：可模拟接受路径，但会引入信任/签名生成器和插件执行边界，不适合当前未具备正式信任的包。
- 选择同源Edge到真实HTTP的合成失败关闭：最小连通性补足，保留当前包真实的空信任状态，不伪造生产信任或生成文件。方案记作可回滚测试基础设施与有限客户端错误呈现调整。

## 风险、回滚、迁移与验证

- 风险：loopback转发会遮蔽部分浏览器到服务边界；通过仅POST代理与可检查的真实API端口/请求合同限制。登录/Requirement mock仍不能代表生产认证/读取组合。
- 数据影响：仅一次性runner临时合成数据库，无业务迁移；验证完成后销毁临时数据库。
- 回滚：移除P25 runner job、Node/Python bridge和临时HTTP fixture；若客户端错误映射变化则恢复对应映射。保留P19/P24各自既有证据。
- 验证：P25定向检查之后执行GitHub hosted全链（前后端、PG18/pgvector、wheel、父包/A17/A34/A35/A50、Edge），仅以PASS_SCOPE_LIMITED关闭。
- 隐私：无客户数据、外部API、厂商AI、正式秘密、真实Publisher key、插件执行或文件生成；runner temp必须D盘，用户本机及C盘不运行项目代码/测试。

## 首轮 hosted 偏差（修复前登记，2026-11-05）

- Run [41895767137](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41895767137) 中P25专用job在D盘runner temp完成前端与sidecar provenance、Node/Python语法检查和依赖安装后，sidecar包哈希/文件清单校验通过；随后Windows initdb.exe非零退出，未启动PostgreSQL、API或浏览器。P25 job失败，其他独立hosted作业继续中；无产品API修改、插件执行或数据写入。
- 首轮包装器为避免日志泄漏只报告命令名，未保留initdb标准错误，因此目前无法确定真实根因；不得假设为locale、路径或sidecar文件问题。
- 修复前方案：仅让P25 harness在命令失败时输出截断的initdb标准输出/错误尾部，并过滤临时绝对路径、用户名和控制字符；成功时保持静默。复核PG配置文件/共享库、初始化参数与D盘路径；保持密码/Secret不进入命令参数或日志。之后重跑P25及完整hosted链。此为测试诊断变更，不调整产品服务信任。


## 第二轮 hosted 偏差（修复前登记，2026-11-05）

- Run [41897161326](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41897161326) 的P25 job再次在initdb.exe启动前失败；P25脚本语法、依赖、同runPG18 sidecar完整性均通过。新增诊断显示initdb stdout/stderr均为空；当前日志尚未包括Windows进程退出码，因此根因仍未知。PostgreSQL服务、真实HTTP与Edge步骤未执行。
- 实施前方案：诊断helper仅增加进程退出码并在启动PG前依次调用包内pg_config.exe --version、postgres.exe --version，验证二进制可加载；命令失败时仍只保留截断、去runner-temp路径的标准输出/错误。复核PATH包含verified bin/lib及工作目录。不改产品代码、DB合同、Publisher信任或预期拒绝。诊断确认根因后，先记录再实施后续修复。


## 第三轮 hosted 根因证据与修正决定（实施前，2026-11-05）

- Run [41898332690](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41898332690) 的二进制版本探测均成功，但initdb正式初始化退出码为3221225781（0xC0000135，Windows STATUS_DLL_NOT_FOUND），stdout/stderr为空。证据指向初始化阶段的原生动态库加载失败；API/Edge尚未运行。
- 仓库现有PG18 hosted smoke采用同一重建sidecar、临时D盘数据目录、auth=trust/UTF8/locale=C，以poc_admin初始化，且不改写全局PATH。P25与该可复用路径的差异是使用postgres用户名并额外重写PATH。
- 最小修正：P25按已有PG smoke采用poc_admin及继承runner原PATH，保留版本探测和受限退出码/错误尾部；把D盘PG runtime/bin加入PATH只供该child process需要时再定位。该调整不改业务数据、Schema、License/Publisher信任或API。下轮若仍失败，先检查并输出隔离PG日志末尾的去路径摘要，再选后续修复。


## 第四轮 hosted 偏差与精确执行差异（修复前登记，2026-11-05）

- Run [41899785899](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41899785899) 的前后端/PG18 sidecar/P24 Edge均通过；将数据库用户改为poc_admin并取消PATH改写后，initdb仍以3221225781/0xC0000135退出，stdout/stderr为空。真实API和Edge未运行。
- 复核发现上次“与既有PG smoke相同”的描述不准确：P25虽改用poc_admin和原PATH，但仍显式向子进程传入os.environ副本，且data目录在harness工作根中；已知成功的tools/smoke_windows_pg18_sidecar.py由subprocess继承环境，并在RUNNER_TEMP直接创建独立ASCII临时子目录。
- 修正前计划：精确复用已验证的执行形状——Sidecar提取留在P25工作根；PG数据使用新的、受控前缀RUNNER_TEMP直接子目录；initdb/pg_ctl/psql不传env副本，让子进程原样继承runner环境；poc_admin及已知参数保持。PG停止后只删除两个经resolve验证且名称前缀匹配的自有临时目录；失败退出码/临时路径仍去敏。若再次失败则暂存受限PG initdb诊断Artifact，而非删除未审阅日志后继续猜改。


## 第五轮 hosted 偏差及诊断方案（修复前登记，2026-11-05）

- Run [41901521102](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41901521102) 在P25前端/后端/PG18 sidecar/P24 Edge均通过后，P25仍于initdb返回3221225781/0xC0000135退出。`pg_ctl status`对部分初始化目录返回了非预期代码，安全清理逻辑拒绝删除；临时目录保留在该GitHub runner的D盘工作区。未运行真实HTTP/Edge请求，产品代码未触及。
- 这证实之前对环境/PATH/目录形状的推断不成立。暂停猜测式参数修复。实施前计划为：失败时写一个受限P25诊断JSON，包含命令名/退出码/去runner路径的末尾stdout/stderr、pg_ctl状态码、PG临时目录内的相对文件名及大小、存在时日志去路径后的短尾；禁止提交或上传数据库文件/sidecar内容/API请求数据。workflow的证据上传step改为always运行，仅上传该摘要；未知PG进程状态时继续保留PG和runtime目录，不强行删除。取得下一轮hosted证据后再选修复。


## 第六轮 hosted 诊断结果与后续编码前检查（2026-11-05）

- Run [41903687738](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41903687738) 的前端全量测试/生产构建、后端全量测试/wheel、同run PG18/pgvector sidecar、P24 Edge 与 A50 Edge 均通过；P25 语法/输入校验通过，真实HTTP/Edge阶段仍未执行到。
- 受限摘要 Artifact 上传成功：`initdb.exe` 退出码 `3221225781 (0xC0000135)`，stdout/stderr为空；`pg_ctl status` 返回码4并指出数据目录不存在，PG临时目录为空且没有服务日志。说明初始化进程在创建数据目录前就异常退出，不能解释为数据库迁移、API拒绝或浏览器问题。无真实HTTP、Edge POST、业务表写入、插件、文件生成、客户数据或外部调用。
- 对同run完整性已校验的非发行 sidecar 做了限界静态依赖清单复核：`initdb.exe` 的直接 PostgreSQL/ICU DLL及其包内递归导入均能在包内找到；这不是 Windows 装载器实测，也无法排除系统运行库、延迟加载或运行时装载差异，根因仍为待证。
- 诊断修复本身已按前次计划实施并通过hosted语法检查，失败摘要在P25失败后成功上传。此轮P25未通过，不得关闭验收。
- 下一次编码前检查：只增强Windows Server 2025 hosted诊断，不改产品行为/API/Schema/DB数据；用runner上的Microsoft PE工具（存在时）获取`initdb.exe`依赖名称，并检查其非系统依赖/VC运行库在runner及sidecar位置的存在性；记录受限Application Error事件字段或明确“无事件”，同时保留退出码。所有输出仅DLL名称、布尔存在性、截断错误码/短事件字段并去D盘runner绝对路径；不上传runner环境变量、数据库/sidecar文件或完整系统日志。恢复状态未知时继续保留D盘临时目录。取得这一轮真实Windows装载证据后再决定是否修PATH/运行库/包选择；不得先推断并静默改包或系统。


## 第七轮 hosted 诊断与下一项实施方案（2026-11-05）

- Run [41907221688](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41907221688)：前端、后端、同run PG sidecar rebuild、父包组装、A17/A34/A35、P24 与 A50 均通过；P25 initdb仍以 `3221225781 / 0xC0000135` 退出，数据目录未创建，P25真实HTTP/Edge未执行。
- 新增Windows诊断有效运行：Microsoft `dumpbin /dependents` 递归检查initdb及其8个相关模块；输出内的全部系统/sidecar DLL定位均为present，缺失依赖列表为空；关键VC运行库位于System32；Application Error/Windows Error Reporting无initdb匹配事件。故当前证据不支持“静态缺DLL”或“缺VC Redist”结论，仍不能解释initdb初始化失败。
- 同一workflow的独立 `smoke-parent-postgresql` 作业在Windows Server 2025完成PostgreSQL 18.6/pgvector 0.8.6临时生命周期，状态 `PARENT_PG18_TEMP_LIFECYCLE_PASS_LIMITED`；同run A17、A34与A35作业也成功。该证据来自另一runner作业及父包中的PG组件，不可直接替代P25新sidecar实际调用验收。
- 下一项仅调整P25测试harness的PG初始化命令，使其精确采用已通过 `tools/smoke_windows_parent_package_pg_cloud.py` 的形式：`initdb -D <temp> -U postgres --auth-local=trust --auth-host=trust --no-locale -E UTF8`；PostgreSQL临时超级用户连接也对齐为 `postgres`。原因是这是现有Windows hosted通过证据的实际命令，可直接隔离本次P25调用差异。改动不触碰产品代码、schema、认证/License/Publisher信任或数据迁移；如失败，现有Windows依赖诊断仍随失败摘要上传。PostgreSQL临时目录只在D盘runner temp，不上传数据库文件。然后执行P25及完整hosted回归；仅真实HTTP 422、Edge安全提示且数据库计数不变方可PASS_SCOPE_LIMITED。


## 第八轮 hosted 结果与标准输入对齐检查（2026-11-05）

- Run [41910278934](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41910278934)：前端、后端、PG18 sidecar rebuild、父包/A17/A34/A35、P24/A50均通过；P25仍在initdb阶段以 `3221225781 / 0xC0000135` 退出，PG数据目录未创建，失败Artifact成功上传，HTTP/Edge未运行。将临时用户名和initdb参数对齐到通过smoke的调用后，结果未变。
- 对照同run成功的 `tools/smoke_windows_parent_package_pg_cloud.py`，现存主要进程启动差异是：其 `subprocess.run(..., capture_output=True)` 继承标准输入；P25的 `run_checked` 显式传 `stdin=DEVNULL`。`initdb` 的其他选项/用户已精确对齐；工作目录均继承runner当前目录，临时路径均位于D盘runner temp。此差异尚不能证明根因，但可作为下一项最小对照。
- 下一项编码前检查：仅移除P25命令包装器对标准输入的DEVNULL重定向，使PG18版本探测、initdb与psql均按当前已通过smoke的继承方式运行；不改产品代码、数据库合同或认证/License/Publisher信任。现有诊断保持。若initdb仍失败，不再猜测CLI/PATH，转为在同一P25 Windows进程中调用官方PostgreSQL初始化调试(`--debug --no-clean`)并仅上传截断、去敏错误尾与文件名/大小；禁止上传DB文件。通过后进入真实HTTP/Edge验证。


## 第九轮 hosted 结果与 TEMP/TMP 对照计划（2026-11-05）

- Run [41913332612](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41913332612)：前端、后端全量测试/wheel、PG sidecar rebuild、父包/A17/A34/A35、P24/A50通过；P25在 `initdb` 阶段仍以 `0xC0000135` 退出、未创建数据目录，诊断摘要上传成功。initdb参数已与通过smoke完全一致，P25命令包装器也取消了 `stdin=DEVNULL`；两项对照均未改变结果。
- 与同run成功的父包PG生命周期smoke继续对照后，剩余可见环境差异之一是workflow为P25显式设置 `TEMP/TMP=RUNNER_TEMP(D:)`，而父包smoke继承runner默认 `TEMP/TMP`。这仍是待验证的执行环境差异，不能宣称为根因。
- 下一项编码前检查：只移除P25 Python运行步骤对TEMP/TMP的显式D盘覆盖，令initdb/PG命令继承Windows hosted runner默认临时目录；所有源码检出、前端/sidecar输入、P25工作根、PG数据目录、数据库及summary仍通过 `RUNNER_TEMP` 显式固定在D盘。Python调用Edge Node子进程时显式恢复 `TEMP/TMP=RUNNER_TEMP`，避免浏览器/Node临时文件落出D盘。无数据外发或产品/Schema变化。若结果变化，记录并复查PG数据目录确在D；如仍失败，再用 `initdb --debug --no-clean` 限定诊断。


## 第十轮 hosted 结果与初始化调试方案（2026-11-05）

- Run [41916567299](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41916567299)：TEMP/TMP对照后P25仍在initdb阶段以Windows退出码 `3221225781 (0xC0000135)` 失败；摘要Artifact成功上传，未启动PG、真实HTTP或Edge POST，数据库计数验证未运行。前后端全量测试/wheel、PG18 sidecar重建、P24 hosted Edge、A50 Edge、嵌入式Python组装通过；父包组装作业在本记录时仍运行中。
- 移除P25运行步骤对TEMP/TMP的覆盖、并为Edge Node子进程显式指定D盘runner temp后，initdb结果未变化。此前对齐initdb参数、stdin及已知DLL静态依赖探测也未消除错误；静态依赖存在不能排除动态装载或初始化内部原因。根因仍未知，不能宣称为数据库/API/Edge行为。
- 下一项按第八/九轮已登记的条件方案，仅给P25合成PG `initdb` 增加官方诊断参数 `--debug --no-clean`，保留D盘runner temp边界；失败Artifact继续只包含去敏、截断输出、相对文件名/大小和状态码，不上传数据库文件、sidecar内容或完整日志。先采集初始化内部阶段证据，再决定是否调整runner环境或测试夹具。若故障导致PG状态无法确认，维持现有保留临时数据的失败关闭规则。
- 此为hosted测试诊断，不改产品代码、API、Schema、Migration、认证/License/Publisher信任或业务数据。验证门槛仍为真实HTTP安全拒绝、Edge安全提示及相关数据库计数前后不变；未满足前P25保持未通过。


## 第十一轮 hosted 诊断结果与延迟导入检查方案（2026-11-05）

- Run [41918283038](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41918283038) 的P25定向步骤加入 `initdb --debug --no-clean` 后仍以 `3221225781 (0xC0000135)` 退出。debug stdout仅报告进入debug/no-clean模式，没有初始化阶段内部说明；`pg_ctl status` 返回4，数据目录不存在、部分文件清单为空，Application Error/WER未记录initdb匹配事件。该命令未达到真实PG启动、HTTP或Edge请求，P25失败关闭。
- 同run递归静态依赖探测的9个模块均无缺失项；该检查只证明普通导入表的文件可定位，不覆盖延迟加载/按需载入。run中的前后端、PG sidecar重建、P24/A50、A17语法边界等独立作业通过，父包组装当时仍运行。没有客户数据、外部API、插件、文件发布或产品DB写入。
- 第十一轮代码仅增加受限initdb调试开关；输出与临时目录仍受现有截断、去路径/文件清单和D盘生命周期规则控制。此诊断无产品/API/Schema/Migration变更，P25仍未通过。
- 下一项编码前检查：保留普通导入扫描，追加同一hosted runner的 `dumpbin /imports` 延迟导入名称探测，覆盖initdb及当前递归依赖模块；只记录DLL名称和可定位状态，并把Application Error/WER查询扩展为initdb及postgres进程名。不得上传完整dumpbin输出、数据库文件、sidecar内容或系统日志。若没有发现可解释的差异，停止基于猜测反复改参数，转用已通过的同run父包PG二进制作哈希/版本对照或调整任务拆分，让不受阻WBS继续推进。


- 同一 \`--debug --no-clean\` 候选在 hosted run [41919589855](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41919589855) 重复复验，P25仍以 \`0xC0000135\` 在数据目录创建前失败；debug输出仍只有模式提示，普通依赖扫描无缺项，Application Error/WER摘要为空。后端/前端、PG sidecar、P24/A50和嵌入式运行时作业通过；P25未通过，不构成额外产品验收。
- 延迟导入诊断依据 Microsoft Learn 的[\`DUMPBIN /IMPORTS\`](https://learn.microsoft.com/en-us/cpp/build/reference/imports-dumpbin?view=msvc-170)（列出静态及延迟加载导入）：只解析标记为delay-load的DLL名和本机可定位状态，并把initdb、postgres及递归依赖纳入探测；Application Error/WER过滤扩展到initdb/postgres进程。摘要不保存完整工具输出或系统事件文本。


## 第十二轮 hosted 结果与 Node PATH 对照计划（2026-11-05）

- Run [41921391921](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41921391921) 的 P25 延迟导入检查探测 initdb/postgres 及常规依赖共15个模块，`DUMPBIN /IMPORTS` 未发现延迟DLL，普通及延迟依赖缺失项均为空，Application Error/WER摘要为空。添加 `--debug --no-clean` 后仍仅输出模式提示；initdb以 `0xC0000135` 退出，pg_ctl返回4，D盘数据目录和文件清单为空，真实HTTP/Edge未执行。
- 同run前后端全量/wheel、PG18 sidecar rebuild、P24/A50、嵌入式Python/Windows父包组装、父包PG生命周期smoke、A17、A34、A35均通过；父包PG smoke报告PostgreSQL 18.6/pgvector 0.8.6，P25为唯一失败job。该对照说明同run父包中的PG生命周期可运行，但尚未比较P25 initdb进程的完整PATH与父包smoke环境；不据此推断根因。
- 延迟加载/静态依赖和TEMP/TMP、stdin、命令参数对照均未解释错误。下一项只为P25 PostgreSQL子进程构造临时PATH副本，过滤由本job额外安装的Node可执行目录，同时保留系统/Python/PG路径和全局环境；对initdb、pg_ctl、psql使用该副本，Edge/Node继续使用原环境。证据摘要只记录Node目录是否找到/过滤及条目数，不输出原始PATH。PG数据和其他项目临时文件仍在D盘。
- 若该对照仍不改变initdb结果，停止反复调整环境变量；根据同run父包PG smoke成功证据，转为用已验证的父包PG目录进行二进制哈希及执行路径对照，或暂停P25并推进独立WBS。P25关闭条件仍为真实HTTP安全拒绝、Edge安全提示和数据库相关表计数不变。


## 第十三轮 hosted 结果与路线切换（2026-11-05）

- Run [41925875768](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41925875768) 的 P25 job 仍在 PostgreSQL 初始化前失败关闭：`initdb.exe` 返回 `3221225781 / 0xC0000135`；数据目录未创建，`pg_ctl status` 返回4。受限摘要确认 Node 目录被找到并只从 PostgreSQL 子进程 PATH 副本移除（1项），但错误未变；未启动PostgreSQL、真实HTTP、Edge请求或数据库计数核对，P25未通过。
- 同run后端测试/wheel、前端测试/构建、PG18/pgvector sidecar重建、嵌入式后端组装、父包候选、父包PG18.6/pgvector0.8.6生命周期、A35、A17和A34均成功。此处仅作独立作业结果，不能替代P25真实HTTP/Edge验收。
- PATH对照未改变结果，依既有止猜测条件不再改动P25环境变量。按STATUS已登记的下一步，对剩余Output/Worker trust boundary进行独立盘点：当前Jobs generic claim可覆盖`OUTPUT_GENERATE`，而现有明确的Plugin Worker只做包验证且不执行插件；因此先为Output生成作业建立严格Owner专属claim边界，不接通或执行插件。该路线切换与接受范围见`OUT-01-A01-P26`编码前检查。
- 所有运行均在GitHub hosted Windows Server 2025 runner的D盘临时区；用户本机/C盘未运行项目程序、代码或测试。没有客户数据、外部API调用、插件执行或输出文件生成。


## 第十四轮 hosted 证据与包内 PostgreSQL 对照计划（实施前登记，2026-11-05）

- Run [41953529123](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41953529123) 的 P25 仍在 initdb.exe 建库前以 3221225781 / 0xC0000135 失败，数据目录不存在；没有启动真实 HTTP、Edge 或执行数据库写入。hosted 诊断记录了 initdb/postgres 及递归依赖共 15 个模块，普通/延迟导入缺失列表为空，System32 VC/UCRT 项存在，Application Error 事件为空。另有同轮父包PG生命周期 smoke 成功，证明该runner作业中的另一份包内PG可以运行，但目前尚未与P25重建sidecar逐文件比较。
- 环境参数、TEMP/TMP、stdin、调用参数和普通/延迟依赖诊断已多轮无效；停止继续调整环境变量。根据此前登记的止猜测条件，下一项仅增加基于同run、provenance校验的父包候选与P25 sidecar的 PostgreSQL 文件指纹/版本及安全初始化对照。先检查两个候选的相对路径与SHA-256，摘要只保留相对DLL/EXE文件名、hash、版本和错误码，不上传PG数据文件或完整日志；父包候选须验证commit/run/release_eligible=false，所有解包和数据目录都留在D盘RUNNER_TEMP。
- 对照不得降低P25门槛或伪造发行信任：仅当已通过父包smoke的候选运行形状可在同一P25进程中复现、并能定位sidecar与父包二进制/布局差异时，才据证据选择后续最小修复；两者若内容完全相同仍失败，记录阻塞并转向独立WBS。任何PostgreSQL启动仅限一次性合成库；无HTTP/Edge请求则不声称P25通过。
- 风险/范围：只改P25 hosted 验收夹具与诊断，暂不改产品API、Schema/Migration、Publisher信任或安装包。迁移无；回滚删除对照输入/脚本并恢复单sidecar job；运行失败时保留D盘临时数据。验证：GitHub hosted Windows Server 2025上完成二进制/版本差异检查及同进程最小生命周期对照，成功后再运行真实HTTP+Edge失败关闭全链。无客户数据、秘密、外部API、插件执行、输出文件或C盘/用户本机执行。


## 第十四轮 hosted 结果与阻塞转向（2026-11-05）

- Run [41956565929](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41956565929) 中P25新增对照成功执行：同一commit/run的父包验证通过，父包记录的PG archive SHA与sidecar SHA一致；从两份包读取并对比了1,627个PostgreSQL payload文件，路径集合及SHA-256完全一致，无差异。P25同一Windows runner进程从父包路径独立执行initdb，仍以3221225781/0xC0000135失败，输出无额外错误，data目录未创建；随后sidecar路径也重复相同失败。真实HTTP/Edge仍未执行。
- 同run父包完整独立 smoke `Clean extraction and temporary PostgreSQL lifecycle smoke` 为success，A17/A34/A35/A50亦成功；因此同一候选在不同Windows hosted job可启动，而P25 job无法启动。证据把差异收窄为任务执行环境/装载上下文，不能归因PG文件内容。多轮系统/DLL/环境探针已无解释力；暂停P25猜测式修复，保留P25为BLOCKED_DIAGNOSTIC，必须之后在能启动该包PG的同一受控作业组合中重试真实HTTP/Edge门槛。
- 本轮仅新增P25诊断比较脚本与workflow输入，验证该脚本源代码在GitHub hosted执行；不改产品代码、API、Schema或DB。P25专用job失败，主workflow不全绿；前后端、PG sidecar/父包组装、父包PG smoke及其他列明作业通过。没有生成客户数据、外部调用、插件执行、输出文件或C盘运行。
- 按“阻塞转向不受影响WBS”，暂停P25并进入CR-OUT-026/OUT-01-A01-P30：实现活动Output lease下不可重试失败的Job/Output原子终态收敛。仍使用已通过的同run父包PG smoke承载隔离PG验证，不把其结果当P25通过。用户本机/C盘代码和测试执行始终为零。


## Run 42017800786 hosted differential result (2026-11-05)

P25 的 runner-temp 输入校验、PG sidecar provenance、依赖清单/语法检查及“同run父包PostgreSQL启动对照”步骤均成功；父包与 sidecar 的 1,627 个 PostgreSQL payload 文件 SHA-256 一致。但对照中的父包 initdb 与 P25 initdb 都以 `3221225781 / 0xC0000135` 退出，均未创建数据目录；P25 受限摘要确认 PG 目录为空、无服务日志、`pg_ctl` 指向目录不存在。静态依赖扫描未发现缺失项，系统错误事件为空；真实 API、Edge POST 和业务写入均未发生。故本轮排除“父包/sidecar payload差异”，未提供可据以修复的系统装载根因，不能将P25标为通过。

本次结果不支持继续重复相同 initdb 参数/PATH/目录对照。下一步从既有 P25 父包临时数据库 smoke 与 P25 harness 的**进程启动上下文/实际二进制装载环境**差异读取配置和实现，并设计一个会区分假设的最小 hosted probe；偏差/修复仍先记本CR再运行。不要强制清理任何未知临时PG进程或数据目录；本次 runner 已报告 initdb 未创建目录。继续保持仅D盘 hosted执行。


## 差异对照修正：PG子进程 PATH 过滤（变更前记录，2026-11-05）

对Run [42017800786](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42017800786) P25失败日志与已知通过的 `tools/smoke_windows_pg18_sidecar.py` 逐行对照后发现，CR前文“复用既有 smoke 执行形状”的表述不准确：P25 的 `postgres_child_environment()` 会从PATH中删除 Node 安装目录，摘要确认 `node_directory_removed=true`；同run父包差异对照也复用了这一过滤环境，所以其initdb失败并未与通过的既有 smoke 形成有效对照。既有 smoke 原样继承 Windows runner PATH，且可以初始化同一套 PG18 sidecar。此结果提供了此前未隔离的可检验差异，虽尚不能证明根因就是 PATH。

**实施前选择：** 移除P25对 Node PATH 项的过滤，让initdb、pg_ctl、psql按既有成功 smoke 继承未修改的 runner PATH；保留D盘独立目录、合成数据库、受限摘要、无客户数据和失败时不强制清理。同步修正父包对照使其采用同样原始PATH。若此单变量对照仍失败，则恢复代码或另立下一项差异，不再重复参数/目录猜测。此次只改Hosted验证harness，不改产品代码/API/Schema、Publisher信任或真实功能状态。


## 2026-11-05 实际P25启动命令与已通过smoke不一致（代码调整前登记）

进一步比较当前文件源码（而非历史计划描述）后确认，`tools/smoke_windows_pg18_sidecar.py`通过的启动命令是 `--pgdata=<D:\\Temp child> --username=poc_admin --auth=trust --encoding=UTF8 --locale=C`，并继承原始runner环境；当前P25仍使用 `-D <D:\\Temp child> -U postgres --auth-local=trust --auth-host=trust --no-locale -E UTF8 --debug --no-clean`，且先从PATH删除Node目录。前述“按既有 smoke 精确对齐”的实现并未反映在当前源码。这解释了为什么与父包的差异对照不能代表已通过的 smoke 命令。

**最小可判别调整：** 仅将P25和其父包对照的 initdb 用户、参数及环境继承改为逐项复用已通过 smoke 的启动形状；取消Node PATH过滤，同时保留P25所需的隔离D盘目录、不同loopback端口、临时库名、受限摘要和未初始化时的保留策略。分别记录数据目录仅含临时合成数据。该实验整体验证的是“精确复用已通过的 PG smoke 初始化协议后，P25真实HTTP/Edge是否可继续”，不是产品功能修复；若仍失败再根据新证据选择，不声称当前猜测已确认根因。


## Run 42020582422 复验结果与下一单变量（变更前记录，2026-11-05）

本次已把P25/父包对照命令改为smoke相同的 `poc_admin`、`--auth=trust`、`--encoding=UTF8`、`--locale=C`，并保留原始PATH；但父包initdb对照和P25实际initdb仍均以 `0xC0000135`、空stdout/stderr、未创建数据目录退出。与此同时同run `Clean extraction and temporary PostgreSQL lifecycle smoke` 成功，P25与父包的D盘输入摘要/sidecar一致。这证明命令参数差异并非充分解释，尚未定位根因。

当前两个任务的显著环境差异之一是P25为Edge显式运行 `setup-node`，其PATH包含Node目录；成功的父包PG smoke未设置Node。此前Node路径过滤曾与不同initdb参数一起尝试，不能隔离该因果因素。下一轮实施唯一变量：在P25的PG child环境及同run父包差异脚本中移除Node安装目录PATH，同时保持本次smoke命令/用户/数据目录/其他环境不变；摘要仅报告过滤是否发生和计数。若仍失败，则不再认为Node PATH是充分根因，转向逐项导出成功 smoke 与 P25 的非敏感环境变量差异，不扩展产品代码。


## Run 42022786436 Node PATH 单变量结果与 runner 对照计划（变更前记录，2026-11-05）

精确 smoke 参数下，P25 与其D盘父包对照均从原始PATH中移除Node目录后仍以 `3221225781 / 0xC0000135` 退出；摘要确认未建数据目录且无服务日志。同run独立父包PG smoke成功，故Node PATH删除不是充分修复。该次Hosted run的后端、wheel、前端/build、PG sidecar、嵌入式运行时和父包组装成功；P25仍BLOCKED_DIAGNOSTIC，不改变Pilot/Gate/Release结论。

源码比较发现当前成功的PG smoke job没有执行 `actions/setup-node`，P25 job会执行Node 24。为识别任务级 runner 环境差异，下一次只在成功的 `smoke-parent-postgresql` job加入与P25相同的 `actions/setup-node@v4, node-version=24`，不改P25命令或sidecar。若其仍通过，则继续比较安全白名单内的环境变量名称/非敏感配置；若失败，Node安装对照成立，再进一步仅隔离其环境影响。新对照仍只用合成数据库和D盘临时目录。


## Run 42024740026 Node 24 smoke 对照结果（2026-11-05）

成功的 `smoke-parent-postgresql` job加入 `actions/setup-node@v4,node-version=24` 后，清洁提取的 PostgreSQL/pgvector生命周期 smoke 仍成功；同run P25主流程及父包initdb对照仍因 `0xC0000135` 在数据目录创建前失败。P25摘要无临时数据库文件/日志，Node PATH过滤已发生。故“安装Node 24”及单独Node PATH均不是充分解释，CR-OUT-021近期两轮对该环境问题未能收敛。

决策：停止重复 initdb 旗标/PATH/安装Node对照，P25继续 `BLOCKED_DIAGNOSTIC`，保存各轮合成摘要与现有失败关闭行为。把研发时间转回独立可交付的P34 Output文件发布路径；若后续因P34/Pilot验收必须恢复P25诊断，再先在同一P25 job中运行既有PG smoke helper作进程内对照，并只采集经过允许列表筛选的非敏感环境证据。当前不会把P25描述成通过。


## 2026-11-06 同一 P25 job 复用父包 PG smoke（实施前记录）

run [42156574221](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42156574221) 中P39已通过Hosted Edge保存合同，但P25仍在initdb启动前以 `0xC0000135` 失败。既有父包临时PG18 smoke在独立job通过；CR-OUT-021既有决策要求恢复P25时，先在P25同一job运行该helper，再采集白名单环境证据。本次编码前检查见 `docs/progress/out-01-a01-p25-same-job-smoke-precheck.md`。

**实施前决策：** 在P25输入完整性/语法/provenance检查之后、原有父包与sidecar initdb差分之前，使用完全相同的父包ZIP与verification-summary，在唯一RUNNER_TEMP/D盘子目录运行既有 `tools/smoke_windows_parent_package_pg_cloud.py`。不改其命令参数、不修改生产代码或服务；helper失败则该job立即停止，成功才进入既有P25差分/HTTP/Edge流程。结果将区分“同job PG smoke已失败”与“同job smoke成功但P25后续仍失败”；仍不把诊断当成P25通过。数据只为一次性合成临时PG。回滚仅删除该工作流步骤及本次文档。


## P25 同一 Hosted job PG18 smoke 差分实现候选（2026-11-06）

基于 `e2d2debd72dd816af004bce97288ccd9e3928b76` 的编码前检查，Hosted workflow候选在P25的既有D盘输入/provenance/语法检查后、父包与sidecar initdb差分前，新增单一步骤调用已在独立 `Clean extraction and temporary PostgreSQL lifecycle smoke` job通过的 `tools/smoke_windows_parent_package_pg_cloud.py`。该步骤复用完全相同的父包ZIP与verification summary，使用新的RUNNER_TEMP直系work-root和summary；nonzero立即停止P25 job，成功才进入原有P25步骤。summary纳入P25的Always evidence上传。只改workflow与追踪文档；无生产代码/API/Schema/Migration/安装包变化，无客户数据/秘密/外部调用/插件执行。

该实现候选尚未通过Hosted运行；不得把同job smoke本身描述为P25 HTTP/Edge通过。回滚为删除该单一步骤和关联证据路径。


## Run 42159992981 同作业 smoke 成功、P25过滤 PATH 仍失败（2026-11-06）

- run [42159992981](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42159992981)：P25同一Windows Server 2025 job中，新增既有 `smoke_windows_parent_package_pg_cloud.py` 成功，摘要 `PARENT_PG18_TEMP_LIFECYCLE_PASS_LIMITED`，PostgreSQL 18.6/pgvector 0.8.6、D盘临时库，父包SHA-256 `aae4c268e2e27864139f54a3c553fbf5bb1d1db471a5cb15b465814004dcc857`。随后父包/sidecar对照证明1,627个PG payload路径及hash完全相同，但过滤Node目录PATH的父包直接initdb仍以 `3221225781/0xC0000135`退出；P25同样失败。数据目录未创建，输出空；HTTP/Edge未启动。
- 完整smoke能在同一job成功，但尚不能证明Node PATH过滤是根因：smoke使用候选原始PG路径、继承未改PATH，initdb用户/参数也不同。下一步按唯一问题做精确单变量：同一解包二进制、相同参数、同job分别用原PATH及只移除Node目录的PATH运行initdb；若两者同结果，不再归因PATH。
- 后端全量、wheel、前端测试/build、PG侧车/父包、P39、P24、A50、A17/A34/A35等其他jobs成功；P25失败令整体workflow为failure。P25仍BLOCKED_DIAGNOSTIC，不构成Pilot/Gate/Release通过。


## 相同解包 PG 二进制的 PATH 双臂探针实现候选（2026-11-06）

依据本CR上一节和 `docs/progress/out-01-a01-p25-same-binary-path-precheck.md`，仅扩展 `validation/out-01-a01-p25-real-http-edge/compare_parent_pg.py`：同一已校验父包PG payload解包路径中的同一个initdb.exe，以完全一致的P25参数分别执行原PATH与移除Node路径后的PATH；各用独立RUNNER_TEMP子目录。结果只记录Node路径过滤布尔/计数、退出码、stdout/stderr字节数和PG_VERSION存在布尔，不记录原始环境、错误文本或库内容。未改P25真实流程、产品代码/API/Schema。回滚仅还原比较器和对应追踪记录。代码候选等待Hosted Windows验收，尚无结果。


## Run 42162415883 PATH 双臂结果：排除PATH过滤为充分原因（2026-11-06）

- P25同一Hosted Windows job中的compare步骤使用同一父包payload解包路径下的同一个 `initdb.exe`、完全相同P25参数及独立D盘数据目录。Node目录过滤PATH删除1项；过滤与原始PATH两臂都返回 `3221225781/0xC0000135`，stdout/stderr均0字节，均未创建 `PG_VERSION`。同run真实P25也失败，未启动HTTP/Edge。PG18.6/pgvector 0.8.6 payload 1,627项与sidecar一致。
- 因两臂结果一致，PATH过滤不是充分原因。此前同一job的parent-package smoke成功，但它使用另一个initdb调用profile（`-D`, `-U postgres`, `--auth-local=trust`, `--auth-host=trust`, `--no-locale`, `-E UTF8`），而P25使用 `--pgdata`, `--username=poc_admin`, `--auth=trust`, `--encoding=UTF8`, `--locale=C`。此前证据没有在同一个解包二进制路径下对这两个profile做比较。
- 下一步按本CR先记录一个明确差异：同一initdb路径、原始PATH、同一D盘runner-temp父目录，分别运行上列两个既有profile；只记录退出码、输出字节数及PG_VERSION存在布尔。两profile差异视为一个“命令profile”变量组；如结果不同，再拆解用户/auth/locale旗标，不能直接归因单一旗标。不得改生产harness行为或宣称P25通过。
- run [42162415883](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42162415883)其余jobs成功，P25单job失败使整体workflow结论为failure；P25/Pilot/Gate/Release状态不变。
