# AI-05-A04 AI 任务详情与运行历史

日期：2026-10-03；状态：`AI_TASK_DETAIL_PASS`；依据冻结 API-03、DEC-770/778～780与A02严格客户端。下一项：`AI-05-A05` 建议卡片、原文定位与人工维护提示。

## 范围与实现

新增`/projects/:projectId/ai/:taskId`只读详情页。首读并行请求Task详情与Invocation第一页，只有两者均按当前服务器授权成功才显示；任一失败、后续分页重复或后续授权失效都清空Task和全部历史。路由Project/Task变化后丢弃迟到响应。列表页的AI任务号改为详情链接。

页面显示Task状态、Suggestion状态、输出/上下文策略、固定输入版本和Invocation实际模型/Prompt/Schema/Context/validation/usage/latency/安全错误，不显示请求/响应正文、Secret、Provider request ref或fingerprint。DOC-02输入链接到既有Document详情。取消、重试及当前Job状态只通过Task固定`job_id`链接到已有受控Job详情页；没有Job引用时明确关闭入口，不在AI页面复制写服务。

## 验收、兼容与回滚

定向详情/列表10项通过；前端全量64文件/1233项通过；typecheck通过；Vite生产构建138模块成功。产物SHA-256：HTML `6aaa5fc7b4a67f4e777e623101691bc3073dd6e142696491908f1a9493e39493`、JS `a8174fca5aade1ac1c17f0ce10918386a5b015ba2e991a2b5e2f9903e0142ceb`、CSS `68639d930047223a91fa461459ff26e4f73056fad97cdd636ae54bc5a7c94773`。无后端/API/Migration/依赖/外发变化，未重复运行后端测试。回滚删除详情页/路由并恢复列表纯文本任务号即可；Job实现和历史不变。Suggestion正文、原文定位、人工维护字段、提交/外发授权、Accept/Reject与真实浏览器仍待后续。
