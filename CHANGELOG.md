## Unreleased · 2026-11-06（P39 Hosted验收器静态接线遗漏，修复前记录）

- 源码复核发现P39候选Synthetic server尚未服务production dist静态SPA，request summary将包含非API资源；与Content-Disposition转义风险一并先记CR-OUT-034，未将静态发现表述为已运行失败。下一步仅补server静态回退和限定API请求记录，Hosted node --check/Edge验收待跑。

## Unreleased · 2026-11-06（P39 Hosted验证器静态转义偏差，待云端复验）

- P39候选提交后的静态复核发现附件文件名响应头在Node脚本中的转义可能提前结束字符串，尚未以Hosted node --check确认，也未形成P39通过结果。已先补记CR-OUT-034，拟只修验证器引用字面量和合成字节数组；产品逻辑不变。

## Unreleased · 2026-11-06（OUT-01-A01-P39：Hosted Edge下载候选，非发行版本）

- 新增独立Hosted Windows Edge验证器和Workflow job，复用同run production frontend，在合成同源HTTP fixture下执行输出历史SUCCEEDED行→Artifact引用→Document attachment保存；验收将比对Edge实际保存字节、Hash及长度，并验证FAILED行无下载按钮、跨项目引用在内容请求前被拒绝。
- 限制：该候选使用合成API/文件，不通过PostgreSQL或实时FastAPI；P38真实HTTP路由证据单独保留。P39尚待Hosted运行，不能标PASS；无正式trust、Win11设备或发行结论。

## Unreleased · 2026-11-06（OUT-01-A01-P38受限通过，非发行版本）

- P38按CR-OUT-033以PASS_SCOPE_LIMITED完成，Hosted run [42139905574](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42139905574)：父包PG18真实Artifact引用与Document下载路由/Repository/Storage验证授权引用、字节/Hash/长度/MIME、跨项目隐藏及损坏文件失败关闭；后端4,087 tests/wheel、前端205 suites/2,098 tests/typecheck/build、A17/A34/A35/P24/A50成功。
- 全run 14/15 jobs成功，独立P25在initdb.exe初始化前以0xC0000135退出，真实HTTP/Edge未执行，workflow非全绿。P38未用生产trust、未打开TCP或浏览器下载，也不表示Win11/Pilot/Gate/Release通过。
- 下一项P39先完成Hosted Edge输出历史下载保存验收的编码前检查，CR-OUT-034；仅合成浏览器HTTP合同，P38真实HTTP路由证据独立保留。

## Unreleased · 2026-11-06（P38第二轮PG18响应封套测试偏差，非发行版本）

- run [42138062500](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42138062500) 的PG18 ASGI verifier把P36标准 {data, trace_id} response envelope误按顶层字段读取；字段布尔检查失败，但存储定位符与正文隐藏检查通过。产品端点按标准封套工作，P38验证器未解封数据，下载流验收未执行。已先记CR-OUT-033，修复验证器解包后重跑。

## Unreleased · 2026-11-06（P38首轮PG18引用HTTP断言失败，非发行版本）

- Hosted run [42136117411](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42136117411)：后端4,087 tests/wheel、前端205 suites/2,098 tests/typecheck/build及父包组装通过；PG18新增ASGI HTTP verifier在Artifact固定引用字段/不泄露联合断言处失败，未执行文件流下载断言，P38未通过。已先记CR-OUT-033，将细分安全布尔项后重跑。整体流程还含独立P25失败。

## Unreleased · 2026-11-06（P38验收依赖兼容偏差，非发行版本）

- 发现父包PG smoke最小Hosted依赖不包含TestClient所需httpx；在运行前静态确认并按CR-OUT-033记录。验收器将改用FastAPI ASGI原生请求驱动相同HTTP router与StreamingResponse，不增加依赖；产品代码不改，P38仍待Hosted验收。

## Unreleased · 2026-11-06（OUT-01-A01-P38：受保护下载HTTP集成候选，非发行版本）

- 变更：父包PG18 verifier增加真实Artifact引用HTTP到Document受保护内容流的端到端验证，覆盖成功字节/hash/大小/MIME、跨项目与未知引用隐藏、跨项目内容隐藏、篡改文件失败关闭及存储定位不披露。Session/Project/License为合成测试夹具，PG和文件均限Hosted D盘临时目录。
- 兼容性：无产品API/Schema/Migration/default composition/正式trust变化。P38 Hosted验收待运行，未通过前不标PASS。

## Unreleased · 2026-11-06（OUT-01-A01-P37：输出历史下载入口，非发行版本）

- 结果：按CR-OUT-032以PASS_SCOPE_LIMITED完成。Hosted run [42126880417](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42126880417)：前端205 suites/2,098 tests/typecheck/build，后端4,087 tests/wheel，父包PG18 P36固定引用权限断言及A17/A34/A35/P24/A50通过。
- 变更：输出历史中仅SUCCEEDED行提供下载入口；严格解析P36同源Artifact引用后转至受保护Document内容流。无后端/API/Schema/Migration变化。
- 已知限制：P37测试尚未贯穿真实Document HTTP字节；正式Platform trust、Windows 11实机和Pilot/Release未通过。整体run 15 jobs中14成功，独立P25 initdb.exe 0xC0000135失败。
- 下一步：OUT-01-A01-P38编码前检查通过，按CR-OUT-033补充临时PG18下的受保护Artifact→Document内容流HTTP集成验收。

## Unreleased · 2026-11-06（P37第三轮Hosted解析偏差，非发行版本）

- run [42126285195](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42126285195) 的前端测试仍因新用例 `artifactReader` 的换行类型断言解析失败；列表Client断言已修正，但该遗漏使新增suite仍0 tests、其余2,092项通过。已先补记CR-OUT-032，随后统一修正同类fixture语法并重新Hosted验收；P37未通过。

## Unreleased · 2026-11-06（P37第二轮Hosted解析偏差，非发行版本）

- run [42125753500](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42125753500) 前端suite仍因对象字面量 `as` 类型断言语法失败，204个suite中的其余204通过、2,092项用例通过；typecheck/build未执行。已按CR-OUT-032先记录，改为显式变量类型标注后重新Hosted验收；P37未通过。

## Unreleased · 2026-11-06（P37首轮Hosted解析偏差，非发行版本）

- run [42124943609](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42124943609) 前端全量测试2092项通过，但新增 `OutputRequestListView.spec.ts` suite因对象字面量后的换行类型断言语法错误未能解析；typecheck/build未执行，P37不通过。偏差先记录CR-OUT-032，计划只修测试夹具语法后在GitHub hosted重跑；未在本机/C盘运行。

## Unreleased · 2026-11-06（OUT-01-A01-P37：输出历史受控下载入口候选，非发行版本）

- 变更：新增同源OutputArtifact引用读取Client；仅SUCCEEDED请求显示“下载文件”，通过P36授权API取得固定DocumentVersion引用，严格校验Project/Request/UUID/Hash/大小/MIME/内容路径后导航到现有Document下载route。失败不导航、不自动重试。
- 兼容性：无后端/API/Schema/Migration变化；现有输出请求历史读合同不变。
- 已知限制：正式Platform trust缺失，P36 opt-in route及Document下载route尚无Win11真实会话下载证据；Pilot/Gate 3/Release未通过。
- 验证：GitHub hosted完整回归待跑；本地/C盘没有运行项目代码。未验收前不标PASS。

## Unreleased · 2026-11-06（OUT-01-A01-P36：OutputArtifact固定引用读取，非发行版本）

- 变更：新增受项目授权的独立Artifact引用读取Application/Repository/HTTP及Windows Output read opt-in composition。仅SUCCEEDED请求、AVAILABLE Artifact、ACTIVE GENERATED_ARTIFACT Document及AVAILABLE固定DocumentVersion/FileObject的完整关系可返回；内容仍走受保护Document下载URL。
- 兼容性：无数据库Schema/Migration；既有OUTPUT_REQUEST_GET/LIST响应未改变；默认login-only应用未挂载。
- 已知限制：Windows正式License trust源仍阻塞Platform服务装配；前端下载入口尚未实施；Artifact引用URL需在Document下载路由已装配的受保护Platform模式使用。没有Win11实机、用户下载或Pilot证据。
- 验证：GitHub hosted run [42121003242](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42121003242)中后端4,087项/wheel、前端测试/build、父包PG18新Repository投影、A17/A34/A35/P24/A50均通过。整体workflow仅独立P25 HTTP/Edge失败，故P36为PASS_SCOPE_LIMITED而非整体workflow通过。详见CR-OUT-032与docs/progress/out-01-a01-p36-artifact-reference-read-result.md。

## Unreleased · 2026-11-06（PLG-04-A03：受控本地安装物化，非发行版本）

- 变更：增加未装配的内部Plugin安装物化器；由受信内部调用传入Verified Package和Installation UUID，对签名ZIP重新验证并在服务data_root生成精确UUID安装目录，逐文件Hash核验、同卷no-replace提升和精确重放；Host proof绑定Installation UUID。无Schema/Migration/API/default composition/Worker/插件执行变更。
- 兼容性：新增内部Host evidence UUID字段且缺省可空，以保持现有Runtime Revalidation Port兼容；Installation Owner记录新安装时必须要求精确UUID匹配。现有业务API与数据库合同不变。
- 升级：无需DB migration；新目录位于 `plugins/installations/<installation UUID>`。PG/文件系统失败后保留目录供精确重放，不自动覆盖/清理未知目录或staging。
- 已知问题：正式publisher信任、服务账户data_root ACL、Win11实机与默认装配未验证；无插件执行。Pilot/Gate 3/Release未通过。独立P25仍因hosted initdb.exe 0xC0000135失败。
- 验证：hosted run [42110700182](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42110700182)，后端4,078项/wheel、前端/build、PG18/pgvector、A17/A34/A35/P24/A50通过；A17 summary含安装物化正向marker和篡改目录零事实marker。P25失败，整体workflow非全绿。结论PASS_SCOPE_LIMITED；用户本机/C盘未运行。详见 `docs/progress/plg-04-a03-host-installation-materialization-result.md`。

## Unreleased · 2026-11-06（PLG-04-A02：Installation Owner归档证据复验，非发行版本）

- 变更：Installation Owner先通过只读归档证据Port重新核验不可变已登记包身份/版本/哈希/签名/Manifest快照，再要求独立Host安装/兼容证据；失败关闭时不写Installation、RuntimeValidation或Audit。
- 兼容性：无Schema/Migration/API、默认组合、生产publisher信任或依赖变化。
- 升级：无需数据库迁移；历史无归档字节或无独立Host证据的包仍不能产生安装事实。
- 已知问题：未配置正式publisher trust；未解压、安装或运行插件。P25真实Output Create HTTP/Edge仍被Windows hosted initdb 0xC0000135阻断；Pilot/Gate 3/Release未通过。
- 验证：GitHub hosted run [42092840314](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42092840314) 后端/wheel、前端/build、clean PG18、A17专项summary marker、A34/A35、P24/A50通过；独立P25失败，故整体workflow非全绿。结论PASS_SCOPE_LIMITED。用户本机/C盘未运行。

## Unreleased · 2026-11-06（PLG-04-A01：Plugin签名包正文私有持久化）

- 版本：未发行的内部开发候选；不是Pilot或正式Release。
- 变更：Worker在Package登记成功后以UUID locator保存原始签名ZIP；同卷无覆盖提升、SHA-256/大小验证和精确重放；只读适配器重新验证签名/ZIP/Manifest及登记快照，仅返回元数据。
- 兼容性：无冻结Schema/API变更，无新依赖或迁移。
- 升级：无需DB Migration；新导入包正文写入受保护data_root的 `plugins/packages` 命名空间；历史数据库中仅有元数据的旧包不自动补齐，安装证据仍失败关闭。
- 已知问题：生产publisher signer清单为空；本次不表示真实信任/安装/插件执行。P25 HTTP/Edge继续被initdb.exe 0xC0000135阻断。
- 验证：GitHub hosted run [42070621770](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42070621770)中后端4,071 tests/wheel、前端/build、PG18 smoke、A17/A34/A35/P24/A50通过；仅独立P25 job失败。全workflow非全绿，结论PASS_SCOPE_LIMITED。

