# SUR-04-A02：SurveyConclusion 五表与 Migration 0109

日期：2026-10-07。结论：`SUR_04_A02_CONCLUSION_SCHEMA_PASS`。下一项：`SUR-04-A03` 类型化来源
proof adapters。

## 编码前检查与范围

- 依据CR-SUR-009，仅实现冻结SRV-05五表的ORM、Migration、数据库保护和验证；不开放Owner、HTTP、
  Review、Trace或Workflow写入，不创建客户事实。
- Migration head由0108推进为`20261007_0109`。无第三方依赖、Secret、外部AI或客户数据外发。
- Root在本阶段只接受初始DRAFT；五表UPDATE/DELETE/TRUNCATE全部失败关闭。A06才会用独立迁移开放
  Review状态投影。

## 实现

- `srv_conclusions`：显式series/version、Project/Survey、规范化Round/AI Task固定引用、内容指纹、
  声明计数、supersedes和Review投影。新series必须v1，后继必须同series/Project且同Survey连续升版。
- 部门/模块结论：有序不可变内容、可空VALIDATED链尾Response refs；预留结构化
  `SCOPE_EXCLUSION/RISK_ACCEPTANCE`五字段并要求Evidence+Review完整形状。因正式决定Owner尚未实现，
  后续应用Owner首版仍会拒绝用这些字段解除阻断。
- Evidence refs：`SUPPORT/CONFLICT`、固定DocumentVersion、Evidence lock/content fingerprint；数据库
  重证PROJECT/ELIGIBLE/AVAILABLE/ACTIVE快照。
- Open issue refs：首版只允许同Project `handover/HND-03`，固定state和lock snapshot。
- Root插入重证全部Round为同Project/Survey的CLOSED，AI refs为同Project已成功`SURVEY_ANALYZE`；
  子项Response refs必须为同Project、VALIDATED且无后继更正的链尾。
- 延迟collections trigger要求四类owned集合实际行数与Root声明一致；空历史可降级，有任意五表历史拒降。

## 验证

- 定向：11项测试、27项subtests通过；Migration head/down-revision、五表Project scope、typed FK/CHECK、
  失败关闭guard、ORM inventory和离线/有历史拒降均覆盖。
- Windows 11 / PostgreSQL 18.6：0108带既有User升级0109并保留、drift=0、空历史
  0109→0108→0109、CLOSED Round、VALIDATED链尾Response、Evidence/HND-03 snapshot、v1→v2连续series、
  immutable负例及有历史拒降全部通过；临时数据库已删除。
- 后端全量最终`2911 passed / 3 skipped / 4230 subtests`。首次全量曾因历史ORM inventory未登记五张
  新表得到`2910 passed / 3 skipped / 1 failed`，补清单后定向及全量均重跑通过；没有隐藏该偏差。
- 最终开发wheel含1087项，0109与Survey ORM均存在，SHA-256
  `c2381c00b1ecde3a123e438ca5427067088255dd754e1603a47ddc71004198f2`。它仅是开发验证制品，
  不是可用安装包。

已知未完成：A03来源公共Port、A04 create/list/get、A05 validate、A06 Review、SUR-05 HTTP/UI、
SUR-06 Workflow资格、Windows Server 2025、Gate 3、UAT和发行包。

