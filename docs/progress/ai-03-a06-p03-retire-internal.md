# AI-03-A06-P03：PromptTemplate 内部原子退役

版本：0.1.0.dev0；日期：2026-10-02；状态：Win11 隔离 PostgreSQL18 内部链 PASS；公开/生产路由未实现。

输入：冻结 API-03/DM-04、CR-AI-009、Schema0062、前序 Prompt 服务/通用收据。Changed：新增当前 DeploymentAdmin/CSRF/License 受权退役命令；仅 DRAFT/ACTIVE 可退役，根行锁和强版本条件控制，保留旧活动版本指针作历史。根状态、Audit、不可变首次结果0062、通用幂等收据同事务；原 Key 返回历史结果前仍重验当前身份/License，不读取根现态重建 ETag。没有 Prompt 正文/厂商出站。

Files：`modules/ai/application/retire_prompt_template.py`、`infrastructure/prompt_retire_repository.py`、单元和隔离PG验证、CR/状态/决策/版本说明。Migration：本项无新增，复用0062。API：无新增或挂载。

Verification：Win11隔离PG18随机库 DRAFT/ACTIVE 退役、管理员/CSRF/License、错误版本/不存在、同Key并发/历史重放、Audit故障回滚和撤权拒绝 exit0；单元2项；后端全量2087运行、3项既有跳过；开发wheel SHA-256 `55a1ea046c29163d4544f088685378903eea661812568d43d334b6a6e7332d6a`（临时输出未提交）。随机库已清理；无真实业务Prompt或外发。

兼容/升级/回滚：先受控升级0062方可装内部服务，当前未装生产；撤服务可停止新退役，既有根状态/Audit/结果/收据保留并向前修复。Known Issues：生产信任/公开HTTP/真实目标账户、退役后 Invocation 资格、Server2025/Debian、Gate3/UAT/可用包未验。Next：`AI-03-A06-P04` 可选退役 HTTP 合同与隔离PG18。
