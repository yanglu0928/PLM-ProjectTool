# AI-03-A05-P01：PromptVersion 激活前置与首次结果设计

版本：0.1.0；日期：2026-10-02；状态：设计/变更登记 PASS，代码与数据库验证尚未开始。

输入：冻结 API-03 `AI_PROMPT_ACTIVATE_VERSION`、DM-04 Prompt 模型、现有 Prompt 根/版本 Schema0059、版本创建结果0060、通用收据0015。前置的内部版本创建及 Win11 隔离 PG18 合成 HTTP 整链已通过；正式准入材料/人工审查阻塞生产路由，但不阻塞独立激活 Schema 设计。

结果：CR-AI-008 已先登记，选择 AI 所有不可变激活首次结果，收据仅保存该结果 UUID。服务未来在行锁内核对同 Template 目标版本和当前状态/强版本；新激活根指针/状态、Audit、结果、收据必须同事务。历史重放返回首次响应且重验当前 Session/License；不能读取现时根伪装首次响应。旧冻结提交不追写。

Changed/Files：CR-AI-008、本进度、决策、状态。Migration：本项无，下一项规划 0061。API：无变更。Tests：本项静态对照冻结合同/现有 ORM、收据和迁移；未运行新代码测试。兼容/升级/已知问题：历史结果落地后不可自动 down；正式 Prompt 审查/发行包信任、Server2025/Debian13、Gate3/UAT/可用包未验。Next：`AI-03-A05-P02` ORM/Migration0061 与隔离 PG18 空/有数据升降级验证。
