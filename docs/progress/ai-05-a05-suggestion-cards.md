# AI-05-A05 AI 建议卡片、原文定位与人工维护提示

日期：2026-10-03；状态：`AI_SUGGESTION_CARDS_PASS`；依据冻结 API-03、DEC-770/778～780 与 CR-AI-020。下一项：`AI-05-A06` AI Task 提交与逐次外发授权。

## 范围与实现

新增 `/projects/:projectId/ai/:taskId/suggestion` 只读建议详情页，并从 AI Task 详情按服务器返回的 `suggestion_state` 进入。页面逐条展示类别、标题、分析摘要、判断依据、建议和质量标记，始终固定提示“AI建议，不是正式业务事实”，不提供接受、拒绝或写入正式版本的按钮。

来源只消费 `AIReadClient` 白名单重建的 `source_locations`：V2 按本次 citation 的 node id 显示服务端生成的位置标签，V1 明确显示整个文档版本；原文动作只打开同源、固定 DocumentVersion 的受权 content URL，不复制客户正文，不接收模型 URL/locator，也不在浏览器中自行搜索。V2 待确认项逐字段显示“维护什么、填写提示、原因、必填/选填”，但本页不包含表单，不把空缺内容伪装成已确认事实。

身份未读取、强制改密、无权/不存在、错误响应和路由迟到响应均失败关闭；服务器错误正文及未知字段不进入页面。

## 验收、兼容与回滚

建议详情/Task详情定向 10 项通过；前端全量 65 文件/1238 项通过；typecheck 通过；Vite 生产构建 141 模块成功。产物 SHA-256：HTML `e9f59398a436ac74dac2f1bcdca599b4d124f108e9110fe06757d08d65fc60f7`、JS `914b871234c6792670bcf102a31894979d1fef77567ebb4a95fd5e19e7858cc7`、CSS `db65985b4714d88dc1d693078d755f4264555e2bfe4450a69cf2eba93844ebca`。

无后端、冻结 API、Migration、依赖或外发变化，未重复运行后端测试。回滚删除建议页/路由和 Task 详情入口即可；历史 Suggestion/Evidence/DocumentVersion 不变。提交、逐次外发授权、Accept/Reject、真实浏览器、Gate 3、UAT 与发行包仍待后续。
