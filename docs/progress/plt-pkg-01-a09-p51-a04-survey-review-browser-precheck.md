# PLT-PKG-01-A09-P51-A04：P51候选 Survey Review 浏览器纵向验收

日期：2026-10-25；状态：`PREFLIGHT_PASS_RUN_PENDING`。

## 编码前检查

- 当前Phase/WBS：Phase 2 / `PLT-PKG-01-A09-P51-A04`。
- 输入基线：P51-A02 当前候选 SHA `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`，其清洁 stage `D:\PLMToolTemp\plm-current-app-stage-p51a02-96313d4e`；P51-A03 包内迁移/合成HTTPS PASS；`CR-SUR-014` 和 P05/P06 已验方案；最新 `validation/sur-07-a08-survey-version-packaged/verify.py` 与 Edge runner。
- 前置任务：当前候选22,197项清洁提取/原子落地通过，包内0185迁移、HTTPS登录/Session/无License拒绝及临时资源清理通过。
- 涉及模块：只运行当前包内完整 Survey Review UI 合成验收；不修改产品代码/API/ORM/Migration/权限。
- 实体/API：一次性隔离 PostgreSQL 内新建合成 Project/Handover/Survey/SurveyVersion/Review/Round；复用已冻结路径，只断言现有 `/api/v1`。
- 权限与事实边界：ProjectManager 可读本项目当前 Review 状态但无决定控件；数据库确认受指派 Reviewer 后能读任务/详情/固定 SurveyVersion 深链并看见按钮；自动化不得点击“批准本轮/退回修改”，数据库必须零决定、批准指针NULL。客户内容、项目数据均不使用。
- 验收：Edge 真浏览器→Caddy HTTPS→包内API/PG；D盘隔离临时布局唯一命名，候选SHA前后固定；Review列表/详情标签和固定版本 ID 深链正确，审计/幂等收据/许可拒绝正确；临时 PG/HTTPS进程/Vault/profile/目录清理；输出需明确 `release_eligible=false`、非真实客户确认。
- 风险：前序P05已发现读取Owner缺口与脚本错误断言，必须使用经修正的最新版夹具；若出现任何决定写入，立即判失败并保留合成DB证据，不将其称客户决定或通过；不触碰正式根/SCM/真实DB。
- 回滚：只弃用候选和临时合成结果，历史包与用户数据不变；本项无代码修改。

## 实际验收结果

- 当前候选 SHA `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455` 在 P51 一次性布局中通过 `SUR_07_A12_P05_PACKAGED_EDGE_PASS` 和 `SUR_07_A12_P05_PACKAGED_PG_PASS`。Edge 对 Review 列表、Review 详情及 Survey `fixedVersionId` 深链进行真实浏览器交互；ProjectManager 作为项目成员读取成功但无决定按钮，实际受指派 Reviewer 有待办/详情/精确版本链接且看到两个决定按钮。脚本只验证按钮可见，不点击。
- 数据库断言：固定 Survey Review/Round 唯一、Review/Round 与 SurveyVersion 精确绑定，Reviewer 快照为 ACTIVE/PENDING，Audit/幂等收据存在，Review 决定数量为0、批准 SurveyVersion 指针仍 NULL。上游 Handover 已批准流程只使用合成角色/资料并留下测试用决定，不含客户数据；不能视作客户批准或业务事实。
- 上游 Survey DRAFT 创建/Validate/ProjectManager 送审、同Key重放、Audit、合成失效 License 403以及 HTTPS 登录/Session=200均通过；候选 `fixed_candidate_unmodified=true`、`release_eligible=false`、`legal_clearance=false`。
- 最终外层检查候选 SHA 不变；Edge、Caddy、API、PG18与Python无遗留进程，P51-A04 pristine/target/partial/edge profile/PG临时目录/Vault目标已清理。P51-A02的stage与atomic placement两份固定目录保留供后续非发行验证。
- Console JSON 中中文列表标签出现显示乱码；浏览器/HTTP返回值的精确中文断言在验收脚本内部已通过。该差异仅为当前PowerShell输出编码表现，不是UI数据/标签失败。

## 结论及边界

`PLT-PKG-01-A09-P51-A04` 仅证明本次 Windows 11 非发行候选对当前 Survey Review 切片可交互、权限隔离正确；没有真实客户Reviewer或客户数据，且Survey Review未作决定。正式公钥/License、Operator ceremony、安装账户/ACL、法律、三平台、全业务链/真实UAT、Gate/Pilot仍未完成。
