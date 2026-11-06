# OUT-01-A01-P25 编码前检查：真实Harness复用完整父包PG运行根

- 日期：2026-11-06
- Change Request：CR-OUT-021
- WBS：OUT-01-A01-P25
- 结论：PASS_WITH_LIMITATION，允许实施一个可回滚的Hosted测试夹具布局修正；P25维持BLOCKED_DIAGNOSTIC。

## 单一问题与证据

run [42166973706](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42166973706) 在同一Hosted Windows Server 2025 job中，以相同P25 initdb profile和原始runner环境，在经完整性校验的父包提取根成功（exit 0，PG_VERSION=true）；现有compare的PG-only提取根及真实P25 Harness侧车提取均返回0xC0000135、零输出。父包/sidecar的1,627项PG payload路径与Hash完全一致。布局/加载上下文影响是证据支持的判断；尚未定位具体DLL。

## 编码前检查与实施

- 现有流程已同job下载、验签名/Hash并完整解包非发行父包，之后删除提取根；P25 Harness再次从同run PG sidecar独立解包，导致运行上下文不同。
- 仅让P25 workflow使用parent-smoke helper的可选“保留提取根”flag；成功后保留完整包根，清除helper产生的合成PG临时数据。非P25调用保持原清理路径。
- P25 Harness从保留根的 payload/pgsql 运行，并要求同run smoke摘要中的Run ID、Commit、PASS状态和完整根P25 initdb成功字段匹配；把sidecar逐文件hash与父包嵌入式PG树核验，避免错用或未经校验二进制。
- Hosted workflow的P25步骤结束后执行always清理，仅允许本Run的D盘RUNNER_TEMP直系精确命名目录；Harness自身在finally也执行受路径约束清理。
- 保留compare中的PG-only失败摘要作为原故障基线；不改变生产API、Schema、迁移、License/Publisher信任或默认挂载。

## 验收与边界

只在GitHub Hosted Windows Server 2025/D盘运行。合成数据库/Project、空Publisher manifest、无客户数据/外部API/插件/文件生成。若数据库不能安全停止或清理路径不匹配则失败并保留受限诊断。运行成功最多为PASS_SCOPE_LIMITED；不得推断Pilot/Gate/Release通过。

回滚删除保留flag、完整根传递、复用验证和always清理代码，恢复sidecar PG-only解包方式。只记录退出/字节数/状态布尔，不输出环境值、原始错误文本、DB内容。Secret检查不提交客户数据/令牌/密码。

## run 42170525215 后的下一轮编码前检查（2026-11-06）

- 结果：完整父包P25 initdb profile成功、完整根复用和1,627项sidecar/嵌入式PG Hash匹配均通过；P25 Harness实际执行 initdb 后，错误明确为无法在父包根外的RUNNER_TEMP新建data目录（Permission denied）。PG_CTL因data目录不存在返回4；后续清理逻辑将该可恢复的“尚未创建数据库目录”状态包装成cleanup异常。P25从未启动PostgreSQL/API/Edge，14/15 workflow jobs成功，整体仍failure。
- 证据支持优先把P25本次合成PG工作目录改为已验证父包根的直系子目录，使目录ACL继承与成功P25 profile所在完整根一致；不把permission denied进一步推断成产品缺陷。工作目录仅D盘/同run临时父包，具名为 p25-real-pg-<run-id>，由Harness在确认停止/未创建data后清理，workflow always cleanup父根兜底。
- 单独修复Harness终结处理：pg_ctl返回4只有在pg_data确实不存在、pg_run确属当前保留父包根的精确直系子目录且无reparse点时，才允许移除空测试目录并让原始initdb异常向上报告；其他非3/运行态仍失败关闭。不得将状态4写成数据库已停止。
- 范围保持不变：没有产品代码、API、DB、迁移或Publisher trust变化；保留run 421705为失败证据。Hosted独立复验后才可能关闭P25；成功上限仍PASS_SCOPE_LIMITED。用户本机/C盘不运行代码。


## 目录权限调整实现候选（2026-11-06）

- P25 Harness现将唯一的合成PostgreSQL工作目录放入同run、已验证完整父包根下的 p25-real-pg-<run-id>；该父包根内此前已由相同P25 initdb profile验证可建数据目录。PG runtime继续使用逐文件匹配sidecar的 payload/pgsql。没有改initdb flags、PATH过滤或HTTP流程。
- finally逻辑允许pg_ctl status=4仅在data目录缺失、目录未变成reparse点、pg_run为根内精确命名直系子目录且该目录无其他内容时清理；否则仍保留并失败关闭。该分支只清理测试夹具目录，不把initdb失败变为通过。
- 代码候选已同步到功能分支，尚未Hosted验收；P25仍BLOCKED_DIAGNOSTIC。


## Run 42172719463 后诊断与单点修正编码前检查（2026-11-06）

