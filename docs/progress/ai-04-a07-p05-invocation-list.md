# AI-04-A07-P05 AI Invocation 最小化列表

日期：2026-10-03；状态：`INVOCATION_LIST_PASS`；依据冻结 API-03、CR-AI-020、DEC-770/774/775。下一项：`AI-04-A07-P06` Suggestion GET与定位编排。

编码前检查：当前 Phase 2；P02～P04已通过。任务只实现冻结`AI_TASK_INVOCATION_LIST`，不读取Suggestion payload、不改Schema、不挂Windows组合。输入为当前Session/License/Project授权、受权Task及不可变Invocation；API为`GET /api/v1/projects/{project_id}/ai-tasks/{ai_task_id}/invocations`；仅创建者或项目管理角色可读。验收为最小投影、稳定attempt分页、Task绑定cursor、Task/Invocation协议域隔离、默认关闭，且请求/响应、Secret、Provider request ref、fingerprint和Context正文零输出。

实现：新增Invocation读取应用合同、PostgreSQL最小列投影、opt-in Router与`aii1` AES-GCM cursor。每页先重验Session/License/Project，再读取Task安全投影确认创建者或管理角色；Invocation按`attempt_no DESC, ai_invocation_id DESC`分页。Context只返回固定Content Plan identity/version、policy、mode及Retrieval/Bundle refs，并在Repository内对Invocation与Plan的Project、retrieval和bundle fingerprint一致性做失败关闭校验；fingerprint本身不进入DTO。cursor与P04使用同一`ai-read-cursor-v1`密钥合同，但family、AAD、前缀和Task绑定独立，不能跨协议解码。

兼容、升级与回滚：无Migration、Schema或新依赖；新增可选Router参数，默认应用仍404。P07再接当前账户Vault和Windows组合。撤Router可恢复关闭状态；cursor失效不影响Invocation历史。旧Invocation若没有Content Plan可返回`context=null`，不会猜测Context版本。

验证：Windows 11确定性验证标记`AI_04_A07_P05_INVOCATION_LIST_PASS`；定向14通过、211子测试，覆盖创建者/管理角色、非创建者拒绝、最小DTO、query/error、cursor Task绑定/篡改及与Task family隔离；后端全量2329通过、3跳过、2999子测试；wheel 815项 SHA-256 `f36edbea41edf6a6e7fe21528858b480fee29009f23616da1c72765fd9297e88`。未访问真实Provider、客户数据或Secret。真实PostgreSQL/Vault/Windows组合按P07执行。

已知问题：P06尚未把Suggestion canonical payload、固定Content Plan来源和P03 Document locator组合为当前授权响应；P07仍需真实数据库及缺钥启动关闭验证。Server 2025未复验；Debian 13按用户指令跳过验证但仍为兼容目标。
