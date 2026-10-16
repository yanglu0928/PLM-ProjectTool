# SUR-01-A06-A05-P02：Windows 11 Survey 来源定位浏览器闭环

日期：2026-10-06。结论：`SUR_01_A06_A05_P02_WINDOWS_BROWSER_PASS`。下一项：`SUR-02-A01` Round 运行时与冻结基线前置核查。

## 实现与偏差

- 隔离夹具使用 Windows 11 本机 Microsoft Edge、构建后的 Vue、Windows 生产 FastAPI 组合和 PostgreSQL 18.6，创建四类合成来源、PROJECT Template、Handover Evidence 与一次性项目经理凭据。
- 真实页面首次复验发现 Version 列表返回的是声明计数加空问题数组的摘要，而前端沿用了详情完整数组校验。读取客户端现只在列表路径接受“两数组同时为空”的摘要，详情仍要求声明计数与完整数组精确一致。
- 真实 Edge 发现来源定位和既有 Evidence Viewer 把原生 `fetch` 绑定到客户端实例，浏览器在发请求前拒绝。两个客户端均改为无接收者调用，并增加接收者回归测试；其他模块未顺手改动。
- 验收夹具改用 LocalFileStorage 的规范对象 locator，并以整文档 Evidence 验证 Viewer；登录审计是认证边界预期写入，来源定位的只读断言限定为 Survey/Version 零写入。
- 托管 computer-use 内核因本机缺少 kernel assets 无法启动，按同一 Windows 11/Edge 范围使用仓库既有 CDP 验收工具。该偏差不改变产品代码、目标浏览器或事实数据库。

## 验证

- 真实 Edge 依次展开 Handover、Capability、PROJECT Template 和 MANUAL：4 个 location 请求均为 200；Handover Evidence Viewer 另有 1 个 200。
- 页面显示公共 Handover 入口、权限受限的 GLOBAL 提示、固定文档历史/原文入口和人工维护提示；无告警、无内部 row identity，Document/Evidence 原文链接均通过受权路径。
- 服务端在浏览器 PASS 后确认 Survey/Version 零写入，并清理临时数据库、凭据、浏览器 profile 与文件。三张本地截图完成视觉复核；`artifacts/` 按仓库规则不提交。
- 前端全量 82 文件 1441 项、TypeScript、Vite 172 模块生产构建通过。主 JS 636.50 kB、gzip 159.26 kB，既有大分块提示继续登记。

## 兼容、回滚与剩余项

无 Schema/Migration、冻结 API、角色、依赖、Secret、外发或客户数据变化。摘要解析仍失败关闭混合/不完整载荷；删除两项兼容修正可回滚代码，但会恢复已由真实 Edge 证明的故障。Survey 定义写 UI、Round/Response/Conclusion、Gate 3、UAT 和可使用发行包仍未完成。