## Unreleased · 2026-11-05（P34B重复Hosted下载阻塞，非发行版本）

- Hosted run [42045197675](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42045197675) 的所有前置构建与测试、嵌入后端运行时、A17 harness、P24/A50通过；父包在固定Caddy 2.11.4输入下载第二次遇到HTTP 504，PG18 smoke/P34B skipped。已先记CR-OUT-030/031。
- 验收工作流仅增加该固定资产下载的最多3次退避重试；所有既有固定版本和完整离线校验保持不变。产品代码验收仍未完成。

## Unreleased · 2026-11-05（P34B首轮PG18接线失败，非发行版本）

- Hosted run [42042776664](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42042776664)：父包和Clean PG18 smoke启动成功；P34B verifier在导入应用Owner时因其提交版本缺少Repository新增的GeneratedFileRequestFacts而ImportError，Storage/P34A/P33验收未执行，不代表业务断言失败或P34B通过。先记CR-OUT-030/031，已定位为提交接线落后于Repository接口，修复后云端重验。
- 同run P25 HTTP另有失败，保持独立诊断。后端全量/wheel、前端/build等通过；未在本机运行代码/测试。

## Unreleased · 2026-11-05（P34B首轮Hosted外部下载阻塞，非发行版本）

- Hosted run [42040802059](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42040802059)：后端全量/wheel、前端/build、PG18 sidecar、嵌入式后端及A17/A34/A35/P24/A50前序验证通过；父包组装下载固定Caddy 2.11.4资产时收到504 Gateway Time-out。父包PG smoke及P34B verifier被跳过，不能记P34B通过或失败。
- 已先记录CR-OUT-030/031；保持版本和校验不变，重启托管验证确认是否为暂态外部下载问题。未在本机运行代码/测试。

## Unreleased · 2026-11-05（P34B云端实现，验收待执行）

- 按CR-OUT-030/031新增未装配的Output SYSTEM发布Owner/Repository：短事务核验Request和Job fence，事务外验证并无覆盖提升文件，再事务内写FileObject AVAILABLE/FileStateEvent/SYSTEM Audit，之后依次委托P34A和P33；恢复只允许已验证STAGE_ONLY、FINAL_VERIFIED、LINKED_PAIR。
- 扩展隔离PG18父包verifier：从D盘RUNNER_TEMP中的合成STAGED文件出发，检查存储提升、P34A/P33链、P33 Audit故障回滚边界及精确重放。没有调用产品API/Worker/插件或默认组合。
- 无Schema/Migration/API/依赖/发行包变化；无客户数据或本机代码运行。此项仍待GitHub hosted验收，不能视为P34B通过。P25仍独立BLOCKED_DIAGNOSTIC；Pilot/Gate 3/正式Release未通过。

## Unreleased · 2026-11-05（P25 Node 24环境对照，非发行版本）

- Run [42024740026](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42024740026) 中前后端测试/build、PG18 sidecar、运行时和父包组装、A35通过；加入Node 24后的父包PG18/pgvector lifecycle smoke仍成功。P25及父包initdb对照继续0xC0000135、无数据目录/日志，未启动真实HTTP/Edge。P25维持BLOCKED_DIAGNOSTIC，详见CR-OUT-021。
- 暂停重复PATH与启动参数对照，研发切回不依赖P25的OUT-01-A01-P34；无产品代码/Schema/API变化。只在GitHub hosted D盘执行。

## Unreleased · 2026-11-05（P25托管诊断，非发行版本）

- Run [42017800786](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42017800786) 中后端/wheel、前端/build、PG18 sidecar、父包组装、A17准备与A35交接成功；P25与同run父包PG initdb均以0xC0000135在数据目录创建前失败，真实HTTP/Edge未启动。
- 1,627个PG payload文件与sidecar完全一致，目录无数据/服务日志，静态依赖扫描无缺项；该证据未确认系统装载根因。P25继续BLOCKED_DIAGNOSTIC，详细差异和下一探针记录于CR-OUT-021。
- 不涉及产品代码、Schema、API、安装包或业务数据；仅GitHub hosted D盘运行。

## Unreleased · 2026-11-05（P34编码前检查，非发行版本）

- 按 CR-OUT-030 完成本地Storage→OutputArtifact一致性编码前检查，结论PASS_WITH_LIMITATION。ADR-008已有流式Hash/大小校验、同卷不可覆盖提升、提升后复验和文件身份边界；新增协调层必须在短PostgreSQL事务外做文件I/O，并把final-only/linked-pair窗口留给受限恢复，不得盲删文件。
- 无代码、Schema/Migration、API、安装包或生产装配变化；源码只读检查通过 GitHub，未在用户本机/C盘执行。
- 下一步：核查DocumentVersion创建/发布和恢复Audit完整路径，然后实现内部未装配的输出文件发布协调Owner，并在GitHub hosted Windows runner D:及隔离PG18验收。
- 已知限制：P25 initdb 0xC0000135仍独立阻断；Windows 11 Pilot、Gate 3与正式Release未通过。

## Unreleased · 2026-11-05（内部云端验证，非发行版本）

- OUT-01-A01-P33 按 CR-OUT-029 以 PASS_SCOPE_LIMITED 完成。Hosted run [42013184586](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42013184586) 的父包PG18 smoke通过首次 Artifact/OutputRequest/Job/Audit 同事务成功、Audit失败全回滚、错误Document引用拒绝、四项校验追加、相同成功Claim重放保持原结果且不新增记录、改动后的重放拒绝；后端全量/wheel、前端/build、父包组装、A17、A34通过。
- 重放只接受同一Project/OutputRequest/PluginExecution/Artifact/DocumentVersion/FileObject/Hash/四项校验及已完成Job与已释放原Lease，返回原Facts且不增加Audit或validation历史；其他claim或变更引用失败关闭。无Schema/Migration/API/default composition变化。
- 兼容/升级：无数据库迁移、冻结API或部署升级变化。仅在GitHub hosted Windows Server 2025 D盘临时PG18与合成数据验证，不启动产品API/Worker/插件，不写本地文件，无客户数据。生产Publisher仍未装配。
- 已知问题：同run独立P25仍因initdb.exe 0xC0000135失败，真实P25 HTTP/Edge未验证，整体workflow非全绿；Windows 11 Pilot、Gate 3与正式Release未通过。下一项按ADR-008开展OUT-01-A01-P34编码前检查。结果见 docs/progress/out-01-a01-p33-output-success-finalization-result.md。

## Unreleased · 2026-11-05（P33 PG fixture状态偏差）
- Hosted run [41997886517](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41997886517) 后端/wheel、前端/build、PG18/pgvector、父包、A17之前置前序verifiers通过；P33 PG18 verifier的合成请求以 lock_version=0 进入 GENERATING，被Owner正确失败关闭。已先记CR-OUT-029，仅把fixture修正为P29启动后有效值1，再重跑。

## Unreleased · 2026-11-05（P33 PG verifier fixture偏差）
- Hosted run [41995972249](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41995972249) 后端/wheel、前端/build、PG sidecar、父包及P24/A50成功；新增P33 PostgreSQL verifier在合成source refs SQL字符串转义处SyntaxError，未执行P33 DB验收。已先记录CR-OUT-029；改为参数化JSONB fixture 后复验。

## Unreleased · 2026-11-05（P33首轮Hosted偏差）
- OUT-01-A01-P33 首轮run [41992151148](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41992151148) 中新增成功Owner用例发现Audit outcome枚举接线错误（传SUCCEEDED，而冻结Audit契约要求SUCCESS）；整体变更被SYSTEM_UNAVAILABLE收敛并回滚。先记CR-OUT-029，再仅修Audit outcome及测试期望，重新全量托管验收。没有本机代码运行或持久化副作用。

## Unreleased · 2026-11-05（内部云端验证，非发行版本）

- OUT-01-A01-P32 按 CR-OUT-028 以 PASS_SCOPE_LIMITED 完成。Hosted run [41988323089](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41988323089)：P32 PostgreSQL 18专项、父包 PG smoke、后端/wheel、前端测试/typecheck/build、A17/A34成功。Migration 0232验证空库/既有合成数据升级、空库降级重升及历史保护；复合关系、AVAILABLE正反例、只追加/不可变和TRUNCATE保护通过。
- 兼容/升级：新增冻结OUT-02的 ORM/Migration 0232；只允许数据库元数据，不存正文。生产写入口保持关闭。父包SHA-256 `ad37ffd0b7fc6b59968ecb2b10f2e8cddc9f3431c9851e70a0e03c221d1440e2`，20,216个payload文件。未在用户本机/C盘运行。
- 已知问题：独立 P25 `initdb.exe` 以 `0xC0000135` 失败，真实 HTTP/Edge 未启动，整体 workflow 非全绿。Pilot/Gate 3/正式Release未通过。详见 `docs/progress/out-01-a01-p32-output-artifact-result.md`。

## Unreleased · 2026-11-05（内部云端开发，非发行版本）
- P32编码前检查发现冻结模型包含PluginExecution，但当前分支尚无其ORM/表/Migration；OutputArtifact固定Project FK及AVAILABLE一致性条件因此无法实现。原始预检文档有一处把模型定义误写成源码已有实现，已在编码前核对并更正，未产生代码/Schema变化。OUT-01-A01-P32保持BLOCKED_DEPENDENCY并转至PLG-03-A01；按CR-PLG-014先补齐冻结Execution持久化基础。

## Unreleased · 2026-11-05（内部云端开发，非发行版本）
- OUT-01-A01-P32编码前检查通过受限评估：冻结模型已定义 OUT-02 OutputArtifact 与 validation results，但生产ORM/Migration尚缺。按 CR-OUT-028 先实现关系持久化基础；不提前声称成功发布，不新增API、文件/插件执行或写入口。后续依赖 Artifact 一致性发布Owner。P25 initdb阻塞独立保留。
- 所有代码及数据库验证只在GitHub hosted runner的D盘临时目录执行，不使用用户本机/C盘。

## Unreleased · 2026-11-05（内部云端验证，非发行版本）
- OUT-01-A01-P31 按 CR-OUT-027 以 PASS_SCOPE_LIMITED 完成；hosted run [41963052416](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41963052416) 的父包 PostgreSQL 18.6 smoke 验证固定30秒暂态错误回队、attempt耗尽后 Job/Output 原子失败、错worker/旧token/非白名单拒绝及 Audit 故障双Owner回滚。后端全量测试/wheel、前端/build、PG18 sidecar、父包组装、A17、A34通过。父包SHA-256 `61593a1aab3529b09c15baa0231d6723eb1cad337a709db272b6148db2c87e1b`，20,214个payload文件。
- 同run独立P25 job仍在 `initdb.exe` 数据目录创建前以 Windows `0xC0000135` 失败，真实HTTP/Edge未启动；整体workflow不全绿，P25保持BLOCKED_DIAGNOSTIC。结果见 `docs/progress/out-01-a01-p31-output-retry-result.md`。
- 兼容/升级：仅GitHub hosted Windows Server 2025、D盘临时数据；不是发行安装包或Windows 11设备验收。无Schema/Migration/API/default挂载变化、无产品服务、插件、文件生成或客户数据操作；Pilot/Gate 3/Release仍NOT_READY。

## Unreleased · 2026-11-05（内部云端验证，非发行版本）
- OUT-01-A01-P30 按 CR-OUT-026 以 PASS_SCOPE_LIMITED 完成；hosted run [41959590610](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41959590610) 在同一 PG18 transaction 中终结 Job/Output 为 FAILED、释放当前 lease 并写SYSTEM Audit。错worker、旧token、非白名单错误被拒绝，Audit故障双Owner回滚；后端4042 tests/wheel、前端/build、父包PG smoke、A17/A34/A35/A50成功。P25仍独立因initdb 0xC0000135阻塞。无Schema/API/Worker/Plugin/文件生成，且未在本机/C盘运行。结果见 docs/progress/out-01-a01-p30-output-failure-result.md。

