# AI-03-A03：PromptTemplate DRAFT 身份内部创建

版本：0.1.0；日期：2026-10-02；结果：Windows 11 / 隔离 PostgreSQL 18 内部命令 PASS，公开 API 与 PromptVersion 仍关闭。

依据：Gate 2 冻结 DM AI-03、API-03 两个独立操作、Schema 0059 与 DEC-676。原 A02 的下一任务措辞将模板与首版合并；此处按冻结合同拆开，不改正式基线。

Changed：新增受控 TaskType/PromptTemplate 身份、内部创建服务和 AI 自有 Repository。仅持久化 DEPLOYMENT/DRAFT 根，`active_version_no=NULL`、`lock_version=0`；不接收/保存 Prompt 正文，不产生可调用版本。当前 DeploymentAdmin/CSRF 双检查、License Guard、同事务幂等收据和 Audit；同键重放返回创建时 DRAFT/v0 快照，不误投影后续退役状态。

Files：`apps/backend/src/plm_assistant/modules/ai/domain/prompt_identity.py`、`application/create_prompt_template.py`、`infrastructure/prompt_create_repository.py`、单元测试、`validation/ai-03-a03-prompt-create/verify.py`、本记录、决策日志及状态。

Migration：无，复用 0059。API：无新增/挂载。兼容性：Windows 11 隔离 PG18 合成验证；正式目标账户、Server 2025 和 Debian 13 未验。升级/回滚：未装配命令时可停止；已存在的 DRAFT、Audit、幂等历史不物理删除，修正走后续受控状态。

Tests：单元 3 项通过；隔离 PG18 当前管理员/CSRF/License 拒绝、DRAFT 无版本、收据/Audit、同 Key 冲突与双并发、退役后首次视图重放、Audit 故障回滚、撤权后拒绝均通过。后端全量 2055 项通过、3 项跳过；开发 wheel 构建通过，SHA-256 `8e9d3a880e9edcb2397ce021f9a9f4e76afc1e97cb838cffbcd1155558b88294`（包不提交）。

Known Issues：`AI_PROMPT_CREATE` HTTP 未实现；PromptVersion 正文和安全校验留给 A04；本任务没有证明 PromptRegistry/AIService 可调用。AI-01 真实 Worker、AI-02 质量/AVAILABLE、Gate 3/UAT/可用包仍待。Next：`AI-03-A04` 不可变 PromptVersion 创建内部命令，先固定正文规范化、敏感内容审查与策略引用验证。
