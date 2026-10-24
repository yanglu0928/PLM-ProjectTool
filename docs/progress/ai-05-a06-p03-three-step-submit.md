# AI-05-A06-P03 三步 AI Task 提交页面

日期：2026-10-03；状态：`AI_THREE_STEP_SUBMIT_UI_PASS`；依据冻结 API-03、CR-AI-021、DEC-782/783 与P01/P02。下一项：`AI-05-A06-P04` Windows 11真实PG/浏览器三步验收。

新增 `/projects/:projectId/ai/new` 与工作台入口。页面只从服务器选项选择Task/Egress/Provider/Model，并从当前项目文档元数据锁定 effective/latest DocumentVersion；显示标题、文件名和固定版本ID，不读取或复制正文。动态参数控件完全来自受控Task Policy字段约束。

交互严格分为三次明确动作：生成Preview（不外发）→核对region、来源、大小/Token/重试上限、风险和到期时间并勾选明确授权→创建Task进入队列。任何一步不会自动触发下一步；不确定结果显示并保留该步操作号，提示先核对事实而非换号重试。ProjectManager可完成整链；ImplementationMember可按冻结权限生成Preview，但页面明确提示不能自行批准，当前首版不提供跨账户接力页。授权后、建Task前可撤销，并提示撤销不能收回已发送数据。

页面/工作台定向10项通过；前端全量67文件/1249项、typecheck及Vite 145模块构建通过。产物SHA-256：HTML `1a9c6b57688d9dcac676ca6faf2d8b225e65407da62a1d0feb8284608c660ef9`、JS `217ede756bbd004b6503c71640c0231e355c348fb105604505c07b7480638dec`、CSS `b4aa05c9062e66efffb9a02d95c185d6861977aa595c6573ad56727b5f1b9917`。无后端/API/Schema/Migration/依赖或真实外发变化；删除页面、路由和入口可回滚。
