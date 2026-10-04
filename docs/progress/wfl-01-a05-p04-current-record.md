# WFL-01-A05-P04 当前 Checklist 记录与固定依据查询

日期：2026-09-26；版本：0.1.0.dev0；CR-WFL-004；结果：WINDOWS_INTERNAL_QUERY_PASS。

## 编码前检查

- 当前 Phase：Phase 2 Platform Core；当前 WBS：WFL-01-A05-P04。
- 输入基线：冻结 DM-02/SC-01/API-02、CR-WFL-004、Checklist 记录设计 V1 与 P02/P03 验证。
- 前置任务：不可变 Domain/0032 两表及隔离 Schema 已 PASS；公开写服务/实际 Owner 不作为本内部查询的已完成前置。
- 涉及模块：仅 Workflow Application Port/DTO 与 Infrastructure Repository。
- 涉及实体：Workflow、ChecklistItem、ChecklistRecord/Refs；不改 Schema。
- 涉及 API：无公开入口/冻结字段变化；涉及权限：调用方必须先完成 Session/Project/License；Port 本身不承担授权，不挂载到 HTTP/CLI。
- 验收标准：当前投影与完整首次→更正链一致，固定引用完整、不跨项目；旧非初态无链/过时记录拒绝；不初始化/修改/提交；锁保持到调用方结束事务。
- 风险：历史观测不是现在批准；Workflow 与 Item 版本不同；无实际 Owner/Gate，不能凭历史 ELIGIBLE/APPROVED 直接放行。

## 实施

新增不可变 `CurrentChecklistRecord`、`ChecklistBasisObservation`、调用方事务 `CurrentChecklistRecordPort` 与 SQLAlchemy 实现。DTO 校验 typed Scope/项目、状态白名单、版本/UTC/摘要长度、重复/缺失引用、正向依据形状及 nested 值；不将摘要长度当成加密验签或内容已重验。

查询要求显式活动 Session 事务、非零 Project/Workflow UUID 与固定 V1 Item。按写入方相同顺序 FOR UPDATE 锁 Workflow→Item，使用 Core column mappings 避免 Session ORM identity map 旧值。事务锁不修改投影，调用方负责提交/回滚并持有先前的授权事实锁；本 Port 不自行打开事务。

只读取同 Project/Workflow/Item 全部不可变根，按 Item 版本检查从 PENDING/0 开始的完整连续链、前驱身份/结果、阶段定义和 Workflow 版本递增，当前根必须匹配 Item 状态/版本。Workflow 当前锁可以大于记录 after_workflow_version（其他 Item 或工作流活动），不能错误要求两序列相等。缺 scoped Workflow/初态未记录返回 None；旧裸 PASS/缺链/过时投影明确不可用，不返回旧记录，不推断回填。

当前根 refs 使用独立固定快照，保留当时 Scope/状态/版本/Hash/UTC。后续 Evidence 合法变化不会覆盖当时记录；返回 ELIGIBLE 表示历史观测，不是当下 eligibility。FAIL 可以保留 INELIGIBLE/RETURNED 或没有 refs，BLOCKED 不自动恢复。实际 Gate 必须继续经受权 Owner 重验。

## 实际验收

Windows 11/Python 3.13/PostgreSQL 18.6；7 项新单测及完整后端 670 项无失败（2 项既有符号链接环境跳过）。包括不可变/缺依据/重复/Scope/负面事实/畸形证明/事务要求，以及模拟缺根、断链、旧前驱/结果、错误阶段/定义、当前结果及锁版本不一致拒绝。

`validation/wfl-01-a05-p04-current-record/verify.py` 随机隔离库实际 PASS：初态无写、未知 Item、跨项目/不存在 Workflow、首次空 FAIL、带正向 refs 的 PASS、更正前驱、另 Item 增加 Workflow 版本、GLOBAL Evidence/WAIVED 理由影响、Evidence 后续失效保留历史、BLOCKED 下新 FAIL 保存 INELIGIBLE/RETURNED、缺链旧 PASS/过时 current 拒绝。对 Workflow/Item 两条并发更新实际观察 PostgreSQL lock_timeout 拒绝，调用方事务结束后 Workflow 更新成功；读前后数据库快照一致。清理只删除脚本创建的隔离库。

0032 Checklist Schema、0031 Transition 历史、受权初始化/Workflow GET/Windows 两种显式组合的既有脚本回归 PASS。Review/例外仍为合成身份，License 与相关组合信任源为合成；本内部 Port 未验证公开 Permission/License 接线，也未调用实际业务 Owner。

开发 wheel 构建/包含新 Port 与 Repository PASS；SHA-256：`209ee52a0a4cbc3e2990d18897ce177575a22c01725031211f3493235b0cea1a`。不是最终安装程序包。

## 兼容、回滚与后续

无 Migration/API/依赖/总体架构变化；需要现有 0032，升级无新增数据库动作。回滚不装配此内部 Port，既有事实及历史不变。完整链读取成本随单 Item 更正次数增长，性能/覆盖率未测，后续需在实际 Gate 性能任务验收，不能宣称 P95 已达标。

Server 2025 未运行，Debian 13 按用户要求暂不验证；目标兼容性不删除。实际 Review/例外 Owner、受权记录命令、Gate evaluator/固定记录关联、START/完成、生产信任源与可用程序包仍待。Gate 3 未通过。

Next：WFL-02-A01-P04 GateItem 固定 Checklist 记录关联设计/前置核查；保持旧历史不改写，不将裸状态或合成批准当 Gate 证明。
