# SOL-03-A04-P03-P03-P05-A03：OutlineVersion CREATE Windows 显式写装配

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P05_A03_OUTLINE_VERSION_WINDOWS_PASS`；Win11 合成信任/隔离 PostgreSQL 18.6，正式目标服务账户与发行信任源未验。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本任务。输入：Gate2 API-04、CR-SOL-016/017、DEC-1143、P05-A02 双 Scope 真实 ASGI/PG、现有 `--platform-write` 安全组合根。
- 单一问题：把已验可选路由只挂入 Windows 显式写模式，并重建完整 Document/Parse/Evidence/Reference/Requirement/Section/Outline 现时证明链；缺安全依赖失败关闭。
- 模块/实体/API/权限：Windows Solution 工厂及生产组合根，现有冻结 POST；项目角色仍由 Owner 校验。不改 Schema/Migration/公开合同/角色/依赖。
- 验收：工厂缺任一依赖或非法存储根拒启动；Win11 双 Scope 真实合成文件/Session/ASGI/PG 从工厂而非测试手装 Port 走完整创建、重放和拒绝链；默认关闭、全量回归。风险：目标服务账户公钥/Vault/ACL/CA 和 Server2025 尚未实测。

## 实施与验证

新增 `create_windows_outline_version_create_router`，显式接收两个受控绝对存储根（生产均传 `settings.data_root`，隔离夹具可分别指向 Document/Parse 目录）；内部构造 Document/Parse/Evidence 最小现时证明、Solution 当前 Reference 与 GLOBAL 确认、Requirement 已批准版本、Section/Outline、项目授权/License/收据/Audit 的同事务 Owner。`production_login` 仅在 `include_secret_write` 分支创建并传给可选 App；默认/只读路径不设置本路由。工厂构造失败转为固定启动错误，不向 UI 泄露路径/异常。

工厂单元 4 项/21 子例通过，覆盖版本路由形状、所有缺失依赖与相对路径拒绝。Win11 两套隔离 PG18.6/真实合成文件复用 P05-A02 请求链，但每次改由正式 Windows 工厂重建端口：PROJECT/GLOBAL 201、重放、固定关联、角色/CSRF/License/篡改、GLOBAL 真实时钟到期及零额外写退出 0。首次 GLOBAL 到期脚本沿用注入时钟而工厂正确忽略，修为测试库合成确认记录临时到期（仅隔离库，恢复后供旧夹具继续验证），全新库重跑通过。后端全量 3456 通过/3 跳过/5284 子例。

兼容/回滚：无新 Schema/API/依赖；可关闭写模式/撤该路由装配，不删除已有版本/首响/审计历史。正式 Windows 服务账户与 HTTPS/License 信任源、Server2025 当前版本、UI/浏览器、20 并发和 Gate3/UAT/发行仍待；Debian13 实机依用户指令跳过。下一项 OutlineVersion CREATE 前端安全请求桥及页面/浏览器。

TraceLink：Gate2 API-04 → CR-SOL-016/017 → DEC-1143 → P05-A02 ASGI/PG → 本 Windows 显式组合 → 前端/浏览器。