- OUT-01-A01-P29 按 CR-OUT-025 新增内部Output生成启动Owner：同事务验证当前Output lease，并将精确绑定的QUEUED请求转为GENERATING、设置execution ref/lock_version及SYSTEM Audit；同执行重放幂等。并发锁顺序已按CR记录统一为Output→Jobs。
- 新增Owner单测与隔离PostgreSQL hosted verifier；不新增Schema/Migration/API/default挂载，不运行Worker/插件、不生成文件。变更限GitHub hosted Windows 2025 D盘runner，未在用户本机或C盘运行。
- 首轮 hosted run 41948211782：后端4036 tests/wheel、前端/build、PG18/pgvector通过；父包 smoke 在P29 verifier前因结果字典字面量\\n语法错误失败。已记录CR-OUT-025并修复工具脚本，等待完整重验；此结果不代表P29通过。
- 第二轮 hosted run 41949611412 的PG smoke verifier在启动业务断言前因2个合成fixture被按5个变量解包失败；偏差已记CR并修复，等待完整复验。
- 第三轮 hosted run 41951315834进入真实PG18断言后发现旧token用例仍传当前ClaimedJob；偏差已记CR并修复为实际过期/重领以产生前序正token，等待完整复验。
- OUT-01-A01-P29最终按PASS_SCOPE_LIMITED完成，证据为完整Hosted run [41953529123](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41953529123)。PG18验证有效绑定原子启动、错worker/旧token/错request拒绝、同执行幂等、SYSTEM Audit身份和Audit失败回滚；父包PG smoke、A17、A34、A35、A50成功。后端4036 tests/wheel、前端/build、PG18/pgvector通过。
- 整体workflow仍因独立P25 initdb.exe 0xC0000135失败而非全绿；P25未通过。Pilot/Gate/正式Release仍NOT_READY。P29不代表真实Worker/Plugin/文件执行、Windows 11新设备或正式信任完成。详见docs/progress/out-01-a01-p29-output-start-transition-result.md。

## Unreleased · 2026-11-05（内部云端开发，非发行版本）

- OUT-01-A01-P28按CR-OUT-024以PASS_SCOPE_LIMITED完成。Hosted run [41944746044](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41944746044) 后端4,031 tests/wheel、前端/build、PG18/pgvector及父包PG smoke通过。新增Output专属活动lease proof，正确claim通过，错worker、旧fencing token、非Output owner和过期lease均拒绝；读取proof不改状态。详见 docs/progress/out-01-a01-p28-output-lease-proof-result.md。
- P25仍在initdb阶段以0xC0000135失败，真实HTTP/Edge未执行；Pilot/Gate/正式Release不变。
- 兼容/升级：无Schema、Migration、公开API、安装包升级或数据迁移。证明仅在hosted合成PG时点有效，非真实Worker/插件/文件发布验证。只在GitHub hosted runner D盘运行，未使用用户本机/C盘。


## Unreleased · 2026-11-05（内部云端验证，非发行版本）

- OUT-01-A01-P24按CR-OUT-020以PASS_SCOPE_LIMITED完成。GitHub hosted run [41888874127](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41888874127) 14/14 jobs成功：前端2,093项测试/typecheck/build、后端4,022 tests/wheel、PG18/pgvector、父包及A17/A34/A35/A50通过。Windows Server 2025 hosted Edge验证DOCX请求UI固定合同、CSRF/幂等、202回执/历史导航、503无自动重试与未批准版本隐藏入口。仅合成API与数据，无DOCX生成、插件执行、客户数据或外部调用。详情见 docs/progress/out-01-a01-p24-edge-create-ui-result.md。真实Publisher信任、Win11实机、Gate/Pilot/Release仍未通过。下一项P25先做真实HTTP+Edge集成编码前检查。

## Unreleased · 2026-11-05（内部云端验证，非发行版本）

- P24 hosted Edge确认202请求已发出但回执UI消失；根因定位为SessionClient请求期间 canSubmit=false 导致整个Create组件卸载、异步结果丢弃。先按CR-OUT-020登记产品修正，再实施区域与提交门控拆分并增补定向测试。

- P24 首轮hosted run [41875807078](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41875807078) 的P24 Edge步骤因合成RequirementVersion响应被前端冻结解析器拒绝而失败；尚未触发输出请求。根因调查与纯fixture修复/诊断计划已先登记 CR-OUT-020，待修复后全链复验。

- OUT-01-A01-P23按CR-OUT-019以PASS_SCOPE_LIMITED完成。GitHub hosted run [41869866457](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41869866457) 13/13 jobs成功：前端204测试文件/typecheck/build、后端4,022项/wheel、PG18、父包及A17/A34/A35/A50通过。首轮前端测试解析错误已记录后修复；不代表DOCX生成、正式Publisher信任、Win11实机、Gate/Pilot/Release。详见docs/progress/out-01-a01-p23-output-request-create-ui-result.md。下一项P24为hosted Edge UI/API契约集成验证。

- OUT-01-A01-P20按CR-OUT-016以PASS_SCOPE_LIMITED完成：OutputRequest详情GET接入Windows显式read组合。Hosted run [41835015557](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41835015557) 13/13通过，后端4,021 tests/wheel、PG18.6授权/404隔离/最小投影/只读验证、前端、20,202文件父包和A17/A34/A35/A50通过。无默认路由，Session/License为合成；Pilot/Gate/Release不变。见docs/progress/out-01-a01-p20-output-read-composition-result.md。

- OUT-01-A01-P22按CR-OUT-018以PASS_SCOPE_LIMITED完成只读历史列表UI。Hosted run [41859511797](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41859511797) 13/13成功，前端2,084 tests/typecheck/build、后端4,022 tests/wheel、PG18、父包及A17/A34/A35/A50通过。未改API/Schema/默认后端挂载，合成验证不代表Win11/正式信任/Gate/Pilot/Release。见docs/progress/out-01-a01-p22-output-list-ui-result.md。

- OUT-01-A01-P21按CR-OUT-017以PASS_SCOPE_LIMITED完成：OutputRequest列表GET接入Windows显式只读组合，专用当前账户Vault HMAC key缺失时失败关闭。Hosted run [41846611865](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41846611865) 13/13通过；后端4,022 tests/wheel、前端/build、PG18.6授权/分页/游标篡改/只读、20,204项父包与A17/A34/A35/A50通过。候选ZIP SHA-256 ab296298508a7030262cb5494b584249fc54f0ffee6b5b209bc81eb4af24c1f1。无Schema/API变化；仅托管合成验证，不代表Win11或生产信任。见docs/progress/out-01-a01-p21-output-list-composition-result.md。

## Unreleased · 2026-11-04（内部云端验证，非发行版本）

- OUT-01-A01-P19按CR-OUT-015以PASS_SCOPE_LIMITED完成：Output Create仅在Windows显式write组合挂载，冻结角色权限及同事务Session/CSRF接线完成。Hosted run [41830014604](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41830014604) 13/13通过，后端4,018 tests/wheel、PG18.6组合实际HTTP和信任缺失无写入、前端、20,201项父包及A17/A34/A35/A50通过。Publisher清单为空，真实请求失败关闭；未执行插件或生成文件。Pilot/Gate/Release不变。详情见docs/progress/out-01-a01-p19-output-create-composition-result.md。

- OUT-01-A01-P20开始前置检查：下一项接入冻结OutputRequest详情GET至Windows显式read组合，具体见CR-OUT-016与docs/progress/out-01-a01-p20-output-read-composition-precheck.md。

## Unreleased · 2026-11-04（内部云端开发，非发行版本）

- OUT-01-A01-P18按CR-OUT-014以PASS_SCOPE_LIMITED完成，GitHub hosted run 41809547922 13/13 jobs成功。后端4,013 tests/wheel、前端测试/typecheck/build、PG18.6合成HTTP/权限/Audit/幂等、20,199文件父包、A17/A34/A35/A50通过；父包内部SHA-256 076c3d844a771d5d63100cab51f15c72f2a99fa569e41b4fe377cea5ca08d947。creator/ProjectManager取消成功，ImplementationMember拒绝且无写入，默认App无路由。两轮偏差均先记录并修复后全量重验。兼容性限hosted synthetic，非Win11实机/发行；无数据库/API升级。已知限制：write opt-in、运行中取消待Worker确认、正式publisher/License trust/DB凭据/ACL/TLS缺失；Pilot/Gate/Release不变。详见docs/progress/out-01-a01-p18-output-cancel-composition-result.md。下一项P19核查Output Create composition。


- OUT-01-A01-P17按CR-OUT-013以PASS_SCOPE_LIMITED完成。Hosted run [41799812913](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41799812913) 13/13 jobs成功：后端4,006 tests/wheel、PG18.6取消Owner真实事务、前端、非发行父包、A17/A34/A35/A50均通过。取消事务正/负scope、If-Match、同Key并发幂等、Audit失败全回滚、运行态仅请求取消、PG数据库完成时间均通过；父包20,197项SHA-256 1377ca1ab3b6404fbc7d53447ea906d7440cd3c6ad33e475ce33165d4a00f9b5。验证器两次时钟快照假失败均修复并记录CR。无默认composition/真实Output Worker或Win11实机证据，Pilot/Gate/Release不变。详见docs/progress/out-01-a01-p17-cancel-postgres-result.md。下一项P18按CR-OUT-014接入显式Windows write composition。

- OUT-01-A01-P16按CR-OUT-012以PASS_SCOPE_LIMITED完成：新增 opt-in OutputRequest取消HTTP/Owner及Jobs-owned同事务取消端口。Hosted run [41793207115](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41793207115) 13/13 jobs成功，后端4,006 tests/wheel；前端、PG18 sidecar/父包、A17/A34/A35/A50通过。新Owner无专用PG18行事务验收、无默认组合装配、无Output终态Worker，保持限界结论。详见`docs/progress/out-01-a01-p16-output-request-cancel-result.md`。下一项P17直接补Hosted PG18正负行/事务、版本竞争与Audit回滚测试。

- OUT-01-A01-P15按CR-OUT-012完成源码编码前检查（PASS_WITH_LIMITATION）。确认冻结取消需以OutputRequest为资源且使用其lock_version；现有Job取消dispatcher在独立读写UOW间分派，不能原子更新OutputRequest和OUTPUT_GENERATE Job。已记录由Output协调Jobs-owned事务端口的方案，未改代码/测试/Schema/API合同。详见`docs/progress/out-01-a01-p15-output-request-cancel-precheck.md`。下一项P16实现opt-in取消Owner与HTTP，专属PG18事务验收另列。

- OUT-01-A01-P14按CR-OUT-011以PASS_SCOPE_LIMITED完成。Hosted run [41789030529](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41789030529) 14/14 jobs成功：后端3,998 tests/wheel、前端、PG18/pgvector、非发行父包、A17/A34/A35/A50通过。新增 OUTPUT_REQUEST_LIST 分页GET、三类冻结角色策略、Project/Session/page_size绑定的Output独立HMAC cursor及投影测试。首轮仅旧授权矩阵计数断言未更新，已先记录CR并修正，复验通过。router未挂载、正式cursor密钥未接线、没有专门PG18输出行测试。详见`docs/progress/out-01-a01-p14-output-request-list-result.md`。P16完成；下一项P17直接补新Owner的hosted PG18事务验证。


- OUT-01-A01-P14编码前检查通过并登记CR-OUT-011：实现冻结OUTPUT_REQUEST_LIST的项目内只读keyset分页，严格应用ProjectManager/ImplementationMember/CustomerManager授权及独立HMAC cursor family；仅依赖注入密钥、默认路由不挂载。详见`docs/progress/out-01-a01-p14-output-request-list-precheck.md`。


