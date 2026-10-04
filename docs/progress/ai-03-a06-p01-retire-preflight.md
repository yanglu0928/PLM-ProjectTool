# AI-03-A06-P01：PromptTemplate 退役前置与首次结果设计

版本：0.1.0.dev0；日期：2026-10-02；状态：冻结冲突与变更登记 PASS；代码/迁移/运行验证尚未开始。

输入：冻结 AI-03 DM/API-03、现有 Prompt Schema0059～0061、通用幂等收据、CR-AI-006/008。静态核查确认根状态/活动指针/锁版本可变，收据 UUID 不能自足恢复原 200 响应；0061 激活结果固定 ACTIVE，不适合复用。

结果：先登记 CR-AI-009，选 AI 专属不可变退役首次结果 Schema0062；保留历史活动版本指针、阻断新调用的资格由后续 Invocation 单独检查。服务未来根行锁、强版本与当前管理员/License 检查，根/Audit/首次结果/收据同事务；原 Key 重放重验身份/License，不依赖根现态重建首次响应。

Changed：本设计/CR/决策/状态/版本说明。Files：仅 Markdown。Migration/API：本项无；后续0062及原冻结退役路径的可选实现。Tests：静态对照冻结合同、Prompt ORM 和收据；新运行测试未执行。兼容/回滚：原冻结提交保持；本项无运行行为可回滚。Known Issues：正式审查/发行信任、生产路由、退役后 Invocation 防护、Server2025/Debian/Gate3/UAT/可用包未验。Next：`AI-03-A06-P02` ORM/Migration0062与隔离PG18验证。
