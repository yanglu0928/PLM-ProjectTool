# SOL-04-A15：Section LIST Windows 显式组合

日期：2026-10-09。结果：`SOL_04_A15_SECTION_LIST_WINDOWS_COMPOSITION_PASS`，限 Windows 11 合成信任源/当前账户 key 工厂与隔离 PostgreSQL 18.6 真实 ASGI；正式目标服务账户完整生产启动未验。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / SOL-04-A15。
- 输入基线：冻结 API-04 `SOL_SECTION_LIST`、A14 可选 HTTP、A13 Windows 独立 Section cursor Vault key 工厂、现有显式读/写模式。
- 前置：内部 Owner/PG、签名 cursor、临时 Vault 失密恢复、真实可选 HTTP 均通过。
- 模块/实体/API/权限：仅 Windows Solution LIST 工厂、production_login 显式读/写模式注入和合同/PG 验证；不改实体、Schema/Migration、角色或冻结 API。
- 验收：读/写模式用真实 Session/PG 读取三页，登录专用/默认 404、读模式 Section POST404、写模式 CREATE201 不被 LIST 哨兵拦截；缺 Section key/信任依赖失败关闭并释放 runtime；后端全量。
- 风险：模式串线或目标账户密钥缺失。LIST 仅在 `include_secret_read` 分支创建，cursor 独立 Vault key 缺失时拒启动；目标账户/正式公钥/HTTPS 另验。

## 实施与验证

新增 `create_windows_section_list_router`，只接受 `SectionListCursorCodec`，装配已验证的 Session/License/项目成员读 Owner；`production_login` 在显式只读/写模式读取 `project-section-list-cursor-v1` 并注入 LIST，登录专用不注入。Windows 11 隔离 PG18.6 工厂/真实 Session/ASGI 验证三页、权限/游标/License、缺依赖拒启动；同一应用同时注入 Section CREATE+LIST，POST201 与 GET 四条共存。生产组合合同增补 Section key 合成替身、缺 key 两模式释放资源和登录/读/写路由边界。

首轮后端全量有 15 个失败：既有生产组合合同夹具尚未替身新增的必需 Section cursor key，应用在目标断言前拒启动；补充共享合成 key 和缺 key 专项合同后定向 37 项/8 子例通过。后端全量复跑 `3392 passed, 3 skipped, 5113 subtests passed`。正式目标服务账户 key/ACL/备份、完整生产启动、20 并发与 Server2025 未验，不以工厂/合同验证替代。

兼容/升级/回滚：无新 Migration、依赖、前端或冻结 API 变化；撤下 LIST 注入可关闭入口，Section 历史保留。下一项 Section 前端只读/创建安全客户端与浏览器验证，需先拆分单一 WBS；性能/发行仍独立。Gate3/UAT 未通过；Debian13 实机依用户指令暂跳过。
