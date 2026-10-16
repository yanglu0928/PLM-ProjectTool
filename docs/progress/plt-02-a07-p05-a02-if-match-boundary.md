# PLT-02-A07-P05-A02：强 If-Match 请求边界

- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P05-A02。输入：Gate 2 冻结 API-01 强 ETag/If-Match 与 P05-A01 记录锁版本内部命令。前置满足解析器开发；完整写 API 仍未满足。
- Changed：新增仅接受单个规范强 `If-Match: "vN"` 的解析器，映射记录 `lock_version`；缺失为冻结 428 `CONFLICT_VERSION_REQUIRED`，重复/弱/通配/多值/畸形/越界为安全 400 `REQUEST_MALFORMED`。
- Files：Platform API 解析器、单元测试、决策/版本/状态记录。
- Migration/API：无数据库或公开 API 变更；写路由仍关闭。
- Tests：Windows 11/Python 3.13 后端 364/364 PASS；合法边界与各类非法条件覆盖；开发 wheel PASS。
- Result：If-Match 解析边界 PASS；尚未证明写路由、持久幂等或 Secret 生产装配。
- Known Issues：同事务幂等收据、CSRF/请求值脱敏、写 HTTP 与正式主密钥/License 信任源仍未完成；Server 2025、Debian 13 未验证。
- Next：PLT-02-A07-P05-A03 Secret 创建命令持久幂等收据，确保重试不重复创建密文/审计。
