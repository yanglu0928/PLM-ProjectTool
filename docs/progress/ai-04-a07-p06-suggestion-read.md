# AI-04-A07-P06 Suggestion 安全读取与定位编排

日期：2026-10-03；状态：`SUGGESTION_READ_PASS`；依据冻结 API-03、CR-AI-020、DEC-770/771/776。下一项：`AI-04-A07-P07` Windows 11 显式组合与一次性 PostgreSQL HTTP 验证。

编码前检查：当前 Phase 2；P02～P05 已通过。本项只实现冻结 `AI_TASK_SUGGESTION_GET`，不实现 Accept/Reject，不修改 Schema、依赖或 Provider 执行链。输入为当前 Session/License/Project/Task 授权、不可变成功 Invocation/Suggestion、固定 Content Plan 来源及 Document Owner 当前可读事实。验收为只读受控 payload、`NOT_FORMAL_FACT`、输入/模型/Prompt/Context版本、质量标记和服务端定位；任何来源不一致、历史权限撤销、节点丢失或 hash 漂移必须失败关闭。

实现：新增 Suggestion 应用读取合同、PostgreSQL 最小投影和 opt-in Router。Repository 只接受 Task `SUCCEEDED`、Suggestion非 `NONE`、当前 Invocation `SUCCEEDED + VALID`，并核对 Task/Invocation/Suggestion/Content Plan 的 Project、Provider/config、Model/revision、Prompt、Schema、Context 和引用关系。JSONB 重新 canonical 编码并校验 fingerprint；Evidence 顺序按实际引用 ordinal 与固定 Plan source identity/content hash 对齐。读取前后两次验证 Session/License/Project/Task 创建者或管理角色；所有输入 DocumentVersion 均由 Document Owner 重验当前权限和 source hash。V2 再按受控 node id 读取固定 ParseResult，核对 result identity/source/result hash并只返回服务端生成的 `STRUCTURED_NODE`；V1 历史明确只返回 `DOCUMENT` 精度，不做文本猜测。传输不包含 Secret、存储路径、Provider request ref、原始 Provider response或内部 fingerprint。

兼容、升级与回滚：无 Migration、数据库 Schema或新依赖；Document locator 只增加内部固定结果身份/hash供 AI Owner比对，旧调用方兼容。新增 Router 参数默认未注入，因此默认应用继续404。撤销 Router/应用装配可回退到关闭状态，不删除 Task、Invocation、Suggestion 或 Evidence 历史。V1/V2 历史均保留；坏定位不降级为自由搜索。

验证：Windows 11 确定性标记 `AI_04_A07_P06_SUGGESTION_READ_PASS`；定向12通过/22子测试，覆盖创建者/管理角色、非创建者/CustomerMember拒绝、V1/V2、双重Task授权、全部输入Document授权、精确节点、payload/Evidence/Owner hash漂移、默认404和安全错误；后端全量2335通过、3跳过、3009子测试；开发wheel 818项 SHA-256 `eed99c13131a974aa7a5858330afb7744039f61eef83a12c145063cca059981a`。未访问真实Provider、客户数据或Secret。

已知问题：P07 尚需一次性 PostgreSQL 18.6、当前账户 Vault cursor key、Windows显式组合及真实HTTP角色隔离/定位验证；本项Repository由单元与全量回归覆盖，真实数据库组合留P07。Accept/Reject、前端工作台、AI质量/Gate3/UAT/发行包仍待。Server 2025未复验；Debian 13按用户指令跳过验证但仍为兼容目标。
