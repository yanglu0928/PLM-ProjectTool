# SOL-01-A16-P06-P03：Reference Eligibility 双 Scope Win11 Edge/PG 验收

日期：2026-10-09。结果：`SOL_01_A16_P06_P03_REFERENCE_ELIGIBILITY_EDGE_PG_PASS`，仅 Windows 11 合成用户/信任源与一次性 PostgreSQL 18.6。

## 编码前检查

- 当前 Phase/WBS：Phase 2 / SOL-01-A16-P06-P03。输入：冻结 API-04/DM-05、CR-SOL-014、A16-P03～P05 内部/HTTP/Windows 验证、P06-P01/P02 前端；前置满足。
- 单一问题：验证真实 Edge 中双 Scope 资格人工决定界面到 ASGI/Session/PG 的链路；本任务只增加/扩展一次性验证夹具，不修改产品 DB、ORM、Migration、API、权限或前端。
- 涉及实体/API/权限：Reference 根及不可变资格事件、`/api/v1/...:set-eligibility`；PROJECT Manager 与 GLOBAL DeploymentAdmin。验收要求为二次确认前零写、两次决定各一次、当前详情重新 GET、事件/Audit SQL 与权限显示边界。
- 风险：脚本扮演合成操作者，仅证明交互与服务器复验，不能当作客户真人对方案来源的业务认可或正式 License/HTTPS/目标账户证明。

## Changed / Files / Migration / API

- 在既有 PROJECT 修订浏览器服务夹具添加可选资格路由/脚本参数，默认原修订验收路径不变；新 PROJECT Edge 脚本以真实登录、当前详情、理由、二次确认执行 ELIGIBLE→RESTRICTED，并检查 POST 锁/Body、客户角色无写表单。
- 在既有 GLOBAL 脱敏浏览器服务夹具添加可选资格路由；GLOBAL 文档-only 脚本仅在显式 `eligibility` 模式追加当前详情、重新登录后两次资格决定，保留旧默认路径。新包装脚本 SQL 后验根 RESTRICTED/v3、两事件两审计。
- 文件：`validation/sol-01-a12-p03-project-reference-revise-browser/serve.py`、`validation/sol-01-a04-p08-p04-p03-global-attestation-browser/serve.py`、`validation/sol-01-a15-p02-global-document-only-browser/run-edge-browser.mjs`、新增 `validation/sol-01-a16-p06-p03-reference-eligibility-browser/{verify_project.py,verify_global.py,run-project-edge.mjs}`，以及本进度、状态、CR、版本说明。
- Migration/API：无变化；目标库需既有 `0153`。

## Tests / Result

- PROJECT 新脚本退出 0：Win11 Edge/真实会话/隔离 PG，两次确认得到 ELIGIBLE/v1、RESTRICTED/v2；确认前零 POST、页面现时重读、客户角色无写入口；SQL 当前根 RESTRICTED/v2、两资格事件、两 Audit。
- GLOBAL 首轮失败：整页跳转后 SPA 内存身份未恢复，详情提示先登录，未出现资格表单。仅测试导航前置，未观察到资格 POST。显式重新登录后独立新临时库重跑退出 0：文档-only 来源创建/修订后两次资格决定、当前根 RESTRICTED/v3、两事件、两 Audit。
- 两个受修改的旧浏览器脚本（PROJECT 修订、GLOBAL 文档-only）各自独立新临时库回归退出 0。Node 语法检查、Python 编译检查通过；未改产品代码，因此未把旧全量前/后端测试冒充本次运行结果。
- 夹具创建的数据库、文件、API 线程、Edge 进程与 profile 在退出时清理；不上传合成凭据或输出日志。

## Known Issues / Next

结果只证明 Win11 合成交互链；用户真人对实际参考材料的资格判断、正式 License 公钥/账户/HTTPS、Server 2025 当前版本、20 并发、Gate 3/UAT/发行仍待。Debian 13 实机按用户指令跳过。下一项做 Gate 3 剩余差距重新盘点，按阻塞与独立任务顺序继续实施；不能仅凭本浏览器 PASS 宣告可用程序包。

TraceLink：Gate2 API-04/DM-05 → CR-SOL-014 → A16-P01～P05 → P06-P01/P02 → 本 P03 → Gate3。
