# AI-04-A07-P04 AI Task 受权稳定分页

日期：2026-10-03；状态：`TASK_LIST_PASS`；依据冻结 API-03、CR-AI-020、DEC-770/774。下一项：`AI-04-A07-P05` Invocation最小化列表。

编码前检查：当前 Phase 2；P02～P03已通过。任务只实现冻结`AI_TASK_LIST`，不实现Invocation/Suggestion读取、不挂载Windows生产组合、不改Schema。输入为现有Task不可变/状态投影、Session、License和Project角色；API为`GET /api/v1/projects/{project_id}/ai-tasks`；权限按冻结合同仅ProjectManager、ImplementationMember、CustomerManager，且沿用单项读取“创建者或管理角色”的最小披露。验收为稳定keyset、cursor防篡改/错Session/错Project/错page size、默认关闭、安全DTO和无正文/Secret/Provider原始响应。

实现：新增`AITaskListService`与PostgreSQL批量安全投影，按`requested_at DESC, ai_task_id DESC`分页。ProjectManager/CustomerManager可读取项目Task，ImplementationMember查询在Repository前即强制`requested_by=current actor`，CustomerMember由Project政策拒绝。列表复用已冻结AITaskView，返回受控input版本、policy/schema/context/authorization、Job/current Invocation、Suggestion状态和时间，不读取task parameters、Prompt正文或Provider响应。新增`ait1` AES-GCM cursor，AAD绑定`plm-ai-task-list-aesgcm-v1`、Session摘要、Project和page size；cursor不授予权限，每页重新执行全部授权。默认`create_app()`仍不挂载该路由。

兼容、升级与回滚：无Migration、Schema或第三方依赖变化；新增冻结路径的可选Router参数，未传仍404。P07将从当前账户Vault提供独立`ai-read-cursor-v1` 32字节密钥，并把同一密钥以不同family用于Task/Invocation；本项不从环境变量或普通配置读取密钥。可撤可选Router恢复关闭状态，Task历史和cursor之外无状态变化；密钥不一致只使旧cursor失败关闭。

验证：Windows 11确定性验证标记`AI_04_A07_P04_TASK_LIST_PASS`；定向19通过、215子测试，覆盖角色、own-only、稳定位置、cursor绑定/篡改、默认404、查询与安全错误；后端全量2322通过、3跳过、2980子测试；wheel 811项 SHA-256 `febe5a9b085202d88f6a6d33a160c08b508e877fe98faadb65174a744c6c17df`。未访问真实Provider/客户数据/Secret。真实PostgreSQL查询、Vault来源和Windows组合按既定P07统一验证，不能由本项测试冒充。

已知问题：P05 Invocation列表及独立family、P06 Suggestion GET、P07真实PostgreSQL/Windows组合尚未完成；Server 2025未复验，Debian 13按用户指令跳过验证但仍为兼容目标。
