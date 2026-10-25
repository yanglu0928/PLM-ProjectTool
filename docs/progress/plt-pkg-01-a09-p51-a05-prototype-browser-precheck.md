# PLT-PKG-01-A09-P51-A05：当前候选 Prototype 浏览器验收前置

日期：2026-10-25；状态：`PASS`（Windows 11 当前非发行候选；合成数据）。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `PLT-PKG-01-A09-P51-A05`|
|输入基线|CR-EXEC-002；P51-A02当前候选SHA `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`、stage/atomic-placement固定目录；Prototype冻结DM-05/API-04及现有A10-A07 Edge验收器|
|前置任务|P51-A02原子落地/逐项哈希、A03包内PG/HTTPS运行、A04 Survey Review只读及权限Edge/PG链均已通过；本机Prototype源码级Edge/PG验证存在|
|涉及模块|仅新增/适配一次性validation runner并在隔离当前候选上执行Prototype真实Edge/HTTPS/PG验收；不修改产品API/ORM/Migration/权限|
|涉及实体/API|合成Project、Requirement/RequirementVersion/AcceptanceCriterion、Prototype/Package/Template/PrototypeVersion及Review；仅使用冻结 `/api/v1` Prototype、Project和Review接口|
|涉及权限|合成ProjectManager/ImplementationMember/Reviewer；校验匿名/无权限、项目隔离、过期合成License拒绝。自动化不得点击客户Review决定，不得把测试审批表述为客户事实|
|验收标准|包内Vue/HTTPS/API/PG真实操作Prototype身份/包成员/模板/版本/Validate/送审及Review读取；DB核对版本、请求收据、Audit与Review绑定；原候选SHA固定、服务/凭据/profile/临时库清理|
|风险|源码级通过被误称随包可用；测试Reviewer意外作出决定；候选含合成正式信任或被称发行包；runner误清用户目录|
|回滚|弃用单次测试结果/新增验证runner即可；不改正式表/已有用户库/候选ZIP，不触及 `C:\PLMTool`、SCM、客户数据或正式私钥|

## 方案与执行边界

源码级 `validation/prt-01-a10-a07-windows-browser` 已覆盖Prototype身份、Package成员、PROJECT Template、DRAFT Version、服务端Validate、送审、Link历史和登出；包内尚无对应P51验收。静态核对发现其Edge driver硬编码本机合成登录凭据，fixture也直接从源码工作区启动服务，不能直接复用为当前候选包证据。因此本WBS需新增候选专属编排/浏览器入口，复用P51 package smoke的candidate/stage/pristine/target身份检查，且在包内服务启动后再执行Prototype步骤；登录只使用一次性fixture当前会话凭据传递，不写入代码/命令行日志/仓库。若无法证明浏览器实际连接包内服务，则停止并标记未验，不以源码级测试替代。

候选ZIP必须先记录SHA，测试前后保持一致。实际Prototype页面步骤与SQL核对需保留原断言；禁止降低断言或把源码工作区服务冒充包内运行。

本项不要求Survey Review产生决定；Prototype送审若本身会创建Review邀请/待办，验收只确认真实状态与受权读取，不点击决定。使用可弃合成数据和隔离服务，日志/口令不落库、不外发、不提交。即使全部通过，也仅为Windows 11非发行候选的功能证据，不能关闭Gate 3/Pilot正式信任条件。

## 执行过程中的适配记录

首轮包内运行实际证明当前SHA候选可完成布局/运行时启动、HTTPS登录和既有Handover/Survey浏览器/PG验收，但在进入Prototype前，P51回调未提供Prototype源码runner所假定的`project`/`observer_id`上下文，导致验收适配器`KeyError`。这不是产品代码或业务流程失败；原smoke异常路径已停止服务并清理本轮layout/process，候选SHA保持不变。

