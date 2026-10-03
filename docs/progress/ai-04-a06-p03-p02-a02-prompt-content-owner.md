# AI-04-A06-P03-P02-A02 Prompt/参数内容 Owner 与严格渲染

日期：2026-10-03；状态：`PASS`；依据 CR-AI-015/016、DEC-726/727。无 Schema、公开 API、Provider 调用或客户数据外发。

## 实现

- 新增短生命周期 `AIExecutionPromptTaskContent`：固定 Task/Project/Job/原请求人/Trace、Prompt policy/template/version、正文/hash、Provider/Schema/Context policy 和最小标量参数/fingerprint；Prompt、参数与摘要均不进入 repr。
- 内容对象复用 PromptVersion 的 NFC/LF/UTF-8/Secret/控制字符准入规则，重新计算 system/user SHA-256；参数只接受最多16个受控 `STRING / INTEGER / BOOLEAN` 标量，复制后以只读 Mapping 暴露。
- 新增 `AIExecutionPromptTaskContentOwner` 与 PostgreSQL Repository：在 caller-owned 短事务内锁定精确 `QUEUED` Task，要求当前活动 Prompt 仍为 Grant 版本，并由 PostgreSQL 重新验证 `jsonb::text` 参数摘要；任何 Task/Prompt/参数漂移返回统一不可用。
- 新增 `strict-placeholders.v1` 渲染器：仅识别字面量 `{input}`、`{context}`、`{parameters}`，不支持表达式、属性访问、条件或转义执行；Input 必须恰好一次，RAG Context 与非空参数必须恰好一次，未知/缺失/重复/游离大括号失败关闭。
- 动态输入、Context 和字符串参数统一 NFC、LF 和 UTF-8；替换只扫描模板一次，插入正文内的 `{context}` 等字面量不会被二次展开。结果字节和 fingerprint 不进入 repr。

## 验证

- 定向 16 项（Prompt/参数6、Content Plan6、Execution Grant4）PASS。
- Windows 11 / PostgreSQL 18.6 真实隔离库：签发完整 Grant 后投影精确活动 Prompt/参数并渲染；参数 fingerprint 漂移、活动 Prompt 漂移拒绝；repr 无正文/参数，Invocation 数为0，无 Provider 调用。标记：`AI_04_A06_P03_P02_A02_PROMPT_CONTENT_PG_PASS`。
- 后端全量：`Ran 2179 tests in 38.174s`，`OK (skipped=3)`。
- 开发 wheel SHA-256：`c11a990c885c0c76ec93c83038da4ab62887ebffc1839a4f0b26c898518450b0`。

## 开发期偏差与兼容

首轮单测 5/6 通过；唯一失败是负例夹具修改模板却未同步其不可变 hash，因此被内容准入提前正确拒绝。夹具改为同时更新 Content 与 Plan 的测试 hash，随后覆盖未知/缺失/重复占位符并完整重跑通过。未发生程序逻辑回退或外发。

本项新增未装配 Application/Infrastructure 组件和验证脚本；复用现有 0071 Schema，无 Migration、依赖、公开 API、Worker 或生产组合变化。撤去组件即可回滚，Task/Prompt 历史不变。严格渲染策略会使不符合占位符合同的旧 Prompt 不可执行；不猜测修补，需后续以新 PromptVersion 正式准入。

下一任务：`AI-04-A06-P03-P02-A03`，实现 Document 精确 ParseRecord/ParseResult 内容 Owner 与真实文件/PG 校验。
