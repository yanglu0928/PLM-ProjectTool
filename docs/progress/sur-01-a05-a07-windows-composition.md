# SUR-01-A05-A07：Survey 定义 Windows 生产组合

日期：2026-10-06。结论：`SUR_01_A05_A07_WINDOWS_COMPOSITION_PASS`（Windows 11、隔离合成 cursor key）。下一项：`SUR-01-A06-A01` Survey 前端与交互前置核查。

## 实施结果

- 新增单一失败关闭的 Survey 生产组合。显式只读平台模式仅挂载 Survey/Version 四个 GET；显式写模式额外挂载五个普通写 Operation 和一个原子送审 Operation，共覆盖 API-04 冻结的十个 Survey 定义 Operation。默认 App、登录模式仍不暴露这些路由。
- Survey 与 SurveyVersion 分别使用 `survey-cursor-v1`、`survey-version-cursor-v1` 两份独立 Windows Secret key；任一 key 缺失、无效或组合参数异常均拒绝启动，不使用测试常量、自动生成或共享 key 回退。
- 生产组合复用真实 Project 授权、Session/CSRF、License、Audit、持久幂等、四类 Survey 来源证明、目标部门证明、通用 PROJECT Review 内核和 `SRV-02` Subject Owner；未复制 Review 状态机或跨模块正文。
- Windows 11 / PostgreSQL 18.6 全新隔离数据库完成真实 HTTP 闭环：默认关闭、只读模式禁止写、创建、PATCH、四读、Version 创建/校验、原子送审及同键重放、通用 Review 批准、批准版读取和第二个 Survey 归档。数据库后验确认两个 Survey、一个 Version、一个 `SRV-02` Review、一个 APPROVED Round 和持久回执，Alembic head `0106` 无漂移，临时数据库已清理。

## 偏差与修正记录

首轮真实闭环在 Version GET 阶段返回 503。排查证明 Schema、ORM 和创建仓储均以零为首个 `sequence_no`，但 A06 HTTP 序列化边界错误要求 `sequence_no > 0`。这是实现缺陷，不是冻结 Schema/API 变更；已将边界修正为接受 `sequence_no >= 0`，并增加零序号合同断言。修正后使用全新隔离数据库从迁移、写入到批准完整重跑通过，没有沿用失败轮数据，也没有放宽题型、来源、Project 或授权约束。

## 兼容、升级与回滚

本项无新 Schema/Migration、依赖、公开路径、角色、License 粒度、网络外发或客户数据变化，Schema head 保持 `0106`。升级需在目标账户安全供给两份独立 cursor key；撤销生产组合注入可恢复默认关闭，但已经提交的 Survey、Review、Audit 和幂等历史不得删除或逆转。正式目标账户 key 仪式、Windows Server 2025 当前链、Round/Response/Conclusion、Survey UI、性能、UAT、Gate 3 与可交付发行包仍未因此通过；Debian 13 实机按用户指令跳过且不得声明兼容性已验证。

## 验证证据

- 组合、生产入口、Survey 读写/送审及 cursor 定向：46 项通过。
- 后端完整回归：2,846 项通过，3 项按既有环境条件跳过。
- wheel：1,052 个条目，包含 `windows_survey.py`、生产入口及 Survey 三个 API 模块；SHA-256 `5ecfda4d9b0ad06f8dbe5e12541e4b2aff2e95a1eedd2951f7093efb6175c7c0`。
- 真实闭环标记：`SUR_01_A05_A07_WINDOWS_COMPOSITION_PASS: ten frozen Survey definition operations, read-only/write composition, real PostgreSQL, HTTP, Review approval, replay and archive verified`。
