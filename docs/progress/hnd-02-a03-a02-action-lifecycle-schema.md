# HND-02-A03-A02：Schema0099 Action 生命周期完整性

日期：2026-10-05。结论：`HND_02_A03_A02_LIFECYCLE_SCHEMA_PASS`。下一项：`HND-02-A03-A03` Action metadata PATCH Owner。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：HND-02-A03-A02
输入基线：DM-05、API-04、Schema0098、CR-HND-001～003、DEC-852～855
前置任务：Action Create Owner与生命周期前置核查已完成
涉及模块：handover、document、evidence、trace、database migration
涉及实体：HND-03 Root、response/evidence refs、state events、TraceLink FK
涉及API：本项不挂HTTP；PATCH/START/SUBMIT/VERIFY/CLOSE/CANCEL仍无Owner
涉及权限：本项只开放数据库可验证边界，业务角色由后续Owner执行
验收标准：前向状态/取消、投影/事件强锁、owned refs、当前事实、终态、降级与drift
风险：缺引用半提交、事件与Root分裂、Review状态变化阻塞来源、无关Trace关闭、终态复活
```

## 实施结果

- 新增Migration0099，以延迟约束把Root版本、连续事件、提交/验证投影和固定owned refs绑定为一个事务事实。
- 只开放精确前向链和非终态取消；元数据PATCH仍关闭，后续不能借Schema直接跳过Owner权限、License、幂等或Audit。
- 固定DocumentVersion/Evidence按当前PROJECT事实重验；关闭先校验同项目ACTIVE Trace的最低Schema条件，更严格来源/目标由Close Owner负责。
- 修正来源生命周期边界：创建时仍严格要求候选/确认配对，之后只验证固定同项目Item存在，不因进入Review状态而破坏既有Action推进。

## 验证与证据

- Win11/PostgreSQL18.6临时库：空历史0099降升、drift、OPEN→IN_PROGRESS→SUBMITTED→VERIFIED→CLOSED、OPEN→CANCELLED、缺响应整笔回滚、引用不可变、终态拒绝复活和有历史拒降通过；A02真实Create Owner在0099 head回归通过，临时库均已删除。
- 定向12项、后端全量2625项通过，3项按既定环境条件跳过。
- 首次wheel命令把多个文件误作单脚本参数，产生3个加载错误，证据作废；最终开发wheel解包按四个独立测试文件重跑16项通过，SHA-256 `1ee8ef45a636708a8489f460befd2946b65c25f792b4f932f250fb92d8c6446a`。

## 兼容、回滚与未关闭项

内部`0098 -> 0099`仅替换守卫/触发器，无表列、公开API、依赖、配置、网络或外发变化。全OPEN/v0无owned refs历史可降；有生命周期历史拒降。

PATCH/START/SUBMIT/VERIFY/CLOSE/CANCEL业务Owner、解决Trace深层当前事实、HTTP/UI/Workflow与真实下游业务仍待；合成Trace不代表真实Action已解决，Gate 3继续BLOCKED。
