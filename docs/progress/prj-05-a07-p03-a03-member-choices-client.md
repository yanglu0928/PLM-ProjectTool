# PRJ-05-A07-P03-A03：成员候选与部门安全选择客户端

- 日期/阶段：2026-09-28 / Phase 2；状态：PASS（前端合同与构建，不是页面或浏览器验收）。依据 CR-PRJ-006、DEC-20260928-439；A01/A02 前置 PASS。
- Changed：Auth 私有 CSRF 同源单次候选 POST；Project 客户端严格读取单个用户候选或统一空值，不保留额外字段；部门固定 50 条逐页 GET、有限 20 页、重复 ID/游标/坏响应拒绝，只输出 ACTIVE 安全投影。候选只供页面选择，最终写入仍由原成员创建服务端复核。
- Files：`apps/frontend/src/modules/auth/api/sessionClient.ts`、`apps/frontend/src/modules/project/api/projectMemberChoicesClient.ts`、对应客户端测试、本记录、状态、CR、决策和版本说明。
- Migration：无；兼容 DB head `20260927_0049`。API：消费已有 CR-PRJ-006 候选 POST 与冻结部门 GET，不更改服务端合同/权限。依赖/数据升级：无。回滚撤此次客户端方法及选择客户端，保留 A01/A02 后端。
- Tests：前端全量 468/468 PASS、typecheck、生产 build PASS；包含私有 CSRF/同源无重试、统一空候选、错误/401 状态、部门 ACTIVE 投影、坏分页/重复和权限拒绝。首轮部门测试队列误包含登录响应导致 1 项失败，修正测试数据后重跑全量通过。
- Known Issues：页面未组装、真实浏览器/PG 成员创建流未验；正式信任/TLS、Server 2025/Debian、性能/POC-03 质量/Gate 3/程序包待。
- Next：`PRJ-05-A07-P03-A04` 成员创建页面显式确认与原幂等 Key 未知结果恢复，然后 A05 独立浏览器/PG 写链。
