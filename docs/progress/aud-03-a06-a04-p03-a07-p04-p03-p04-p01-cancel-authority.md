# P04-P03-P04-P01 取消申请权限

日期：2026-09-26；状态：INTERNAL_AUTHORITY_PASS / CANCELLATION_OWNER_PENDING。

编码前检查：Phase2，WBS P04-P03-P04-P01；前置真实Session/CSRF/License与Project current成员、Audit原Root/acceptance/pair已验，输入冻结API03 JOB_PROJECT_CANCEL（创建者或PM）、API02 Admin无Project旁路/CR-AUD-004。涉及Audit Application取消权限与Project owned操作政策，无Schema/API/依赖/安全机制变更。

证据：现有导出提交权限只允许当前PM，不能满足已降级但仍有有效membership的原创建者取消。新增AUDIT_PROJECT_CANCEL只读锁住当前成员（停止既有任务，不创建业务成果；归档项目可安全申请停止）。PROJECT要求真实Session+CSRF+有效License+当前有效membership，并且当前PM或Root原actor；Admin无项目旁路。DEPLOYMENT须当前Admin，无License豁免。

可信Owner必须从持久Root取original_actor/spec并重新绑定Root/acceptance/Job，不能相信浏览器提交的原创建者UUID。新Port只返回绑定元数据，不写取消/Audit/正文或commit。下一项Owner申请与实际取消来源审计同UOW；不把权限Port当取消已实现。

验收：实际临时PG双Scope当前Session/CSRF/License；原创建者当前有效其他角色允许、非创建者同角色拒绝、新PM允许、跨项目/停用/无成员Admin/部署撤权拒绝，归档只停止权限明确；完整回归与wheel，无生产修改。

Changed/Files：新增`export_cancel_authorization.py`严格request/绑定DTO，Project owned `AUDIT_PROJECT_CANCEL`只读锁住有效成员，4新unit与真实PG验证脚本。本入口不证明浏览器给的original actor为真，必须Owner从实际Root取；不代替未来Job取消申请授权/If-Match/持久幂等/审计。

Tests/Result：4新unit通过；真实双Scope原Root输入/Session-CSRF/User-部署角色/合成License，多类当前creator角色允许/非creator非PM拒绝/current PM允许、Admin无member跨项目/暂停成员拒绝、Archived仅停止权限，九表每读无写，原发布回归通过。测试首轮member_state字段误用失败，修正实际state后新临时库完整重跑通过。Windows11/Python3.13后端1012项无失败（2既有环境权限跳过）；开发wheel 593427 bytes，SHA256 `3693e887a1f6cd8bafddfe7e4804ba7979d9956fa19e33d1702307df344198a4`，不是安装包。

完整回归首轮失败：既有Project矩阵将操作数固定24，新取消操作为25。保留所有旧检查、明确新操作的ALL_MEMBERS/非业务写/锁读三条断言，并完整重跑；不以减少矩阵测试绕过失败。

Migration/API：无变化，无新依赖，0042不变，无生产升级；撤未装配取消权限Port/操作政策保历史可回滚。Known Issues/Next：P04-P02先绑定实际Root与当前权限、同UOW第一申请历史/唯一USER Audit来源及原结果幂等，再SystemActor确认/到期恢复；取消入口不公开。完整Scope/正式材料/三平台/质量/Gate/可用包仍待。
