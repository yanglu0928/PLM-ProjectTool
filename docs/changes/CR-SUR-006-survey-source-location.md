# CR-SUR-006：Survey 固定来源受权定位增量

日期：2026-10-06。状态：依据 `CR-EXEC-001` 持续授权批准实施。Gate 2 原冻结提交 `64cdf09`、现有 Survey 四读合同和 Schema 0106 保留，不追写原冻结内容。

## 来源与冲突

冻结 `SURVEY_VERSION_GET` 会返回问题来源的版本内 row identity，足以证明不可变 SurveyVersion 引用了哪个 Handover/Capability/TEMPLATE/MANUAL 来源，但这些 identity 不是浏览器可导航的公共业务标识。前端若把它们猜成路由，会绕过来源 Owner、当前 Project 权限和 Evidence 固定版本校验；若复制来源正文进问题卡片，又会丢失版本、权限与定位语义。

Handover 固定项已有公共 `analysis_item_id` 与同项目 Evidence；PROJECT TEMPLATE 已有固定 DocumentVersion。Capability 属于 GLOBAL 标准能力域，其 Document/Evidence 仍受 GLOBAL 管理员权限保护，不能因为用户是某 Project 成员就扩大可见范围。MANUAL 只有说明，不天然等于固定文档或 Evidence。

## 方案比较与选择

- 方案 A：浏览器根据内部 row UUID 猜现有页面或 Evidence。存在误定位、越权和内部实现泄漏，拒绝。
- 方案 B：把来源正文复制进 Survey 读取响应。破坏来源 Owner 与固定版本语义，且增加敏感正文扩散，拒绝。
- 方案 C（选择）：新增兼容只读子资源 `GET /api/v1/projects/{project_id}/surveys/{survey_id}/versions/{version_id}/questions/{question_id}/sources/{source_ordinal}/location`。服务端先按 `SURVEY_VERSION_GET` 重验 Session、License、Project 成员和精确 SurveyVersion，再由来源 Owner 将内部 identity 解析为最小公共引用；只返回当前调用者可以安全获知的定位候选，不返回内部 row identity、文件路径或正文。

## 合同与语义

响应只允许以下顶层字段：

- `source_kind`、`source_ordinal`；
- `resolution_state`：`LOCATABLE`、`PARTIALLY_LOCATABLE` 或 `UNAVAILABLE`；
- `current_eligibility`：固定历史来源目前是否仍满足创建新 SurveyVersion 的来源资格；它不是客户确认、Review 或业务事实；
- `record_ref`：Handover/Capability 的公共业务标识，或 TEMPLATE 的公共 Document/Version 标识；
- `locations`：有界、有序的 `BUSINESS_RECORD`、`EVIDENCE` 或 `DOCUMENT_VERSION` 公共目标；
- `unavailable_reason`：仅允许 `MANUAL_SOURCE_NOT_FIXED`、`NO_AUTHORIZED_LOCATION`、`SOURCE_TARGET_UNAVAILABLE` 或 null。

固定历史来源即使不再是“当前正式版本”仍可解析其公共历史标识，但必须令 `current_eligibility=false`，不得称为当前已批准事实。所有 Evidence 点击仍调用既有 Evidence Viewer，再次校验 Scope、当前权限、固定 DocumentVersion、locator 与 fingerprint；本端点本身不返回 `content_url`。GLOBAL Document/Evidence 在没有 GLOBAL 管理员证明时不得出现在 `locations`。MANUAL 无固定对象时返回 200 + `UNAVAILABLE/MANUAL_SOURCE_NOT_FIXED`，不把说明变成链接。

不存在的 Survey/Version/Question/ordinal、跨 Project 或来源 identity 不一致统一按资源不可见处理；查询参数、正文和未知字段拒绝。响应 `Cache-Control: no-store`，不写 Audit，因为它是零写入读取。

## 实施拆分

1. `SUR-01-A06-A04-P01`：本 CR、合同增量和边界核查。
2. `SUR-01-A06-A04-P02`：Survey 来源定位 Application Owner 与 Handover/Capability/Document 最小解析 Adapter；同事务验证精确来源，不开放 HTTP。
3. `SUR-01-A06-A04-P03`：严格 HTTP、Windows 显式平台组合及 Windows 11/PostgreSQL 18.6 真实只读验证。
4. `SUR-01-A06-A05`：前端按点击调用定位，再由 Evidence Viewer/Document/Handover 页面完成真实浏览器闭环。

## 影响、迁移与回滚

这是 `/api/v1` 的向后兼容新增 GET，不修改现有 URL/响应、Schema/Migration、ORM、角色、依赖、Secret、网络或数据外发范围。新增端点复用 `SURVEY_VERSION_GET` 权限；不新增更宽角色。来源 Adapter 归各来源模块所有，Survey 不直接读取跨模块私有表。

应用回滚方式为不注入定位 Router/Resolver，端点恢复 404；现有 Survey 四读与历史数据不变。若未来要让普通 Project 成员查看 GLOBAL Capability 原文，必须另建跨 Scope 授权 CR，不能放宽本合同。

## 验证计划

- 单元：精确 Project/Survey/Version/Question/ordinal，四类来源，历史与当前资格分离，顺序/数量/字段失败关闭。
- 权限：四类 Project 读角色可解析同项目目标；撤权、跨项目、无 License、GLOBAL 非管理员目标不泄漏。
- 合同：无请求正文/查询，严格最小响应，内部 row ID、正文、文件路径和 `content_url` 不出现。
- PostgreSQL：真实固定来源、来源状态漂移、零写入与事务一致性。
- 组合：默认/login-only 404，Windows 显式 Survey 读/写模式开放；Windows 11 真实 HTTP/PostgreSQL 通过后才标 P03 PASS。

## 实施记录

- 2026-10-06 / `SUR-01-A06-A04-P02`：完成内部Service、精确Survey source identity读取及三个来源Owner Adapter。Windows 11/PostgreSQL 18.6真实ORM验证四类来源、GLOBAL withholding、历史/当前分离和零写入；定向16、后端2854/3与wheel通过。HTTP、Windows组合及浏览器留P03/A05。
- 2026-10-06 / `SUR-01-A06-A04-P03`：实现冻结GET端点、严格路径/query/body校验、安全错误映射与互斥公开投影，并注入Windows Survey读/写组合。Windows 11/PostgreSQL 18.6真实HTTP验证默认404、四类来源、跨项目隐藏、状态漂移和零写入；定向46、后端2858/3及wheel1060通过。A04后端闭环完成，前端点击与浏览器闭环留A05。
- 2026-10-06 / `SUR-01-A06-A05-P01`：新增严格前端location客户端和问题卡片按需点击；只消费公共引用，Document固定版本可直接打开，Handover跳转公共分析，Evidence经Viewer再次核验后显示精确位置。人工/无权限/目标缺失给受控维护提示，历史来源明确不作为当前事实。定向39、前端全量82文件1438项、typecheck及172模块build通过；真实Windows浏览器留P02。
- 2026-10-06 / `SUR-01-A06-A05-P02`：Windows 11真实Edge经构建Vue、生产FastAPI与PostgreSQL18.6完成四类来源点击和Evidence Viewer闭环；4个location与1个Viewer均200，无UI告警或内部row identity，Survey/Version零写及临时资源清理通过。复验中按DEC-938修正列表摘要/详情边界与两个原生fetch调用上下文；前端全量82文件1441项、typecheck/build通过。托管浏览器内核缺资源，使用同机Edge/CDP并登记工具偏差。CR-SUR-006运行闭环完成。

