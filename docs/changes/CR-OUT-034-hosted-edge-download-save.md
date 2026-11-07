# CR-OUT-034：Hosted Edge输出历史下载文件保存验收

- 日期：2026-11-06
- 状态：编码前检查通过，Hosted Edge验收待实施
- WBS：OUT-01-A01-P39
- 来源：P37只用模拟Client/导航验证前端入口；P38通过PG18与真实FastAPI routes/Repositories/Storage验证Artifact引用到Document内容字节，但采用ASGI原生scope且没有浏览器下载保存。剩余证据缺口是浏览器是否按真实输出历史入口触发附件保存，以及下载内容是否与HTTP响应一致。
- 基线：冻结API Contract V1、Document下载合同、CR-OUT-032/033。维持既有API/Schema/Migration、Opt-in生产路由和Trust边界。

## 编码前检查

- 当前阶段：Phase 2 Platform Core。
- 输入基线：P37 PASS_SCOPE_LIMITED；P38 PASS_SCOPE_LIMITED；OutputRequestListView、OutputArtifactReadClient及Document download attachment response。
- 前置任务：前端产物由P24/P37 Hosted验证；P38已通过真实PG18 Artifact→Document HTTP/Storage组合；Hosted Windows Server 2025 runner可运行Edge并将profile/证据置于D盘RUNNER_TEMP。
- 涉及模块：输出历史Vue视图与现有客户端；仅新增独立Hosted Edge harness/job和合成HTTP fixture。
- 涉及实体：合成Project、OutputRequest、Artifact引用和DocumentVersion下载响应；无持久化业务实体变化。
- API：不变。使用既有Artifact引用GET与Document content GET URL形态、标准response envelope及Content-Disposition attachment头。
- 权限：只使用合成Session与项目授权；不设置Publisher/License生产信任，不向默认应用挂载路由。
- 验收标准：真实Edge载入同run production frontend；输出历史包含一条合成SUCCEEDED行；点击“下载文件”后先获取固定Artifact引用，再请求同源Document content URL；Edge完成附件下载；保存文件字节、长度和SHA-256与预设合成负载一致；无失败/非SUCCEEDED行下载、不可信host/跨项目引用不得引发内容请求或保存；Edge profile、下载和summary只写Hosted D盘临时目录并清理；全量前端测试、typecheck/build和代码/Secret边界检查通过。
- 风险：单独浏览器contract harness不通过真实PostgreSQL或FastAPI网络服务器；P38的真实路由证据与本项浏览器字节保存证据是同一固定合同的分层验收，不宣称同一真实产品进程端到端。P25真实Windows HTTP/Edge全流程仍因initdb 0xC0000135未运行。正式Publisher/License trust、Windows 11设备、Pilot、Gate和Release均不由本项验收。
- 实施步骤：先新增独立验证器和Hosted job，复用同run production dist；只使用合成同源fixture。完成后在GitHub hosted Windows runner验收并核查summary、下载文件hash和全链回归。
- 预期修改：validation/out-01-a01-p39-edge-download、.github/workflows/cloud-sandbox-validation.yml及追踪文档；除非Hosted发现产品缺陷，不修改生产前后端。
- Migration/API变更：无。
- 风险控制/回滚：无信任密钥、客户数据或外部调用；回滚仅删除新增Edge job/harness/追踪记录，不修改已保存业务事实或文件。
- Secret检查：仅合成常量；禁止记录登录密钥、Cookie、session token或文件正文。

## 决定

PASS_WITH_LIMITATION：P39可以进入Hosted Edge harness实现；验收仍限浏览器同源下载合同，不冒充P38实时服务或正式产品信任。按持续授权直接执行并将所有实际偏差先记CR-OUT-034。


## P39 Hosted实现候选

新增独立Edge验证器和Hosted Windows job，复用同run production frontend；合成HTTP fixture返回严格Artifact引用及attachment响应，由Edge实际下载到D盘Runner临时目录，并独立读取落盘文件校验字节/Hash/长度。负例覆盖FAILED行无下载入口及跨项目引用被前端严格客户端拒绝、未请求内容URL。未连接真实FastAPI/PG；与P38分层证据，不宣称同进程端到端。待Hosted验收。


## P39首次静态复核发现的验收器源码偏差（修正前记录）

