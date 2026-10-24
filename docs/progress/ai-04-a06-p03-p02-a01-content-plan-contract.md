# AI-04-A06-P03-P02-A01 无正文 Content Plan 与 Owner Port 合同

日期：2026-10-03；状态：`PASS`；依据 CR-AI-015/016、DEC-726。无数据库、公开 API、Provider 调用或客户数据外发。

## 目标与实现

新增内部 `AIExecutionContentPlan` 合同，把 Preview、Task 和 Invocation 后续需要共同绑定的执行身份收敛为一个不含正文的不可变对象：

- 按序业务 InputRef 与精确 Owner 内容身份分离；内容身份保存 revision/object UUID、producer/profile version、schema/policy、源/正文摘要、大小和记录数，不保存正文或 storage locator。
- Prompt 身份固定 policy/version、template/version、system/user hash、Provider/Output Schema 和严格 rendering policy/version。
- Context 只允许 `NONE` 或完整 `RAG_CONTEXT` 两种闭合形态；RAG 必须同时提供 RetrievalRun、ContextBundle、fingerprint 和非零边界，不能用半空对象表示降级。
- Plan 固定 Provider/config/Model/revision/region、数据类别、最小载荷策略、Envelope 编码和 Token estimator 的版本身份。
- `content_plan_fingerprint()` 对所有上述字段做规范化 SHA-256；Parse revision、结果 hash、顺序、Prompt/Context/编码/估算版本任一变化都会改变摘要。
- `require_content_plan_for_grant()` 逐项核对现有 Execution Grant 的 Project、Purpose、Task、业务 Input、Prompt、参数、Context policy、路由、类别和最小化策略；不匹配统一失败关闭。
- `AIExecutionContentIdentityOwnerPort` 定义资源 Owner 在 caller-owned transaction 内解析精确内容身份的最小 Port；查询只携带 Plan/Project/原请求人/Trace/Purpose/策略，不携带正文、Session、Key 或 locator。

## 验证

- 定向 10 项：Content Plan 6 项 + 既有 Execution Grant 4 项，全部 PASS。
- 后端全量：`Ran 2173 tests in 38.941s`，`OK (skipped=3)`。
- 开发 wheel：`plm_project_tool_backend-0.1.0.dev0-py3-none-any.whl`，SHA-256 `1ccf1411c3eee3ebc438f8108213b6ecdab3a358cd81f199907d685cd48acf0c`。
- 合同对象 repr 隐藏所有 digest；字段检查确认没有 `content`、Prompt 文本、参数值或 storage locator。

## 开发期偏差

首次定向执行在模块导入时发现新 Prompt identity 校验条件少一个闭合括号；修复后重跑。第二次执行发现测试使用的 parser version `1.0.0` 被通用 Ref 规则误拒绝，调整为独立的数字开头版本规则。第三次执行发现项目漂移样例已经在 Plan 构造时正确失败，测试却在 `assertRaises` 外构造；移动断言边界后重跑。三项均为新合同/夹具问题，未触及既有生产行为，最终定向、全量和 wheel 均从修正状态重新执行。

## 兼容与遗留

本项只新增未装配 Application 合同和单元测试；无 ORM/Migration、依赖、公开 API、Job/Worker 或运行组合变化，撤除新模块即可回滚。Plan 尚未持久化，也没有读取正文；旧 Preview/Authorization/Task 继续不可执行。

下一任务：`AI-04-A06-P03-P02-A02`，实现 Prompt/Task 参数的短生命周期内容 Owner 和严格模板渲染，不接 Provider 网络。