- OUT-01-A01-P13按CR-OUT-010以PASS_SCOPE_LIMITED完成。Hosted run [41785576480](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41785576480) 14/14 jobs成功：后端3,988 tests/wheel、前端、PG18/pgvector、非发行父包、A17/A34/A35/A50全通过。新增固定版本OutputRequest read service、project隔离SQL projection与opt-in GET，HTTP/授权/SQL安全投影测试通过。该运行没有针对该Repository的PG18正向数据测试；正式路由未挂载、无插件/文件输出。详见`docs/progress/out-01-a01-p13-output-request-read-result.md`。下一项P14核查OUTPUT_REQUEST_LIST的角色和分页游标。


- OUT-01-A01-P13编码前检查通过并登记CR-OUT-010：读取固定OutputRequest refs/状态/JobRef的opt-in详情GET，按project+request双重过滤，Context正文不出库。详见docs/progress/out-01-a01-p13-output-request-read-precheck.md。

- OUT-01-A01-P12按CR-OUT-009以 PASS_SCOPE_LIMITED 完成。Hosted run [41780566043](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41780566043) 14/14 jobs成功；后端3,979 tests/wheel、新增OUTPUT_REQUEST_CREATE opt-in HTTP contract tests、PG18.6及完整非发行父包/A17/A34/A35/A50通过。服务未启动真实API、router默认未挂载、未执行插件或文件发布。详见docs/progress/out-01-a01-p12-output-request-create-http-result.md。下一项P13为OUTPUT_REQUEST_GET固定版本只读详情。

- OUT-01-A01-P12编码前检查通过并登记CR-OUT-009：仅接入冻结API-03的OUTPUT_REQUEST_CREATE单端点，复用既有Owner，router默认不挂载。详见docs/progress/out-01-a01-p12-output-request-create-http-precheck.md。

- OUT-01-A01-P11按CR-OUT-008以 PASS_SCOPE_LIMITED 完成。Hosted run [41777943851](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41777943851) 14/14 jobs成功；Plugin Owner-backed Output capability只读投影、正式publisher缺失/最新不兼容/歧义失败关闭已由PG18.6合成库验证。后端3,975 tests/wheel、前端与完整父包/A17/A34/A35/A50通过。无Win11实机、产品API启动、正式信任或插件执行。详见docs/progress/out-01-a01-p11-plugin-operation-capability-result.md。下一项P12为冻结OUTPUT_REQUEST_CREATE的可选HTTP adapter。

- OUT-01-A01-P11按CR-OUT-008编码中：新增Plugin owner-backed能力只读端口与Output adapter；Output能力默认改为关闭，只有明确的enabled/trusted证据才可通过。托管PG18验证与全链结果待完成，不构成正式publisher信任或Pilot结论。

- PLG-02-A08按CR-PLG-013完成并以 `PASS_SCOPE_LIMITED` 关闭。Hosted run [41770188317](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41770188317) 13/13 jobs成功：后端3970 tests/wheel、前端测试/typecheck/build、PG18 Migration 0230与插件停用HTTP幂等/Audit回滚验收、20,180项非发行父包及A17/A34/A35/A50通过。父包SHA-256 `a49af407…b61dfae`。三轮失败及修复先记CR后处理。未在Win11设备实测、未启动正式产品API；Pilot/Gate 3/正式Release仍未通过。详见`docs/progress/plg-02-a08-installation-disable-result.md`。

## Unreleased · 2026-11-04（内部云端验证，非发行版本）

- PLG-02-A07按CR-PLG-012完成并以`PASS_SCOPE_LIMITED`关闭。Hosted run [41759878694](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41759878694) 13/13 jobs成功：后端3967 tests/wheel、前端/build、PG18.6 Installation详情读取、父包20,176项、A17/A34/A35/A50通过。父包SHA-256 `cd54f676…d9a6a7`。首次FastAPI测试断言失败已先登记CR、改成公开HTTP行为校验后全量通过。未启动产品API、未做Win11实机验证，Pilot/Gate/正式Release未通过。详见`docs/progress/plg-02-a07-installation-read-result.md`。下一项PLG-02-A08冻结PLUGIN_DISABLE HTTP入口编码前检查。

## Unreleased · 2026-11-04（内部云端开发，非发行版本）

- PLG-02-A06按CR-PLG-011完成内部Installation操作停用Owner，PG18真实临时库验证多操作原子撤销、History/Audit、stale lock、失败回滚和精确重放。Hosted run [41755590662](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41755590662) 13/13 jobs、后端3,959 tests/wheel及完整父包/A17/A34/A35/A50通过；父包20,173文件SHA `cfe8f74d…a3d1072`。不接公开API/默认组合/插件执行。详见`docs/progress/plg-02-a06-installation-disable-result.md`。开始A07冻结Installation detail GET前置核查。

## Unreleased · 2026-11-04（内部云端开发，非发行版本）

- PLG-02-A06编码前核查已通过并登记CR-PLG-011：冻结API存在人工PLUGIN_DISABLE，但现有Owner缺少显式停用命令；本项实现同事务操作撤销、DISABLED History/Audit与状态版本更新。真实宿主安装适配器、公钥/License正式信任缺口保留为独立任务。详见`docs/progress/plg-02-a06-installation-disable-precheck.md`。后端实现及云端验收待完成。

## Unreleased · 2026-11-04（内部云端验证，非发行版本）

- PLG-02-A05按CR-PLG-010完成并以`PASS_SCOPE_LIMITED`关闭。GitHub hosted run [41743782405](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41743782405) 13/13 jobs成功；后端3,955 tests/wheel、PG18.6 Migration 0229退役guard、父包/A17/A34/A35/A50链通过。父包20,173文件SHA `81b1425c…e016515`。A34显示产品启动仍被正式信任、DB凭据、ACL和TLS阻断。无公开API/默认组合/物理卸载/插件执行。详见`docs/progress/plg-02-a05-installation-retirement-result.md`。下一项PLG-02-A06编码前检查。

## Unreleased · 2026-11-04（内部云端开发，非发行版本）

- PLG-02-A05编码前检查已通过：冻结状态已含RETIRED，现有逐操作History/Audit可表达人工退役；登记CR-PLG-010后实现内部终态Owner与Migration 0229。范围排除API、物理卸载和插件执行。详见`docs/progress/plg-02-a05-installation-retirement-precheck.md`。托管验收待完成。

## Unreleased · 2026-11-04（内部云端验证，非发行版本）

- PLG-02-A04按CR-PLG-009完成并以`PASS_SCOPE_LIMITED`关闭。GitHub hosted run [41738951137](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41738951137) 13/13 jobs成功：后端3,945 tests/wheel、前端/build、PG18.6 Migration 0228及有数据降级保护、父包PG smoke、A17/A34/A35/A50通过。两轮验证器偏差已先记CR再仅修正断言并完整重跑。未接公开API/默认组合/真实安装适配器，不安装/执行插件；Pilot/Gate/正式Release仍未通过。详见`docs/progress/plg-02-a04-runtime-revalidation-result.md`。下一项PLG-02-A05编码前检查。

- PLG-02-A04编码前检查完成：按冻结Installation/RuntimeValidation状态设计内部重验证Owner；不兼容时原子撤销操作启用、标记INCOMPATIBLE并记逐操作历史/Audit；从不兼容恢复只转DISABLED，须显式再启用。CR-PLG-009先行登记Migration 0228、回滚和托管验收计划；目前未改程序。详见 `docs/progress/plg-02-a04-runtime-revalidation-precheck.md`。用户本机不运行代码/测试。

- PLG-02-A03按CR-PLG-008以 `PASS_SCOPE_LIMITED` 完成：operation集合原子切换、历史安装状态维护、同事务Audit与逐operation不可变历史；migration 0227。GitHub hosted run [41728983860](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41728983860) 13/13 jobs成功，后端3,937项、父包PG18 smoke、A17、A34、A35、A50通过。首次PG verifier 17/3守卫计数偏差已先记CR，再更新为20/4并重验通过。无API/默认组合/物理安装/PluginExecution；Pilot/Release仍未就绪。详见 `docs/progress/plg-02-a03-installation-activation-result.md`。下一项PLG-02-A04编码前检查。

## Unreleased · 2026-11-04（内部云端开发，非发行版本）

- 已完成PLG-02-A03编码前检查并登记CR-PLG-008：实现Manifest operation子集按操作原子切换、旧/新Installation状态和同事务Audit；不接API/默认组合、不执行插件。计划revision 0227并用合成数据在GitHub hosted D盘验收。详见`docs/progress/plg-02-a03-installation-activation-precheck.md`。

- PLG-02-A02以`PASS_SCOPE_LIMITED`完成：内部安装事实Owner、PostgreSQL 0226最小INSERT守卫、原子Audit与PG18验证通过；GitHub hosted run [41721092729](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41721092729) 13/13成功，后端3932项和父包/A17/A34/A35/A50链通过。仅合成安装记录，无物理安装/默认组合/API/启用/执行/正式信任。两个迁移head断言偏差已先记CR再修复。详见`docs/progress/plg-02-a02-installation-owner-result.md`。下一项PLG-02-A03启用/状态变更Owner前置核查。

- PLG-02-A02第二轮run 41718480221后端全量、前端、PG18 sidecar与父包组装成功；Windows父包PG smoke发现PLG-01迁移验证器仍固定期待0225。偏差修复前已记CR-PLG-007；A35通过，A17结果尚未确认，A34未执行。

- PLG-02-A02实现提交0534e041新增受控Installation事实Owner、PostgreSQL repository、0226 append-only insert守卫和合成单测；首轮hosted run 41717001638后端3932项中一项旧migration head契约仍写0225，偏差先记入CR-PLG-007，待修正后完整重跑。未接API/默认组合、未部署真实包、未启用或运行插件。

- PLG-02-A02编码前检查通过有界范围：只记录由受控适配器验证的INSTALLED事实，不安装文件、不启用、不执行；数据库Owner开放需事务局部标记，明确不等于正式数据库身份隔离。无安装来源时失败关闭。详见`docs/progress/plg-02-a02-installation-owner-precheck.md`及CR-PLG-007。

- PLG-02-A01代码提交374fb1f6新增冻结Installation、EnabledOperation、RuntimeValidation三表ORM与PostgreSQL Migration 20261104_0225，包含精确Package/Manifest引用、重复启用唯一索引和Owner关闭/历史保护。GitHub hosted验收待完成。
- 本轮未接安装或启用API，未运行插件，也未创建真实信任/客户事实。

- OUT-01-A01-P10只读源码盘点完成（PASS_SCOPE_LIMITED）：PLG-01-A08只登记VERIFIED包，没有PluginInstallation/启用操作/正式运行信任事实Owner；Output Create继续失败关闭。
- 已先登记CR-PLG-007并完成PLG-02-A01编码前检查。下一项按冻结PLG-02表映射新增Installation/启用操作/runtime validation ORM与受保护Migration 20261104_0225；只在GitHub hosted D盘运行验收，本机/C盘不运行。
- 当前不实现安装/启用业务Owner或API，不执行插件，不创建信任或客户事实；云端全链验收后再更新本记录与STATUS。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）
- A08新增migration 20261103_0224和ORM staging metadata，保存package upload ID/hash/size、detached signature、signer key ref；新验证脚本覆盖append-only、TRUNCATE拒绝及有数据降级拦截，云端PG18验收待完成。
- A08 Job/Outbox首段由run [41602717998](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41602717998)全13/13 jobs成功。编码前复核确认后台验签还需持久保存detached signature/signer key reference；已先记录CR-PLG-006新增append-only暂存元数据表和0224 migration，Job payload仍只存ID/hash/size。
- 修正幂等键哈希域分隔符为固定ASCII冒号；前一替换未匹配转义文本，已记入CR-PLG-006。当前队列代码云端验收待本次提交。
- A08 Job/Outbox测试夹具已修正：无效值在测试函数中构造，避免pytest collection时提前异常；幂等键域分隔符规范化。产品逻辑未改，等待本次hosted验证。


