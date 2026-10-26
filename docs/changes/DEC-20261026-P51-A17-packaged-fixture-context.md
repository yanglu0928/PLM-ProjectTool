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
