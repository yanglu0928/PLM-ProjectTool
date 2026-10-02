# CR-AI-008：PromptVersion 激活首次响应不可变结果

日期：2026-10-02；状态：依 V1.1 持续授权登记，尚未实施；关联冻结 API-03 `AI_PROMPT_ACTIVATE_VERSION`、DM-04 PromptTemplate/Version、CR-AI-006；原 Gate 2 冻结提交 `64cdf09` 保留。WBS `AI-03-A05`。

冲突与证据：冻结接口要求 DeploymentAdmin 以 Session/License/CSRF/幂等/强版本控制激活不可变 PromptVersion，返回 200 active version。既有通用幂等收据仅保存一个 UUID、状态码与请求指纹；根表 `ai_prompt_templates` 的 `active_version_no` 与 `lock_version` 会在后续切换/退役变化。直接读当前根来重放旧成功会返回错误版本/ETag，或拒绝本应可重放的历史结果；审计记录本身不包含完整首次响应快照。现有 `ai_prompt_version_create_results` 专属于创建版本，不能复用其语义。

方案比较：A 用收据指向 Template 并读取当前根，无法保留首次响应，否决。B 将复合版本/ETag 塞入通用收据字段，破坏其通用/不可变语义，否决。C 新增 AI 所有的 `ai_prompt_activation_results` 不可变首次结果，以 result UUID 供通用收据引用，保存 template/version、actor、Audit、trace、前后 lock_version 与受限状态快照；选 C。

与原基线差异：增量 Schema `0061` 增一张不可变结果表与必要 FK/约束/历史保护；不重写 `0059/0060` 或 Gate 2 原冻结提交，不变更 `/api/v1` 路径、状态码、权限、技术栈或 PromptVersion 内容禁令。只允许已存在同 Template 的版本被激活；ACTIVE Template 必须有合法活动版本，RETIRED 不可激活。生产写路由仍受 CR-AI-007 正式准入材料和发行验收阻塞。

风险与控制：错误复合关联、跨模板重放、根版本并发竞争、Audit/收据/状态非原子、历史结果被更新或截断。以 FK/Check/唯一键、不可变触发器、行锁/乐观锁及同事务写入控制；服务重放仍重验当前身份和 License，不能把旧成功当新授权。Schema down 只允许空结果表，生产已有历史不可降级。

迁移/回滚：ORM 与 Alembic up/down 同步；空库与有 Prompt 历史库升级/降级、约束和 drift 验证。已写历史后不物理删除，故不可自动回退；若需恢复由实施团队依离线备份与受控版本路径处理，旧版读写兼容性与发行计划另验。

验证计划：`A05-P01` 冻结冲突与设计/CR；`A05-P02` Schema0061 空/有数据 up/down、FK/Check/历史保护/ORM drift；`A05-P03` 内部激活同事务权限/License/并发/重放/故障回滚；之后可选 HTTP/隔离 PG18 和正式信任装配。Gate3/可用包不得由 Schema 测试替代。

A05-P02 结果：ORM/Migration0061 已实现；Win11 隔离 PG18 空库升降/重升、有 Prompt 历史升级、drift=0、复合 FK、形态/Audit 唯一及不可变保护通过；有激活结果降级被拒。后端首轮2项旧版头/表清单断言失败，更新后2082项通过/3项既有跳过，开发wheel通过。内部激活服务/正式生产迁移尚未完成。

A05-P03 实施前补充：激活历史 PromptVersion 时必须从目标正文/策略重新计算规范指纹，并由当前受信 Prompt 准入端口批准；否则升级前未审版本可能被激活。方案 A 仅查版本存在否决，方案 B 重用 CR-AI-007 精确指纹准入选定；不新增 Schema/API/依赖，测试覆盖已存在但未列入清单的版本被拒且状态/Audit/收据均不变。已成功激活的同 Key 重放只返回原不可变结果，不触发新状态写；真实 AI Invocation 资格另行验收。
