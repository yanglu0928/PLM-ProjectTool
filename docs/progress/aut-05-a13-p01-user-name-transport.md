# AUT-05-A13-P01 管理员用户改名受控前端传输

2026-09-28 / 0.1.0.dev0 / PASS（仅传输桥合同；改名 UI 尚未接入）。

编码前检查：Phase2、Gate2/Phase1已满足；输入冻结 API-02 `AUTH_USER_PATCH`、现有 Windows11 显式 write Factory 与 User详情强ETag。涉及前端 Auth `SessionClient`、User 名称字段、固定 PATCH；当前 DeploymentAdmin/Session/License/CSRF/If-Match 仍由后端重核。DEC-427先记决策、风险、回滚和验证。无生产后端/DB/Schema/Migration/依赖/API/角色变更。

新增 `patchAdminUserName`：规范非零目标 UUID、强 `"v0"` 或无前导零版本、可安全递增界限与非空长度约束；固定 JSON `{"username":...}`、16KiB 受限、同源 Cookie/no-store/禁止重定向、私有内存 CSRF、单次请求与超时。401 清本地 Session/CSRF；网络或超时不自动重试，调用方后续须 GET 对账后决定。传输层不解释安全八字段、业务错误或改名成功；A13-P02/P03 分别完成响应客户端和页面。

验证：新增 4 组传输合同场景，合法初始 `"v0"` 固定路径/头/body，无效目标、弱/前导零/超大版本及无效名称零网络，新鲜 CSRF 前置、401 清证明、超时单次与互斥；前端 327/327、typecheck、build exit0。未执行本项实际 HTTP/PG 或浏览器改名，不能标完整功能可用。

兼容当前 DB head0049，无升级步骤；回滚撤新桥/测试，当前页面无入口。限制：无幂等 Key 的冻结 PATCH 若网络结果未知，绝不能盲目重发；改名会改变原登录名，真实行为已在后端隔离验证，但前端对账/交互待。
