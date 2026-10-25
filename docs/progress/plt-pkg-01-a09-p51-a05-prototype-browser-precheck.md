# PLT-PKG-01-A09-P51-A05：当前候选 Prototype 浏览器验收前置

日期：2026-10-25；状态：`PREFLIGHT_PASS_RUN_PENDING`。

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
