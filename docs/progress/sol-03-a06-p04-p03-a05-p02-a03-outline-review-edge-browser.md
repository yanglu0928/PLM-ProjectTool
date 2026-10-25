# SOL-03-A06-P04-P03-A05-P02-A03：方案大纲送审与客户批准真实浏览器链

日期：2026-10-24。状态：`PASS`（Windows 11隔离PG18.6/合成身份/真实Edge）。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前Phase/WBS | Phase 2 / `SOL-03-A06-P04-P03-A05-P02-A03` |
| 输入基线 | 冻结SOL-03送审、统一Review读/列表/决定，A05-P01同库现时重证，A05-P02-A01/A02前端 |
| 前置任务 | 完整合成Requirement/Section/Trace来源PG验证，SOL-03合成客户HTTP终态与前端合同均已验；本机Win11 Edge、PG18、前端构建可用 |
| 涉及模块/实体 | 仅一次性验收脚本与隔离应用组合；不改生产功能或实体 |
| 涉及API | SOL-03版本GET、送审POST、Review列表/详情/决定既有`/api/v1`接口 |
| 涉及权限 | 合成项目负责人及独立合成客户会话；跨项目零内容残留；浏览器不使用测试账户作生产信任 |
| 验收标准 | 真实Edge负责人选择客户送审201→客户待办发现SOL-03→打开固定版本→批准200→待办消失/历史保留；PG版本/批准指针/结果/Audit闭合；退出0且临时库/浏览器档案清理 |
| 风险/回滚 | 仅隔离临时PG/随机端口/合成身份；不接客户资料、外部AI或生产账户。不通过时记录真实失败并修复，不虚报Pilot/Gate |

验收只证明Windows 11隔离合成环境的浏览器链，不证明默认Windows生产组合、正式信任、真人签署、离线安装或三平台发行。

## 实施与验收

- 新增自拥有loopback/一次性PG18.6验收夹具，复用已验完整Requirement、Section及Trace当前来源，创建SOL-03 DRAFT并在隔离HTTP预检`order/source/coverage`三维PASS，再启动显式完整Review/Outline读写组合与生产构建Vue。
- 真实Edge `155.0.4283.62`：合成项目负责人登录、选择当前项目客户确认人、明确核对范围后送审201；独立合成客户登录，从服务端Review待办发现“方案大纲”、打开本轮固定OutlineVersion、返回Review批准200；待办消失、历史APPROVED保留；跨项目页面无前项目评审残留。浏览器无未处理异常，PNG渲染检查通过，脚本exit0。
- 隔离PG核对OutlineVersion `APPROVED`、大纲根当前批准指针指向该版本、单Review/单决定、两条START/APPROVED不可变结果及单批准Audit。随机端口、临时数据库/文件和Edge档案由夹具清理；合成登录密码只在进程环境传给子进程，未写入仓库。
- Python语法和Node脚本语法检查通过；前序A05-P02-A02前端全量1867项/typecheck/build已通过，本WBS未修改生产程序，未重跑后端全量单元测试。

## 边界与后续

无生产代码、Schema/API/权限/License变化。可撤本独立验收脚本而不触动评审历史；不删除真实数据。下一WBS需将已验的Outline送审/Review显式组合安全接入默认Windows受控启动，并继续正式信任来源与离线安装/升级。真实客户签署、Pilot/Gate 3及三平台Release仍未完成。
