# CR-EVD-003：模板证据资格与上下文缺口

日期：2026-10-01。状态：前置分析与方案已记录，尚未实施。来源：`EVD-01-A04-P01` 编码前核查。原冻结提交 `64cdf09` 保留；用户的持续授权允许在记录、验证后实施最小兼容调整，不代表 Gate 自动通过。

## 冲突与证据

冻结 DM-03 要求 `TEMPLATE` 只能作为结构/问题参考，不得独立成为客户现状或结论的 ELIGIBLE Evidence；API-02 的 `EVIDENCE_SET_ELIGIBILITY` 只接受 Evidence 身份及目标资格，Evidence 当前状态没有绑定用途或正式主题。当前 EvidenceService 只持有固定 DocumentVersion，无法在同一资格事务内通过 Document 应用边界取得来源文档类别；单独读取再写存在类别/权限与状态的时序风险。直接赋予模板 ELIGIBLE 会让下游误把它当客户事实。

## 方案比较与选择

- A：对所有 Evidence 允许 CANDIDATE→ELIGIBLE，交给未来 Binding 判断模板用途。过渡期间状态会误导 UI 和下游；不采用。
- B：首版模板 Evidence 不可从 CANDIDATE 升为 ELIGIBLE，仅保留候选/结构参考或受权判为 INELIGIBLE；非模板须经 Document 模块同事务来源类别/版本可用性证明和人工命令。未来若 Binding 能证明结构用途，可另建可追溯规则修订；采用。
- C：现在扩展冻结 Eligibility/Binding 数据模型，增加必填用途和客户事实类型。范围与迁移面过大，且 Binding 未实现；不采用。

## 差异、影响与验证

方案 B 比冻结文字更严格：模板在首版不能作为 ELIGIBLE 的结构证据使用，但仍可作为候选的结构/问题参考；不改变 API 字段或历史 Evidence 行。需先为 DocumentService 增加一个当前授权、同事务、固定 DocumentVersion 归属与文档类别读取 Port，再实现 CANDIDATE→ELIGIBLE/INELIGIBLE 受权命令。状态选择暂定只允许候选首次裁定；重复同 Key 返回首次结果，重新裁定须独立设计，不凭空覆盖历史。验证必须包括模板拒绝、真实 PROJECT_RECORD 允许、非成员/降权/跨项目/License/CSRF 拒绝、并发、Audit 回滚及正式绑定前状态边界。若发现已存在正式模板 ELIGIBLE 行，迁移/升级不得自动撤销，须先只读清点与人工复核；当前隔离库不代替生产结论。回滚为关闭资格公开路由，保留历史事件/收据，不删除正式记录。

## 未关闭事项

Document 同事务来源 Port、资格策略/命令/HTTP/目标账户测试及 Binding 用途规则未完成。无生产数据迁移、无 Gate 3 PASS。