P39候选提交后，GitHub源码复核发现Node harness的Content-Disposition文件名字面量在嵌入引号前保留了双重反斜杠，可能导致JavaScript语法错误。尚未以Hosted node --check确认，也未把该静态风险描述成运行失败；P39未通过。修正前先记录：下一提交只改验证器字符串字面量并改用显式字节数组表达合成负载，随后以Hosted node --check和Edge实际落盘Hash/长度结果判定。产品代码、API、Schema及生产信任边界不变。静态复核又确认两处同属P39验收器接线遗漏：新Node server当前没有把同run dist内容作为静态SPA返回，且记录器会把前端静态资源请求误收为API请求；按现有Edge harness边界，P39无法加载页面并会误报外部路径断言。均未运行验证，P39仍Incomplete。计划一并只修独立harness：恢复安全dist内静态资源读取/SPA回退，限定API请求记录范围，并用字节数组构造附件fixture，然后执行Hosted语法与浏览器保存验收。


## P39验收器修复候选（偏差先记录后实施）

根据上述修正前记录，仅修改P39 harness：dist内文件安全解析并对SPA路由回退index；静态资源不计入API请求日志；Content-Disposition用单引号常量拼接版本文件名；使用显式byte array保证fixture包含NUL和0xFF字节。生产前后端未改。待Hosted node --check及Edge保存/拒绝路径验证。


## P39 Hosted首轮浏览器流程未触发下载（run 42144778960，未通过）

Hosted run [42144778960](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42144778960) 的P39 job通过artifact provenance及Node语法检查，Edge打开生产前端并完成合成登录和输出历史读取；随后未观察到Artifact引用GET、Document内容GET或Browser downloadWillBegin事件，失败于“Edge did not report attachment download”。因此P39未验收，不是产品后端HTTP拒绝证据。初步判定缺失证据是点击交互/按钮可用状态或前端handler是否触发；需加按钮状态、点击返回和有限等待请求轨迹诊断。修复仅限Hosted harness，并在下一轮重新证明引用请求、内容请求和Edge下载完成。

## P39第二轮诊断候选

根据run 42144778960的实际请求摘要（仅login和output-requests GET），P39 harness改为先等待成功行按钮真实可用，再通过CDP鼠标移动/按下/释放触发浏览器事件；增加有限等待和安全的按钮状态/API路径诊断，以区分未触发与HTTP/保存失败。跨项目负例同样采用鼠标事件。尚待Hosted运行，未形成P39通过证据。


## P39第二轮Hosted鼠标点击仍未发出引用请求（run 42145821433，未通过）

Hosted P39 node --check及provenance通过。Edge成功渲染含三行的输出历史，CDP探针确认目标SUCCEEDED行“下载文件”按钮存在且enabled=false? 运行证据明确enabled=false为否（disabled=false）；CDP鼠标事件后UI出现“暂时无法获取输出文件，请稍后重试。”，但Node合成服务器仍只记录login和history GET，没有Artifact引用GET、Document内容GET或下载事件。第二轮因此未通过，不能归因产品后端。下一修复先开启Chrome DevTools Protocol Network/Runtime诊断（仅记录API path/method、失败码和异常短文，不记录Cookie/Headers/body），定位请求是否在浏览器fetch之前被拒绝；仅在证据确认后改对应测试fixture/交互，不改生产逻辑。

## P39第三轮诊断候选

已按run 42145821433证据增强独立测试harness：启用CDP Network/Runtime，日志限定为API pathname/method、network failure type/errorText及异常class/短text，不采集请求认证信息、Cookie、Headers或body。等待Hosted结果明确“fetch未触发、浏览器阻断或服务器未收到”中的实际原因后，再选择最小修复。未改产品代码。


## P39 third Hosted diagnostic still shows no Artifact fetch (run 42146593192, not passed)

Hosted run [42146593192](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42146593192) repeated: frontend route loaded, successful row enabled, CDP mouse click shows the generic safe error, but Network events and Node server logs contain only login and output-history GET; no Artifact or content request, no Network.loadingFailed and no uncaught Runtime exception. This narrows the failure to a synchronous/asynchronous client-side rejection before an observable fetch, but does not identify its input. P39 remains failed. Before changing any product code, next harness-only step wraps global fetch and AbortController to count whether OutputArtifactReadClient reaches getJson/fetch; logs will contain only safe API pathname/method and counts, no auth material or body.

