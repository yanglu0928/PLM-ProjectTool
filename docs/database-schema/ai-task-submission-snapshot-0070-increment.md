# Schema0070：AI Task 提交快照增量

日期：2026-10-03；WBS：`AI-04-A05-P02`；依据：CR-AI-014、DEC-715/716。原 Gate 2 冻结提交 `64cdf09` 与 Schema0063～0069 保留，不追写。

## 变更

`plm.ai_tasks` 增加四个迁移期可空字段：

- `prompt_template_ref UUID`、`prompt_version_no BIGINT`：复合外键指向 `plm.ai_prompt_versions`；
- `task_parameters JSONB`：只接受 JSON object，数据库硬上限为 16 个一级键及 16,384 个 UTF-8 字节；
- `task_parameters_fingerprint BYTEA`：固定为规范 PostgreSQL `jsonb::text` 的 SHA-256。

四列必须全部为空或全部完整。完整快照插入时，数据库触发器锁定 PromptTemplate，并验证模板为当前 `ACTIVE`、活动版本与提交版本一致、`task_type` 一致，以及 PromptVersion 的 `output_schema_ref`、`rag_policy_ref` 与 Task 已有策略引用一致。四列在 Task 创建后不可修改，完整历史存在时禁止物理降级。

## 兼容与阶段边界

0069 以前的 Task 以四列全空原样升级，不猜测回填。为保持当前尚未公开的内部创建链兼容，0070 本身仍允许全空行；它只建立完整快照的存储和数据库防护。`AI-04-A05-P03` 必须让应用层所有新建 Task 写入完整快照，并把全空旧行判为不可执行。在 P03 及后续 HTTP/Worker 前置完成前，不得将0070描述为新任务提交已启用，也不得开放 AI Task 公共入口。

Task Policy 对参数的逐键类型、枚举、深度和数组项限制属于应用层规则，不由本迁移猜测；数据库只提供拒绝非对象、尺寸/键数、摘要和 Prompt 一致性的最后防线。Document/Requirement 正文继续只允许通过不可变 InputRef 引用，不得塞入参数。

## 升级、回滚与验证

升级前须备份并停止相关写入，按顺序从0069升级0070。未产生完整提交快照时可降回0069；一旦存在完整快照，降级会持有 `ACCESS EXCLUSIVE` 锁并明确拒绝，须向前修复或从受控备份恢复，不能删除历史绕过。

Windows 11 / PostgreSQL 18.6 已验证：空库升级/降级/重升级、有0069历史升级与NULL保留、Alembic漂移、复合Prompt引用、活动版本/task type/output schema/RAG匹配、JSON对象/键数/字节/指纹、快照不可变及非空拒降。首次运行发现PL/pgSQL局部变量与列同名歧义，修正变量名后；第二次运行发现数组在键枚举前产生原生错误码，改为先显式检查JSON类型；最终从头全量重跑通过。

Debian 13 按用户指令暂不验证；Windows Server 2025 本任务未验证。Schema0070 尚未用于生产迁移。
