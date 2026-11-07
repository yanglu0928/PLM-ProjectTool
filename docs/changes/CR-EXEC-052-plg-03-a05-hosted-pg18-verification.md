# CR-EXEC-052：PLG-03-A05 Admission Owner Hosted PG18 针对性验收

- 日期：2026-11-07
- Phase/WBS：Phase 2 Platform Core / PLG-03-A05
- 状态：编码前检查完成，待新增托管验收器与独立复验
- 基线：CR-EXEC-050、CR-EXEC-051；冻结 PluginExecution schema、Jobs/Output/Audit contracts 不变
- 类型：验证范围补齐；仅新增 Hosted synthetic PG18 验收器及调用点，不改产品API、DB Schema、Migration、默认组合或Worker

## 发现与证据

CR-EXEC-051 实现已提交并通过静态复核。锁顺序修正先登记于 CR-EXEC-051：精确拒绝非整数 attempt，且避免在已锁定 Installation 后逆序锁定不可变 Package/Manifest。

Hosted run [42326604885](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42326604885) 证据：
- Backend 全量 4,105 tests、wheel；Frontend tests/build；同一提交的 embedded runtime、parent package、A17 candidate assembly 均成功。
- P25 real HTTP/Edge failure-closed 通过；A17 packaged PlanVersion/HTTPS/PostgreSQL 流程通过。
- A05新增单元用例纳入Backend全量，但该套件使用应用测试端口/mock，未在PG18实际调用Admission Owner/Repository/Audit；因此A05数据库验收标准尚未满足，不得标PASS。
- 同次run的SUR-07-A08仍因 child initdb.exe exit 3221225781失败；TEMP环境探测同码，且未应用，按CR-EXEC-039维持停止。父包P40在history-ready阶段失败，安全诊断仅显示登录200、output-request history GET 200、无网络失败、无运行时异常、无summary；两者均非本WBS，不在此处顺手修复。
- 公开/生产Publisher trust仍为空；真实Worker未接线；不能执行插件。

## 编码前检查与计划

- 输入：PLG-03-A05 Owner/Repository/Application tests、PLG-03-A01 migration verifier、父包PG18 lifecycle smoke。
- 缺口：当前PG18 smoke验证迁移和其他Owners，但没有对新Admission Owner作数据库调用；A05只获得4,105项应用回归，不能替代该证据。
- 唯一任务：增加独立Windows Hosted D盘 PG18 验收器，并从既有临时PG18 smoke在migration及PLG-03 schema完成后调用。
- 验收：在独立合成数据库上迁移至当前Head，使用真实SQLAlchemy UoW、Plugin Execution Repository及AuditService；Jobs fencing/Output admission仅注入显式synthetic ports，不伪装为正式信任或客户事实。验证 PENDING root、state event、Audit 同事务持久化；相同绑定重放不增加记录；审计失败整体回滚；invalid attempt/stale claim在零持久化时拒绝；数据库guard关闭时写入仍失败。数据库及临时文件严格归GitHub Hosted runner D盘当前run，清理仅限自有随机数据库和目录。
- 本验收不得安装/启动/运行插件，不开启Worker，不发客户数据，不加入生产装配。回滚为移除验收器/调用点；无需数据迁移。
- 前置数据：只合成Project/User/OutputRequest/ContextSnapshot/Plugin package/install/manifest/Job；Publisher trust及用户客户数据均不参与。
- Secret scan：提交前扫描全部新增/修改文件内容；Hosted Windows runner执行语法、PG18 smoke与后端全量/wheel。

## 偏差边界

本次补验是关闭原已批准验收标准的证据缺口，不更改冻结Schema、授权语义、模块边界或正式范围。A08/P40失败保持单独记录并在有独立可行路径时处理；不将整体非全绿run表述成全通过。
