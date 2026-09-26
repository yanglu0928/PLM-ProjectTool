# CR-WFL-002：Workflow 持久层与状态语义补充

日期：2026-09-26；当前任务 WFL-01-A03-P01；状态 DESIGN_RECORDED / IMPLEMENTATION_PENDING。
依据：DM-02 Workflow、SC-01 WFL-01/WFL-02 映射、SC-02 M-PRJ/A-PRJ、API-02 Workflow、CR-WFL-001 配置 V1。原冻结提交 `64cdf09` 不修改。

## 冲突与方案

1. DM-02 同时允许 Stage BLOCKED、要求 current_stage 与 ACTIVE 一致，却未规定阻断时指针。方案 A 不使用 BLOCKED，会失去已有状态语义；方案 B（采用）将“当前工作阶段”定义为 ACTIVE 或 BLOCKED 中唯一一个，Workflow 仍 ACTIVE。BLOCKED 不是另一个阶段，指针不移动；满足 Gate 后由受控操作恢复 ACTIVE，再按顺序推进。这个一致性补充必须进入迁移/应用校验，不能静默扩展。
2. COMPLETED Workflow 的 current 指针未规定。方案 A 清空，丢失当前 DTO 的终点定位；方案 B（采用）保留最后一个已完成阶段 key。NOT_STARTED 指针为空；ACTIVE 指向唯一 ACTIVE/BLOCKED；COMPLETED 指向最后阶段且全部阶段 COMPLETED。
3. 冻结 transition 只接受目标阶段 key，没有最终完成命令语义。不得新增 COMPLETE/DONE 虚构阶段，不得把 PLAN→PLAN 当推进。本 CR **不定义也不启用最终完成 HTTP**；后续单独完成 API 增量设计和验收，持久层可表示终态但不等于有生产写路径。
4. 一个 Project 恰有一个 Workflow；已有 Project 尚无 Workflow 表。迁移只创建结构，不凭空给现有项目指定进度/确认。初始化回填与未来 Project 创建接线为后续独立应用任务，必须一次事务创建 NOT_STARTED 和完整 V1 阶段/清单；初始 Checklist 全 PENDING。未完成接线前不能宣称恰有一个或挂载业务写路由。

## 范围、风险与控制

- 采用用户持续自主授权；这是明示状态语义修订和 Schema 增量设计，保留基线历史。无栈/Scope/License 改动，无新依赖，无客户确认或正文产生。
- 四张 WFL-01 表按已冻结名称，跨父对象以复合 FK 防漂移；所有定义内容固定到实例，不接受 latest 自动升级。
- 风险：多行状态不一致、直接 SQL 绕过 Gate、历史 Checklist 被覆盖。数据库负责归属/状态结构及定义只读，真实 Gate/PM/License/Review/Evidence 与历史/Audit 必须由同事务受控服务证明；数据库结构不能代替授权事实。
- 当前任务仅设计。后续迁移独立 review/up/down/空库/有数据验证；禁止仅凭 ORM 通过宣称完成。
- WFL-02 成功迁移与 Gate item 历史为后续独立 Schema；Checklist 记录须有独立追加事件/快照设计，不用更新字段抹去历史。相关公开写路径一直关闭直到历史、授权与验收完备。

## 迁移/回滚/验证

- 计划增量 `20260926_0030` 创建 WFL-01 结构，不修改既有表或事实。生产升级前备份；有 Workflow 数据时拒绝破坏性 downgrade，回滚采用代码不装配与保留表。
- 不自动回填项目进度；初始化另有幂等/并发/失败回滚验收。未来定义变更另发版本/CR，不能覆盖 V1 实例。
- 验证：四表 ORM parity、项目/父子复合归属、键/顺序唯一、初态、可延迟事务内全阶段/清单一致性、状态/指针、历史不可删除、空库 up/down/再 up、有既有 Project 升级不变、有 Workflow 非空 downgrade 拒绝。真实数据库脚本不得连接生产。
- 实际结果追踪 `docs/progress/wfl-01-a03-p01-persistence-design.md` 与后续 P02 Schema 报告。本 CR 记录并不代表约束已实现。
