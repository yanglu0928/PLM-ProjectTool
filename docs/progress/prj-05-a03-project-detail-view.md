# PRJ-05-A03 项目详情只读页面

2026-09-28 / 0.1.0.dev0 / PASS（前端组件合同；真实浏览器/PG 待后续任务）。

编码前检查：Phase 2 / WBS PRJ-05-A03；输入 Gate 2 冻结 `PROJECT_GET`、PRJ-05-A01 安全只读客户端、PRJ-05-A02 列表路由及原 Windows 显式平台读组合。前置满足，改密浏览器最终提交与此只读任务独立。仅涉及前端 Project 详情页/路由/列表导航；无实体、Migration、服务端 API、权限、依赖变更。验收：直接 URL 与列表导航均需服务器当前 Session/License/成员授权 GET；无内存身份或受限改密不读取；非法路径 ID 请求前拒绝；404 对无权/不存在统一，401/403 固定提示；服务器返回详情 ID/强 ETag 不一致不展示；路由参数切换先清旧内容且晚到响应不能覆盖新状态；前端测试/typecheck/build PASS。风险是把列表当授权或展示旧项目；回滚撤详情路由/页面/链接即可。

L2 决定：列表链接只传规范项目 ID，不传项目正文或授权状态。详情页不读取 Auth `authorized_projects` 形成内容或客户端权限，只在现有非受限内存身份下调用独立 `ProjectReadClient.get`；客户端核对请求 ID 与响应 ETag，页面按路由代次丢弃晚到结果。无 CR、不改冻结合同。

Changed：新增 `/projects/:projectId` 只读详情页，显示服务端名称/编号/状态/创建时间，返回项目列表；项目列表名称链接该页面。错误清除旧详情、固定安全中文提示，无创建、编辑或权限提升。

Tests：新增 8 项页面合同，前端总计 139/139、typecheck、build PASS。覆盖无身份/受限零请求、直接 URL、文本转义、401/403/404、非法 ID、跨项目路由切换旧内容清除、响应 ID 不符。客户端 ETag 校验已有 A01 单测；本项未跑真实浏览器/PG、后端全量、coverage、性能。无 Migration/API/权限/依赖变化。下一 PRJ-05-A04：Windows 11 真实浏览器与隔离 PostgreSQL 项目列表/详情联调、空授权与跨项目拒绝；正式信任/HTTPS、Server2025/Debian、CR-AUT-008 性能 FAIL、Gate3/可用包仍待。
