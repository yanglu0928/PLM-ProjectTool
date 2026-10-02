# CR-AI-006：PromptVersion 创建首次结果可重放性

日期：2026-10-02；状态：依 V1.1 持续授权登记，P01 Schema 隔离验证通过、P02 运行写链未完成；WBS `AI-03-A04-P01`。原 Gate 2 冻结提交 `64cdf09` 和 Schema 0059 保留。

来源与冲突：冻结 API-03 `AI_PROMPT_CREATE_VERSION` 要求 `201 immutable PromptVersion`、幂等及条件写。通用平台收据只有 UUID `ref_id`、操作和状态码；PromptVersion 的持久身份是复合 `(prompt_template_id, version_no)`。第一次成功后可继续追加版本，重放时用当前最高版本会变更首次结果；仅保存模板 UUID 无法恢复原版本号。

方案比较：A 从模板当前版本推断，历史重放不可靠，否决。B 修改平台通用收据为动态 JSON，扩大跨模块存储契约和泄漏 Prompt 元数据风险，否决。C 新增 AI 自有不可变 `ai_prompt_version_create_results`，以结果 UUID 供通用收据引用，并以复合 FK 绑定原版本、Actor、Audit、内容指纹和首次版本/ETag，选择 C。

差异与影响：在 0059 后追加 Migration `0060` 与 ORM，不改冻结 API 路径、角色、PromptVersion 主键/不可变要求或技术栈；结果表仅保存摘要和元数据，不复制正文。通用收据引用结果 UUID；业务写入必须将 Version、结果、Audit、收据和模板乐观版本更新放同一事务。内容准入按 DEC-677 另行失败关闭；此表不是内容安全证明。

迁移与回滚：空库、现有模板/版本历史升级；空结果表可安全降级到 0059。有结果历史则拒绝物理降级，保留历史向前修复。正式库升级需备份及目标账户演练；本轮仅隔离 PostgreSQL 18。

验证计划：ORM/Alembic drift=0；空库 up/down/re-up、带已有 Prompt 历史升级；非法复合版本/Actor/Audit/指纹/乐观版本拒绝；UPDATE/DELETE/TRUNCATE 不可变、非空降级拒绝；后续 P02 验证同 Key 并发/历史重放、审计失败回滚、授权与内容准入。任何一项未验证不标对应运行能力 PASS。

安全边界：不得将真实 Prompt、客户数据、Key、Golden 答案、日志或测试凭据提交到 Git；本项测试仅合成无敏感文本。Release/Gate 3 不因本 CR 自动通过。

P01 结果：Win11 隔离 PG18 空库升降级、有 PromptVersion 历史升级、Alembic drift=0、缺复合版本/坏指纹/坏乐观版本/重复结果、历史更新删除截断、非空降级拒绝均通过；无生产迁移或运行命令。全量回归与构建记录见 `docs/progress/ai-03-a04-p01-version-result-schema.md`。
