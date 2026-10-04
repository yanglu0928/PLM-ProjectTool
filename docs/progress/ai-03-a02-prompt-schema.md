# AI-03-A02：Prompt 基础 Schema

版本：0.1.0；日期：2026-10-02；状态：隔离 Schema 验证 PASS，管理服务/API/正式环境未实施。

Changed：新增 AI 自有 PromptTemplate/PromptVersion ORM 与 Migration 0059，注册 Alembic 元数据，版本历史触发器和跨模板活动指针约束；无厂商调用、客户数据或运行路由。依据 DEC-674/675，原 Gate 2 冻结提交不变。

Files：`apps/backend/src/plm_assistant/modules/ai/infrastructure/prompt_orm.py`、`apps/backend/src/plm_assistant/migrations/versions/20261002_0059_ai_prompt_schema.py`、迁移环境与元数据/迁移合同测试、`validation/ai-03-a02-prompt-schema/verify.py`、本记录及 Schema 增量说明。

Migration：0058→0059；空库 up/down/re-up、已有 Auth 数据升级、ORM drift=0、跨模板/悬空活动指针与非法形态拒绝、版本 UPDATE/DELETE/TRUNCATE 拒绝、非空降级拒绝在 Win11 隔离 PostgreSQL 18 实测 PASS。后端全量 2052 测试通过、3 项跳过；开发 wheel 构建通过，SHA-256 `979b2937f7748efb6c1f9be48e43ec76128073b9d53219f66380611f6fc5c7ce`（构建产物不提交）。正式生产迁移未执行；非空历史仅向前修复。

API：无新增或挂载；冻结 AI_PROMPT_* 仍未实现。权限：此项无可调用入口，后续命令必须校验 DeploymentAdmin/CSRF/License/Audit。兼容性：Windows 11 隔离数据库验证；Windows Server 2025、Debian 13 和目标账户未验。

Known Issues：数据库不负责识别恶意/敏感 Prompt 或验证正文哈希，一切写入必须在后续受控服务中校验；AI-01 真实 Worker、AI-02 AVAILABLE/质量证明、Gate 3/UAT/可用包仍待。Next：`AI-03-A03` Prompt 创建内部命令与首版不可变写入。
