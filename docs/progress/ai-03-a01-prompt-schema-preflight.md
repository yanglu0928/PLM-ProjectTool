# AI-03-A01：PromptTemplate / PromptVersion Schema 前置设计

版本：0.1.0；日期：2026-10-02；状态：设计验收 PASS，Schema/运行时未实施。

## 输入与边界

- Gate 2 冻结 `64cdf09`：DM 的 AI-03 为 DEPLOYMENT 级 PromptTemplate；SC-01 固定 `ai_prompt_templates` 与 `ai_prompt_versions`、活动指针与不可变版本分离；SC-02 固定 `(prompt_template_id, version_no)` 唯一；API-03 固定管理员列表、详情、创建、增版、激活及退役接口。
- 现有迁移头为 `20261002_0058`，仓库尚无 Prompt ORM、表或路由。此项仅设计，不引入 Migration、外发或运行时调用，不将 Prompt 设计描述为已经可用。
- 业务模块不能直连厂商 SDK；Prompt 内容只能供统一 PromptRegistry / AIService 解析。AIInvocation 后续必须保留 PromptVersion、输入版本/Hash、策略和模型快照。

## 后续 Schema 最小方案

1. 根表 `ai_prompt_templates`：UUID 主键、受控 `task_type`、`scope=DEPLOYMENT`、`template_state` (`DRAFT/ACTIVE/RETIRED`)、可空 `active_version_no`、乐观 `lock_version`、创建者/UTC 时间。`RETIRED` 不物理删除，不自动恢复 ACTIVE；ACTIVE 必须有有效活动版本，DRAFT/RETIRED 的活动指针语义在命令设计时明确定义并以 DB 约束固定。
2. 子表 `ai_prompt_versions`：复合键 `(prompt_template_id, version_no)`，正整数版本；受权保存的 System/User 模板正文及各自规范化 SHA-256，`output_schema_ref` 与 `schema_version`、`rag_policy_ref`、`provider_policy_ref`、创建者/UTC 时间。后续增加正文长度/编码上限与确定性规范化规则，不允许哈希替代正文校验。版本一经创建，正文和策略引用不得 UPDATE/DELETE/TRUNCATE。
3. 活动指针使用同模板复合 FK 指向子版本，防跨模板/不存在版本；循环 FK 使用可延迟约束或等效的先建表后加约束迁移顺序。根表状态与指针一致性在数据库约束/受控命令内双重检查，不允许仅靠 UI。版本号并发分配在根行锁内单调递增，历史缺号不重用。
4. 子版本外键拒绝级联删除；已有任一版本时 downgrade 安全拒绝，不清理历史。空库及带旧 AIProvider/AIModel 数据的 0058→0059 升级均应可行；空表可降回 0058。正式库升级另需备份与目标账户验证。
5. 普通日志、审计和 API 元数据列表不得复制正文。未来受权详情正文可见性、Secret/客户固定副本/Golden 答案/绕过 Evidence 或 Review 的指令检测，属于创建/增版服务的失败关闭前置；数据库不能凭 CHECK 证明语义安全。无客户正文、真实 Key 或模型调用用于 Schema 测试。

## 验收矩阵与后续拆分

|项|期望证据|本项|
|---|---|---|
|冻结语义/字段/唯一性/活动指针|设计映射 + 后续 ORM/Migration drift=0|设计完成；迁移未运行|
|空库 up/down/re-up、带旧数据升级|隔离 PostgreSQL 18 实测|未运行|
|跨模板/悬空指针、非法状态/版本、不可变历史|数据库负例与事务回滚|未运行|
|非空降级拒绝、正式库备份|隔离拒绝测试/发行演练|未运行|
|创建、增版、激活、退役及管理员授权|独立内部命令和可选 HTTP 验证|未实现|

下一项 `AI-03-A02` 仅实现 ORM + Migration `0059` 与上述数据库验收；此后再拆 Prompt 内部命令、只读/写 HTTP、Windows 显式组合。AI-02 `AVAILABLE`/质量证明及 AI-01 真实 Worker 仍独立阻塞 Gate 3。

## 兼容、升级与已知问题

本设计不修改冻结模型或 API；选择循环指针的实现方式属于 SC 物理设计细化，按 DEC-674 记录。若后续发现 DB 无法同时强制状态/指针与受控多语句写入，应先登记 CR 并比较最小替代，再实施。当前无 Migration、API、程序包变更；未验证 Windows Server 2025、Debian 13 或正式部署账户。
