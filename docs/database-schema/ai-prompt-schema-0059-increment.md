# AI-03 Prompt Schema 0059 增量

版本：0.1.0；日期：2026-10-02；依据 Gate 2 冻结 DM/SC AI-03 与 DEC-674/675。原冻结提交 `64cdf09` 不追写。

`ai_prompt_templates` 保存 DEPLOYMENT 级逻辑身份、受控 TaskType、DRAFT/ACTIVE/RETIRED、活动版本指针与乐观版本；`ai_prompt_versions` 保存 `(prompt_template_id, version_no)` 唯一不可变版本、受权模板正文/哈希、OutputSchema 与 RAG/Provider 策略版本引用、创建者/UTC 时间。复合、可延迟 FK 保证活动指针只能指向同模板既存版本。DRAFT 不带活动指针；ACTIVE 必带；RETIRED 可保留最后活动指针以供历史解释。

数据库限制正文长度、哈希格式、引用格式和状态/版本基本形态；触发器禁止版本 UPDATE/DELETE/TRUNCATE。哈希与正文一致性、Secret/客户资料/Golden 答案检查、单调分配、管理员授权、状态转移与 Audit 由后续 Application 命令执行，不能把格式约束冒充语义校验。Prompt 正文不得写普通日志。

Migration `20261002_0059` 自 0058 增量升级；空表可降级，有根或版本历史则锁表后拒绝降级。正式生产升级需另行备份与目标账户验证；本次仅 Windows 11 隔离 PostgreSQL 18 合成测试。