首轮对22,197项候选进行了重复完整哈希/复制，累计读约8.8GB、写约2.8GB，导致纯包验证耗时异常。P51-A02已有同SHA ZIP逐项校验、stage清洁解包及原子安装落地/读回证据，P51-A03/A04已用同候选启动包内服务。为避免重复铺设而保留同等产品验收，本轮调整为：重验候选ZIP SHA；核对P51-A02原子安装布局路径、完整文件清单和非发行manifest；在同卷私有临时target对固定已验布局建立硬链接隔离副本，再在此target执行同一包内PG/HTTPS smoke和Edge/PG Prototype流程。Hardlink源布局只读，不向源目录写入License/密钥/测试数据；任一库存、哈希身份或链接不符即失败关闭。此为validation执行优化，不改产品/候选或降低Prototype行为断言；回滚只删除本轮自有target，保留A02源布局和候选。若文件系统不支持安全硬链接则退回原完整原子副本方案。

验收适配进一步发现并记录：Prototype 专项必须在上游 Handover/Survey 合成“过期License拒绝”负例之前运行，故新增仅供包验证的 `before_expiry_probe` 回调；其后保留并完成原过期License负例。夹具行使用仅限隔离临时数据库的管理连接，所有应用/API/Edge操作仍用最低权限应用账户。上游回归会用尽源IP登录桶，故仅清除本次临时PG中的合成限流桶；不会改动产品限流代码。项目文档列表异步加载增加Edge等待；Reviewer标签从环境变量映射到该包夹具内的合成Handover客户。首轮幂等断言误把回执`result_ref_id`指向PrototypeVersion，按Owner实现改为ReviewRound。期间出现一次上游Edge调试端口启动不稳定，清理确认无残留进程/布局后重跑；无产品缺陷证据。

## 最终验收结果

- 固定候选 SHA-256 `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；22,197个载荷；P51-A02已验证 stage 复用后在隔离同卷布局执行，最终SHA未变。
- 当前候选内 Caddy HTTPS、随包Python、临时 PostgreSQL 18.6启动；包内Handover/Review、Survey Review及Prototype真实Edge链通过。Prototype浏览器确认身份、Package成员、模板/固定文档/批准需求、DRAFT版本、服务端Validate、送Review、历史链接及登出；仅验证受权Reviewer能看到Review动作，不点击决定。
- PG断言：PrototypeVersion=`IN_REVIEW`，绑定Review与Round，批准指针NULL，决定0，`V1_PRT_VERSION_SUBMIT_REVIEW`完成回执指向对应Round。上游Handover合成批准属于测试夹具；Survey及Prototype没有决定。
- 包内总体 smoke PASS：登录/Session 200、无License保护Project路由403，48临时Vault目标、临时PG/API/Caddy/Edge/profile及隔离文件均清理；固定候选不变。
- 未验证/未宣称：真实客户数据/确认、正式License/公钥/服务账户信任、安装/升级Pilot、完整Prototype→Solution→Plan→Output链、Gate 3、Windows Server 2025、Debian 13及正式发行；候选 `release_eligible=false`、`legal_clearance=false`。

## 变更文件与兼容性

- 新增 `validation/plt-pkg-01-a09-p51-a05-prototype-packaged/verify.py`；适配 `validation/prt-01-a10-a07-windows-browser/run-edge-browser.mjs` 的HTTPS/动态合成登录与Reviewer标签。
- 包验证基础工具增加可选“复用已验证stage”的快路径及隔离DB夹具连接；Handover包验收器增加可选送审前回调。没有改产品代码、API、ORM、Migration、权限、License策略或候选载荷。
- `node --check`、Python `py_compile` 通过；当前候选包内完整回调链及临时资源清理通过。先前运行失败均为测试适配/断言映射或一次边缘浏览器启动问题，最终同SHA全链复跑通过。
- 最终全链复跑后，`tools/tests/test_smoke_current_app_packaged_https.py` 与 `tools/tests/test_smoke_packaged_platform_write_https.py` 合计 6/6 PASS；无残留Edge/服务进程或本轮P51-A05布局。一次中途上游Edge启动及UI加载竞态在安全清理后重跑，并在浏览器验收器增加表单数据就绪等待，最终真实Edge完整链PASS。
