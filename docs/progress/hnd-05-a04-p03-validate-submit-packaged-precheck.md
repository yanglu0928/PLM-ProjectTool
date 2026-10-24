# HND-05-A04-P03：交接校验与送审 Windows 11 非发行包验收

日期：2026-10-25；状态：`FRONTEND_DEFECT_FIXED / NEW_PACKAGED_EDGE_PG_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `HND-05-A04-P03`；只验证已实现的 DRAFT 当前来源校验与客户评审送审，不改变冻结 API/Schema/权限。|
|输入基线|已同步提交 `cd1c51e9`；HND-05-A02-P04 固定非发行候选 SHA `3e84a42c3c22fd5f02ec5a13a35bc86d28394f9d1cf9b846952bdfa8cf2cb209`；A03-P01/P02 与 A04-P01/P02 前端合同测试通过。|
|前置|既有包内合成项目固定文档、交接分析、PROJECT Evidence、当前批准 GLOBAL Capability 与两张 DRAFT 卡片的验收夹具可复用；必须重新打入当前前端，不把旧 ZIP 当成本轮证据。|
|正式约束|送审前 `NEED_CONFIRM` 卡片须有同一 `analysis_item_id` 的非取消 Action；必须通过正式 Handover Action API 创建，不能改库伪造覆盖。客户确认人须为当前项目有效成员，服务端事务复核。|
|验收|清洁解包逐件哈希；Edge/HTTPS/隔离 PG 生成 DRAFT 后打开校验报告，核对真实 Audit/回执及同号重放；先验证缺 Action 时送审拒绝，再建正式 Action 并送审至 IN_REVIEW，核对唯一 Review/Round/Audit/收据、同号重放及匿名/无项目权限/不合格 Reviewer 负例；临时信任与进程清理。|
|风险|仅 Windows 11 合成信任，非真人客户确认、正式公钥/服务账户、离线安装升级、Gate 3～7 或三平台发行；不上传 ZIP/客户数据/秘密。|

前置满足，可开始本 WBS。验收结论仅以固定候选、实际浏览器请求和 PG 事实填写。

首次固定候选 SHA `556770f2b6ab316ba14d68c225c4b527da2ca3dc9b05e38e7f616f94b23171fb`
清洁解包 22,196 件退出 0；随后完整测试在默认 C 盘 Temp 复制第二份布局时因
`ENOSPC` 退出 1，尚未执行浏览器或数据库步骤，不计通过。现有 C 盘可用空间不足以
同时容纳暂存和两份一次性布局；验收夹具改用 D 盘专用 ASCII 临时根，仍遵守工具的
“直接 Temp 子目录、全件复核、事后清理”边界，不改变候选/产品或正式安装目标。

D 盘重跑清洁解包与原有项目文档/交接分析/PROJECT Evidence、GLOBAL 能力批准、
DRAFT 双卡片均通过；新送审前置的“缺 Action 拒绝”和正式 Action 创建亦已到达。
首次夹具对无项目资格 Reviewer 预期使用 `REVIEW_REVIEWER_INELIGIBLE`，实际
HND-02 Subject Owner 将该资格失败闭合为 `BUSINESS_REVIEW_NOT_ELIGIBLE`（HTTP 422）；
程序正确拒绝，夹具断言与冻结错误边界不一致。保留此失败，修正夹具预期后复跑，
不改产品权限或候选包。

第二轮越过全部旧前置和 Action/不合格确认人拒绝，Edge 另起浏览器再次登录同一合成账号
触发平台 PostgreSQL 登录限流（HTTP 429）；未到页面校验/送审，不计通过。已有旧前置
已真实验证 Edge 登录。为不放宽限流，本轮夹具改为将刚从正式 HTTPS 登录取得的短时
合成 Session Cookie 注入一次性 Edge Profile 后导航到详情页，页面校验/送审仍走真实
浏览器、CSRF、HTTPS、授权和 License；Cookie 仅通过本地子进程环境传递，不写仓库
或输出，不作为正式安装/客户信任凭据。候选字节不变，第三轮复跑待验。

第三轮显示仅 Cookie 在新页面只能恢复只读身份，不能恢复内存 CSRF 或提交权；
真实 Edge 详情正确显示“尚未读取当前身份”，第三轮未到校验或送审，不计通过。
按原安全设计保留此拒绝；夹具改为在同一次 Edge 登录会话内，通过真实 HTTPS
依次执行缺 Action 拒绝、正式 Action API 创建、不合格 Reviewer 拒绝，然后导航
页面校验与送审。这样既不调高/清空登录限流，也不伪造 Session 或降低 CSRF。
第四轮同一候选待验。

第四轮同一合成 Edge 登录通过，缺 Action 和不合格 Reviewer 均 HTTP 422 拒绝，
正式 Action POST 201；DRAFT 详情与 `:validate` POST 200 均真实发生，但校验面板
在 SessionClient 写入繁忙期间从 DOM 消失，报告没有重新显示，随后超时。
不计页面通过。现有页面根 `v-if` 把瞬时 `canSubmit` 当作可见性条件，两个兄弟面板
还使用同一版本 ID 作 VNode key；属于前端组合缺陷。先加可复现测试，再使授权角色
决定可见性、提交能力只约束按钮，并给兄弟节点不同 key；不修改冻结 API/后端权限。

针对瞬时 Session 繁忙新增校验与送审面板回归，两项从失败/缺失转为通过；
详情页同时断言两个面板可见。授权角色和 DRAFT 状态决定面板可见性，
CSRF/Session 提交能力只约束写按钮；只读会话保留明确重新登录提示。
定向面板/详情合计 14 项、前端全量 188 文件 2008 项、typecheck/build 退出 0。
原 SHA `556770f2…171fb` 的包不含此修复，不能再用来证明本轮页面通过；
需从修复后干净已同步提交重建新非发行候选并独立清洁解包/整链复验。
