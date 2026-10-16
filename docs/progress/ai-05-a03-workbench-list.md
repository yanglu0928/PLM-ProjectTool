# AI-05-A03 AI 任务与建议状态工作台

日期：2026-10-03；状态：`AI_WORKBENCH_LIST_PASS`；依据冻结 API-03、DEC-770/778/779与AI-05-A02严格客户端。下一项：`AI-05-A04` AI任务详情、Invocation运行历史与既有Job状态编排。

## 范围与实现

本项只新增项目级`/projects/:projectId/ai`只读入口、任务状态列表及项目详情导航。页面只使用A02白名单DTO，按当前路由Project分页读取Task；跨页ID重复、后续授权失败、路由切换后的迟到响应均清空或丢弃旧数据。展示任务类型/状态、建议状态、输出合同、ETag、安全错误和既有Job详情链接，不展示Prompt/输入正文、Provider响应、Secret或fingerprint。

页面始终醒目标注“AI输出不是正式业务事实”和“建议需人工确认”；没有表单，也不提供接受、拒绝、取消或重试操作。Session内角色只作界面状态提示，服务器仍逐次执行Session/License/Project授权。未登录和强制改密账户不发起业务请求。

## 验收、兼容与回滚

定向工作台与项目详情23项通过；前端全量63个文件/1228项通过；typecheck通过；Vite生产构建135模块成功。构建产物SHA-256：HTML `f4abbd0be23d7cb934d65ff3d6b18cff9b011e02a76d9a9f6ec1d6a97fd001fb`、JS `43aed6a957b62bd223613e96af2bc0768420111411f910a78374723a619aada7`、CSS `fca6b3609079330fa99ca9df530c4819e8acbbc3fbe8e65222be4af582513669`。无后端、API、Migration、依赖或外发变化；未重复运行后端测试。回滚删除页面/路由/项目入口即可，A02客户端与后端历史不变。详情、Invocation、定位原文、人工字段维护、提交/外发授权和Accept/Reject仍由后续WBS完成。
