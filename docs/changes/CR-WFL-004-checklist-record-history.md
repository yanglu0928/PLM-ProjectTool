# CR-WFL-004：Checklist 追加记录与受控更正

日期 2026-09-26；设计 WFL-01-A05-P01；状态 DOMAIN_SHAPE_IMPLEMENTED / SCHEMA_APPLICATION_PENDING。P02 已验证不可变快照形状；两表/0032、真实 Owner/Gate/命令未完成，不能据此判记录链 Schema PASS。
依据 DM-02 ChecklistItem/WAIVED、API-02 WORKFLOW_CHECKLIST_RECORD、SC-01 WFL-01、CR-WFL-001/002/003；用户持续授权 V1.1。原冻结 `64cdf09` 和 0030/0031 不覆盖。

## 证据与差异

现有 0030 的 ChecklistItem 仅保留 item_state 与 lock_version，允许后续更新；没有每次记录的 actor/trace/理由/依据历史。DM-02 状态图列出 PENDING→PASS/FAIL/WAIVED，却未展开后续资料补全或重新评估的更正方式。只覆盖当前值会丢失依据；拒绝所有更正又无法处理 FAIL 后补证或 Evidence 撤销。

采用追加更正：首次 PENDING→PASS/FAIL/WAIVED；后续在当前阶段内可重新记录 PASS/FAIL/WAIVED，每次递增 Item 与 Workflow 乐观锁，追加新记录并引用上次记录，旧记录不改。不允许回 PENDING，不允许对已完成/未进入阶段静默修改，不允许把 WAIVED 作为改写失败质量指标的快捷方式。新 PASS 必须独立重新证明，不因旧 PASS/WAIVED 继承批准。

这是明确的更正语义补充和 owned Schema 增量，不扩大业务 Scope、改栈或破坏冻结请求字段。安全放行仍是真实 PM/Session/CSRF/License/非归档/If-Match/持久幂等及 Owner 事实证明；AI 不能批准客户事实。

## 比较与采用

- A：只更新当前值/Audit 摘要，无法完整还原引用与被替换记录，拒绝。
- B：将全部记录正文复制成 JSON，缺 FK/类型/Project 与查询保护，拒绝。
- C（采用）：增加 WFL-01 owned `wfl_checklist_records`、`wfl_checklist_record_refs`，同事务保留前后状态/Item 与 Workflow 锁版本、supersedes/actor/trace/UTC/用户提供理由影响和当时依据事实；结构不复制客户正文。

PASS/WAIVED 必须具备服务端已证明的固定 Evidence 与相应 Review；Review 引用从 Owner 解析，不新增请求必填字段。WAIVED 再要求批准例外/理由/影响。FAIL 可以无依据集合，表示当前不能满足；reason/impact 遵从冻结可选字段，不伪造来源或批准，也不能据 FAIL 推进。未提供的理由不由 AI 填成正式客户意见。

## 迁移、回滚与验证

计划在 0031 后独立 0032 创建两表，不改变旧状态、不伪造旧记录、不新增“已确认”数据。采用 unique(workflow,item_key,after_item_version) 查当前记录，暂不向当前表加入 latest 指针或循环 FK。旧 PENDING/0 可开始新链；旧非 PENDING 或版本不为 0 却无可信历史链的实例保持原值，后续写服务拒绝并转可追溯修复，不凭空回填。

根记录与引用只允许一次事务插入，数据库强制创建事务标识；提交后 UPDATE/DELETE/TRUNCATE/补写子项拒绝。supersedes 必须同 Workflow/项目/item，且匹配当前记录版本/状态，不能指向未来或循环；提交时核对 Item/Workflow 结果与锁递增，不允许只有历史或只有服务成功声明。

0031 GateItem→ChecklistRecord 的明确关系尚缺，后续独立增量补可查询固定引用，保留旧 Gate 快照原样；新 Gate 运行放行必须证明当前记录链并保存引用，在补齐前仍不开写路由。这不是永久省略原 Trace/Gate Scope。

升级前备份；任一记录/引用存在时拒绝破坏性 down，空表才允许。应用回滚不装配相关服务，保留两表和旧记录。验证须空库/有数据 up/down/re-up、旧状态不变、ORM parity、初次/重复/更正链、合法/缺项/伪造依据/跨项目/跨 Item/锁冲突/并发/审计故障全回滚、追加封口、真实授权/Owner/HTTP 拒绝矩阵与回归。结构测试使用合成 Review 不代表实际 Gate。

分步实施：P02 不可变纯领域快照；P03 ORM/Migration/隔离结构；后续当前记录 Query、Gate 记录关联、内部受权命令/Owner 查询及 HTTP。Review/例外或业务 Owner 未具备时失败关闭并转独立 Platform Core 前置，不跨 Phase 编造业务事实。

风险：Review/例外表与批准 Port 当前缺失；多态引用不能仅靠 UUID 判存在/授权。Evidence 观测状态可变须锁定/保存指纹和版本。所有真实 Owner/性能/Server 2025/发行验收仍待；Debian 13 暂不验证。
