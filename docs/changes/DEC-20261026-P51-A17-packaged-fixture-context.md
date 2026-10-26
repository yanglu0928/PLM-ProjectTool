# DEC-20261026-P51-A17：包内验收合成来源夹具上下文

- 日期：2026-10-26
- WBS：`PLT-PKG-01-A09-P51-A17`
- 状态：执行中，fixture 构建尚未收敛；不构成验收通过
- 类型：仅测试工具决策，不修改产品基线/API/Schema/正式 License 信任

## 背景与差异

P51-A17 的 Windows 11 非发行候选已完成摘要与清洁 stage 检查，但源级 Approved Outline 构造器需要 PostgreSQL 端口、Runtime、License Guard、Audit、Session 和 Document/Download/ParseResult Port。既有 HTTPS smoke callback 采用多层 `**kwargs` 转发，直接增加回调参数会破坏上游探针的签名；正式 `create_windows_license_services` 启动门面也不适用于在同一临时进程内拼装来源 fixture。

## 决定

仅对包验回调传入的 `fixture_db` 函数附加该次 smoke 所拥有的临时 PG 端口/数据库、API 临时数据根和合成公钥文件路径。A17 fixture 使用该端口构造同一隔离数据库 Runtime，并由正式 License Guard、Audit、Document/Download/ParseResult 实现组合既有 Outline 业务 Owner。合成公钥直接读取 smoke 在临时安装布局生成的公钥文件；不生成客户或正式信任事实。回调新增数据通过已存在的 `fixture_db` 能力传递，不扩展层叠探针的 kwargs。

将既有 Outline fixture 的连接工厂在本次内存运行实例中绑定到 smoke 随机命名的 disposable database；不能沿用旧 PG fixture 固定的 `postgres` 数据库名。

A17 在调用 PlanVersion fixture 后不重复运行与本 WBS 无关的 Survey 审批后 Edge/合成过期 Edge 驱动；Survey 的包内创建/Validate/送审与 PG 检查仍由上游链执行。这样不会把后续 Chromium 临时 Profile 清理故障误判成 PlanVersion 失败，也不把被跳过的 Survey 后置项声称为本轮通过。

为解除缺失来源阻断，新增测试夹具必须在同一个 disposable PostgreSQL 内通过 Section Create、SectionVersion Create、当前 Validate、Trace、SubmitReview 和被分配 Reviewer 的 Review 决策服务建立合成 Approved Section；不得用 SQL 写入批准态、绕过评审 Owner，或复用另一数据库中的批准记录。合成内容只可来自本轮已标记的包内固定测试 Document、Requirement 和 Evidence。此夹具的 Review 结果仅用于本次 PlanVersion 包验，不代表客户确认或产品业务事实。

系统临时根通过 `PLM_P51_TEMP_ROOT` 显式限制到 ASCII D 盘 `PLMToolTemp` 目录。测试启动采用 Python `-B`，避免修改摘要已验证的 stage。

## 影响与风险

- 仅修改 P51 测试 harness；无产品文件、冻结 API、Schema、数据库迁移、安装服务或正式 License 根变化。
- 合成来源只写入本轮可删除的 smoke PostgreSQL 数据库；测试应从业务 Owner 产生 Approved 状态，不能以 SQL 伪造批准。
- 若公钥路径、PG 上下文或正式组件构造不成立，fixture 应失败关闭；不得跳过真实包内 PlanVersion 浏览器/API/SQL 验收。
- 测试数据不得外发；候选继续标记 `release_eligible=false`、`legal_clearance=false`。

## 回滚及验收

