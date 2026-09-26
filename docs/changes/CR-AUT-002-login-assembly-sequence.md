# CR-AUT-002：登录生产装配前置与 Session HTTP 时序调整

日期：2026-09-25；来源：AUT-03-A07 生产依赖装配编码前检查；状态：ACCEPTED_UNDER_CONTINUOUS_AUTHORIZATION。

## 冲突与证据

冻结 API-02 的 SessionView 必须返回当前授权项目摘要，架构要求 ProjectMember 事实由 Project 模块持有；现有后端尚无 Project/ProjectMember ORM 或授权读取器，`SqlAlchemySessionView` 因此强制外部 Project Port。现有非敏感 BootstrapSettings 只有 bind/data/log，无长期运行的数据库凭据或可信 Origin 来源。`create_app()` 也仅在显式注入 Router 时开放登录。AUT-03-A07 若现在宣称“生产装配通过”，就必须伪造空项目权限或把测试/明文配置冒充生产信任源，均与冻结安全边界冲突。

## 方案与选择

- A：临时把项目摘要固定为空并开放登录。拒绝；未来存在 ProjectMember 时会错误隐瞒/授权，属于不可信生产行为。
- B：提前实现整个 Project 模块和 SecretKeyProvider 后再继续 Auth HTTP。可行但范围过大，延迟可独立验证的能力。
- C：先完成可注入、默认关闭的 Session GET/续期/注销 HTTP，再补 Project。可行，但冻结 SessionView 的项目摘要仍会空缺。
- D：A07 标为前置未满足，不挂生产路由；先按 Phase 2 顺序建立 Project/ProjectMember 的真实持久层与授权摘要读层，之后恢复 A07，并继续 Session HTTP。选择 D；Project 本就在 V2.1 Phase 2 Scope 内，不是跨阶段新增。

## 差异、影响与验证

本 CR 只调整实施时序，不改冻结 API/Schema/架构。A07 不得记 PASS；公开登录仍 404。Project Schema 与授权读层须遵守冻结 PRJ-01～03 模型并完成 ORM/Migration/升级验证。后续 Session HTTP 必须测试 Cookie/CSRF/Origin、轮换与失败响应，并保持默认关闭。恢复 A07 时需用真实 ProjectPort、生产数据库配置、可信 Origin 和端到端 PostgreSQL 验证证明接线安全。

迁移：无。回滚：可恢复原时序，但不得把未满足的前置虚报通过。剩余风险：当前程序包不可供用户登录；目标 Gate 3/UAT 不因本 CR 自动通过。
