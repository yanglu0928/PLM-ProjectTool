# CR-PRT-006：Prototype 并发测量的 Hosted 资源与 SQL 可比性诊断

日期：2026-11-07。状态：编码前检查完成，待实施/Hosted验收；性能门槛仍 FAIL。

## 来源与证据

Gate 3 当前阻塞明确包含 Prototype 非 AI GET 20 并发 P95 ≤500ms 未达。docs/progress/prt-01-a11-a05-p04-p23-current-baseline-load.md 记录默认池业务P95 932–1028ms、临时20+0池912–930ms；docs/progress/prt-01-a11-a05-p04-p24-load-variability.md 同轮默认池615–667ms而临时池997–1084ms，方向反转。现有结果无法区分宿主资源波动、采样扰动、请求路径和数据库工作量，不能据此调连接池或业务授权逻辑。

## 执行前检查

- Phase：2 Platform Core；单一WBS：PRT-01-A11-A05-P04-P25，只增强现有20并发合成负载Harness的资源观察能力。
- 输入基线：冻结Prototype资格/授权/来源完整性语义，非AI GET P95≤500ms；P23/P24结果；CR-EXEC-002的Win11 Pilot优先顺序。
- 前置：P23/P24功能断言通过但性能未达；父包Hosted PG18 smoke与P40/P25已经各自PASS_LIMITED。当前不改变产品Owner、API、Schema、配置和连接池。
- 验收：Hosted Windows Server 2025 D盘用合成数据运行既有负载；在完整负载Verifier进程运行期间以固定间隔采样CPU与可用内存，仅记录总运行时长和聚合P95/极值；采样范围覆盖夹具准备、HTTP负载及清理，不伪装为单独HTTP阶段计时；只输出聚合数值，不记录主机名、用户名、SQL参数、请求正文、Cookie或凭据；诊断失效不得使功能验收误报通过，且P95门槛仍独立判定。保留业务状态/强ETag/来源/文件证明与零写断言。
- 限制：Hosted Windows Server 2025数据不能证明Windows 11 P95；该WBS只检验观测器和实验可解释性，不关闭性能Gate或Pilot。

## 方案、影响与恢复

- 方案A：直接提高生产连接池。拒绝：P24方向反转且没有资源证据。
- 方案B（所选）：仅在测试Harness加入可选、白名单摘要的Windows资源采样，使用标准库/Win32只读计数；任何平台/权限不可用均返回固定UNAVAILABLE并继续原功能断言，不能输出原始系统信息。
- 方案C：降低500ms门槛或剔除权限、Review、source checks。拒绝：违反冻结验收和安全边界。
- API/Schema/数据库/产品运行配置无变化，无迁移或用户数据影响。回滚为删除Harness采样器、其单测和workflow调用；原产品与P23/P24基准保持不变。
- GitHub Hosted Windows Server 2025 D盘全量Backend/Frontend和专用合成PG18/Edge回归；Secret检查。禁止用户本机/C盘运行代码。未通过或测量不可用则如实保留FAIL，转向独立任务。


## 实施前静态复核偏差

首次采样器草稿将可用内存值误接到CPU汇总数组，静态逐行复核在执行前发现。草稿尚未运行、未用于报告；先登记后调整采样接口为独立返回CPU百分比与可用内存值，并增加计算/汇总/不可用状态单测。若Hosted验证未能证明每项CPU样本来自SystemTimes差值，则不采纳性能观测结论。


## 首轮完整 Hosted 负载偏差（2026-11-07）

PRT P25专项job 128400386400：Backend dependencies安装与同run PostgreSQL 18 sidecar下载均成功；完整验证器执行后返回非零，任务失败。工作流只输出固定失败句并在finally清理原始D盘日志，未保留异常类别、阶段marker或源码位置。因此不能判定为产品性能缺陷、性能门槛失败或环境问题；本轮性能状态保持未判定。先记录后新增严格allowlist摘要：整数exit code、异常类名、最多8条源码basename:line和固定marker名；不输出异常正文、日志、SQL、请求/凭据/临时路径。复验后按摘要决定后续，原始日志继续不上传。


## 第二轮 Hosted 诊断缺口（2026-11-07）

PRT job 128402481517现已保留安全摘要：RuntimeError，调用帧为验证器包入口及物理PG验证器line 1521，marker仅PRT_HOST_RESOURCE_SUMMARY。源行对应initdb启动边界，但共享物理PG helper把子进程returncode省略在通用RuntimeError中；未能区分加载错误/其他初始化错误。下一步先记录并仅把整数returncode添加到内部固定异常摘要，由CI白名单提取命令basename+数值码；不输出stdout/stderr/路径/消息，不重复同一initdb猜测环境变量。依据退出码若为已知DLL装载失败，则按CR-EXEC-039原则停止该环境路径，保留P95未判定。


## 第三轮实施方案（2026-11-07）

Hosted run [42372561151](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42372561151) 的受限摘要确定：失败命令initdb.exe，exit code 3221225781 (0xC0000135)，调用帧落在PRT验证器将本轮runtime复制到scratch之后的初始化步骤。该run同轮PG18 sidecar构建成功，前轮父包 smoke 也已从完整候选包启动隔离PG18成功。证据差异是 PRT 验证器复制 bin/lib/share 后使用副本，而父包直接使用已校验包布局；不改变TEMP/TMP或Loader搜索假设。

选择的最小方案：PRT只读复用由本轮固定摘要旁包解压并校验的完整PG18/pgvector运行目录，数据库 data/log仍仅放置本run D盘scratch；启动前检查必需二进制/扩展文件，缺失立即停止。删除PG目录复制和二次复制vector扩展。该变更仅验证Harness布局，回滚为恢复原copytree行为；不改产品/DB/API/性能门槛。完整Hosted PRT验收复跑，若仍0xC0000135则停止本运行路径，不尝试TEMP/PATH猜测。


## Runtime复用修正后的静态边界复核

切换到完整runtime后，首次patch静态复核发现原PG lifecycle try/finally的缩进边界尚未随复制块调整，且源目录检查位于scratch创建后；尚未运行或解析执行。先记录后将源目录/必要文件验证移到scratch创建之前，并保留PG启动、验证与清理逻辑在同一try/finally内，避免失败时留下临时目录。