## P39第四轮请求前诊断候选

在合成浏览器页面登录前临时wrap window.fetch与AbortController；只记录API pathname/method及AbortController/fetch调用计数，不保留参数、认证头、Cookie或正文。首轮列表读取后记录基线，点击后若UI安全错误则输出差值和CDP Network/Runtime摘要，以判定严格客户端是否在调用fetch前拒绝。诊断仅为Hosted harness，不改产品源码，等待运行。


## P39第四轮Hosted已触达fetch但传输未到server（run 42147565204，未通过）

run [42147565204](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42147565204)中Harness包裹window.fetch的path-only trace记录到GET /api/v1/projects/{syntheticProject}/output-requests/{syntheticRequest}/artifact；CDP Network无该请求，Node server也未收到。前端显示安全错误，P39仍未通过；证据说明严格客户端已越过本地UUID前置并调用fetch，但浏览器到本地合成server的传输行为仍未查明。下一步按CR-OUT-034在fetch wrapper只记录Promise拒绝的error name及固定归一类别（Abort/TypeError/Other），不输出message、URL参数、Cookie/Header/body；再Hosted观察。产品API/代码未改。

## P39第五轮Hosted fetch拒绝诊断（run 42148130637，未通过）

Hosted run [42148130637](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42148130637)复现Artifact引用未到达浏览器Network/合成服务器；UI显示安全提示。页面侧path-only fetch trace包含预期Artifact GET，AbortController计数由2增至3，未有内容GET或Edge下载，P39仍未通过。Frontend测试/build、PG18 sidecar重建、A17 D盘边界和A50通过；后端全量测试在检查时仍运行，不能据此声称整轮完整通过。偏差先记于本节；下一步只增加原生fetch Promise rejection的固定类别统计（Abort/TypeError/Other），不记录错误message、查询参数、认证信息或正文，然后在Hosted复验。产品API/Schema/信任未改。


## P39第六轮Hosted复验重复失败（run 42148721420，未通过）

Hosted run [42148721420](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42148721420)复现同一现象：artifact 引用GET只出现在Harness页面内存的method/path trace；CDP Network与合成HTTP server没有请求，页面给出通用安全提示，无Document content GET或Edge保存。P39继续未通过。此轮Backend全量测试/wheel、Frontend测试/typecheck/build、PG18侧车重建、A17 D盘临时路径检查、P24/A50及Embedded Python组装成功；P39是该Workflow唯一失败job。偏差和下一最小诊断已先记录：Harness在原生fetch Promise拒绝时仅采集规范化类别（Abort/TypeError/Other），不保存错误文案或任何请求敏感数据；不改生产代码/API/Schema/Trust。


## P39第七轮Hosted fetch Promise拒绝类别诊断候选

依照run 42148721420和上节预先记录的计划，Harness临时封装原生fetch Promise，只在被拒绝时保留method、API pathname和固定类别Abort/TypeError/Other；同步抛错也归入同一白名单分类后原样抛回，不保存错误message、query、认证信息、Header、Cookie或请求正文。基线/失败摘要只输出拒绝类别条目。仅验证工具变更，不动产品逻辑；等待Hosted运行确认本地拒绝类型或继续缩小浏览器到server的传输边界，P39保持未通过。


## P39第七轮Hosted诊断发现原生fetch TypeError（run 42149813781，未通过）

Hosted run [42149813781](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42149813781)的去敏fetch wrapper观察到Artifact引用GET以TypeError拒绝；Abort归一类别未出现。该调用未进入CDP Network或合成HTTP server，页面仍给通用安全提示，无Document content GET或附件保存。P39未通过，且此证据本身不区分浏览器传输故障、请求signal/选项故障或Edge本地策略。下一Harness-only诊断将记录固定白名单的signal有效性/已abort布尔值、credentials/cache/redirect枚举，并在失败后对合成同源引用路径分别执行无signal和有效signal的原生fetch对照探针，只记录状态码/媒体类型或固定拒绝类别；探针结果明确标记为诊断请求，绝不充作产品点击验收。不得记录错误message、认证信息、cookie、headers内容、请求/响应正文。


## P39第八轮诊断计划：signal 与基础同源网络对照

