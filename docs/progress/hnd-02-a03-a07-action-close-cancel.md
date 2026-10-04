# HND-02-A03-A07：Action CLOSE/CANCEL Owner

日期：2026-10-05。结论：`HND_02_A03_A07_ACTION_CLOSE_CANCEL_PASS`。下一项：`HND-02-A04-A01` Action 读取/HTTP 前置核查。

## 实施结果

- CLOSE仅允许当前ProjectManager按强ETag执行`VERIFIED -> CLOSED`；Root、关闭事件、`closed_at`、`resolution_trace_ref`、Audit和持久幂等收据同事务。
- 新增Trace Owner解决关系证明边界：关系必须为当前ACTIVE、PROJECT且同项目，并对两端调用已注册Owner复验。ANALYSIS_ITEM来源必须精确匹配该Action固定的HND-02 Analysis/Version；HUMAN来源只接受显式选择的SRV-02/SRV-05/REQ-03正式下游版本，并以关闭reason绑定人工决定。
- CANCEL仅允许当前ProjectManager从OPEN/IN_PROGRESS/SUBMITTED/VERIFIED进入CANCELLED；保留已有提交、验证和Evidence投影，不伪造`closed_at`或解决Trace，终态不可复活。
- 冻结Trace模型已包含`handover/HND-02`，因此无需Migration或新增HND-03 Trace节点；复用Schema0100和CR-HND-003。

## 验证

- Win11/PostgreSQL 18.6真实临时库验证通过：PM-only、HUMAN正式下游Trace、精确HND-02 source、无关目标拒绝、终态保护、OPEN/VERIFIED取消、历史保留、强ETag、首次结果重放、并发、Audit回滚恢复及License拒绝。
- 新增7项定向单元测试；相关权限合计14项通过；后端全量2647项通过/3跳过。
- 开发wheel构建及解包导入通过，SHA-256 `c04d7c3c9abdf28ea87a5480908d3e7a3960a5a96cd83fd57948af93093ca0b2`。
- 首次尝试以pytest启动，但当前受控Python环境未安装pytest；按仓库正式unittest入口完整执行。PostgreSQL夹具首轮暴露初始事件reason/时间与短幂等键不合法，结果作废并修正夹具后以新临时库重跑通过。

## 限制与回滚

- 无公开HTTP、配置、依赖、外发或生产数据变化。停止装配两个Owner即可关闭新写；合法CLOSED/CANCELLED历史不删除、不倒退。
- Survey/Requirement真实Owner尚未实现；生产装配必须在对应Owner注册前保持失败关闭。本轮合成Owner只验证机制，不代表真实项目解决事实。
- Action读取/HTTP/UI、Handover Review、Workflow Adapter、真实资料质量、性能、正式信任及发行仍待；Gate 3继续BLOCKED。
