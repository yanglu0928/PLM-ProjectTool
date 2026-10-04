# AI-05-A07 Windows 11 AI 工作台完整浏览器验收

日期：2026-10-04；状态：`AI_WORKBENCH_WINDOWS_BROWSER_PASS`；依据冻结 API-03、CR-AI-021/022、DEC-782～786。下一项：`RAG-01-A01` RAG 冻结模型、Schema、API 与现有实现差距的编码前核查。

## 范围与环境

- Windows 11 x86-64 build 26200、Microsoft Edge 154.0.4258.53、PostgreSQL 18.6；实际 Vite 构建资产经同源代理访问生产 FastAPI。
- 一次性合成账户、项目、文档版本、ParseResult、Provider/Model/Prompt/策略和 Windows Vault 凭据；Provider 地址为不可解析的 `.invalid` 域。
- 复用 P04 三步提交后继续验证 Task详情、空 Invocation 历史、既有 Job 详情、浏览器返回以及工作台列表回显；不启动 Worker，不调用模型厂商。

## 发现与修正

第一轮扩展脚本在浏览器内模板正则转义失败，数据库仍按 P04 终检并完整清理；只修验证脚本后使用全新隔离库重跑。第二轮真实页面在 Job GET 返回 503，定位到内部 Owner 投影把合法 `Task=QUEUED / Job=PENDING` 错当不一致。依持续授权先登记 CR-AI-022，再以显式封闭状态对修正并补仓储回归，未改变公开合同或数据状态机。

最终链路通过：

1. 登录、进入项目/AI工作台，按 Preview、明确授权、Task Create 三个独立动作创建任务。
2. Task详情返回 `QUEUED`、`NONE`、固定 DocumentVersion 和“当前任务尚无可见调用记录”；无告警。
3. 既有 Job详情返回 `AI_TASK_EXECUTE`、Owner `ai`、`PENDING`、0次尝试和不可人工重试；无告警。
4. 浏览器后退到 Task，再返回工作台；同一 Task/Job 显示“等待执行”“暂无建议”。
5. 浏览器网络实际观察 Task GET、Invocation LIST、Job GET、Task LIST 四类响应均为 200；数据库终检为1 Preview、1 Authorization、1 Task、1 Job、0 Invocation。

四张最终截图完成视觉检查，未见遮挡、截断、错误状态或正文/Secret泄露。临时 Edge profile、前后端、数据库、角色、Vault和文件根全部清理。验证标记：`AI_05_A07_WINDOWS_WORKBENCH_PASS`。

## 回归、兼容与边界

- 新增仓储回归3项，相关9项通过；后端全量2349项通过、3项既有条件跳过。
- 开发 wheel 823 项，SHA-256 `b0c2325b1a3b67806ee9da1956ce7761fc8937363bb08b5a3785de2728953af7`。
- P04 前端全量1250项、typecheck及145模块构建证据仍适用于同一前端资产；本项未修改产品前端。
- 无 API、Schema、Migration、依赖、权限或外发策略变化。Accept/Reject仍需真实 Draft Owner/Review 锁；本项不证明真实 Provider 质量、Server 2025、Debian 13、Gate 3、UAT或正式发行包。
