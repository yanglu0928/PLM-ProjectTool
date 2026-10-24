# SOL-05-A04-P13-P06-P02-P03-A01：章节客户评审浏览器验收

日期：2026-10-23。状态：`WINDOWS_EDGE_PG_PASS`，仅合成客户；正式信任与实际客户确认未验。

## 编码前检查

| 项目 | 结论 |
|---|---|
| 当前 Phase | Phase 2 Platform Core，Windows 11 受控 Pilot 关键路径 |
| 当前 WBS | SOL-05-A04-P13-P06-P02-P03-A01：客户待办、固定章节与终态浏览器链 |
| 输入基线 | 冻结 `/api/v1`、CR-SOL-024/025、P13-P05-P03 送审 PG、P13-P06-P01 终态 PG、P06-P02-P01/P02 前端合同 |
| 前置任务 | 上述内部合成验收通过；生产构建可用。先由已验 API 夹具建立 IN_REVIEW，不冒称本片覆盖负责人浏览器点击送审 |
| 涉及模块 | 仅新增隔离的 Windows 11 Edge/ASGI/PG 验证夹具；不改业务源码 |
| 涉及实体 | SectionVersion、Review/Round/Decision、Review assignment、Trace、Audit、幂等收据 |
| 涉及 API | 登录、Review LIST/GET/:decide、SectionVersion GET；不变更公开合同 |
| 涉及权限 | 合成 CUSTOMER_MEMBER 当前项目；跨项目读取拒绝，批准须精确分配与现时六维 |
| 验收标准 | 真实 Edge 从服务器待办发现 Section Review，打开固定章节，完成批准；PG 只有一次决定/Section 终态，待办消失、历史保留、跨项目不泄漏；临时资源清理 |
| 风险 | 测试账户/License/密钥均为合成，仅证明受控组合，不是正式信任或客户确认；负责人浏览器提交另列 A02 |

无基线/API/Schema 改动；若发现合同偏差，先另记 Change Request 再调整生产实现。

## 实测偏差与处理（实施前登记）

首轮 Edge 登录/待办/Review GET 与固定 SectionVersion GET 均获得 HTTP 200，但详情页拒绝读取。后端 SectionVersion GET 已按 CR-SOL-022 的固定结构化规格绑定返回 `spec_binding_state`、`declared_spec_count`、`spec_not_required_reason`、`structured_spec_refs`，前端旧版严格字段解析未同步。这是已实施后端合同的前端适配遗漏，不新增或改写 `/api/v1` 字段，故不新建 API Breaking Change；保留 CR-SOL-022 与本记录作为追溯。

- 风险：若直接忽略新字段，客户无法核对本轮固定规格适配依据；若放宽所有未知字段，会削弱客户端失败关闭。
- 方案：仅将上述已存在字段逐项加入严格解析，核对声明状态/数量/唯一身份与依据文本；详情展示固定规格引用和适配依据。拒绝不一致响应，不接受泛化额外字段。
- 兼容/迁移：不涉及 ORM/Migration；现有后端响应正向兼容，尚未发行的前端内部构建需重新构建。回滚前端变更会恢复“读失败”，但不影响服务器已存 Review/Section 事实；不得回滚后虚报浏览器通过。
- 验证：新增客户端正反例、前端全量/typecheck/build，重跑相同 Edge/PG 浏览器链，并复验终态与历史。

## 验收结果

一次性 Windows 11/PostgreSQL 18.6 合成数据环境中，已验 API 夹具先建立 Section IN_REVIEW，真实 Edge 登录合成 CUSTOMER_MEMBER，从服务器 `my_pending` 发现 Section Review，打开本轮固定 SectionVersion 并读取固定规格/作者适配依据，然后提交 APPROVE；浏览器证明待办消失、全部历史保留、跨项目页面清空。PG 再读确认 SectionVersion/Review/Round 均 APPROVED、章节批准指针为本固定版本、决定仅一条。浏览器临时 Profile 与 PG 夹具由验证脚本清理；本片未接真实客户资料/AI外发。

第一次运行因合成客户采用不可变凭据的旧测试哈希而中断，调整为创建时写入合成 Scrypt 凭据；第二次暴露上述前端严格字段漂移，修复后 Edge 链通过。定向 13 项、前端全量 157 文件/1857 项、typecheck/生产构建通过（主 bundle 超 500kB 的既有警告仍在）。后端业务实现未修改，沿用已验 PG 送审/终态夹具；未重跑后端全量。

仍需 `SOL-05-A04-P13-P06-P02-P03-A02` 验证负责人在真实浏览器点击章节送审及回执，不把本片已有 API 夹具送审描述成 UI 验收。Gate 3、Pilot、正式三平台发行与真实客户确认未完成。
