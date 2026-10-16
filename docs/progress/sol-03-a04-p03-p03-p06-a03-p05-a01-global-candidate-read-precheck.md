# SOL-03-A04-P03-P03-P06-A03-P05-A01：项目 GLOBAL 候选只读前置核查

日期：2026-10-09。结果：设计前置完成；本项没有开放项目成员路由，不标记功能或 Gate PASS。

## 编码前检查与事实

- Phase 2 Platform Core；单一问题是 CR-SOL-018 的项目成员 GLOBAL 候选最小只读面如何同时满足已发布标签、当前资格及项目授权。
- 已有 0157/0158 不可变发布事件、管理员发布 Owner/HTTP/Windows 显式写组合，旧 GLOBAL 根没有发布事件时默认不可见。
- 现有 GLOBAL 管理员列表 `GlobalReferenceReadService` 用管理员端口且会返回原始 `Root.name`，不可改成项目端通道。现有 `ReferenceUseProofService` 可在同一事务重验当前固定版本、人工 ELIGIBLE 事件、Document/Evidence 来源指纹和有效脱敏确认；它不授权调用者，也不提供展示标签。
- 项目写资格目前是 `SOL_OUTLINE_VERSION_CREATE`，只允许 ProjectManager/ImplementationMember；项目候选读应新增同角色的专用只读策略，不借管理员 Session，也不沿用四角色的普通 Reference 列表权限。

## 决策与后续拆分

先在 Solution 仓储按 GLOBAL 根 ID 有界扫描，取每根最新发布事件；仅最新事件为同一当前版本 `PUBLISH`、标签有效且根/版本初筛合格时进入候选。用项目上下文的独立 Owner 先验 Session、License、项目成员资格，再对每个候选在同一事务调用现有当前 Reference/来源/确认证明。任何证明失败只使该候选不可见，未知基础设施异常则整体失败关闭；最终响应白名单仅含根 ID、固定版本 ID、审定标签、版本号和资格状态，不泄露原始名称、来源/路径/正文、确认资料或管理员身份。CREATE 仍独立重证，候选快照不是永久授权或正式业务事实。

分页不能按“可见项”推进扫描位置，否则撤回/过期造成遗漏或重复；下一游标应指向已扫描原始根 ID，独立签名并绑定 Session/Project/page size。单次扫描量和逐项证明次数必须有上限；即使本页 0 个可见项也可继续翻页，不能宣称全量为空。后续拆为 P05-A02 仓储/最小投影及当前证明、A03 受权 Owner/签名游标、A04 可选 HTTP 与严格合同、A05 Windows 组合和 Win11 ASGI/PG、A06 前端/真实浏览器。每项分别验收，不提前关闭 CR-SOL-018。

本项仅静态对账，无程序、Schema/API/依赖变更，未运行新动态测试。边界：尚无项目成员 GLOBAL 候选读取，正式服务账户、Server2025、性能和 Gate 3 仍待验；Debian13 实机按用户指令跳过。回滚为撤销此未实施的设计增量，既有发布历史不动。

TraceLink：Gate 2 API-04 → CR-SOL-018 → 0157/0158 → DEC-1152 → P05 项目候选读面 → P06 GLOBAL 页面。
