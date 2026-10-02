# CR-AI-009：PromptTemplate 退役首次响应快照

日期：2026-10-02；状态：依 V1.1 持续授权登记，设计已定、尚未实施；关联冻结 API-03 `AI_PROMPT_RETIRE`、DM-04、CR-AI-006/008；原 Gate2 冻结提交 `64cdf09` 不改。WBS `AI-03-A06`。

冲突与证据：冻结接口要求 DeploymentAdmin 携带 Session/License/CSRF/幂等键/强 If-Match 退役模板并返回 200 RETIRED。通用收据只保存一个 UUID、状态码和请求指纹；根表 `template_state`、`active_version_no`、`lock_version` 是可变当前状态。若收据仅指向根，历史重放会从现态重建首次 ETag/活动版本，无法独立证明原结果，且在修复/未来变更后可能误回传。激活结果0061只允许固定 ACTIVE、复合版本归属，不可复用为退役结果。

方案比较：A 收据指向当前根并假定 RETIRED 永远不变，无法保留独立首次结果且把应用状态机当数据库审计证明，否决。B 改通用收据承载 ETag/活动版本，污染已冻结通用语义，否决。C 新增 AI 所有的不可变 `ai_prompt_retire_results`（预定 Schema0062），保存模板、操作者、Audit、trace、退役前状态/活动版本、前后 lock_version 和固定 RETIRED，收据指向结果 UUID；选择 C。

差异：在现有 Prompt Schema 后增量表/ORM/migration，不改冻结 `/api/v1`、PromptVersion 内容、技术栈或 License。退役可从 DRAFT 或 ACTIVE 执行；RETIRED 再次新请求拒绝，但原 Key 在当前授权/License 重验后可返回首次结果。退役保留已有活动版本指针作为历史，AI Invocation 资格须按 RETIRED 拒绝新调用，不得以指针存在推断可调用。

风险与控制：并发根版本竞争、结果/审计/收据分裂、历史状态被改写、退役后仍被调用。通过根行锁/乐观锁、同事务写入、FK/Check/不可变保护和单独 Invocation 准入控制；正式生产路由仍受 CR-AI-007/PLT 发行信任前置约束，不能拿合成密钥开放。

迁移/回滚：0062 ORM/Alembic up/down 同步；空库与已有 Prompt 历史库升级、drift、约束、历史保护及空表 down/re-up。非空退役结果表拒绝物理 down；已投产需保留历史，向前修复或受控备份恢复，不删除退役 Audit/收据。

验证计划：P01 本变更/冻结冲突设计；P02 Schema0062 隔离PG18空/有数据升降/拒降；P03 内部服务权限/License/CSRF/并发/重放/回滚；P04 可选HTTP合同与隔离PG18；P05 正式挂载前置核查。Gate3/UAT/可用包须独立验收。

P02 结果：ORM/Migration0062 已实现；Win11 隔离PG18空/有Prompt历史升级、空表降级重升、drift=0、合法DRAFT/ACTIVE首次快照、复合归属/形态/Audit唯一/历史保护、非空拒降通过。首轮外键名长度、随后 SQL NULL 三值逻辑负例失败，分别修正显式短名和非空条件后重测通过；后端全量2085运行/3跳过、开发wheel通过。内部退役服务/生产迁移未完成。

P03 结果：内部退役服务和 AI 仓储已实现；当前管理员/CSRF/License 双重检查、DRAFT/ACTIVE 根行锁和强版本条件、根/Audit/0062首次结果/收据同事务，原Key重放保留首次 ETag 且撤权拒绝。Win11隔离PG18合成权限/许可/同Key并发/历史重放/Audit故障回滚通过；后端2087运行/3跳过，开发wheel通过。公开HTTP/正式生产迁移及 Invocation 资格仍未完成。

P04 结果：可选退役HTTP实现冻结路径200，仅严格空对象与Session/Origin/CSRF/幂等/强If-Match，结果最小安全投影。Win11隔离PG18实际HTTP默认/普通用户404、200与重放、冲突409、许可403和单次根/Audit/结果/收据通过；合同3、后端2090运行/3跳过及开发wheel通过。默认/生产仍不挂载，正式信任/Invocation未验。

P05/P06 结果：核查后确认单向安全退役不要求 Prompt 内容签名清单，但平台信任不豁免；仅在 Windows 显式写组合装配退役 Router，登录/只读保持404。Win11隔离PG18合成写组合200/重放、普通用户404、License403、缺平台游标密钥失败关闭及单根/Audit/首次结果/收据通过；后端2090运行/3跳过，开发wheel通过。正式目标账户/发行信任、生产迁移、Invocation资格、Server2025/Debian、Gate3/UAT/可用包仍待，不以合成证据替代。