- 结果：同run父包/PG18.6/pgvector0.8.6、完整根及根内data启动、sidecar逐文件Hash和always清理通过；P25 Edge确实向真实Create HTTP组合发送一次POST，但Harness记录HTTP 500。页面展示安全的通用不可用/提交结果未确认提示，预设的精确验证文案没有出现。
- 其余14/15 jobs成功，包括后端全量/wheel、前端测试/build、PG18/pgvector、父包/A17/A34/A35/P24/P39/A50等。整体Workflow失败。数据库前后快照未完成，不能宣称无写入；同一日志中的422事件未能关联到该POST。
- 单一问题：现有Harness在UI文案等待失败时立即退出，并且没有保存安全错误码，丢失了后续DB复核及根因所需的最小证据。
- 结论：PASS_WITH_LIMITATION，仅允许Harness诊断/控制流修正。Node从真实合成响应解析错误码但只保留固定允许的协议错误码，否则写UNRECOGNIZED；页面文本仅归类为有限枚举；即使预期文案缺失，也先写Node结构化摘要并让Python执行after snapshot，最终仍严格要求HTTP 422、预期安全UI类别、单POST、无回执/重试及数据库计数不变，任一不符退出失败。不得将500改判通过，不改产品逻辑，不记录响应正文/认证/异常原文。
- 之后通过GitHub Hosted Windows/D盘全链验收。失败继续登记，不影响其他WBS；本机/C盘不运行项目代码。


## Harness诊断候选实施记录（2026-11-06，待Hosted）

- 按上述编码前检查，仅改P25 Node/Python验证器：错误Envelope只输出协议白名单码或UNRECOGNIZED；Edge alert归为固定类别；真实请求分支继续检查无回执/无自动重试，但不因预设文案未出现而提前异常退出。
- Python读取Node摘要后先比较请求前后数据库快照，再联合严格判定HTTP 422、VALIDATION_FAILED、指定安全UI类别、单POST、无成功回执及计数不变。失败摘要最多保留HTTP状态、错误枚举、UI类别、请求次数、数据库相等/进程退出布尔；不包含原始正文/异常消息。
- 仅GitHub分支改动；尚未Hosted验收，P25仍BLOCKED_DIAGNOSTIC。没有本机/C盘运行。


## Run 42176547201后补充编码前检查（2026-11-06）

- Hosted结果：PG真实初始化/启动、父包对照、Node Harness语法检查和always清理通过；P25 Node正常写出诊断。有限结果显示real_backend_posts=0、HTTP/error code为空、UI类别SAFE_SUBMISSION_UNCONFIRMED、数据库前后目标计数相同。no_status_receipt=false，而no_success_receipt=true。由此只能证明本轮选定表快照未变化，不能证明真实Create API已到达或拒绝。
- 上轮run 421727的POST status=500没有本轮上游证据支持；不把它报告为Output HTTP响应。当前根因是UI动作到upstream桥的连通/路由仍待识别。
- 结论PASS_WITH_LIMITATION：仅增加Harness-only path class/method/status摘要，限在realbackend动作时间窗且去掉UUID/query/header/body；并将成功回执验证限于成功文案/结果文本，不把非成功ARIA状态误作回执。下一轮仍严格要求一个真实upstream POST/HTTP422/VALIDATION_FAILED/无重试/无成功回执/DB不变，未满足继续失败关闭。
- 只在GitHub Hosted Windows D盘验收，不在用户本机/C盘运行。


## Path-class诊断候选实施记录（2026-11-06，待Hosted）

- realbackend阶段现在截取本轮UI动作发生后的合成API请求，仅保留method、固定path class、status/upstream status及白名单错误码，最大20条；不输出UUID/查询参数/请求头/正文/错误消息。
- 不再将任何ARIA status节点存在视为成功回执；只检查成功受理/创建语义，同时保留无自动重试检查。
- Python继续先比较数据库前后快照，再严格判定真实后端POST/HTTP/错误码/UI/回执/计数合同。Harness退出及临时根D盘always清理条件不放宽。尚未Hosted验收，P25不PASS。


## 42178693259后的代理异常类编码前检查（2026-11-06）

- 请求轨迹已将路径定位为OUTPUT_REQUESTS_CREATE、method POST，Node自身status 500，backend_status/error code为空；数据库目标计数前后相同；前端安全提示为提交结果未确认。故请求确实到Node本地代理，但没有上游HTTP响应。当前Harness外层catch返回了原始错误字符串，既不安全也不利于区分故障阶段。
- 结论PASS_WITH_LIMITATION：Node外层catch仅对本轮真实Output POST填固定proxy_failure_class：Fetch TypeError映射FETCH_TYPE_ERROR，其余映射PROXY_EXCEPTION；向Edge只返回固定SYSTEM_UNAVAILABLE 503，绝不回传异常message。请求方法/path class/status/upstream status/proxy class有限诊断保留。Node仍需成功产生摘要、Python先执行DB快照后严格判定；成功条件不放宽。
- 只做Hosted Harness修正，不改真实产品代码。通过GitHub Hosted Windows/D盘验证；本机/C盘不运行。
