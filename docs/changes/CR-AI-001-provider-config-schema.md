# CR-AI-001：AIProvider 配置版本持久化增量

日期：2026-10-02；状态：依据 CR-EXEC-001 持续授权实施；依据 CR-SEQ-001 前置 AI-01 基础任务。Gate 2 原冻结提交 `64cdf09` 保留，Phase 2/Gate 3 未通过。

## 来源、冲突与证据

冻结 DM-04 要求部署级 AIProvider 的 `CONFIGURED / ACTIVE / SUSPENDED / RETIRED` 生命周期、SecretRef、受控端点/地区/外发类别、能力和配置版本；SC-01 映射 `ai_providers` 与 `ai_provider_config_versions`，SC-02 将其归类 M-DEP。现有正式 Migration 至 `20261002_0053`，两表尚不存在。AI-01-A01 只有不可变内存合同，不形成可审计配置历史或并发根身份。必须以增量 Migration 实现，而非追写冻结 DB Schema V1。

## 方案比较与所选差异

- 不选把 API Key/完整端点 URL、客户 Prompt 或请求正文写入 Provider 表：违反 Secret 和数据外发边界。
- 不选只有一张可覆盖配置的表：无法追溯 Provider/region/模型路由配置变更和逐次外发授权对应版本。
- 选择部署级 `ai_providers` 根身份与当前配置指针、状态、乐观版本；不可变 `ai_provider_config_versions` 保存版本号、类型、显示名、端点策略引用、SecretRecord FK、地区/外发类别及四个能力布尔位。复合 FK 使指针不能串用其他 Provider 的版本；配置历史不可 UPDATE/DELETE/TRUNCATE；Secret 仍只存引用，值由现有 SecretResolver 受控读取。此增量不改变冻结实体含义、API、技术栈或 Scope。

## 影响、迁移、回滚

新增 ORM 和 Alembic `20261002_0054`，无旧 AIProvider 行回填、无公开 API/生产组合变更。升级前备份；空库、已有其他业务数据的库均允许升级。空 AIProvider 表可降级；只要新根或配置版本存在，降级安全拒绝，防止丢失授权/配置历史，须通过向前修复或经独立受控恢复。升级运行不自动激活 Provider，也不凭 FK 证明 Secret purpose、有效性、许可证、角色或外发授权；这些属后续 Owner Service。历史版本保留，不在配置轮换时原地修改。

## 验证计划与剩余风险

在 Windows 11 本机隔离 PostgreSQL 18 中验证：空库 up/down/re-up、有数据升级保持既有行、ORM/Alembic 无差异、受控字段/版本/FK/指针/能力约束、历史不可改写、非空降级拒绝；后端全量回归和 wheel。测试只用合成身份与无明文 SecretRecord，不连接外部 AI。此验证不代表 Provider 配置 Service、激活/连通、逐次客户数据外发、POC-03 质量、Server 2025/Debian 运行或 Gate 3 通过。

2026-10-02 验证结果：Windows 11 隔离 PostgreSQL18.6 空库 up/down/re-up、有旧数据升级、复合 FK/历史保护/约束、非空降级拒绝、两库 Alembic check PASS；后端1907运行/3跳过、开发 wheel PASS。详见 `docs/progress/ai-01-a02-provider-schema.md`；正式生产迁移、Service/AI质量/三平台/Gate 仍未验证。
