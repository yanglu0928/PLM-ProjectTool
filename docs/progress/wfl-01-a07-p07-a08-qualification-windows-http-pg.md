# WFL-01-A07-P07-A08：Checklist资格预览Windows真实HTTP/PostgreSQL闭环

日期：2026-10-06。结论：`WFL_01_A07_P07_A08_WINDOWS_QUALIFICATION_HTTP_PG_PASS`。

## 完成范围

- 新增Windows资格预览生产组合，复用真实Session、License、ProjectManager/ACTIVE
  Project授权、完整Workflow读取及Handover当前事实Owner。
- 仅在显式`platform-write`挂载；默认应用、登录模式和只读平台保持关闭。
- 真实Win11/PostgreSQL 18.6一次性数据库中，使用Approved Handover/Review、固定
  Document字节、PROJECT Evidence、Capability、AI和VERIFIED Action完成GET。
- 响应只含最小Evidence/Review/Handover Version身份、当前Item、强ETag和
  `Cache-Control: no-store`；匿名、额外query及未注入路径分别失败关闭。
- Handover验证夹具的调用前后业务快照一致，证明预览未形成业务写入。

## 首轮失败与修复

真实投影首轮返回503，定位为服务按`stages[0]`取当前Handover；生产Repository返回完整
六阶段且首项为Kickoff。修复为按`workflow.current_stage`精确定位，并让单元夹具使用真实
阶段状态。下一轮仍503，定位为组合误用要求CSRF的`SqlAlchemyProjectWriteAccess`；GET
改用只读Session Port，Project授权仍调用`WORKFLOW_CHECKLIST_RECORD`，未扩大角色或状态。

## 验证、兼容与剩余

- 资格/Application/HTTP/Windows组合/生产入口定向45项通过。
- 后端全量2765项运行，3项按既定条件跳过，0失败。
- Win11/PostgreSQL 18.6迁移、Alembic check、真实HTTP与临时数据库/文件清理通过。
- wheel模块纳入检查通过，SHA-256：
  `83664a5775c80974310f423d756b8c3d3d886a177f0af6fd303fb3ea976155f3`。
- 无Schema/Migration、依赖、Secret、外发或冻结写DTO变化；撤资格Router注入即可回滚。
- 前端页面与真实浏览器、CLOSED Trace Target Owner、20并发、正式信任、Gate 3/UAT和
  可用发行包仍未完成。下一项：`WFL-01-A07-P07-A09` 前端资格预览与Checklist记录页面接线。