- A08继续开发：新增Plugin package verification Job/Outbox queue contract与PostgreSQL repository；使用Deployment-scoped幂等键摘要，Job payload只含opaque upload ID、SHA-256及大小，Outbox仅引用Job和upload ID。相同key/相同内容重放原Job，内容不同冲突。
- 当前仍缺staging与Job协调/Audit/HTTP/Worker；定向测试与全链云端回归等待本提交运行，A08不标完成。
- 执行全部通过GitHub hosted runner；不在用户本机/C盘运行。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A07 已完成并以 PASS_SCOPE_LIMITED 关闭：hosted run [41593955795](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41593955795) 全13/13 jobs成功，后端3,909项及PostgreSQL 18真实登记/Audit原子性、失败回滚、幂等/冲突、0223迁移守卫通过。A07验收结果与CR-PLG-005已更新。
- 父子行写入顺序修复在同一事务先flush Package再添加子行；Audit/子记录失败仍整体回滚。代码未提前commit。
- 当前进入 PLG-01-A08 编码前检查，目标对齐冻结的异步签名包导入Contract。A07不包含公开HTTP/Job、ZIP持久化、安装或插件执行。
- 运行仅在GitHub hosted Windows Server 2025 D盘临时工作区，未在用户本机/C盘；测试数据为合成数据。正式信任、Win11实机、Gate/Pilot/Release状态不变。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- 路线纠正：A06后续路线先误指向已在2026-11-02完成的OUT-01-A01-P03，且该P03结果当时指向已完成的PLG-01-A01。保留历史记录，依据实际结果将当前WBS校正为PLG-01-A07；详见CR-PLG-005。
- PLG-01-A07编码前检查已完成：目标为只读验签/归档检查后的Package、Manifest operation/dependency和Verification结果原子登记；沿用0222元数据表，新增Owner migration仅允许INSERT并拒绝UPDATE/DELETE，保留TRUNCATE守卫。无公开HTTP/Job、ZIP内容落盘、安装、启用或插件执行。
- 限制：包内正式信任清单仍为空；hosted测试只用合成key/包。A07不让测试信任源进入默认生产组合，Pilot/Gate/Release不变。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A06 全链路验收完成：GitHub hosted Windows run [41582564698](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41582564698) 13/13 jobs成功；后端3,902项/wheel、前端、PG18/pgvector、父包、A35 handoff、A17包内PlanVersion flow及A34替换/显式恢复演练通过。A06只读ZIP/Manifest/整包签名联合检查为PASS_SCOPE_LIMITED。
- 偏差追溯：首轮Windows ZIP/EOCD fixture错误与第二轮既有随机UUID误报均先记录、后修正并完整复验，详见CR-PLG-004及A06结果文档；未改产品逻辑来消除随机误报。
- 兼容性/升级：没有新增DB/API/Migration或外部包格式升级；不执行插件导入、安装或运行。
- 限制：仅GitHub hosted Windows Server 2025合成验证；未形成Windows 11设备验收、正式信任、Gate、Pilot或Release证据。下一项按CR-EXEC-002为OUT-01-A01-P03。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A06 第二轮hosted run [41581853457](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41581853457) 的A06定向归档/EOCD用例通过，但后端3,902项中1项既有capability source proof单测因随机UUID偶然包含“cccc”而误报敏感repr，导致wheel/父包/A17/A34跳过。根因与修正前记录见CR-PLG-004/A06检查；先固定测试fixture再跑全量链。A06尚未PASS。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A06 首轮hosted run [41581198290](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41581198290) 后端3,902项中1个测试错误、1个失败；根因为Windows ZIP测试写入器规范化反斜杠夹具与EOCD测试字面量转义错误，检查器的对应负向断言未按预期执行。失败与修正计划先记入CR-PLG-004/A06检查；没有证据显示产品安全绕过，后端失败后wheel/父包链被跳过。
- 状态：A06未通过，正在先修正纯测试夹具后云端重跑。所有运行仍限GitHub hosted runner，不运行用户本机/C盘。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A05 新增只读包内发布者公钥Resolver并适配现有Plugin签名Verifier。hosted run [41579068045](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41579068045) 13/13 jobs成功，后端3,895项、wheel、前端、PG18、父包及A35/A17/A34链通过。空正式key manifest继续拒绝所有真实发布者签名。
- 兼容性：仅GitHub hosted Windows Server 2025；不在用户本机/C盘运行。没有Win11设备验收。
- 升级说明：无ORM/Migration/API；新Resolver只读取包内公开资源，无插件导入/安装/执行。
- 已知限制：仅PASS_SCOPE_LIMITED；无真实发布者key、动态撤销源或生产签名包。Gate3/Pilot/Release状态不变。下一项先固定ZIP envelope和无落盘安全读取合同，见CR-PLG-004。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A04 完成 Developer Workbench 插件 Ed25519 key ceremony 工具、空发布者清单资源及回滚恢复。首轮run [41575141107](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41575141107) 全13 jobs成功后，独立代码审查发现失败回滚残留ACTIVE清单，已先记CR并修复；修复提交 aaef9391b0a98b8b202e5140f7266b8a0a8841a0 的 hosted run [41576991044](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41576991044) 全13 jobs成功。后端3,889项、仪式5项、wheel、前端、PG18、父包、A35/A17/A34通过。
- 兼容性：只在 GitHub hosted runner 执行；工作目录/测试key使用 runner D盘临时环境。不在用户本机/C盘运行。
- 升级说明：无DB/API/Migration；wheel包含空公开信任清单。真实签发私钥不生成、不上传。
- 已知限制：A04仅PASS_SCOPE_LIMITED；真实密钥仪式、离线备份恢复、运行时信任、Windows11实机、Gate/Pilot/Release均未由本项证明。详细见 docs/progress/plg-01-a04-key-ceremony-result.md。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A03 完成只读版本化Manifest parser和路径校验；hosted run [41573036147](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41573036147) 13/13 jobs成功，后端3,889项全通过。此前3次路径断言失败经追查是测试helper直接传dict给bytes parser，已在结果文档中更正测试盲区和失败根因。
- 兼容性：仅GitHub hosted Windows Server 2025与合成Manifest；无本机/C盘运行、无Windows 11实机验收。
- 升级说明：内部代码更新，无DB/API/Migration；不生成安装包。
- 已知限制：不含ZIP解压、正式发布者信任、包导入/安装/执行。A03为PASS_SCOPE_LIMITED，Gate3/Pilot/Release仍NOT_READY。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A03 第三次 hosted run [41572410413](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41572410413) 发现12个入口路径子例由测试fixture helper误传dict导致，目标字段规则没有被测到。根因已记入CR-PLG-002/前置记录，修复测试后重跑，A03保持未通过。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A03 第二次 hosted run [41571779122](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41571779122) 仍在入口路径错误码专项断言失败；首次修正未闭合问题。已在CR-PLG-002与前置记录追加复现，暂停PASS结论并进行更精确定位。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A03 首轮 hosted run [41571211968](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41571211968) 后端3,888项中1项入口NUL错误码断言失败；输入已被拒绝，尚未出现路径穿越绕过。已在编码前检查/CR-PLG-002中记录，修复后重新跑全链。
- 兼容性：仅GitHub hosted Windows Server 2025；未在用户本机/C盘运行。
- 已知限制：A03验收尚未通过，不能标为可安装/可执行；后续包/A17/A34依赖链被跳过。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG任务顺序已记录：正式Plugin发布者根公钥/撤销源尚不存在，不能将合成验签提升为生产信任；先做独立版本化Manifest parser和入口路径校验（PLG-01-A03），其格式已在 [CR-PLG-002](docs/changes/CR-PLG-002-plugin-manifest-v1.md) 固定。生产信任源后续单独建设。
- 兼容性：开发分支文档/实现；Cloud runner D盘运行，用户本机未运行程序。没有Windows 11设备结论。
- 升级说明：Manifest parser无Schema/API迁移；未安装产品。
- 已知限制：A03不验签/解压/执行，不使Package进入VERIFIED；真实Trust root尚待。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A02 按 CR-PLG-001 增加纯Ed25519 detached插件包验签器：对完整包字节计算SHA-256并绑定签发者key-ref，密钥由独立Trust Port提供；8项定向单测及全链 hosted run [41569062762](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41569062762) 13/13成功。
- 兼容性：GitHub hosted Windows Server 2025与合成密钥；未在用户本机/C盘运行，也无Windows 11新实机验证。
- 升级说明：内部开发分支代码，无数据库/API变化；没有产品安装包或生产包升级。
- 已知限制：生产公钥信任/撤销源、包导入、Manifest兼容校验、安装和执行尚未接入；结果PASS_SCOPE_LIMITED，Gate 3/Pilot/Release仍NOT_READY。详情见 `docs/progress/plg-01-a02-signature-verifier-result.md` 和 `docs/changes/CR-PLG-001-plugin-package-signature-format.md`。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A01 已增加插件包不可变元数据持久层；GitHub hosted run [41566771430](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41566771430) 全13 jobs成功。当前转入 PLG-01-A02；由于ADR-005未指定签名算法，先登记 [CR-PLG-001](docs/changes/CR-PLG-001-plugin-package-signature-format.md)，冻结 Ed25519 与完整包摘要签名格式，再开始编码。
- 兼容性：仅云端 Windows Server 2025 runner；无本机/C盘执行、无Windows11新实测。
- 升级说明：仅开发分支规则/代码计划，不生成安装包。
- 已知限制：真实发布者信任源/撤销源缺失；A02合成测试不能作为正式信任、Gate、Pilot或Release证据。

## Unreleased · 2026-11-03（内部云端验证，不是发行版本）

- PLG-01-A01 新增 PluginPackage 不可变元数据 ORM 和 migration `20261102_0222`，包含 package、manifest operation/dependency 与追加式验证记录。Hosted run [41566771430](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41566771430) 13/13 jobs成功，后端/前端、PG18 schema、候选包、A35/A17/A34链路均通过。
- 兼容性：仅 GitHub hosted Windows Server 2025 与隔离PG18合成数据；临时文件在runner D盘。没有在用户本机/C盘运行代码，也没有Win11实机验收。
- 升级说明：仅开发分支数据库增量；尚未在用户或生产数据库安装，不是发行/安装包。
- 已知限制：签名验证、正式发布者信任源、包导入/安装/执行和Output registry尚未实现；PLG-01-A01为PASS_SCOPE_LIMITED，Gate 3/Pilot/正式Release仍NOT_READY。详情见 `docs/progress/plg-01-a01-package-registry-schema-result.md`。

## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- OUT-01-A01-P03 增加可信固定来源 Context resolver：通过显式 Source/Template/Policy/Plugin Operation Ports 校验精确版本、项目授权、审核态和类型关联，只按策略白名单输出受限Context及稳定fingerprint；缺定义/跨项目/未批准状态/不可信操作失败关闭。无Migration/API/Router/Plugin执行。
- 首轮新增深度负向测试夹具未超过限制导致run [41416698193](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41416698193)后端套件失败；已在CR-OUT-003记录后加深夹具。修正提交[run 41417503109](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41417503109)全13 jobs成功，含后端全量/wheel、前端、PG18重建、父包、A50 Edge、A17 Edge/HTTPS/PG、A34隔离替换恢复。
- 兼容性：仅GitHub hosted Windows Server 2025，所有临时运行目录使用D盘runner temp；不在用户本机/C盘运行。本次未做Windows11设备验收。
- 升级说明：包含P03代码的内部非发行父包候选artifact [13129330605](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41417503109/artifacts/13129330605)，不作为安装/发行包，不执行产品安装或服务启动。
- 已知问题：当前仍无生产Template/Policy/Plugin Operation registry和Requirement/Solution/Plan resolver adapters，实际生产Output Create保持不可用/失败关闭。P03为PASS_SCOPE_LIMITED；Gate3、Pilot、正式Release仍NOT_READY。详情见docs/progress/out-01-a01-p03-trusted-resolver-result.md。
- 偏差与修正：详见docs/changes/CR-OUT-003-output-trusted-resolver-boundary.md。

## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- OUT-01-A01-P02 已完成OutputRequest同事务Owner、幂等回执、Jobs-owned Outbox入队与可逆migration `20261102_0221`。hosted PR run [41413844603](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41413844603) 全13 jobs通过；PG18.6合成验收含并发合流、冲突、故障回滚、快照不可变及含历史的降级/重升级。仅PASS_SCOPE_LIMITED，不含公开HTTP、真实来源/模板注册、插件/Artifact、客户数据或Win11/正式发行验证。详情见 `docs/progress/out-01-a01-p02-create-idempotent-owner-result.md`。

- OUT-01-A01-P01 新增冻结 DM-04/API-03 语义下的 OutputRequest 与不可变 OutputContextSnapshot ORM/迁移，revision `20261102_0220`；CR-OUT-001 按本切片证据验证关闭。hosted run [41405621292](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41405621292) 全13 jobs成功，后端3,853项全量测试通过；PG18.6 空库升级、降级/再升级、既有合成数据升级通过。父包SHA-256 `a3062a6311d20c6d63f93dea6ce13b58136b8c0c45115e93345d45708cb3e1ea`，20,126文件。
- 兼容性：仅GitHub hosted Windows Server 2025，临时工作目录/数据位于D盘runner temp；没有在用户本机C盘运行。未进行本轮Windows 11设备验收。
- 升级说明：仅内部开发分支增量迁移，未在任何用户/生产数据库安装。
- 已知限制：Output业务Owner尚未完成，新表保持写入关闭；未实现HTTP、Plugin、Artifact或端到端生成。未启动产品服务、未使用正式License trust、未处理客户数据；Gate 3、Pilot、正式Release仍NOT_READY。

## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A50-E01 在 GitHub hosted Windows Server 2025 的 headless Edge 上完成待办来源导航专项合成验收；run [41396427656](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41396427656) 全13 jobs成功。固定版本目标在第2页精确定位；HUMAN来源不产生定位API/虚构锚点；跨项目和失效来源失败关闭并保留Action详情。后端3,850、前端2,075/200文件、typecheck/build及同run父包、PG18/pgvector、A34、A17链路均通过。父包SHA-256 `238d6a53db0f5e7e9955020e6caeecbb5a8d445a0f2025eadca081638ff83237`，20,122个payload文件。
- 兼容性：仅GitHub hosted Windows Server 2025，临时数据/工作目录在D盘runner temp；不是Windows11实机测试。没有在用户本机运行程序，无客户数据或外部API调用。
- 升级说明：生成非发行内部候选Artifact；没有产品安装/服务启动，不含正式License信任。
- 已知限制：状态仍为PASS_LIMITED；Gate 3、Pilot、正式Release及正式信任前置仍NOT_READY。

## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A50 实现交接待办按需解析固定来源并跳转到精确问题卡片；新增可选只读 source-location 子资源，冻结 Action GET 与数据库结构不变，无 Migration。Hosted run [41391544470](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41391544470) 全12 jobs成功：后端3,850项、前端2,075项/200文件、typecheck/build通过；父包20,122文件 SHA-256 `24f37f60…f8dc6db3eda`，PG18.6/pgvector0.8.6临时生命周期、A34隔离替换恢复、A17 packaged PlanVersion Edge/HTTPS/PG 29 API通过。A50结果为PASS_LIMITED，专项待办导航 Edge 验收留至A50-E01。
- 兼容性：本轮仅GitHub hosted Windows Server 2025；未进行新的Windows 11设备验收。没有在用户本机运行代码。
- 升级说明：非发行候选内部功能增量；无数据库迁移，不构成安装/升级包，不启动产品服务。
- 已知限制：A17浏览器测试覆盖PlanVersion，不覆盖A50来源导航；正式信任及Pilot/Gate/Release仍NOT_READY。

# Changelog

## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A49 在可读就绪报告置顶第一条待办，并以JSON字段复用有序动作首项；hosted run 41388401825 全12 jobs成功。零待办仍要求独立核验，授权值全false。父ZIP SHA-256 `07d74e91…f49c88920c`、20,122 files；A17/A34/PG通过。PASS_LIMITED。
- 兼容性：仅 hosted Windows Server 2025；无新Windows 11实测。
- 升级说明：仅内部非发行诊断候选更新，没有产品安装/升级。
- 已知限制：正式信任、DB身份、服务ACL、TLS和法务放行缺；Pilot/Gate/Release NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A48 按固定依赖顺序输出信任、DB凭据、服务ACL、TLS四组readiness待办；hosted run 41386839114 全12 jobs成功。零blocker完整登记仍需独立核验且不授权；候选ZIP SHA-256 `8e642dc1…aa48948`、20,122 files；A17/A34/PG通过。PASS_LIMITED。
- 兼容性：仅 hosted Windows Server 2025，无新Windows 11实测。
- 升级说明：仅内部非发行诊断候选更新；未安装/升级产品。
- 已知限制：正式信任/DB/ACL/TLS/法务条件未满足，Pilot/Gate/Release保持NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A47 为9个 readiness 缺项增加静态责任角色和下一步动作；hosted run 41383869172 全12 jobs成功。父包ZIP SHA-256 `1db6e14e…1452d370`、20,122 files；完整不授权、未知/秘密输入不回显；A17/A34/PG组合通过。PASS_LIMITED。
- 兼容性：仅 hosted Windows Server 2025；没有新的 Windows 11 实机验收。
- 升级说明：仅内部非发行候选诊断工具更新；未安装产品。
- 已知限制：正式公钥/License、DB身份、服务ACL、TLS与法务放行缺；Pilot/Gate/Release NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A46 为 readiness PowerShell 入口新增可选中文可读模式；GitHub hosted run 41382282100 全12 jobs成功。不完整/完整/无效三态通过，完整不授权、哨兵不回显，默认JSON保持兼容。候选ZIP SHA-256 `c9b6d945…7164d3`、20,122 files；A17/A34/PG18组合通过，PASS_LIMITED。
- 兼容性：仅 hosted Windows Server 2025；无新的 Windows 11 实机运行。
- 升级说明：只更新内部非发行父包诊断工具；没有安装/升级程序。
- 已知限制：正式公钥/License、DB身份、服务ACL、TLS、法务放行未满足；Pilot/Gate/Release仍 NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A45 为包内就绪报告增加9个缺项的静态中文填写指导；hosted run 41378263123 全12 jobs成功。候选ZIP SHA-256 `e2858a6b…0256ca`、20,122 files；完整登记不授权、非法值不回显、manifest不变。A17/A34/PG组合通过，结果 PASS_LIMITED。
- 兼容性：仅 GitHub hosted Windows Server 2025；未进行新的 Windows 11 实机验收。
- 升级说明：仅更新内部非发行候选诊断工具；未安装或启动产品。
- 已知限制：正式公钥/License、DB身份、服务ACL、TLS和法律放行仍缺；Pilot/Gate/Release NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A44 将非秘密 Pilot 就绪报告/模板和 PowerShell 入口纳入 Windows 候选包，并在 hosted run 41376505925 完成12/12组合验收；9项缺项正确显示、完整登记仍不授权、非法输入不回显。父包SHA-256 `8e3e4e37…f801d`，20,122 files；A17 29 API/A34恢复通过。详情见 [A44结果](docs/progress/plt-pkg-01-a09-p51-a44-readiness-tool-bundling-result.md) 与 [run](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41376505925)。
- 兼容性：仅 GitHub hosted Windows Server 2025；未进行新的 Windows 11 实机验收。
- 升级说明：仅内部非发行包内容变化；没有产品安装/服务升级。
- 已知限制：正式公钥/License/DB身份/服务ACL/TLS和法律放行仍缺；Pilot/Gate/Release保持 NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A43 从固定公开输入云端重建当前 PR 源码的 Windows 父包候选；12/12 hosted jobs 成功，父包 ZIP SHA-256 63ed5c8d…05a7a、20,118 个文件。同run完成暂存、PG18/pgvector、A17 29次API合成业务流和A34隔离替换/手动恢复演练。详情见 [A43 结果](docs/progress/plt-pkg-01-a09-p51-a43-hosted-rebuild-result.md) 与 [run 41370951575](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41370951575)。
- 兼容性：仅GitHub hosted Windows Server 2025；不能推定Windows 11新运行兼容。
- 升级说明：生成仅限内部验证的临时候选artifact，不是安装器或正式Release；未在本机安装/运行。
- 已知限制：正式信任、License、数据库凭据、服务ACL与TLS前置仍缺，应用/服务未启动，Pilot/Gate/Release保持NOT_READY。

## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A42 将包外 Authenticode 指纹校验接入候选暂存CLI。安装器与指纹成对提供；校验失败时ZIP暂存目标不创建；成功收据仅标记 TEST_ONLY。GitHub hosted Windows run 41370763918 的26项定向回归和A35集成通过，PASS_LIMITED。
- 兼容性：仅在 GitHub hosted Windows Server 2025 验收；不推定 Windows 11 实机兼容。
- 升级说明：仅开发/云端验证工具更新，没有安装包升级或产品安装。
- 已知问题：真实产品发布者证书/固定指纹及安全安装执行路径仍未建立；Pilot/Gate/正式Release仍 NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A41 新增 Windows Authenticode 只读校验器，要求包外签发者指纹；未签名、签名异常、指纹不匹配或调用失败均拒绝。GitHub hosted Windows run 41370436650 的24项定向回归及真实签名/未签名文件验证通过，PASS_LIMITED。
- 兼容性：只在 GitHub hosted Windows Server 2025 验证；不推定 Windows 11 实机兼容。
- 升级说明：仅内部验证工具；没有改变候选父包，不安装或升级已有程序。
- 已知限制：未提供真实产品代码签名证书/外部正式指纹，验证结果标记 TEST_ONLY；Pilot/Gate/正式Release仍 NOT_READY。


## Unreleased · 2026-11-02（内部云端验证，不是发行版本）

- P51-A40 新增 hosted 离线候选暂存CLI与专用 GitHub Actions 验收；19/19 定向测试通过。A35 父包 SHA-256 `94700239…e2f2`，20,119 payload files 验证并暂存；A38 保持5项启动阻断，包内诊断 `BLOCKED/exit 2`。验收 run [41369734304](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41369734304)，结果 PASS_LIMITED。
- 兼容性：验收运行于 GitHub hosted Windows Server 2025、D盘 runner temp；不构成 Windows 11 实机兼容证据。自2026-11-02起没有在用户本机运行程序。
- 升级说明：仅内部开发工具/云端workflow变更；没有生成可安装升级包，不触碰已有安装。
- 已知问题：正式产品公钥/License信任、数据库凭据身份、服务账户ACL、TLS材料及包外可验证代码信任仍未齐；未安装、未启动服务，Pilot/Gate/正式Release保持 NOT_READY。

