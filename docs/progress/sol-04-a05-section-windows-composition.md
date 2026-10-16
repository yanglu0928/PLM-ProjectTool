# SOL-04-A05：Section CREATE Windows 显式组合

日期：2026-10-09。结果：`SOL_04_A05_SECTION_WINDOWS_COMPOSITION_PASS`，限 Windows 11 合成信任源、隔离 PostgreSQL 18.6 的工厂/ASGI 验证；正式生产启动与目标服务账户未验。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A05。
- 输入基线：冻结 API-04 `SOL_SECTION_CREATE`、CR-SOL-012、已验证 A03 Owner 与 A04 可选 HTTP。
- 前置：0148 Migration/Guard、内部授权/Receipt/Audit、真实可选 HTTP 均通过。
- 模块/实体/API/权限：仅 Windows Solution 组合根与 production_login 显式写模式注入；不改实体、Schema、冻结合同或角色。PM/实施成员权限仍由 Owner 复验。
- 验收：显式写工厂用真实 Session/PG 创建与重放，缺依赖启动失败；登录专用、只读及默认应用不注入 Section 写 Router；后端全量。
- 风险：模式串线或目标账户信任材料缺失。写入口仅在 `include_secret_write` 分支创建，缺依赖 fail closed；正式目标环境单独验收。

## 实施与验证

`create_windows_section_create_router` 装配已验证的 Section Owner、项目写授权、Receipt/Audit；`production_login` 仅在显式写模式注入，默认/登录专用/只读保持空。Windows 11 一次性 PG18.6 工厂/真实 Session/ASGI 夹具验证 201、重放、角色、跨项目、暂停、Origin/CSRF、License、默认 404，以及缺依赖拒启动，原 PROJECT Reference 夹具回归通过。生产组合根参数装配的真实目标账户/正式公钥/Vault/HTTPS 启动未运行，不以合成验证替代。

后端全量 `3386 passed, 3 skipped, 5100 subtests passed`。兼容/升级/回滚：无新 Migration、依赖、前端或冻结 API 变化；移除显式写模式 Router 注入可关闭入口，已有 Section 历史保留。下一项 `SOL-04-A06` Section 只读 Owner/HTTP 的前置核查；后续 UI/真实浏览器独立施工。Server2025、性能、Gate3/UAT/发行未验；Debian13 实机依用户指令暂跳过。
