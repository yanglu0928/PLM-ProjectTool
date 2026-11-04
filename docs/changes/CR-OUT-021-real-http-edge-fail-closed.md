# CR-OUT-021：真实 Output Create HTTP 与 hosted Edge 失败关闭集成

- 日期：2026-11-05
- 状态：编码前检查PASS_WITH_LIMITATION；hosted实现与复验待执行
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
