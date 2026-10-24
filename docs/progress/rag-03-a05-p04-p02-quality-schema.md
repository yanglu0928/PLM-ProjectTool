# RAG-03-A05-P04-P02：不可变业务质量与激活证据 Schema

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_EMBEDDING_INDEX_QUALITY_SCHEMA_PASS`

## Changed

- 新增 Schema0087 与 ORM：`rag_embedding_index_quality_results` 保存数据集/隔离声明/评估制品 SHA-256、固定策略、样本及正确数、Project 隔离/越界引用/失败关闭结果；不保存 Query、Golden 答案、客户或文档正文。
- 数据库固定样本数 50～10000、分类门槛 9000、精确引用门槛 9800 basis points，并从正确数重算实际值。FAILED 证据可保留；PASSED 必须同时通过隔离、零越界引用和失败关闭检查。
- 新增不可变 `rag_embedding_index_activation_results`，精确绑定目标 Index、QualityResult、可选旧 ACTIVE、操作者、Audit、Trace 与新旧锁版本。
- Index 守卫增加 READY→ACTIVE 与 ACTIVE→RETIRED 分支；deferred validator 要求同事务 ActivationResult，重验最新质量结果、当前 Model、来源 Chunk/指纹、全部构建授权和同用途唯一 ACTIVE。直接更新 ACTIVE/RETIRED 不能提交。
- 本分项只建立数据库边界；生产代码尚无登记或激活写服务，正式环境没有由本项创建 ACTIVE。

## Migration / Compatibility / Rollback

- Migration：`20261004_0087`，从0086追加两张不可变表并扩展 Index 状态守卫。
- 空历史可降0086；存在 Quality/Activation 历史或 ACTIVE/RETIRED Index 时拒绝降级，必须向前修复。
- 无公开 API、依赖、Provider I/O 或客户数据外发变化。Windows Server 2025、Debian 13、正式性能不在本分项验证范围。

## Tests

- Windows 11 / PostgreSQL 18.6：空库 upgrade/down/re-up、Alembic drift 0。
- 真实 Schema0086 READY 前置后，登记明确的隔离合成 FAILED 48%/74% 与 PASSED 90%/98% 元数据；失败证据不能激活，证据不可改删。
- 直接 READY→ACTIVE 因缺 ActivationResult 被 deferred validator 拒绝；同事务 Audit、ACTIVE 与 ActivationResult 可提交，唯一 ACTIVE 基础生效。该临时 ACTIVE 只存在于用后即删的合成数据库，不是业务质量证明。
- 非空质量/激活历史拒降；质量表确认无 Query/Golden/客户正文列。
- RAG 单元 70 项、Migration/ORM Metadata 7 项通过；后端全量 2442 项通过、3 项条件跳过。
- 洁净 wheel 安装后确认从 wheel 路径导入，隔离 77 项通过；SHA-256 `bbe7b7b1159ec282d762e0215d696c207a5e6df64c42bd83fb177babdd418c02`。
- 零真实 Provider I/O、零客户数据外发、零 Secret 入库。

## Validation corrections

- 首轮空库迁移发现 PL/pgSQL 比较 `CASE` 表达式需要显式括号；仅修正 SQL 语法后以全新库重跑。
- 首轮 drift 检查发现 ORM 未声明两项数据库默认门槛；补齐 `9000/9800` server default，未降低门槛，并全新重跑 drift 0。
- 首轮 P02 验证脚本误调用不接受回调的中间 fixture；改用既有发送边界 fixture 的公开回调入口后，以全新随机数据库完整重跑。
- ORM Metadata 首轮准确发现两张新表未加入显式登记清单；补齐清单后相关 7 项及全量回归通过。

## Known issues / Next

进入 `RAG-03-A05-P04-P03` 实现受权质量登记 Owner。仓库仍没有新的独立达标业务证据；隔离合成值不进入正式库，真实 ACTIVE、Gate 3、UAT 和发行包继续保持未通过。
