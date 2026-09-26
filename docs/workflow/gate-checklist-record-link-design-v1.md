# Gate 固定 Checklist 记录关联 V1

2026-09-26；WFL-02-A01-P04；CR-WFL-004 后续 owned Schema 增量；设计由 P05/0033 实施并完成隔离 Schema 验证，见 P05 进度报告。实际 Owner/Gate 命令仍未完成。

## 证据、比较与选择

0031 GateItem 有 result/typed refs，但没有固定 ChecklistRecord FK；0032 每次更正已不可变，P04 当前查询能拒绝旧无链/过时投影。只比较当前 PASS 不能反向定位作出判断的具体记录。

不采用覆盖旧 Gate 结果或自动推算旧 record_id；不复制记录 JSON；不新增无必要的独立映射 Aggregate。采用在 `wfl_transition_gate_items` 增加 nullable `checklist_record_id` UUID、`observed_item_version` bigint、`record_fingerprint` bytea 三字段（同空或全有，非零/正版本/32 bytes），复合 FK (record_id,workflow_id,project_id,item_key) → 0032 同四字段唯一键。保留旧表身份/内容与 0031/0032 原迁移。

nullable 仅为迁移历史兼容：升级前旧 Gate 行保持三字段空；升级后新 INSERT 必须全有，不允许调用方用 NULL 切换旧模式。旧已提交 Gate 不允许补写关联、篡改或删除。旧未关联历史不是新 Gate 命令可用的可信证明，后续查询需显式区分。

## 新关联一致性

插入 GateItem 仍须与新 Transition 同事务（0031 已强制 created_xid/封口），锁 Workflow；所引记录必须同 Workflow/Project/Item、定义 V1、阶段为 Transition.from_stage、result 与 Gate 相同且 PASS/WAIVED，after_item_version 等于当前 Item.lock_version，after_workflow_version 不大于 Transition.before_lock_version，record_fingerprint 等于存储记录摘要。更正后旧 PASS 即使仍存在也不得引用。

关联记录需已提交：禁止把 Checklist 修改和阶段推进混成一个事务（0032 记录提交要求当前阶段不移动）。SQL created_xid 用于同事务拒绝；实际服务仍先通过当前完整链 Port/授权/Owner 检查，不能只靠 FK 作批准。

提交时重核上述固定事实，Gate refs 与记录 refs 的 typed 身份、Scope/项目及内容摘要必须精确一致，不能遗漏、额外混入或替换为另一 APPROVED 身份。Gate 为这次重新观测，锁版本不得小于记录当时版本，verified_at 不早于记录相应观测。不能要求观测版本/时间完全相等，也不能将历史 ELIGIBLE 当作现在仍有效。0031 继续锁/重验真实 Evidence 当前事实；Review/例外实际 Owner 仍缺。

WAIVED 的理由/影响必须与固定记录相同；记录 actor 为记录操作者，不冒充例外审批人，Gate waiver_actor_id 的实际权限/身份需未来批准例外 Owner 独立证明，本 Schema 不伪造批准人关联。PASS 不带 waiver 字段的旧规则保持。

## 迁移、回滚与验收

0033 从 0032 增量：三列、形状 check、复合 FK、插入与 deferred 校验；不新增业务正文、不改 API 请求或依赖，不改变阶段/流程 Scope。先备份，旧行原值不动、新列 NULL；不得 UPDATE 历史来自动填充。

down：有任意新关联拒绝删列/丢失关系；只存在旧未关联行可移除新空字段/新保护，0031 旧不可变保护保留。禁止 offline down。应用回滚可不装配新 Gate 命令并保留 Schema/历史。

验收：空库 up/down/re-up；已有 0031 合成 Gate 和 0032 记录升级/down/re-up 原值不动/不伪造关联；ORM parity/离线 up；合法 PASS/WAIVED/current 记录关联；跨项目/Item/阶段/旧记录/无记录/失败结果/错误版本/Hash/未提交记录拒绝；依据精确集、Scope/内容、版本/时间回退与 waiver 理由影响拒绝；半套/并发/审计故障全回滚、封口/immutability/非空 down；既有 Workflow 回归。合成 Review/例外和 SQL 不证明客户批准/实际 Gate。

性能、覆盖率、真实 Owner/权限/HTTP/Windows 正式信任源另验；Server 2025 未验、Debian 13 暂不验证，完整 Workflow/Gate 3/发行尚未完成。
