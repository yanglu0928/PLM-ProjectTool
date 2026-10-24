# SOL-03-A06-P03-A05-P03-A05-P02：同库完整来源验收

日期：2026-10-24。状态：`PASS`（Windows 11 / 隔离 PostgreSQL 18.6，合成身份与来源）。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前Phase/WBS | Phase 2 / SOL-03-A06-P03-A05-P03-A05-P02 |
| 输入基线 | 冻结API-04三维验证；A05一次性PG真实来源失败关闭证据；现有正式Requirement版本/Review、Section版本/Review、Trace Owner |
| 前置任务 | Windows显式Outline VALIDATE已装配；现有Section客户合成批准夹具具备真实Document/Evidence/Trace/Spec来源，但Requirement v1为仅供Section消费的简化合成状态 |
| 涉及模块/实体 | 仅隔离验收脚本；RequirementVersion v2、SectionVersion新草稿及其Review/Trace、OutlineVersion DRAFT；不改产品Schema或业务Owner |
| 涉及API/权限 | 复用冻结Outline/Section入口及统一Review，项目负责人/实施成员与合成客户身份；跨项目失败关闭 |
| 验收标准 | 在同一临时PG用正式Owner生成完整Requirement v2并获合成客户评审，再生成/批准引用v2的Section新版本；Outline三维全部PASS，撤Trace后异Key不再PASS，旧Key保留原观察；Audit/Receipt可核查，临时库清理 |
| 风险/回滚 | 旧简化Requirement v1仍在历史中，新v2必须成为最新已批准指针；任何Owner拒绝不得复制角色伪造PASS。测试仅合成项目，不外发客户资料；可撤验收脚本，产品历史不变 |

此处的客户评审是测试夹具，不代表真实客户确认。真实发行信任、Gate/Pilot仍独立验收。

## 验收结果

- 原章节的合成需求v1缺少已声明的1条来源子行。仅在一次性PG测试准备阶段补齐该行及Evidence引用；正式需求v2由Requirement创建Owner生成，并经统一Review合成客户批准。v2的来源/验收标准/能力评估声明数和实际子行均为1；没有降低数据库完整性约束。见DEC-1218。
- 历史章节固定的专项规格指向v1，不适用于新需求v2。新建标准功能章节经正式Owner显式选择`NONE_REQUIRED`并记录理由，创建、精确`REQ-03 → SOL-05`追溯、统一Review批准均成功；没有改写旧章节/规格或伪造正式客户确认。见DEC-1219。
- Outline通过冻结HTTP入口创建，首次现时验证为`order=PASS / source=PASS / coverage=PASS`，`ready_for_review=true`；同Key回放一致。两个同时发起的同Key验证只留下一个持久观察，结果一致。
- 撤销新章节的有效Trace后，用新Key验证得到`order=PASS / source=PASS / coverage=FAIL`、`ready_for_review=false`；旧Key仍读取首次PASS观察。三次不同Key验证对应Audit和Receipt各3条。隔离数据库由夹具清理，脚本退出0。
- 未运行真实客户、正式公钥/受控服务账户、浏览器端到端、20并发性能或三平台发行验收；本项不能推导Gate 3/Pilot/Release通过。

验证命令：`apps/backend/.venv/Scripts/python.exe validation/sol-03-a06-p03-a05-p03-a05-p02-full-source-pg/verify.py`。本片仅增加隔离验收脚本和记录，正式程序与Schema没有变化。后续转`SOL-03-A06-P04-P01`核查并实施Outline统一Review Subject的数据库状态窄门；其前置不得用本片合成批准代替正式信任。