- 2026-10-30 P51-A39：只读核查A35真实父包确认根目录无安装/升级入口，只有manifest、hash清单；payload仅含说明、诊断和fail-closed launcher。A34/A35隔离恢复不等于安装或重启。新增CR-PKG-012，在持续授权下推进离线分阶段安装入口，不越过正式信任/服务/TLS/DB门禁；本轮未解包、安装或重启。见A39结果及CR-PKG-012。
- 2026-10-30 P51-A38：新增只读 Pilot 就绪诊断器，合并非发行父包 manifest 的固定阻断字段与A37登记完整度。即使所有标志为真且登记完整，也恒定返回pilot_ready=false/launch_authorized=false/release_eligible=false/legal_clearance=false。Windows 11 Python 3.13合计12/12测试通过；用A35父包SHA 94700239...e2f2内存读取manifest与空模板完成只读集成。无服务/DB/凭据访问或C盘运行，Pilot/Gate/Release不变。详见 `docs/progress/plt-pkg-01-a09-p51-a38-readiness-report-result.md`。
- 2026-10-30 P51-A37：新增 Windows Pilot 非秘密输入登记器、空白JSON模板及操作约定。只接受固定格式的公钥SHA指纹、License/证据引用、固定DB Credential Manager目标、Windows服务身份引用和TLS元数据；未知字段/无效值拒绝且不回显。完整登记也只标记需独立验证。Windows 11 Python 3.13合成测试6/6通过，未读密钥或接入启动放行。PASS_LIMITED，Pilot/Gate/Release不变。见 `docs/progress/plt-pkg-01-a09-p51-a37-input-register-result.md`。
- 2026-10-30 P51-A36：盘点 Windows 11 Pilot 正式信任前置自动化。固定公钥/License、限定数据库凭据、服务身份/ACL、真实TLS链尚缺实际输入；现有工具只提供缺项守门或材料到位后的部分检查。无前置被虚假关闭，Pilot/Gate/Release仍NOT_READY。Windows 11本机启动前置单测2/2通过；另一模块导入依赖未装，不写C盘安装。详见 `docs/progress/plt-pkg-01-a09-p51-a36-windows11-trust-prerequisite-audit-result.md`。
- 2026-10-30 P51-A35：Windows 11 Home 中文版 build 26300 实机 D 盘隔离完成两份父包初装/替换、失败隔离和显式恢复；旧/新20,119项、4类持久标记保留，16/16分块Artifact摘要复核，launcher继续BLOCKED/exit 1且无service/API/listener。hosted run 41026213054全12 jobs success；只PASS_LIMITED，不代表正式安装、其他Windows 11 edition或Pilot/Gate/Release通过。详情见 `docs/progress/plt-pkg-01-a09-p51-a35-windows11-package-rehearsal-result.md`。
- 2026-10-30 P51-A34：hosted Windows Server 2025 D盘隔离完成父包初装、整包替换、失败候选隔离及显式手动恢复；旧/新候选各20,119项，4类持久数据标记保留。launcher持续BLOCKED/exit 1，无service/API/listener启动。GitHub Actions run 41020308619全11 jobs成功，A34证据Artifact SHA-256 `d284a29542f01825da7375151449030c754f7a8cf63a48c37f897f9758b5e325`。A34仅PASS_LIMITED；不代表Windows 11实机安装、正式信任、Pilot、Gate或Release通过。详情见 `docs/progress/plt-pkg-01-a09-p51-a34-cloud-install-rehearsal-result.md`。
- 2026-10-30 P51-A33：父包启动入口在受信任前置缺失时复用只读诊断并输出六项BLOCKED JSON，仍以exit 1拒绝启动；缺诊断脚本/损坏manifest回退、无listener、A29/A30篡改矩阵及同run PG18/A17均通过。Hosted run 41008231772全10 jobs success；后端3,849项；A17 PlanVersion 29 API调用。父包SHA-256 104b8559...55cf6。采用.NET流式SHA-256兼容PowerShell 5.1；多轮偏差及PR #60远端并发合并事实已记录。无API/Schema/Migration变化；仅PASS_LIMITED，Pilot/Gate/Release仍NOT_READY。详情见 `docs/progress/plt-pkg-01-a09-p51-a33-launcher-feedback-result.md`。
- 2026-10-30 P51-A32：精确将父包级payload/check-startup.ps1排除在当前应用布局投影之外；全源清单仍校验、其他未知文件仍拒绝。新增投影单测5/5、后端3,849项通过；A31父包诊断+PG smoke和A17 PlanVersion Edge/HTTPS/PG（29 API）同run通过，详情见A32结果文档。无API/Schema/Migration变化；候选仍非发行，Pilot/Gate/Release NOT_READY。
- 2026-10-30 P51-A31：hosted父包实际解包根目录README诊断命令专项PASS_LIMITED；清洁父包20,119文件，SHA-256 10eca56d...57acc6，命令固定BLOCKED/exit 2/无监听。后续A17组合检查发现新增父包级诊断脚本未列入应用投影白名单，已登记P51-A32；此workflow整体未全绿。无API/Schema/Migration变化；Pilot/Gate/Release仍NOT_READY。
- 完成 P51-A28 受限 Windows 启动协调器正式信任/凭据/ACL/TLS前置显式守门；hosted run 40981581644全10 jobs通过。真实父包仅固定拒绝，A17 PlanVersion Edge/HTTPS/PostgreSQL闭环PASS_LIMITED；不代表Windows 11设备或正式发行。
- 完成 P51-A29 启动manifest严格类型检查及7种篡改清单hosted负例；run 40983612763的PG smoke job通过，stdout为空、无listener、源manifest未变。未接入正向生产启动。
- 兼容性/升级：仅内部非发行候选及启动诊断守门变化，无API或数据库迁移；不得覆盖已有安装。
- 已知限制：正式产品公钥/License trust、服务账户数据库凭据/ACL/TLS配置与Windows 11设备安装升级仍未齐备，Pilot/Gate/Release保持NOT_READY。
- P51-A30新增父包只读启动前置诊断命令：仅读非秘密manifest，输出BLOCKED及缺少项，不启动服务或读取凭据/私钥。hosted run 40988858723的D盘父包PG smoke验证当前报告及4类篡改输入，A29七类守门矩阵同轮通过。
- 版本/升级：仅非发行包增加一个PowerShell诊断脚本与README说明；无API/Schema/Migration变化，不对已有安装执行升级。
- 已知限制：该命令只说明当前候选未具备的启动条件，不会使包具备正式信任/安装资格；Pilot/Gate/正式Release仍NOT_READY。



## Unreleased · 2026-10-30（内部云端验证，不是发行版本）

- 修正 PlanVersion 固定历史读取 Client 对浏览器原生 fetch 的接收者调用方式；增加 this/globalThis 回归覆盖。没有改变冻结 API、数据库、Migration、权限或状态机。
- 完成 A17 父包中 PlanVersion Edge/HTTPS/PostgreSQL 合成闭环 hosted 验收；详情见 [A27 验收记录](docs/progress/plt-pkg-01-a09-p51-a27-planversion-cloud-result.md) 与 [GitHub Actions run 40841364426](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/40841364426)。
- 兼容性：本次前端修复不要求数据库或API升级；hosted Windows Server 2025 验证不是 Windows 11 设备验收。
- 升级说明：仅内部代码候选，不能作为正式安装包；后续同源候选应从该提交重新构建，不对既有安装执行升级。
- 已知限制：manifest 保持 release_eligible=false/legal_clearance=false；正式License信任、服务账户凭据/TLS、离线安装升级和 Windows 11 实机验收仍未完成，Pilot/Gate 3/正式Release NOT_READY。


## Unreleased · 2026-11-04（云端验证待完成，不是发行版本）
- A08新增Windows Plugin package verification Worker CLI组合入口：显式读取Bootstrap/当前账户数据库凭据，检查数据库schema与License后执行一次处理或常驻轮询，并登记诊断进程角色。Worker不安装、不执行插件；未接默认API，也未自动安装服务。
- 新增Worker诊断角色测试。该提交的后端/前端回归、wheel、Windows父包和集成验证待GitHub Actions；A08仍未关闭，Pilot与正式Release仍NOT_READY。
- 所有代码与验证均计划在GitHub托管runner执行，不占用用户本机C盘。


## Unreleased · 2026-11-04（A08 Worker CLI云端结果与集成验收）
- Worker CLI/诊断角色提交 `bcb69866` 的GitHub hosted workflow [41673992094](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41673992094) 全13 jobs成功；不代表新加入的PG18 Worker端到端smoke已通过。
- 新增PG18真实Worker claim/fencing、无信任签名失败关闭、synthetic Ed25519有效包只登记元数据、短暂staging故障与bounded retry恢复的验收代码，并新增Windows入口模块导入保护。验证待本轮hosted workflow。
- 全部运行保持在云端，不使用用户本机C盘；无客户数据外发。


## Unreleased · 2026-11-04（PLG-01-A08受限完成）
- A08 Worker CLI与PG18端到端smoke提交 e37e668e 已通过GitHub hosted workflow [41678551589](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41678551589) 13/13 jobs。任务结论PASS_SCOPE_LIMITED；无插件执行、真实publisher trust/Windows 11设备验收。Pilot/Gate/正式Release仍NOT_READY。
- 下一项转为OUT-01-A01-P04前置核查，调查Output固定来源和模板/策略/插件Registry真实接线，不改变冻结API或Schema。


## Unreleased · 2026-11-04（Output Source 生产接线前置）
- OUT-01-A01-P04源码盘点完成；下一项P05为Requirement固定版本Source Owner读取与组合根映射。实现边界和验收计划已在CR-OUT-005先行记录，尚未修改代码。


