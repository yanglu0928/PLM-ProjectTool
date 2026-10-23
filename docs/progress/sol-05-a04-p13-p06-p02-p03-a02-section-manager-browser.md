# SOL-05-A04-P13-P06-P02-P03-A02：负责人章节送审浏览器验收

日期：2026-10-23。状态：`WINDOWS_EDGE_PG_PASS`（仅合成负责人和客户确认人）。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前 Phase/WBS | Phase 2 / SOL-05-A04-P13-P06-P02-P03-A02 |
| 输入基线 | 冻结SectionVersion `/api/v1`、CR-SOL-022/024/025，P13-P05-P03/P06-P01真实PG与P06-P02-P02前端合同 |
| 前置 | A01合成客户真实Edge/PG待办、固定版本、批准链通过；P03合成PG送审通过 |
| 单一问题 | 真实Windows 11 Edge中项目负责人能否对固定章节完成VALIDATE→选当前合格客户→点击送审并得到准确Review回执 |
| 模块/实体/API | 仅隔离验收夹具；SectionVersion、Review、Member、Trace及审计；登录、项目成员LIST、Section GET/VALIDATE/:submit-review、Review GET，均不改合同 |
| 权限 | 合成PROJECT_MANAGER送审、合成CUSTOMER_MEMBER候选；当前License/Session/CSRF与服务端六维重证不可绕过 |
| 验收 | 一次性PG种入完整来源但不预先送审；Edge真实登录/验证/选择/提交201；同Key回放首结果，PG只一Review/Round/START/Audit；合成客户终态复用A01证据，不冒称真人签署 |
| 风险 | 合成信任源和测试服务账户不等于正式发行；页面若暴露合同漂移，先登记偏差再修复；不接客户数据或外部AI |

无预期Schema/API/正式信任变化；隔离测试目录可撤，历史业务事实不删。首次故障及修复记录在本文件，PASS仅凭实际脚本exit0。

## 实际验收

Windows 11 / Edge 155 / 生产构建 Vue / 真实 ASGI / 一次性 PostgreSQL 18.6 上，先由既有夹具建立固定Section与已批准需求/规格/证据、精确 ACTIVE Trace，但不预先送审。Edge真实登录合成PROJECT_MANAGER；页面在验证前隐藏送审；点击VALIDATE得到六维当前就绪，再从真实项目成员LIST选择合成CUSTOMER_MEMBER，点击送审获得201与Review链接；同Key同体浏览器回放201，重新读取Review可见固定章节。PG断言SectionVersion转IN_REVIEW，Review/Round/START结果/幂等收据/审计各一。脚本exit0。

本片只新增隔离浏览器/PG验证脚本，没有生产代码、Schema/API、角色、License或客户数据变化，前端全量回归沿用A01的1857通过结果，本片未重跑。A01已独立验证合成客户待办→固定章节→批准/历史，但两片不是同一次浏览器会话，不等于真人客户确认或UAT。临时Profile/PG由夹具清理；正式信任、Gate3、Pilot及三平台发行继续未通过。

下一项：`SOL-03-A06-P03-A03` 回到Outline当前覆盖证明；先复核已批准Section、精确RequirementVersion/Trace集合及旧A02阻塞是否真正解除，不能以Section已批准自动推定Outline覆盖PASS。
