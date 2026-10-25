# CR-SUR-014：Survey Review 读取 Owner 装配

- 日期：2026-10-25
- 发现 WBS：`SUR-07-A12-P05`
- 执行 WBS：`SUR-07-A12-P06`
- 状态：`CLOSED_VALIDATED`；按用户持续授权登记并执行，不修改冻结 API/DB Schema；包内合成验收通过。

## 变更原因与证据

P05 包内验收中，ProjectManager 送审成功，但登录为本轮实际受指派的合成客户 Reviewer 后，`GET /api/v1/projects/{project_id}/reviews/{review_id}` 仍返回 `404 RESOURCE_NOT_FOUND`。审阅当前 Windows 组合发现：

1. Survey 的 `SurveyReviewSubjectOwner` 实现了送审与 Reviewer 资格，但缺少通用 Review GET/List 使用的 `authorize_read`。
2. Windows PROJECT Review GET/List composition 注册了 Structured Spec、Section、Handover、可选 Outline Owners，却没有注册 Survey Owner。
3. 因 Owner registry 对未知/未注册主体失败关闭，`SRV-02 + SURVEY_ALL_V1` 的 Review 详情和列表无法读取；前端 P04 的主题/深链实现因此没有可用运行时投影。

首轮 ProjectManager 读请求 404 是预期拒绝；第二轮实际指派 Reviewer 仍 404 才暴露此装配缺口。此前 P03 只确认 Survey Owner/通用路由存在，未核实只读 Owner 方法及组合注册，是前置检查疏漏，已记录。

## 方案与选择

- A：保持当前失败关闭，Survey Review UI 不可用；不符合 P04 已完成的授权读取体验。
- B：按现有 Handover/Outline Owner 模式，为 Survey Review Owner 增加当前成员资格及活动 Survey/精确版本归属证明，并在 Windows PROJECT Review GET/List composition 显式注册该 Owner。决定权限仍只按受指派 Reviewer 的现有规则；不改 API、数据库、审计或持久模型。

选择 B。只允许当前有效项目成员读取该项目中活动 Survey 的 Review 摘要和活动轮固定 SurveyVersion；跨项目、无成员、非活动/不存在 Survey 或不属于该 Survey 的版本仍失败关闭。实际决定仍必须由 PENDING 指派人提交，本 CR 不改变该边界。

## 影响、迁移与回滚

- API：仅让已冻结 GET/LIST 能读取已注册的 SRV-02 主体；路径/载荷/状态码合同不变。
- DB：无 ORM、Schema、Migration 或数据迁移。
- 前端：不变。
- 风险：Owner 过宽会泄漏跨项目/错误版本 Review 投影；通过现有项目成员资格、活动根对象与精确版本存在性检查，以及负例测试控制。
- 回滚：移除 composition 注册并回退 Owner 读取实现，GET/LIST 对 SRV-02 恢复失败关闭；无数据库回滚操作。
- 验证：Owner 单元测试；Windows 隔离 PG HTTP 证明项目成员成功、非成员/跨项目/错误版本拒绝；P05 干净候选 Edge 验证送审、Reviewer 待办/详情、固定 SurveyVersion 深链和决定控件可见，决定数为零；完整前端/后端定向回归、secret scan、包内候选哈希与资源清理。

## P05 验收偏差

`SUR-07-A12-P05` 首轮/复跑均未通过：前者确认 ProjectManager 不可读取，后者在实际受指派 Reviewer 登录后仍收到 404。P05 保持 Incomplete，候选 `fbd0bea95b370258ef211443e77a8bc3deab60dd1df01e762826cea199752720` 未因失败而变成可用包。先完成本 CR 与 P06，再从新的干净提交构建候选重验；不将已失败包用于交付。

候选重建第一次又被源码清洁检查拒绝。检查注释意图忽略用户本地 `.tmp/`，但旧 Git pathspec `:(exclude).tmp/` 未过滤其中解包的数万文件；已把排除改为 `:(exclude).tmp/**` 并增加打包器回归测试。实际确认该规则排除 `.tmp` 下文件，同时仍会识别其他未跟踪路径。没有删除、改写或提交 `.tmp/` 内容。

从提交 `47e979044f90c9618d80d0c1283ee93e024057f2` 重建的候选 SHA `050f37207985e5f407ac713373b2713bc24cafe67a3a36a8b5adc4e786aecfce`（22,197 项，654,939,043 bytes）清洁解包通过。包内首轮确认 Reviewer GET=200，但误用 Handover“返回评审待办”文案导致脚本中止；第二轮确认 Review GET/载荷正常，旧脚本把 ProjectManager 读取预期写成404，但现有策略允许当前项目成员读取，实际200是正确结果。已修正验收为项目成员可读/非指派人无决定按钮，Reviewer 有决定按钮但绝不提交；最终 Edge/HTTPS/隔离 PG18 验收通过，Review/Round、指派快照、Audit/收据均准确且决定数为0、批准指针为空。临时资源已清理，候选哈希未变化。

## 最终验收与边界

- P05/P06 包级验收通过：`SUR_07_A12_P05_PACKAGED_EDGE_PASS`、`SUR_07_A08_PACKAGED_PG_PASS`、`SUR_07_A12_P05_PACKAGED_PG_PASS`、`SYNTHETIC_CURRENT_APP_PACKAGED_HTTPS_PASS`；对应证据见 `docs/progress/sur-07-a12-p05-review-ui-packaged.md`。
- 仅 Windows 11 合成数据及开发环境组合已验；候选 `release_eligible=false`、`legal_clearance=false`。不代表真实客户确认、正式信任、Pilot 可发行、Gate 通过或 Windows Server 2025/Debian 13 兼容。
