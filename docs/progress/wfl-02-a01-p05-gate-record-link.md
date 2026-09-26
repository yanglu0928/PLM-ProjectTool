# WFL-02-A01-P05 Gate 固定记录 Schema

2026-09-26；0.1.0.dev0；CR-WFL-004；结果 WINDOWS_ISOLATED_SCHEMA_PASS。

## 编码前检查与实施

当前 Phase 2；WBS WFL-02-A01-P05；输入冻结 DM-02/SC-01/API-02、CR-WFL-003/004、P04 关联设计及已验证 0031/0032/当前记录 Query。前置 P04 已记录差异、风险、迁移/回滚及验收后再编码。仅 Workflow GateItem/Record/Refs，不改 API/权限/依赖/技术栈；实际 Review/例外 Owner 缺失不被忽略，本项只 Schema。

ORM 增加三 legacy-nullable 字段与同 Workflow/Project/Item 固定记录 FK；独立自包含 Migration 0033 保留 0031/0032。升级不 UPDATE 旧 Gate，不伪造旧关联；新 BEFORE INSERT 强制记录字段全有、引用已提交 current Record、阶段/结果/版本/摘要一致，不能将修改记录和推进阶段混作一个事务。

deferred 提交保护重核 fixed Record/current Item/Transition 版本与阶段、精确 typed refs 身份/Scope/内容双向集合、不回退观测锁/时间、WAIVED 理由/影响相同。0031 原 Evidence 当前事实/原子投影/封口及不可变保护保留，重观测可以使用后来合法版本；记录操作者不会被 Schema 描述成客户例外批准人。Review/例外只有结构保护，实际 Owner 批准还未验。

验收目标：空/有数据 up/down/re-up、旧原值保留、新无链/跨项目/错误项/过时/失败/依据混入/观测回退拒绝、原子/并发/追加不可变/非空 down 与既有回归；风险是 nullable 兼容漏洞和历史观测冒充现在批准，均使用不同 INSERT/deferred/Owner 边界处理。

## 实际验收

Windows 11/Python 3.13/PostgreSQL 18.6；`validation/wfl-02-a01-p05-gate-record-link/verify.py` 随机隔离库 PASS，清理只针对自建库。

- head 空库 up、0032 down/re-up 与 ORM parity；0032 中真实合成旧 Transition/两个 Gate/refs，以及当前记录更正链升级、down/re-up 后原字段/记录一一不变，新关联保持 NULL。非空旧未关联历史允许移除空新列，旧保护保留。
- 合法当前 PASS/WAIVED 固定记录关联；全部五个相邻阶段迁移实际提交、十个新 GateItem 关联，最后仍 ACTIVE/PLAN，未执行最终完成，不冒称整个流程完成。
- 新 NULL/半套/零 UUID/不存在/跨项目/跨 Item/旧 PASS/FAIL/错误版本/摘要、缺 Gate/refs、额外 GLOBAL Evidence、替换 REVIEW_ROUND 身份/内容、退回观测版本或时间、改变 waiver 理由影响、同事务新 Record 拒绝；每次核对 Record/refs/Workflow/Item/Stage/Evidence 和三表快照，失败无残留。
- 两个相同 expected Workflow 版本并发只有一个成功，另一个 SQLSTATE P0001/current facts mismatch；不是把任意数据库错误作为冲突成功。
- 合成 Audit 故障在完整写后全回滚；不是实际审计命令验证。Evidence 版本从 1 合法增加到 2，记录保留旧 1，Gate 重观测 2 且身份/摘要相同可提交；不要求历史观测版本完全相等。
- UPDATE/DELETE/TRUNCATE CASCADE 拒绝；旧已提交 Gate 不可补固定记录；新增关联非空 down 明确拒绝，拒绝后 head 0033/完整快照不变。

后端 672 项无失败（2 项既有符号链接环境跳过）；新增 2 项 ORM/独立迁移契约测试。0032 Checklist、当前记录 Port、0031 历史控制、0030 实例、受权初始化/Workflow GET/Windows 两模式组合脚本回归 PASS。

0031 历史脚本原裸状态 fixture 明确只在 0032 作为 legacy control 运行，随后升级 0033/验证保留；不是修改新 INSERT 保护让旧 fixture 绕过关联。0033 新路径由独立 verifier 使用已提交 Checklist 记录验收。保留 Alembic generated default 警告的已知限制，先前真实 ALWAYS/生成结果验证仍在 0032/0031 回归执行。

开发 wheel 构建/包含 0033 PASS；SHA-256 `52a71bad36d3c67eebfa076ed049bdc4a1e82ff6e6565e5a3c9da104fa1fcfb6`。未测覆盖率/性能，不是可用正式安装包。

## 兼容、升级与后续

升级前备份，Alembic 至 0033；旧历史不补关联，新 Gate 不接受旧裸状态。应用回滚可不装配写入口并保留历史，新关联非空不得 down；仅空关系列可降级至 0032。无冻结 API/依赖或角色变更。

真实 Owner/Review/例外、Checklist 受权写命令、START/最终完成、Gate evaluator、HTTP/生产信任源尚缺；Server 2025 未验、Debian 13 暂不验证；Gate 3/发行未通过。

Next：RVW-01-A01 统一 Review 的身份/固定版本轮次前置检查与 owned Schema 设计，补齐 Gate 真实批准来源，而非把合成 APPROVED 作为正式业务事实。