run 42149813781已确认点击触发的Artifact fetch归一拒绝类别为TypeError。为区分浏览器基础fetch/同源服务与请求AbortSignal/选项，下一修正仅限Hosted harness：在不记录敏感值的前提下采集点击请求同源布尔、signal存在/有效/已abort布尔、credentials/cache/redirect白名单及Accept是否符合预期；捕获产品点击的通用错误后，用明确标记的查询参数对同一合成Artifact引用执行无signal与新建AbortSignal的原生fetch对照，结果只保存拒绝类别或HTTP状态和MIME。诊断GET不作为产品点击或下载验收；产品必须经原点击路径下载成功才可PASS。无生产前后端修改。


## P39第八轮Hosted对照支持Artifact fetch接收者绑定缺陷（run 42152467241，尚未修复）

run [42152467241](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42152467241)中产品点击请求路径确认origin_matches=true、signal_present/valid=true、signal_aborted=false，credentials=same-origin、cache=no-store、redirect=error、Accept正确；原生fetch Promise仍为TypeError，未到达CDP/服务端。失败后分离执行的无signal与有效AbortSignal同源对照GET均返回200/application/json。源码对照发现OutputArtifactReadClient.getJson()以对象属性形式调用this.fetcher(path, options)，而已工作的OutputRequestListClient.get()先赋值const fetcher=this.fetcher后以局部函数调用。由此推断Artifact默认原生fetch收到客户端实例作为this，导致浏览器Web API TypeError；这是源码差异+Hosted对照支持的高置信根因，仍须修复后的真实Edge验收证明。偏差先记后实施：只把Artifact client fetcher复制到局部常量并以局部函数调用，保持GET选项、timeout、错误映射和fixture不变；更新/补充单测确认注入fetcher调用，跑全量Frontend与Hosted Edge P39。无API/Schema/Migration变化；回滚仅还原该client一处调用。


## P39修复候选Hosted轮次发生Harness evaluate异常（run 42154634914，未验收）

已在提交57865990中按上述记录将OutputArtifactReadClient的fetcher改为局部函数调用，并增加检查接收者未绑定的Frontend单测。run [42154634914](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42154634914)中Frontend全量测试与构建成功；但P39 Edge Harness失败于通用CDP Runtime.evaluate异常“Uncaught”，诊断状态未捕获clientProbe，Node仅见登录/历史请求，没有Artifact/Document GET或下载事件。故无法判断真实点击是否已触发，也不能称产品修复已验收。偏差先记：下一Harness-only变更为受限stage标签（login/history/button-probe/mouse-click/alert/download）和异常class类别，并保留CDP message-free，不添加业务代码或请求数据；之后Hosted重新检查产品点击。

run [42154634914](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42154634914)其余Backend/wheel、PG18/pgvector、Frontend/build、嵌入式Python与Windows父包、PG18生命周期烟测、A17/A34/A35/P24/A50成功。独立P25仍因initdb.exe 3221225781/0xC0000135失败；整体workflow不全绿。Pilot/Gate/Release不变。


## P39最终 Hosted Edge结果：PASS_SCOPE_LIMITED（run 42156574221，2026-11-06）

在提交 `5cb5c8114c314895212462dec4c045c65141a720` 的完整Hosted run [42156574221](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42156574221) 中，P39 job成功：Windows Server 2025上的实际Edge从同run production dist进入输出历史；仅SUCCEEDED合成行显示下载入口；点击后请求固定Artifact引用并获得Document attachment；Edge保存文件与预置50字节负载长度及SHA-256 `90130db205e86ba6bec3b8a2d90161db16b34f27226ceca67e206aa8eb923437`完全匹配。FAILED输出无下载入口；跨项目Artifact引用返回安全失败，内容URL没有被请求。此前P39的产品端fetch receiver修复和受限Harness stage诊断均被此次实际保存链路验收。

范围：PASS_SCOPE_LIMITED，仅证明Hosted Edge同源合成浏览器合同及安全失败边界；P38的FastAPI/PG18真实route证据仍是分层验证，二者不是同一真实产品进程端到端。没有正式Publisher/License trust、Win11设备、生产后端进程或客户数据。P25仍在initdb前以 `0xC0000135`退出，因此本workflow整体仍failure、P25仍BLOCKED_DIAGNOSTIC、Pilot/Gate/Release不变。下一项按CR-OUT-021及P25编码前检查，先在P25同一Hosted job运行既有父包PG smoke helper，不重复猜测参数。
