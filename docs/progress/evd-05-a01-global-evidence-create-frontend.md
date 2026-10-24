# EVD-05-A01：GLOBAL 标准能力整文档 Evidence 候选创建入口

日期：2026-10-24；状态：`SOURCE_PASS / WINDOWS_EDGE_PG_PENDING`。

|检查项|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `EVD-05-A01`，只解决部署管理员无法从 GLOBAL 标准能力固定文档建立 Evidence 候选的问题。|
|输入基线|冻结 `/api/v1/global/evidence` POST；已完成 GLOBAL Document 读/上传、Evidence 列表与人工资格页面；`CAP-02-A05-P01` 已确认版本创建要求同源 `ELIGIBLE` Evidence。|
|前置任务|Windows 显式写模式已装配 Evidence Create，服务端从固定文档经 Document Port 重核内容指纹；浏览器仅需提供 `locator_type=DOCUMENT`、固定 Document/VersionId 与标签。|
|模块/实体/API|Evidence 候选身份与同号创建收据；仅前端 Evidence 客户端/页面、Auth 私有 CSRF 桥与路由，不改 Document/Capability 产品代码、Schema 或冻结 API。|
|权限|只允许可提交的 DeploymentAdmin Session，匿名/普通成员在客户端关闭；服务端仍复核 Session/CSRF/License、GLOBAL 来源与文件内容。|
|验收标准|从 GLOBAL ACTIVE `STANDARD_CAPABILITY` 文档选 `AVAILABLE` 固定版本，严格 201/ETag/Location/no-store 及 `CANDIDATE` 回执；未知结果保留原输入/幂等号，登录变化清屏；不能自动标 ELIGIBLE、伪造精确页段定位或外发正文。|
|风险|整文档证据不表示精确页段定位；资格决定仍需独立人工操作。真实 Edge/PG、错误来源/License/权限负例及正式信任未由源码测试代替。|

实现：新增严格 GLOBAL Evidence Create 客户端与独立管理员页面，只提供整文档 Locator；从 DocumentReadClient 分页选择固定版本，创建成功展示 `CANDIDATE` 并引导到现有资格页面。原操作号保存在浏览器 SessionStorage，结果不明须核对后同号重试；未知/存储损坏不静默换号。SessionClient 保管 CSRF，不暴露给页面或 Evidence 客户端。没有自动资格批准、AI 调用或客户数据外发。

首轮定向测试发现新客户端 UUID 正则缺少第四段，合法 DocumentId 被前端误拒，5/8 失败；修复后定向 8/8、前端全量 170 文件 1912/1912、typecheck 和 Vite build 通过。错误记录保留，不把首轮当 PASS。本片无新 Migration/API/License 依赖；真实 Windows 11 Edge/隔离 PG 正向与拒绝矩阵留 `EVD-05-A02`，完成后继续 CapabilityVersion 用户入口。Pilot/Gate 仍 `NOT_READY`。
