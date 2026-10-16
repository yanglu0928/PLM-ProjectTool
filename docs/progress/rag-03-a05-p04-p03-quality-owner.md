# RAG-03-A05-P04-P03：受权业务质量证据登记 Owner

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_EMBEDDING_INDEX_QUALITY_OWNER_PASS`

## Changed

- 新增 `RAGEmbeddingIndexQualityService` 与 PostgreSQL 仓储，登记前要求真实 Session/CSRF、当前角色和 License 重验。PROJECT Index 只允许 ACTIVE Project 的 ACTIVE ProjectManager；GLOBAL Index 只允许 ENABLED DeploymentAdmin。
- 调用方只提交数据集/隔离声明/评估制品 SHA-256、样本数、正确数和三项安全结论；不接收 Query、Golden Answer、客户或文档正文。
- PASS/FAIL 不由调用方输入；服务端用整数 basis points 重算分类与精确引用，固定门槛 9000/9800，并必须同时满足 Project 隔离、零越界引用和失败关闭。
- 幂等范围为操作人/Project/`V1_RAG_INDEX_QUALITY_REGISTER`/键；历史重放会再次验证 Session、角色和 License，不能借旧回执绕过撤权。证据、Audit 和幂等回执同事务提交。
- FAILED 质量是正式不可变证据，不因后续 PASS 被覆盖；本 Owner 不改 Index 状态，`READY→ACTIVE` 仍由 P04 独立原子 Owner 负责。

## Compatibility / rollback

- 本项是 Schema0087 上的内部应用/仓储增量，无新 Migration、公开 `/api/v1`、依赖或 Provider 协议变化。
- 停用组合根中的新 Owner 即可阻止新登记；已产生的 Quality/Audit/幂等证据依 Schema0087 保留，不删除或改写伪造回滚。
- Windows Server 2025、Debian 13、正式业务数据集和真实 Provider 不在本分项验证范围。

## Tests

- Windows 11 / PostgreSQL 18.6：从真实 Schema0087 READY Index 出发，以真实 Session/CSRF 和 ProjectManager 登记 FAILED `48%/74%` 与 PASS `90%/98%`。
- 错误 CSRF、License 失效、幂等载荷冲突、Audit 故障回滚和 ProjectManager 撤权后历史重放全部失败关闭；同载荷重放返回不可变原结果。
- 两份质量证据、Audit 和 completed receipt 数量一致；故障尝试不留半结果；Index 终态仍为 `READY/v2`。
- RAG 定向 76 项通过；后端全量 2448 项通过、3 项条件跳过。
- 洁净 wheel 安装后 RAG 76 项通过；SHA-256 `87657be4c06848d3fd85dd044c4f1fd2f81f6b5827e7163baa3b51ffc73e5350`。
- 零真实 Provider I/O、零客户数据外发、零 Secret 入库。

## Validation correction

首轮验证使用了与既有发送边界 fixture 不一致的合成正文，在 Provider 调用前被 payload fingerprint 断言拒绝。改回该 fixture 的公开固定输入后用全新随机数据库完整重跑通过；产品指纹或数据库守卫未放宽。

## Known issues / Next

两组数值都是隔离合成机制证明，不是新独立业务质量证据。进入 `RAG-03-A05-P04-P04` 实现当前事实重验、同用途旧 ACTIVE 退役与新 Index 唯一 ACTIVE 原子切换；正式 ACTIVE、Gate 3、UAT 和发行包继续保持未通过。