## Unreleased · 2026-11-04（Requirement固定版本Source接线）
- OUT-01-A01-P05提交 [188a2ca0](https://github.com/yanglu0928/PLM-ProjectTool/commit/188a2ca0036acedfeb95b77883446a2315c90255) 的GitHub hosted run [41684956861](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41684956861) 全13/13 jobs成功。后端全量测试/wheel、前端构建、PG18/pgvector、Windows父包、A35、临时PG smoke、A17及A34均通过；A17 Artifact明确包含 `OUT_01_A01_P05_REQUIREMENT_FIXED_SOURCE_PG_PASS`。
- PG18合成烟测验证ProjectId+固定RequirementVersionId精确读取、`APPROVED`状态保真及非成员拒绝；无Schema/API/Migration变更、无外发数据。仅GitHub hosted Windows Server 2025，不构成Windows 11设备/Pilot/Gate/正式发行结论。
- Output文件模板/Policy Registry、Plugin启用/正式信任仍未实现，真实Output Create继续失败关闭。下一项为P06模板固定版本Registry编码前核查。


## Unreleased · 2026-11-04（Output模板Owner编码前核查）
- P06源码及冻结基线核查确认：OutputTemplate不属于冻结65个Aggregate Root；PrototypeTemplate是独立的原型布局/组件合约，不能冒充DOCX/PPT/Flow文件模板。决定在CR-OUT-006下实现只读、内置、固定版本OutputTemplate Registry，不加客户数据库表/API/Migration，不支持项目自定义模板。
- P06结论PASS_SCOPE_LIMITED；P07仅实现内置模板Registry与严格契约验证。Output Policy、Plugin启用/信任及生成/Artifact链未完成，因此不开放真实Output Create。


## Unreleased · 2026-11-04（内置Output模板Registry代码候选）
- P07新增固定版本只读内置DOCX模板metadata Registry，限REQUIREMENT_VERSION来源；无客户DB/API/Migration、自定义模板或渲染逻辑。A17 packaged runtime新增专用标记；本提交GitHub hosted验证待完成。
- Output Policy、Plugin enable/trust、文件生成与Artifact链仍缺；当前不支持真实Output Create。


## Unreleased · 2026-11-04（内置Output模板Registry受限完成）
- OUT-01-A01-P07提交 ab23b77e 的GitHub hosted run [41688934347](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41688934347) 13/13 jobs成功。后端全量/wheel、前端、PG18/pgvector、Windows父包、A35、临时PG、A17、A34全部通过；A17 evidence明确记录 OUT_01_A01_P07_BUILTIN_TEMPLATE_REGISTRY_PASS。
- Registry只提供固定ref的内置DOCX/RequirementVersion模板metadata；不含DOCX渲染内容，不支持自定义，不接真实Output Create。无数据库/API/Migration依赖变化。仅GitHub hosted Windows Server 2025合成验证，非Win11设备或发行证明。
- Output Policy、Plugin启用/正式信任、渲染与Artifact发布链仍缺；Pilot/Gate/正式Release保持NOT_READY。下一项P08先做Policy Registry编码前核查。


## Unreleased · 2026-11-04（Output Policy Owner编码前核查）
- P08确认冻结模型没有OutputPolicy Aggregate Root、DB表或管理API；插件operation registry的trusted/enabled生产事实缺失。依据CR-OUT-007，P09只实现一条内置不可变策略：P07固定DOCX、RequirementVersion/APPROVED，字段title/statement/acceptance_criteria，最多4来源/8192 bytes。word.generate允许列表不能替代plugin信任或启用。
- P08 PASS_SCOPE_LIMITED；本轮不新增Schema/API/Migration、不生成文件、不外发客户数据。


## Unreleased · 2026-11-04（内置Output Policy代码候选）
- P09新增只读固定ref内置OutputPolicyVersion Registry，严格限制P07 DOCX/REQUIREMENT_VERSION/APPROVED、字段title/statement/acceptance_criteria、4来源及8192字节Context；Resolver集成单测使用显式synthetic operation事实，不能视为生产Plugin信任。
- A17新增随包Policy metadata marker；云端验证待本提交。无DB/API/Migration变化，不接生产Resolver、不生成文件或外发数据。


## Unreleased · 2026-11-04（P09首轮云端失败记录）
- run [41692180197](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41692180197) 后端测试单项失败：测试误将空Policy目录的精确错误期待成通用目录无效消息。已先记录CR-OUT-007/P09进度文档，待修正测试断言后重跑全链；P09尚未通过，不是发布版本。


## Unreleased · 2026-11-04（内置Output Policy Registry受限完成）
- P09首轮run 41692180197仅因新增测试对空目录错误文本断言不匹配而失败，偏差先记于CR-OUT-007；产品逻辑未改，后修正测试并重跑。
- 修正提交 ac7cae27 的GitHub hosted run [41693364068](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41693364068) 13/13 jobs成功。后端全量/wheel、前端、PG18/pgvector、父包、A35、PG smoke、A17、A34成功；A17证据含 OUT_01_A01_P09_BUILTIN_POLICY_REGISTRY_PASS。
- Policy仅允许固定DOCX/Template/RequirementVersion APPROVED及有限字段/来源/上下文大小；word.generate allowlist不意味着Operation installed/enabled/trusted。无Schema/API/Migration变更，不接生产Output Create。仅PASS_SCOPE_LIMITED，无Win11新设备/Pilot/Gate/正式发行结论。


## Unreleased · 2026-11-04（PLG-02-A01内部云端验收，非发行版本）

- 版本：内部候选；不是安装包或正式发行。
- 变更：新增冻结PluginInstallation根及EnabledOperation/RuntimeValidation ORM与Migration 20261104_0225。初始Owner写入口保持关闭；不新增API、信任来源或插件执行。
- 验证：GitHub hosted run [41711045048](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41711045048) 13/13 jobs成功。PG18.6隔离合成库验证全新/既有库升级、空库回退重升、复合FK与唯一索引、Owner写入及TRUNCATE拒绝、有安装历史降级拒绝和记录保留；后端全量/wheel、前端、父包、A17/A34通过。
- 兼容性：PostgreSQL schema head推进至20261104_0225；父包候选限GitHub hosted Windows Server 2025验证。没有新的Windows 11实机/正式发行验证。
- 升级说明：升级运行数据库至0225；不对用户现有安装执行升级。降级在PluginInstallation相关历史存在时会拒绝。
- 已知问题：无正式插件安装Owner/API或可信Publisher来源，插件未运行；候选包不具备法律放行。Pilot、Gate、正式Release保持NOT_READY。

## Unreleased · 2026-11-04（内部云端开发，非发行版本）

- 完成OUT-01-A01-P11编码前检查，登记CR-OUT-008：下一项实现只读PluginOperationCapability投影，依据PLG-02持久Owner事实校验安装、启用与最新运行兼容状态；无正式publisher key时trusted始终为false，不修改API/Schema、不执行插件。详见`docs/progress/out-01-a01-p11-plugin-operation-capability-precheck.md`。


## Unreleased · 2026-11-05（PLG-03-A01托管验收；P32恢复，非发行版本）
- PLG-03-A01 PluginExecution持久化基础通过GitHub hosted run [41974625395](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41974625395) 的PG18.6独立schema verifier，结论PASS_SCOPE_LIMITED。全链同轮后端/wheel、前端/build、父包PG18 smoke成功；P25独立initdb 0xC0000135失败，故workflow非全绿。未执行插件、未产生文件、无客户数据。
- 依赖解除后恢复OUT-01-A01-P32；按CR-OUT-028先更新编码前检查。P32的OUT-02持久层代码已提交，GitHub hosted全链与PG18专项验收待完成；API/发布Owner/文件生成与插件执行继续关闭。
- 兼容性/运行位置：数据库迁移链计划推进至20261105_0232；只在GitHub hosted Windows runner D:临时目录运行。本机/C盘不运行项目程序或测试。
- Pilot、Gate 3～7及正式Release状态不变，Windows 11设备与三平台发行未因此通过。


## Unreleased · 2026-11-05（P32首轮托管验收未关闭）
- run [41979765906](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41979765906) 后端全量/wheel、前端/build、嵌入式组装通过；父包PG smoke在P32验证器查询既有合成Job哨兵时因TEXT trace_id错误绑定UUID而停止。该结果不能判定P32约束或Migration验收通过/失败。偏差和仅修验证器参数计划先记CR-OUT-028；等待后续云端全链复验。P25为独立失败，本机/C盘未运行代码。


## Unreleased · 2026-11-05（P32第二轮验证器夹具偏差）
- run [41981257687](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41981257687) 中P32 verifier通过Migration升级和关系/写守卫存在性后，单表TRUNCATE在PostgreSQL外键检查阶段拒绝，未触发自定义TRUNCATE保护断言。该负例夹具范围问题已先记CR-OUT-028；产品DDL未改，修正为根/子表同语句且不使用CASCADE后重跑。P32尚未关闭，P25独立失败。


## Unreleased · 2026-11-05（P32第三轮发现触发器缺陷）
- run [41983022536](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41983022536) 中迁移/约束/owner closed/TRUNCATE验证推进至Artifact validation child insert，发现trigger函数因PL/pgSQL复合布尔条件跨表字段求值而失败。该产品触发器缺陷先记CR-OUT-028，尚无P32通过结论；修复后重跑。P25独立失败。


## Unreleased · 2026-11-05（P32发现AVAILABLE SQL NULL校验缺口）
- run [41984648401](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41984648401) 后端/前端与父包组装成功，专项验证发现缺失validation_summary JSON键使CHECK返回NULL并按PostgreSQL规则通过，从而未能阻止合成未验证Artifact进入AVAILABLE。先记CR-OUT-028，修复为NULL安全比较；P32未通过，生产发布能力仍关闭。


## Unreleased · 2026-11-05（P32第五轮计数夹具偏差）
- run [41986547768](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41986547768) 通过AVAILABLE NULL安全负例、4项通过正例、子表append-only和历史拒绝降级；最终夹具保留断言预期child=1，但实际四项校验fixture写入4条，导致P32未关闭。偏差先记CR-OUT-028，修正为4后重跑。


## Unreleased · 2026-11-05（P34发布Owner前置拆分）
- P34源码审计发现普通上传版本Owner明确拒绝GENERATED_ARTIFACT，P33又要求AVAILABLE DocumentVersion既存；按CR-OUT-031拆分P34A系统生成版本Owner与P34B本地Storage发布协调。仅记录源码证据，尚无代码验收，不视为PASS。后续项目代码仅使用GitHub hosted D盘/云端沙箱，用户本机与C盘不运行。

- OUT-01-A01-P34A编码前检查按CR-OUT-031为PASS_WITH_LIMITATION：Migration 0022来源引用与DocumentVersion触发器支持无Schema调整实现OUTPUT_GENERATION来源；实现/PG18验收待完成。
## Unreleased · 2026-11-05（P34A Owner候选）
- 新增内部SYSTEM-owned Generated Artifact DocumentVersion Owner及SQLAlchemy Repository：按OutputRequest→Job Claim→Execution→FileObject→Document顺序验证；以最终已AVAILABLE FileObject创建不可变DocumentVersion/source ref、推进latest pointer并同事务写Audit。无Schema/API/default composition接线。
- run [42030014722](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42030014722) Backend全量测试/wheel成功，定向fake-port单测包含事务回滚/锁序断言；全链父包PG smoke/A17/A34/A35成功。PG smoke未执行P34A Repository，故本WBS未PASS，下一步加真实PostgreSQL 18专项断言。P25独立initdb 0xC0000135失败，Windows Pilot/Gate/Release不变。仅GitHub hosted D盘运行。
## 2026-11-05 · OUT-01-A01-P34A PASS_SCOPE_LIMITED
- run [42033255833](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42033255833)：后端全量/wheel、前端/build、PG18/pgvector sidecar、clean parent PG18 smoke、父包组装、A17、A34、A35、P24、A50成功。PG18 smoke以无DocumentVersion的GENERATED_ARTIFACT Document/AVAILABLE FileObject起始，执行P34A Owner，核对Version/source ref/latest pointer/SYSTEM Audit，精确重放不新增Audit，再由P33成功终结Owner验证既有端到端事务；P34A结论PASS_SCOPE_LIMITED。
- 同run独立P25仍因initdb.exe exit 3221225781/0xC0000135及未创建数据目录而失败，P25真实HTTP/Edge未执行，整体workflow未全绿。未改变Pilot/Gate/Release状态。

## 2026-11-05 · P34B编码前检查
- PASS_WITH_LIMITATION：确认不得复用Document USER文件发布服务；采用Output SYSTEM专用协调Owner，在不持DB锁的情况下执行Storage hash/同卷提升，之后短事务重核fence与文件事实，再调用P34A/P33。恢复仅允许STAGE_ONLY、FINAL_VERIFIED、LINKED_PAIR；未知形态不动文件。无Schema/API/默认组合变化。尚未编码，见docs/progress/out-01-a01-p34b-storage-publication-precheck.md。


## Unreleased · 2026-11-05（P34B恢复分支定向测试，待云端复验）

- 新增Output文件发布Owner恢复调度单测，覆盖STAGE_ONLY、FINAL_VERIFIED、LINKED_PAIR与不安全/未知形态失败关闭，并验证AVAILABLE final和定位不匹配的Storage调用边界。验证仅安排在GitHub hosted Windows D盘；当前尚未通过，P34B未关闭。
- run [42047066825](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42047066825) 的父包PG18 smoke正常STAGE_ONLY发布、P34A/P33事务及故障回滚/重放断言通过；Backend全量/wheel成功。P25独立失败、A34当时尚运行，不构成整体Workflow全绿。


## Unreleased · 2026-11-05（P34B恢复单测首轮夹具偏差，未通过）

- run [42050570499](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42050570499) Backend 4067项中新增STAGE_ONLY单测因fake把publish_verified的staging定位符误当最终Proof而失败；父包PG18 smoke因依赖跳过，P34B无复验结论。偏差已记录，修正测试替身后重跑；产品代码未因本次失败而变更。


## Unreleased · 2026-11-05（OUT-01-A01-P34B受限完成）

- P34B Storage发布协调按CR-OUT-030/031以PASS_SCOPE_LIMITED完成。run [42051895394](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42051895394) 的Backend 4,067 tests/wheel、前端/build、Windows父包和clean PG18/pgvector smoke通过；Recovery dispatch单测覆盖STAGE_ONLY、FINAL_VERIFIED、LINKED_PAIR精确方法与不安全/未知形态失败关闭。PG smoke验证Storage→FileObject→P34A DocumentVersion/Audit→P33 Artifact/Job完成、P33 Audit失败回滚及精确重放。
- 同run P25 HTTP/Edge独立失败；A17业务步骤后清理临时锁文件遇Windows EBUSY；A34通过，故整体workflow非全绿。P25仍BLOCKED_DIAGNOSTIC。无Schema/API/default composition/Worker/插件执行变化，无客户数据；局部受限结果不代表生产Output、Windows 11设备、Pilot/Gate/Release通过。
- 兼容性：无数据库/API升级要求；仅内部分支Owner/测试变更。下一项按STATUS进入P35 Output生产接线编码前检查。


## Unreleased · 2026-11-05（P34B最终分支复验）

- 最新文档tip hosted run [42055479870](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42055479870) 再次通过Backend 4,067 tests/wheel、Frontend/build、PG18/pgvector parent smoke、20,223项父包构建、A35、A17和A34。父包 SHA-256 `4000d012666f1de0c5e77234efaa6d8ec6848aa898bd7555d802b93fb829457e`；P34B PG链路重复PASS_SCOPE_LIMITED。
- 同run唯一失败为独立P25 HTTP/Edge；A17清理锁文件EBUSY未复现。整体workflow非全绿；P25/Pilot/Gate/正式Release保持原状态。
