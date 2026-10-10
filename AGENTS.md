# PLM 项目实施辅助工具：仓库级 AI 约束

本文件适用于整个仓库。新 Session 或上下文恢复时，按以下顺序读取：

1. `.ai/SKILL.md`
2. `STATUS.md`
3. `AI自主执行与最小人工确认规则 V1.1.md`（并继承其未覆盖的 V1.0 条款）
4. `.ai/skills/plm-project-development/SKILL.md`
5. 该 Skill 针对当前任务指定的参考文件

`AI开发总控指令与 Skill 规范 V1.1.md`、`PLM项目实施辅助工具软件开发实施方案 V2.1.md` 及其正式 License 补充 `PLM项目实施辅助工具软件开发实施方案 V2.1 License 变更补充 CR-LIC-001.md` 是正式基线；补充仅在 License 授权粒度上优先。仅在当前任务涉及对应基线、Gate、L3 事件或基线版本变化时按需读取，不在每轮重复加载全文。

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

- 用户 2026-09-24 已明确作出持续授权，要求按计划持续执行至可使用程序包：原方案不兼容时可自行分析并执行解决方案，无需逐项再批准；实施前必须记录 Change Request、差异、风险、迁移/回滚和验证计划，保留原冻结版本并同步 GitHub。该授权不豁免客观验收，也不授权秘密/客户数据外发、购买或不可恢复生产操作。
- 用户 2026-10-10 同意 `CR-EXEC-002`：优先形成 Windows 11 受控内部试用包，再完成既定三平台正式发行；这是交付顺序调整，不是删除 Scope、降低安全要求或预先通过 Gate。
- 不得把合理推断、待验证事项或 AI 输出描述成已验证事实。

## 当前 Gate

- Phase 0 Gate 1 已通过，结论为 `COMPLETE_WITH_APPROVED_ALTERNATIVES`。
- Gate 2 已于 2026-09-23 由用户明确批准；`ARCH-CANDIDATE-V1`、`DATA-MODEL-CANDIDATE-V1`、`DB-SCHEMA-CANDIDATE-V1` 和 `API-CONTRACT-CANDIDATE-V1` 已冻结为正式开发基线，原冻结内容固定为提交 `64cdf09`。2026-09-24 用户另明确批准 License 专项 `CR-LIC-001` 方案 B，作为可追溯的后续基线修订，不追写原冻结提交。
- 当前处于 Phase 2 Platform Core；最新任务、进展及客观阻塞以 `STATUS.md` 为准。`LIC-02-A02` 的冻结冲突已由用户批准 CR-LIC-001 方案 B；Gate 3 尚未通过。
- 冻结后的总体架构、核心数据模型、DB Schema V1、`/api/v1` Breaking Change、技术栈、安全/License 机制或 Scope 变化必须走可追溯 Change Request；按用户 2026-09-24 的持续授权可在记录、验证与兼容/迁移分析后自主实施，不得静默改写或虚报 PASS。
- Gate 2 批准不代表生产 ORM/Migration、运行 OpenAPI、性能、AI 质量、三平台发行或 UAT 已通过。

## 硬性约束

- 架构：模块化单体；第一版不得拆微服务。
- 后端：Python 3.13.x、FastAPI、Uvicorn、SQLAlchemy 2.x、Alembic。
- 前端：Vue 3、TypeScript、Vite。
- 数据：PostgreSQL 18、pgvector、本地文件系统元数据化管理。
- AI：业务模块只能调用统一 AIService；不得直接调用厂商 SDK。
- RAG：统一平台；PROJECT 数据必须按 ProjectId 隔离；更换 Embedding 模型必须新建索引并全量重建。
- 插件：独立子进程、JSON-RPC over stdio；插件不得直连数据库或管理 AI Key。
- License：MAC 规范化 → SHA-256 → Ed25519；私钥只允许存在于开发者工作台。CR-LIC-001 后首版仅本产品全功能整体授权，七字段签名载荷不增加产品/功能权益。
- 目标环境：Windows 11、Windows Server 2025、Debian 13，均为 x86-64/AMD64 正式兼容目标。
- 不得擅自加入 Redis、消息队列、独立向量库、本地大模型、SSO、手机 App、第三方插件市场或 AI 原型执行沙箱。

## 工作纪律

- 默认执行模式为“持续自主执行至可用程序包 + 偏差先记录后实施 + 按证据关闭 Gate”。L1 直接执行；L2 写决策日志；原 L3 事项走正式 Change Request 并按 V1.1 的持续授权执行，不再逐项请求同意，也不因普通 WBS/Gate 交界等待“继续”。Gate 只有在验收证据满足时才能关闭；客观阻塞要记录并转向独立任务，不伪造通过。
- 一个 WBS 任务只解决一个明确问题，不得跨模块顺手修改。
- 正式编码前必须完成 Skill 中的编码前检查；前置未满足则停止该任务。
- 数据库变更必须包含 ORM、Alembic migration、up/down、空库及有数据升级验证。
- 冻结的 `/api/v1` 不得破坏性修改；Breaking Change 需要新 API、v2 或 API Change Request。
- 所有正式成果保留历史版本，并通过 TraceLink 可反向追溯来源。
- AI 建议必须经人工确认后才能成为正式业务事实。
- 保留并尊重用户已有修改，不覆盖无关工作。

## 加速交付路线

- 以两项不同里程碑管理进度：`Windows 11 内部试用包（Pilot）` 和 `正式多平台 Release`。Pilot 只供受控内部试用，版本说明列明未完功能、未通过 Gate 与适用环境；不得对外称正式发行或把合成 License、测试账户、AI 建议、客户确认当成生产事实。
- 当前优先打通“项目 → 交接 → 调研 → 需求 → 原型 → 方案 → 实施 WBS → 输出文件”的最短完整业务链。优先处理直接阻断纵向链、真实安全装配和 Windows 11 离线安装的问题；独立的质量、性能、正式信任及其他 Scope 缺口保持可追溯并继续推进，不因 Pilot 被豁免。
- 尽早制作可重复的 Windows 11 离线安装/启动/重启/备份/升级验证包；必须使用正式设计的公钥和受控服务账户来源，任何真实信任前置未满足则 Pilot 标为受限或阻塞，不允许测试信任源伪装正式安装成功。
- 每个 WBS 保持单一明确问题，但满足前置时连续执行，不因普通 WBS、模块或 Gate 交界等待“继续”。在互不依赖的检查上可并行运行自动验证；每次变更先跑定向测试，里程碑前跑完整回归、实际数据库/浏览器、权限/License/AI/插件/性能、离线安装升级与 UAT。测试失败先修复，不以减少正式验收项换取速度。
- `STATUS.md` 分别记录 Pilot 与 Gate 3～7/正式 Release 状态，优先级以客观阻断和依赖链为准。Windows Server 2025、Debian 13 继续作为正式 x86-64 目标；未实测不得从 Windows 11 推定兼容，Debian 13 实机跳过期间正式三平台结论维持未通过。

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
