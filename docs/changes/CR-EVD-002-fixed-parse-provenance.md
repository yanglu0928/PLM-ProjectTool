# CR-EVD-002：Evidence Viewer 固定解析来源

日期：2026-10-01。状态：方案已选，实施与验收进行中。来源：`EVD-01-A03-P04-A03-P01` 编码前核查。原冻结基线保留在提交 `64cdf09`，本 CR 是后续增量，不追写原文。用户依 V1.1 持续授权自主实施可追溯的最小兼容调整。

## 冲突与证据

冻结 DM-03 要求 Viewer 对不可变 DocumentVersion 的 typed locator 与 content_fingerprint 重新证明。创建命令对非 `DOCUMENT` 必须给出并已证明固定 `parse_record_id`，但现有 `evd_evidence_records` 只持久化 locator 和摘要；除 `STRUCTURED_NODE` 外，locator 不含 ParseRecord 身份。同一 DocumentVersion 可以并存多个成功的 Parser 版本/尝试，按“最新”选择会把旧 Evidence 指向另一解析结果。通用幂等收据只存请求摘要，无法反推出原 ParseRecord。

## 方案比较与选择

- A：Viewer 枚举同版本成功 ParseRecord，按 locator/摘要猜测匹配。多批次相同内容可歧义，成本无界；不采用。
- B：Evidence 增加内部 nullable `source_parse_record_id`，新非 `DOCUMENT` 候选必须将已证明的 ParseRecord 同事务写入；`DOCUMENT` 为空。Viewer 只读取该固定来源并复验版本、范围、解析结果、locator 和摘要；采用。
- C：给所有公开 locator 类型加必填 ParseRecord 字段。破坏冻结 `/api/v1` locator 形状和旧调用方；不采用。

## 基线差异与影响

仅增加内部 Evidence ORM/Schema 字段及创建/重放一致性校验，不修改冻结公开 Evidence 创建/读取合同，也不改变定位器 JSON。新外键引用不可删除的 ParseRecord；跨版本/Project/状态仍由 Document 授权读取和证明服务校验。不得把短摘录当权威原文，不返回私有路径。`STRUCTURED_NODE` 的旧来源可从既有 locator 确定性迁移；其他旧非整文档证据无法证明原解析批次，保持 NULL 并让 Viewer 失败关闭，元数据读取保留。不得根据当前/最新解析记录回填。

## 迁移与回滚

独立 Alembic 增量添加 nullable 列、外键与必要约束；先迁移结构，确认旧行均可读取，再将旧 `STRUCTURED_NODE` 的合法 `parse_record_id` 确定性回填。非 `DOCUMENT` 新写入由创建服务强制非空；DB 写入保护只约束新行，避免已有不可证明数据被改写为虚假来源。升级验证覆盖空库与含旧整文档、结构化节点、其他非整文档记录；有异常旧结构化引用时迁移拒绝并保留原库，不静默丢弃。回滚须先停写/排空；若已存在非空新来源的 Evidence，保留历史并拒绝降级，不删除该字段；仅空表或所有记录来源为空时允许安全降级。没有生产数据库变更授权时只在隔离 PostgreSQL 验证。

## 验证计划与剩余风险

执行 ORM/Alembic up/down、空库/有数据迁移、外键/状态/不可变保护、创建同事务/幂等重放、跨批次与跨项目失败关闭、Document 撤销与源字节/ParseResult 篡改失败关闭、后端回归和 wheel。随后单独实现内部 Viewer descriptor、可选 HTTP、Windows 组合与前端定位。旧非结构化证据仍可能没有可恢复的解析来源；Viewer 返回稳定不可用错误，不猜测。正式运行账户、Server 2025/Debian、真实文档、性能和 Gate 3 仍需各自证据。