- 回滚：还原 P51-A17 验证器及两个 smoke runner 的本决策改动；不触碰候选 ZIP/父候选/正式数据。
- 验收：语法与差异检查；从已核验 stage 启动本机包内 PG18/HTTPS/Edge；确认真实 Packaged PlanVersion Create、固定读取、Validate、原子 SubmitReview、Reviewer 只读及 SQL 审计状态；检查候选摘要、Secret、临时进程和资源清理。
- 当前结果仍待实测，不预先判 PASS。
- 续行结论：包回调上下文与正确 disposable database 已接通，但当前 P51 合成项目没有 SOL Approved Section；Outline Owner fixture 失败关闭。A17 PlanVersion Edge 尚未启动，后续必须先用 SOL/Review Owners 建立 synthetic Source，再重跑。测试临时输出固定在 D 盘。
- 本轮初次启动在进入 A17 callback 前，旧的 Evidence Edge 登录受 disposable PG 的合成登录限流记录影响返回 503。A17 harness 只在 P51 后续复合浏览器链开始前清空本轮临时库中的 login-rate buckets；不修改产品限流策略或非本轮数据库。
- 后续一次包内复验在 PlanVersion callback 前失败：健康端点超时而工厂独立探针返回 `FACTORY_OK`。检查发现底层 HTTPS/平台包验收器通过 `tempfile.gettempdir()` 选择临时根，依赖调用进程全局状态；该隐式行为不能保证 D 盘隔离，也没有在子进程未退出但启动未就绪时保留安全诊断。原因尚未证明与 C 盘空间有关。
- 修正选择：平台包验收器显式要求 `PLM_TEST_TEMP_ROOT`（默认仅为 `D:\PLMToolTemp`），所有 smoke 工作目录从该根创建并在清理范围校验；API stderr 定向到该 D 盘工作目录，只解析异常类型/源码文件名与行号供失败诊断，不输出原始日志/秘密。回滚仅还原此测试工具改动；不触碰候选包、C 盘 Temp、正式数据库或业务代码。
- 在清洁副本上再次运行后，应用健康检查与整个 Handover/Evidence/Capability/Survey 前置链通过，A17 进入 `_approved_section_fixture`。`AUTH_ACCESS_DENIED` 来自 `_actor` 的 Session/CSRF 身份校验；追踪上游 Handover Review harness 后发现其共享 `context["client"]` 已有意切换为无关 observer，而 `context["login"]` 仍是原打包用户登录回执，二者不可配对使用。A17 夹具此前误从 observer cookie 取 token、却配 manager CSRF。
- 后续修正：在一次性数据库内重置仅本次测试登录限流状态，通过包内正式 Login HTTP 接口为 `Synthetic Packaged User` 获取一组一致的 Session Cookie/CSRF，再由真实 Outline/Section Owners 使用；断言登录返回身份等于已登记 manager UUID。Review 决策账户仍独立合成，并继续通过真实 Review 决策 API。该修正不跳过任何授权校验、不改变产品授权规则；若登录/身份不一致则失败关闭。
- 2026-10-26续行定位：`SectionVersionCreateError: SOURCE_UNAVAILABLE` 由 A17 合成固定 Document 文件路径不符合正式存储约定导致。Document 的 `storage_locator` 已是相对数据根的规范 locator（如 `projects/<project>/objects/...`），但夹具误加了 `private-documents/` 前缀，导致 Document Download Owner 在散列校验时无法读取文件；需求批准证明与 Evidence 授权仍由其各自 Owner 执行。
- 决定：仅将 A17 合成文档写入位置改为 `fixture_db.data_root / storage_locator`，以匹配 `LocalFileStorage` 约定；不改生产存储路径、来源证明、授权条件或 API。验证包括路径/摘要检查、包内 PostgreSQL/HTTPS/Edge 全流程、候选摘要不变、Secret 检查与清理。若失败，回滚仅限验证器路径改动，不删除 C 盘 Temp 内容、候选或用户文件。
- 复验修正：仅改写路径后仍由正式 Download Owner 拒绝。检查发现 P51-A05 既有合成 Requirement Document 使用了非规范 locator `projects/<project>/prototype-input.txt`，而 LocalFileStorage 只接受对象存储 locator `projects/<project>/objects/<bucket>/<file-object-uuid>`；A17 的首次 A17 内容写入因此仍无法成为有效固定来源。第二次包内 smoke 的 A17 前置链通过后重现此错误。
- 决定：修正 P51-A05 共用的**验证夹具**，将该合成 FileObject locator 构造成规范对象路径，并将同一份固定合成字节写至 `fixture_db.data_root / locator`；A17 不再自行覆盖该源文件。该 fixture 仍仅为隔离测试输入，不声称验证了 Document 上传/发布流程。A17 Section/Review 仍必须通过真实业务 Owner 建立，不以 SQL 造 Approved 状态；生产 Document/Storage/Download/授权代码不变。回滚为恢复 P51-A05 夹具旧 locator/移除此合成文件写入，不触碰产品数据/候选/用户文件。
- 后续验收已通过固定 Document Download、Requirement 与 Evidence 证明，SectionVersion Create Owner 成功；Section 送审 HTTP 返回 422。只读对照冻结 Router 合同发现请求夹具传了非空 `submission_note`，而此既有 Section API 明确要求 `due_at` 与 `submission_note` 均为 `null`；不是产品端错误。
- 决定：把 A17 synthetic Section submit 请求的 `submission_note` 设为 `null`，与已冻结 Section API 合同一致；不放宽服务端校验，不改 API/API版本或产品代码。后续继续由真实 Section Submit/Review Owners 完成合成批准来源。
- 后续包内 smoke 已通过 `P51_A17_SYNTHETIC_SECTION_OWNER_REVIEW_PASS`，并进入既有完整 Outline 来源夹具；该夹具需要当前项目内 `CUSTOMER_MEMBER` 评审人，但 P51 Handover Project 仅准备了 `Synthetic Handover Customer` 的既有客户成员角色，不存在活动 `CUSTOMER_MEMBER`。Outline Owner fixture 因无匹配 Reviewer 而停止，未创建错误评审或跳过检查。
- 决定：在本轮 Section 已由指定合成客户评审人批准之后，仅在 disposable 项目内用 ProjectMemberPatchService/Repository 将该合成成员变更为 Outline fixture 所需的 `CUSTOMER_MEMBER`，并保留正常 Project 授权、License、同事务 AssignmentHistory 与 Audit；再运行既有 Outline Owner/Review Owner。若角色转换被业务 Owner 拒绝则失败关闭。无 Project API/权限规则/产品代码修改，无直接成员表写入，不代表真实客户成员事实。
- 一次后续重跑在 A17 callback 前退出：Handover 创建 Edge 自身输出 `PKG_PILOT_01_A04_P06_HANDOVER_EDGE_PASS` 且 PostgreSQL/HTTP 结果 PASS，随后 Chromium Profile cleanup 因 Windows `EBUSY` 无法 unlink `lockfile`，外层将 cleanup 错报为 Handover 业务流程失败。未进入 A17、未将其记录为产品失败；后续重试使用新鲜隔离 Profile/安装目录。
- 一次后续重跑完成上游至 A17 Section Owner Review，并开始既有 Outline 完整来源夹具；该夹具假定继承的 Requirement v1 没有来源行，但本次 P51-A05 合成 Requirement 已包含 1 条 `HUMAN_DECISION` 来源，旧夹具的 `count == 0` 断言因此失败。未修改产品或审批事实。
- 决定：将 SOL Outline 验证夹具的兼容整理改为仅当继承版本来源行确实缺失时补入它预期的 Evidence 来源；若恰有一条已登记来源则验证其形态并复用，不重复插入；其他数量/形态失败关闭。该变更仅用于 disposable 测试夹具，不改变正式 Requirement 来源或批准状态。
- 后续重跑通过 `P51_A17_SYNTHETIC_SECTION_OWNER_REVIEW_PASS` 并进入 SOL Outline Owner；Requirement Create Owner 在 `_actor` 返回 `AUTH_ACCESS_DENIED`。调用处再次把 Handover harness 的 observer Cookie 与 manager Login CSRF 拼成一组不匹配凭据；此前 A17 Section fixture 已单独获得正确配对的 manager Session，但未向继承 Outline fixture 传递。
- 决定：由 A17 Section Owner fixture 返回其包内正式 Login 获得且身份与 manager UUID 匹配的 Session/CSRF，并将这组凭据显式传给 Outline Owner；不读共享 `context["client"]` cookie，不绕过 Session 校验，不改产品代码。
- 后续包验已通过 `OUTLINE_QUALIFIED_REQUIREMENT_V2_PASS`；Outline fixture 在选取当前 Approved Section 后，因固定断言要求其必须为 `FIXED_REFS` 而停止。A17 按设计用 Owner 创建的标准合成 Section 声明 `NONE_REQUIRED`；本 WBS 需要 Approved Outline 来源，不包含专项 structured-spec qualification 验收。
- 决定：SOL Outline source fixture 接受合法的 `FIXED_REFS` 或 `NONE_REQUIRED` 当前 Approved Section 作为其 Review 来源，不改变 A17 draft 的 `NONE_REQUIRED` 声明、不生成规格事实；保持其 Requirement/Section/Outline Validate、Review Owner 路径继续执行。本变化仅调整被 A17 复用的验证夹具前置假设，不更改生产逻辑。
- 复验已通过 Outline Version Validate（order/source/coverage 全部 `PASS`），但 A17 后置检查找不到 Approved Outline。追踪确认 `_outline_full` 只创建并 Validate Outline DRAFT，用于覆盖来源/覆盖测试；它从不提交或批准 Outline，故 A17 原先将其误当成 Approved source。
- 决定：在 `_outline_full` 的完整 DRAFT/Validate 检查后，调用其既有 `_approve_current_outline` 测试 helper。该 helper 经真实 Outline SubmitReview Router、OutlineReviewSubjectOwner 和已分配 synthetic Reviewer 的 ProjectReview Owner 建立 Approved pointer；仍禁止 SQL 写入批准态。继续只写本轮 disposable DB，验收断言绑定当前 Project 的 Approved Outline。
- 首次接入时把 `_approve_current_outline` 调到了 SOL source fixture 模块；实际 helper 定义于 Plan Owner 模块，故在 helper 启动前失败，未写入评审状态。接线修正为由 Plan Owner 模块调用，并同时将该模块连接工厂绑定到 smoke disposable PostgreSQL。
- 重新接线后 Outline Owner Validate 正常，Outline Submission Owner 按 `BUSINESS_REVIEW_NOT_ELIGIBLE` 正确拒绝：被复用的完整来源测试在结束前会故意撤销 Section `IMPLEMENTS` TraceLink，以验证 coverage gap。该负向证据状态必须通过真实 Trace Owner 恢复后，才能构造 Approved Outline。
- 决定：调用 Plan Owner 模块已提供的 `_restore_coverage_edge`，通过实际 TraceLink Owner 恢复本轮合成 Section→Requirement 关系，再由 Outline Submission/Review Owners 审批；不直接 SQL 重建 Trace，不隐藏 coverage gap 验收。
- 已完成 Section/Outline Owner Review 与 Approved Outline 建立；PlanVersion Edge 浏览器收到创建成功回执后，验收器误从 `location.pathname` 提取版本 UUID。创建页按设计保留原路由，版本 ID 实际由“查看固定版本”RouterLink 暴露；该失败属于浏览器验收器定位假设，不是创建 API 失败。
- 决定：从成功回执旁的“查看固定版本”链接读取 `href` 路由段作为 PlanVersion UUID，再继续同一固定版本 GET、Validate、SubmitReview 与只读 Review 检查；不改 UI/API 或产品行为。
- 路由 ID 修正后 PlanVersion 固定详情页成功加载，但原 Edge monitor 的 Create/GET HTTP 响应过滤断言仍未命中。后续只为本机 synthetic 浏览器验收输出 `/plans/` 响应 URL 与状态码诊断（不含正文、Cookie、Headers），再按真实观测校正断言；不得降低固定详情页或 Validate 的验收。
- 响应摘要证实 Plan GET 200、PlanVersion Create 201，但没有 PlanVersion Detail GET。旧等待条件只匹配详情页的静态标题，不能证明数据加载成功；目前固定读取仍未验。
- 决定：Edge 夹具必须等待页面呈现本次创建的具体 PlanVersion UUID 后才能把 Detail GET 计为成功；响应 URL 与状态码需匹配该 version id。超时应报告安全化页面文字/观察到的 URL 状态，不能因静态标题继续。
- 最新复验已贯通 Section/Outline Owner Review、Outline Validate 与 PlanVersion Create 201；固定版本路由已打开，但详情 UUID 未呈现，页面报告读取失败，Network.responseReceived 未观察到 Detail 响应。尚不能区分请求未发出、浏览器网络失败或服务端拒绝。
- 决定：仅扩展本机 synthetic Edge 验收器，记录与本轮 PlanVersion URL 匹配的 Network.requestWillBeSent、responseReceived 和 loadingFailed 安全摘要，并保留现有精确 UUID/200 验收；不记录请求头、正文、Cookie、凭据或完整日志。若已发请求，则据状态/失败原因定位；否则检查路由 Session 授权前置。随后仍需完整包内 Edge/HTTPS/PG 验收，候选标志不变。
- 第二次完整 A17 复验确认：详情路由已打开且 Session 有权，UI `load()` 返回“暂时无法读取”；无 Detail requestWillBeSent、无 response、无 network failure。只读代码发现 PlanVersionReadClient 以 `this.fetcher(...)` 调用原生 Window.fetch，而 SessionClient 明确避免同一接收者调用；浏览器原生 fetch 会因非法 receiver 在网络发送前抛错，被客户端映射成通用 unavailable。属于生产前端读取器缺陷，影响 Detail GET 与列表 GET。
- 决定：按持续授权登记本项产品缺陷修正（CR-P51-A17-READ-FETCHER）：像 SessionClient 一样先取本地 fetcher 再以无 receiver 形式调用；补一项 receiver-free 单测，跑读取客户端/视图定向测试及前端全量 typecheck/build。随后重新构建源提交绑定的新候选并完整包内 Edge/HTTPS/PG 验收；保留旧候选及其摘要。无 API/Schema/数据库变化，风险仅为 fetch 调用上下文，回滚恢复原调用并保留候选历史。
- 修复后新候选实际观察到 PlanVersion Create 201、Detail GET 200（两次）且页面成功呈现 WBS 固定快照，确认产品读取修复生效。验收器随后在等待创建回执时超时：现行 Create View 创建成功后按设计自动导航到固定 Detail 路由，脚本继续假设停留在创建页面。
- 决定：仅调整 A17 Edge 验收器，点击确认 Create 后等待当前计划下的固定版本路由，提取且校验 URL 中具体 UUID，再等待该 UUID 的 Detail 内容；之后仍检查 Create 201/匹配 Detail 200。保留旧候选历史；不修改产品路由、API、权限或业务行为。
- 初次路由条件只检查 `/versions/` 前缀，和创建页 `/versions/new` 重叠，故立即读到字面段 `new` 并被 UUID 断言拒绝；没有因此把错误页面计作通过。
- 决定：收紧为匹配 `/versions/<36字符UUID>` 的完整详情路径后再提取 ID；保留创建后页面正文 UUID 与 HTTP 201/200 双证据。
