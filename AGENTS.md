# PLM 项目实施辅助工具：仓库级 AI 约束

本文件适用于整个仓库。新 Session 或上下文恢复时，按以下顺序读取：

1. `.ai/SKILL.md`
2. `STATUS.md`
3. `AI自主执行与最小人工确认规则 V1.0.md`
4. `.ai/skills/plm-project-development/SKILL.md`
5. 该 Skill 针对当前任务指定的参考文件

`AI开发总控指令与 Skill 规范 V1.1.md` 和 `PLM项目实施辅助工具软件开发实施方案 V2.1.md` 始终是正式基线；仅在当前任务涉及对应基线、Gate、L3 事件或基线版本变化时按需读取，不在每轮重复加载全文。

## 基线与优先级

执行优先级为：

```text
用户最新明确变更
> 正式锁定方案
> 已冻结 ADR
> 已冻结数据模型与 API Contract
> 当前阶段设计
> AI 建议
```

- 只有用户明确表示“修改已锁定方案”时，才可改变正式基线。
- 发现基线问题时，只能提交风险、证据和变更建议，不得直接替换方案。
- 不得把合理推断、待验证事项或 AI 输出描述成已验证事实。

## 当前 Gate

- Phase 0 Gate 1 已通过，结论为 `COMPLETE_WITH_APPROVED_ALTERNATIVES`。
- `ARCH-CANDIDATE-V1`、`DATA-MODEL-CANDIDATE-V1` 和 `DB-SCHEMA-CANDIDATE-V1` 已完成；当前进入 API Contract V1。
- Gate 2 通过前，只允许架构、数据模型、Schema、API Contract、ADR、验证脚手架与必要空壳设计；禁止正式业务功能开发。
- Architecture、Data Model、Database Schema V1 和 API Contract V1 必须在 Gate 2 一并正式确认后，才能进入正式业务编码。

## 硬性约束

- 架构：模块化单体；第一版不得拆微服务。
- 后端：Python 3.13.x、FastAPI、Uvicorn、SQLAlchemy 2.x、Alembic。
- 前端：Vue 3、TypeScript、Vite。
- 数据：PostgreSQL 18、pgvector、本地文件系统元数据化管理。
- AI：业务模块只能调用统一 AIService；不得直接调用厂商 SDK。
- RAG：统一平台；PROJECT 数据必须按 ProjectId 隔离；更换 Embedding 模型必须新建索引并全量重建。
- 插件：独立子进程、JSON-RPC over stdio；插件不得直连数据库或管理 AI Key。
- License：MAC 规范化 → SHA-256 → Ed25519；私钥只允许存在于开发者工作台。
- 目标环境：Windows 11、Windows Server 2025、Debian 13，均为 x86-64/AMD64 正式兼容目标。
- 不得擅自加入 Redis、消息队列、独立向量库、本地大模型、SSO、手机 App、第三方插件市场或 AI 原型执行沙箱。

## 工作纪律

- 默认执行模式为“自主执行 + Gate 确认 + 异常升级”。当前 Scope 内的 L1 工作直接执行；L2 决策写入 `docs/decisions/decision-log.md` 后继续；只有新规则列明的 L3 事件和正式 Gate 才请求人工确认。
- 一个 WBS 任务只解决一个明确问题，不得跨模块顺手修改。
- 正式编码前必须完成 Skill 中的编码前检查；前置未满足则停止该任务。
- 数据库变更必须包含 ORM、Alembic migration、up/down、空库及有数据升级验证。
- 冻结的 `/api/v1` 不得破坏性修改；Breaking Change 需要新 API、v2 或 API Change Request。
- 所有正式成果保留历史版本，并通过 TraceLink 可反向追溯来源。
- AI 建议必须经人工确认后才能成为正式业务事实。
- 保留并尊重用户已有修改，不覆盖无关工作。

## GPT 周额度规则

- 根据用户 2026-09-23 的最新明确指令，本项目不再自动读取 Codex/GPT 周额度，也不再以“剩余低于 20%”作为停止新任务或 WBS 的条件。
- 只有用户之后明确要求查看额度时才查询；不得自行恢复定期检查或停止线。
- 不得未经用户逐次明确确认而使用额度重置、购买额度或消耗 reset credit。

## 代码仓库与同步

- 本项目唯一远端仓库为 `https://github.com/yanglu0928/PLM-ProjectTool.git`，Git remote 名称固定为 `origin`。
- 日常集成分支为 `develop`；开发使用 `feature/*`，PoC 使用 `poc/*`，发行使用 `release/*`。不得直接向 `main` 提交开发代码。
- 每个完成并验证的任务都必须同步其程序、测试、配套文档和版本说明到远端适当分支；不得只保留在本机或聊天记录中。
- 版本说明至少记录版本、日期、变更、兼容性、升级说明、已知问题和验证结果；发布前随 release 分支同步。
- 提交前必须检查并排除密码、API Key、License 私钥、客户数据、运行日志、临时文件和本地环境配置。
- 推送前先获取远端最新状态；存在冲突、非快进更新或未知远端改动时停止推送并报告，不得强制覆盖。
- 用户已授权在当前批准 Scope 和正确分支内，自主使用已绑定的 GitHub 身份执行 fetch、提交和 push；无需为普通同步重复确认。
- GitHub 绑定不扩大仓库、分支或数据范围，也不授权 force push、直接向 `main` 提交、解决未知冲突或上传 Secret/客户数据。

## 未知项

信息不足时使用以下格式，并继续完成不受阻塞的部分：

```text
【待确认】
问题：
影响：
当前可选方案：
建议：
是否阻塞：
```
